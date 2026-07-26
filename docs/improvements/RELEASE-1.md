# Release 1: non-breaking memory-system improvements

Release 1 adds a core-memory tier, makes consolidation incremental, and lets procedural
playbooks round-trip. Every change is non-breaking: no reindex, no field retype, no data
migration, and no change to any external contract.

Retrieval quality is unchanged. That is the intended outcome, and it was verified rather than
assumed: a control run of the previous code against an identical corpus and question set produces
the same numbers as the new code, to three decimals. Ranking work is deliberately deferred to
Release 2 so it can be measured on its own.

Current benchmark: **R@10 0.869, R@5 0.804, R@1 0.524, MRR 0.598**, zero cross-tenant hits.
Per memory type: semantic 0.800, episodic 0.950, procedural 0.944.

---

## A1. Core memory

Atlas had a single memory tier: retrieval. That works well when relevance tracks the query, and
not at all when it does not.

Consider a stored constraint such as *"the nursery must stay quiet between 19:00 and 07:00"* and
the turn *"my hub keeps dropping off wifi, what do I do?"*. The two share almost no vocabulary, so
the lexical leg will not match, the dense leg is not much better, and the cross-encoder scores
candidates against the query, which guarantees the constraint stays out of the results. The agent
then proposes a 2am reboot with an audible chime. The fact was stored, correctly typed, and had no
path into the context.

These are facts whose **relevance is unconditional but whose embedding is query-conditional**.
Retrieval is the wrong mechanism for them by construction, not by tuning. This is the tier Letta
calls core memory, and that file-backed agent setups get from a static profile document.

`fact_type` already carried the labels needed to build it. Facts typed `identity` or `constraint`
are now selected by a filtered term query (no vector search), deduplicated, and injected into a
`<customer_profile>` block in the system prompt, capped at `CORE_MEMORY_LIMIT`.

Two selection decisions are load-bearing:

- **Constraints before identity.** When the cap binds it should drop biography rather than a hard
  limit the agent has to respect.
- **Oldest-first within a type.** Counter-intuitive, and important. Consolidation output is always
  newer than the durable facts it was derived from, so newest-first lets recent churn ("tone
  shifted from enthusiastic to tired") crowd out foundational facts ("owns a Lumio Hub v2"). For
  an always-in-context block, age is a good proxy for durability: stable attributes are
  established early and restated rarely.

Near-duplicates are removed at selection time, after an over-fetch so duplicates cannot consume
slots. Token-set Jaccard rather than an embedding call, because this runs every turn.

**Dependency worth knowing.** The tier is only as good as `fact_type` hygiene. `CORE_MEMORY_ENABLED`
exists so an operator can disable it, reclassify, and re-enable. See the upgrade notes below.

**Breaking?** No. Additive read plus a prompt change. No schema, no API, no stored data.

**Verified.** Unit tests cover the filter, superseded exclusion, both sort keys, the cap, dedup,
blank-text handling and the off switch. End-to-end against a live cluster: 24 facts selected,
correct types, correct ordering, block present in the assembled prompt, event emitted on a real
turn, and a graceful empty-profile case.

## A2. Incremental consolidation

Consolidation read the most recent episodes on every turn, with nothing recording what had already
been distilled. Turn N+1 therefore re-processed almost everything turn N had just seen. Two costs
followed: a full LLM call on every turn regardless of whether anything durable had happened, and
sole reliance on a prompt instruction to avoid writing a fact already held.

A per-user watermark in `atlas_memory_state` now records `last_consolidated_at`. Consolidation
reads only episodes strictly newer than it, oldest first, and advances the watermark to the newest
episode **actually processed** (not to `now`, which would swallow anything written while the pass
was running) and only after the writes succeed.

**Why a side index rather than a field on episodic documents.** Stamping `consolidated_at` onto
episodes needs a backfill, and the natural way to write one is a scripted `_update_by_query`, which
Elasticsearch rejects on indices carrying a `semantic_text` field because it runs through the bulk
path. A separate small index has no such restriction and needs no backfill.

**Why it is better.** A turn that produces nothing durable costs zero LLM calls instead of one,
which inverts the dominant per-turn cost. An episode is considered exactly once. And it introduces
the notion of "already distilled" that safe episodic eviction will depend on later.

**Breaking?** No, with one operational caveat: the index needs provisioning (below). Until then the
watermark is unavailable and consolidation falls back to the previous path, warning once per
process. Initialising a missing watermark to *now* means an existing deployment starts with zero
backlog rather than re-processing months of history.

**Verified.** Ten unit tests. The most important pins the degradation contract: an unreadable *and*
unwritable store must yield `None`, never a timestamp, because treating an unavailable watermark as
"now" would match no episodes and silently disable consolidation altogether. Confirmed end-to-end
against a cluster where the index does not yet exist.

## A5. Retraction distinguished from prior state

Supersession was being asked to represent two different things with one mechanism:

- *"We moved to Edinburgh"*, the fact **was** true and has stopped being true. Legitimate history.
- *"I never lived in Bristol, that was my sister"*, the fact was **never** true. A retraction.

Both wrote identical updates to the superseded document, so nothing downstream could tell them
apart, and the agent rule "treat superseded hits as prior state" would recount a denied fact back
to the customer as their own history.

A harsh contradiction now sets `retracted` on the old document, the flag reaches the agent, and the
prompt rule splits: prior state may be recounted, a retraction may not.

**Deliberately conservative.** Only the in-turn agent path may retract, where the customer's own
words are in context. Consolidation infers contradictions second-hand from stored episodes, so it
takes the confidence penalty (soft, recoverable) but cannot flag a fact as never-true. A misread
there would permanently mark a true memory as false.

**Breaking?** No. Additive boolean; absent on every existing document, which reads as "not
retracted", which is current behaviour.

## C1. Procedural playbooks round-trip

The `write_memory` tool schema exposed `memory_type: "procedural"` but defined no `name`,
`description` or `steps`, so every agent-written playbook was created with `steps: []` while the
system prompt instructed the agent to follow its steps.

Fixing the schema alone was not enough: the recall payload also dropped `steps`, so a recalled
playbook still arrived empty. Both halves are fixed. Procedural hits now return `name`,
`description`, `steps`, `success_count` and `failure_count`.

Observable difference on the same test turn: before, the agent improvised and said the playbook
returned no steps; after, it follows the playbook and asks its actual first diagnostic question, in
a reply less than half as long.

**Breaking?** No. Adding *optional* JSON Schema properties is backward-compatible; `required` is
unchanged, so existing MCP clients keep working (they need a restart to see the new fields).

## Smaller changes

- **Confidence reaches the agent.** Semantic facts carried a `confidence` float that never reached
  the model, so the supersession penalty had no behavioural effect. It is now in the recall payload
  with a prompt rule treating sub-0.7 values as provisional.
- **Consolidation sees events oldest-first.** The prompt asks which event supersedes which and
  whether episodes show a complete multi-step resolution. Both are order-dependent, and events were
  being rendered newest-first with nothing stating the order.
- **Consolidation can express harsh supersession.** It previously omitted `contradiction`
  entirely, so the distinction existed only on the in-turn path.
- **The superseded filter on `list_memories` is opt-in.** Default preserves every existing caller,
  so the Memory Inspector's audit view is unchanged; consolidation opts out.
- **`refresh="wait_for"` removed from the recall stat bump.** It ran synchronously inside every
  recall, blocking for up to a refresh interval, for a write nothing reads within the turn.
- **Consolidation no longer discards a whole pass on truncated output.** The token ceiling was
  raised, and truncation is now distinguishable from malformed JSON in the logs, which have
  completely different fixes. The raw payload moved to `debug` since it contains customer facts.
- **Dedup comparison window** raised and cleared of superseded facts.

## Benchmark harness

Two fixes so the harness can measure a change reliably.

**Deterministic sampling.** Document selection was seeded via the builtin `hash()` of a string,
which CPython salts per process, so each run evaluated a different sample. Seeding from a string
literal makes the draw stable: repeated runs now produce identical results.

**Correct step-text extraction.** Procedural question generation read step content from `text` and
`description`, but the step schema is `{order, instruction, tool}`. No step content reached the
generator, so procedural questions were built from name, description and trigger sentence alone.
Reading `instruction` makes those questions reflect what a playbook actually instructs.

Note that a deterministic sampler is not the same as a frozen benchmark. The sample is drawn from
the live corpus, and this system writes to its own corpus by design, so corpus growth changes the
sample. Do not run the agent between benchmark arms, and prefer a dedicated eval persona that no
demo path writes to.

---

## Change summary

| Change | Breaking? | Needs ops step? |
|---|---|---|
| Core memory tier | No | No |
| Consolidation watermark | No (degrades without it) | **Yes**, create `atlas_memory_state`, grant app key r/w |
| Retraction vs prior state | No | No |
| Procedural playbook round-trip | No (optional schema props) | No |
| Confidence in recall payload | No | No |
| Consolidation ordering / contradiction / limits | No | No |
| Opt-in superseded filter | No | No |
| Recall stat-bump refresh | No | No |
| Benchmark harness | No (script only) | No |

**Tests:** 114 passing, 30 new. **End-to-end:** 26/26 against a live cluster via
`scripts/atlas/verify_release1.py`, which uses a throwaway user and cleans up after itself.

## Provisioning step

`atlas_memory_state` cannot be created by the application API key, which is scoped to an explicit
index list rather than a wildcard. To activate incremental consolidation:

1. Create the index with the mapping in `app/atlas/memory/mappings/state.json`
   (`scripts/atlas/init_memory.py` does this when run with a key that can create it).
2. Grant the application API key `read` and `write` on `atlas_memory_state`.

Until then consolidation runs the previous path and logs one warning per process.

## Upgrade notes

**Input tokens per turn increase.** Measured on a seeded three-persona corpus:

| | added per turn |
|---|---|
| core-memory block | +605 to +825 tokens |
| recall payload, 10 hits | +0 to +702 tokens, depending on how many hits are procedural |

Roughly +1,000 to +1,500 input tokens on a typical turn. Both are governed by constants
(`CORE_MEMORY_LIMIT`, and `CORE_MEMORY_ENABLED` as an off switch). Output tokens are unaffected.

**Core memory depends on `fact_type` accuracy.** A corpus where historical events were typed as
`identity`, or where duplicates accumulated, will produce a noisy profile block. Deduplication and
oldest-first ordering absorb most of it, but the reliable fix is accurate labels. If the block
looks wrong for a real user: disable it, reclassify `fact_type`, re-enable.

**One new failure mode.** Retraction is a hard rule, and only the in-turn agent path can set it
(see A5). If the agent misreads an explicit denial, a legitimate memory is flagged and will not be
recounted on a retrospective question. The document itself is untouched and still queryable; only
the phrasing rule changes.

**Cosmetic.** `use_count` in the Memory Inspector can lag by one refresh interval.

**Suggested order for an existing deployment:** take everything except core memory first, then
enable core memory after eyeballing the block for one real user, then provision
`atlas_memory_state` when convenient.

## Deferred to Release 2

Ranking work, kept separate so it can be measured on its own: making the recency, use-count and
source-prior signals affect final ordering rather than candidate selection only; wiring
`success_count` into procedural ranking; the RRF window size; catalog `title` reaching the
reranker; an abstention floor; an atomic `use_count` bump moved off the request path; and
`request_timeout` / `max_retries` / `retry_on_timeout` on the Elasticsearch client.
