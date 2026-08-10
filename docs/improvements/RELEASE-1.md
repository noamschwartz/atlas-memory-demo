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

## A4. Context without ingestion: the assistant's reply reaches consolidation

Episodic memory holds what the **customer** asserted. Assistant replies are not written to it, and
that is deliberate. The episodic index is the ground-truth tier: once a model's claim is stored as
an event, every later turn treats it as something the customer said, and repetition hardens it.
Keeping model prose out also keeps it out of the candidate pool that gets cross-encoded on every
recall. Durable knowledge from the agent's side is meant to earn its way in through consolidation,
where it arrives typed, with a confidence score and provenance.

**What was wrong.** Consolidation could not see the assistant's side at all, and it needs to for
two specific jobs the prompt already asks of it.

The first is interpreting the customer. A dialogue turn is frequently elliptical: "yes", "that
worked", "still nothing" carry no information without the question or the advice they answer. The
second is procedure extraction. The prompt asks for playbooks with a `steps` array and for
detection of "a complete multi-step resolution", but the steps are described on the agent's side.
Extraction was being asked to reconstruct advice from the half of the conversation that did not
contain it.

**The change.** The prose the agent produced during a turn is passed to `consolidate()` as
transient context. It is rendered in its own `<assistant_reply_context>` block, kept separate from
`<recent_events>`, and then discarded. It is never indexed, never citable, and never itself a
fact. The prompt states this explicitly:

> Use it to interpret an elliptical customer message and to ground a procedure's steps. Never
> extract a fact from it: anything the assistant asserted is unverified model output.
> `supporting_episode_ids` must cite ids from `<recent_events>`, and the context has no ids.

A commitment the agent made ("I've flagged your account, billing will email within two working
days") may be recorded, but only as `fact_type: "world"`, which is retrieval-gated and excluded
from the core-memory block. Never as `identity` or `constraint`.

**Reading both roles while attributing facts to only one** is the established shape for this.
Zep exposes it as `ignore_roles`: the ignored role is skipped for graph ingestion but is still
used to contextualise the messages that are ingested. Mem0's extractor likewise receives the full
user-and-assistant message pair while its prompt constrains what may be attributed as fact.

**A latent bug fixed on the way.** The assistant's prose was being captured into a variable that
was assigned only in one branch of the agent loop, so it was empty whenever a turn exhausted
`MAX_ITERATIONS`, and it discarded any prose emitted alongside tool calls in earlier iterations.
It is now accumulated across iterations. The variable was previously unused, so this had no
visible effect before now, but it would have silently produced empty context on exactly the
longest, most tool-heavy turns.

**Breaking?** No. Nothing is written to any index, no mapping changes, no retrieval path changes,
and the parameter is optional, so callers that omit it (`routes/memory.py`, `stress_test.py`) get
the previous behaviour exactly.

**Why it spans several turns.** A single turn is not enough, because of a timing mismatch. A
customer confirms a fix one turn *after* receiving it. When "it worked" arrives, the steps it
refers to are in the *previous* reply, so a single-turn context would show the extractor the
confirmation and the acknowledgement of it, and never the procedure being confirmed. The context
is therefore drawn from the client's conversation history plus the reply just produced, bounded by
`CONSOLIDATION_ASSISTANT_CONTEXT_TURNS` (4) and `CONSOLIDATION_ASSISTANT_CONTEXT_CHARS` (6000).
Oldest turns are dropped first when the budget binds, since a confirmation refers to the most
recent advice. History is client-supplied and unvalidated, so entries are filtered defensively.

**Known limitation.** History is browser state. If the customer closes the tab between receiving
advice and confirming it, the advice is gone and the confirmation cannot be grounded. Closing that
properly means persisting the reply, which is the thing this design deliberately does not do.

**Verified.** Six unit tests pin both halves of the contract: the reply is rendered into the
prompt and lands in its own block rather than in `<recent_events>`, and it never appears in any
indexed document. Plus the prompt guard rails and backwards compatibility for callers that pass
nothing.

## A4b. Cross-turn synthesis context

Making consolidation incremental fixed a cost problem and created a narrowness one. With a
watermark in place a pass normally sees a single new user message, and some facts do not exist in
any single message. A customer mentions a dog in one turn and chewed cabling several turns later;
the durable constraint ("mounts sensors high because the dog chews cable") is in neither alone.

Consolidation now also receives the `CONSOLIDATION_CONTEXT_EPISODES` (12) messages immediately
preceding the ones being processed, in an `<earlier_events>` block, bounded strictly before the
oldest new episode so the two blocks never overlap. They are read for synthesis only: the prompt
states they have already been consolidated and must not be re-extracted, and any fact drawn from
them must still cite an id from `<recent_events>`.

The context fetch is wrapped so a failure degrades to the previous single-window behaviour rather
than losing the turn's facts.

**Breaking?** No. One additional bounded query per consolidation pass.

## A4c. Advice whose outcome was never confirmed

A conversation usually ends immediately after the agent gives advice. Nobody ever says whether it
worked, so the outcome is lost, and the next conversation is free to re-suggest a fix that already
failed.

The customer's own final message is fine: it is written to episodic and consolidated at the end of
that same turn. What was missing was any record of what the agent advised and whether it landed.

When the assistant context shows concrete advice and the events contain neither a confirmation nor
a rejection of it, consolidation now writes one record:

- `fact_type: "world"`, never `identity` or `constraint`, so it is retrieval-gated and stays out of
  the always-in-context profile block
- `pending_outcome: true`, an additive boolean, queryable so a later pass can resolve it rather
  than having to rediscover it by matching prose
- phrased as what the assistant advised, never as something the customer asserted
- citing the customer message that prompted the advice

No model prose enters the index. What is stored is the utterance-event, which is true regardless of
whether the advice was any good.

`_summarize_existing` marks these as `[pending]` so the extractor can see what is unresolved, and
the prompt tells it to supersede the pending fact once the customer confirms or rejects. The agent
prompt tells it to ask rather than assume: *"Last time I suggested reserving a static IP. Did that
help?"*

**Breaking?** No. Additive boolean, absent on every existing document, which reads as not pending.

**Verified.** Twelve unit tests across both changes, plus a live check on the cluster: a turn
ending on advice produced exactly one `world` fact with `pending_outcome` persisted.

## A4d. Validity time: when a fact was true, not when we learned it

`created_at` and `superseded_at` are **transaction time**. They record when the system learned
something. They coincide with when it was actually true only if customers report changes
immediately, and they do not.

The concrete failure. A customer moves to Edinburgh in November 2024 and mentions it in January
2026. The stored facts are "lives in Bristol" (`created_at` 2024-06, `superseded_at` 2026-01) and
"lives in Edinburgh" (`created_at` 2026-01). Asked "where did I live in March 2025?", the only
interval available is `[2024-06, 2026-01)`, which contains March 2025, so the answer is Bristol.
She was in Edinburgh. The 14-month reporting lag is the entire error, and no amount of retrieval
tuning fixes it, because the information needed was destroyed at extraction time.

Semantic facts now carry optional `valid_from` and `valid_to` date fields. The extraction prompt
sets them **only when the customer's own words date the fact** ("we moved last November", "I had a
Hub v1 until March"), resolving relative expressions against the conversation's timestamps, and
leaves them null rather than guessing. The agent can also set them directly through `write_memory`.

Model-supplied dates are validated before they reach Elasticsearch: `YYYY-MM-DD` or `YYYY-MM` only,
anything else dropped. An unparseable date would fail the whole write and lose every fact in the
pass, and a fact without validity dates is still a useful fact.

Both fields reach the agent in the recall payload, and the prompt now says to reason from them for
any point-in-time question and never from `timestamp` or `superseded_at`. The `<context>` header,
which previously told the agent to use `timestamp` for "when" questions, was corrected so the
prompt does not contradict itself.

**Breaking?** No. Two additive `date` fields, absent on every existing document. Note for later: a
`range` filter on `valid_from` would silently exclude every pre-existing fact, so any future
filtering needs a `must_not exists` fallback. Nothing filters on them today.

**Verified.** Seventeen unit tests including the date-validation table, plus a live check: a
customer stating "we moved to Edinburgh back in November 2024" produced a fact with
`valid_from=2024-11-01` against `created_at=2026-07-28`, the twenty-month gap that previously
produced wrong answers.

## A6. Retrieval-backed deduplication

Consolidation showed the extractor a recency-ordered slice of existing facts and told it not to
duplicate them. That is a window, and a window has a cliff: the fact one position past the limit is
invisible, so it can be neither deduplicated against nor superseded.

The cliff was not theoretical. The seeded corpus measured 28 near-duplicate pairs across 197 live
facts, including byte-identical copies of seeded facts, because the window was smaller than the
corpus. Raising the limit moved the cliff; it did not remove it.

A recency window also cannot catch the case that matters most. "The customer prefers email" and
"The customer asked us to stop emailing" contradict each other while sharing almost no vocabulary.
Neither ordering by age nor a lexical scan will ever put those two side by side.

**The change.** Every candidate fact is now additionally checked against its nearest existing
facts, retrieved with the same hybrid searcher the agent uses at recall time. Nearest by meaning
rather than by age. Three outcomes per candidate:

- **duplicate**: already held, so drop it
- **update**: contradicts or replaces a neighbour, so keep it and attach the `supersedes_id` the
  extractor failed to set
- **distinct**: genuinely new, keep it unchanged

Near-identical text short-circuits to duplicate with no LLM call. Everything else is decided by a
single batched judgment covering all remaining candidates, so the cost is one extra call per
consolidation pass rather than one per candidate. With the watermark active, most turns produce no
candidates and therefore no cost at all.

**Two safety properties worth stating.** A verdict citing an id that was not in the retrieved
neighbour set is ignored, because attaching `supersedes_id` to a hallucinated id would silently
hide an unrelated fact from every future recall. And if the judgment call fails, every candidate is
kept: a missed duplicate is recoverable next time, discarding a real fact is not.

This is the design the original post described as the production architecture and disclosed as not
yet built. It is now built.

**Breaking?** No. One retrieval per candidate plus one batched judgment, both on the write path.
No schema change, no retrieval change, no contract change.

**Verified.** Seventeen unit tests covering the near-identical short circuit, all three verdicts,
hallucinated-id rejection, judge-failure behaviour, and the batching guarantee. A new eval scenario
covers the semantic-contradiction case. Plus a live demonstration: a fact written 900 days ago and
buried under 40 more recent ones was correctly identified as a duplicate, which the previous
recency window could not have done.

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

## Extraction eval

`eval_recall.py` measures `P(retrieved | written)`. It samples documents that are already in the
index, so a fact that was never extracted is never sampled and never scored. Everything above
about what consolidation should capture was, until now, an assumption.

`scripts/atlas/eval_extraction.py` measures the other half, `P(written | said)`.

**Design.** Fourteen hand-written scenarios, each a short conversation plus an assertion over what
consolidation should produce from it. Four properties make it cheap and trustworthy:

- **Extraction runs with `dry_run=True`**, which returns candidates without writing. The
  measurement never mutates the corpus, so it cannot contaminate the retrieval benchmark.
- **Ground truth is hand-written**, following the `needles.py` precedent. Generating fixtures with
  an LLM would mean the thing being tested and the thing defining correctness come from the same
  model.
- **Most assertions are deterministic.** A judge is used only where the question is genuinely
  semantic. The guardrail scenarios, which matter most, need no judge at all.
- **A dedicated user id** that no demo path writes to, wiped in a `finally`.

Each scenario runs three times, because LLM output is not deterministic and one sample is not a
measurement. Scoring is per dimension rather than one number, and **attribution safety gates at
100%**: one leak is the memory-poisoning failure the whole design exists to prevent.

### It found a real bug on its first run

Given a customer message ("my hub keeps going offline") and an assistant reply asserting account
details the customer never mentioned, consolidation produced:

```
fact_type=identity   "The customer is on the Premium tier with three registered properties."
fact_type=world      "The customer's hub is running firmware 4.7.2."
```

Both stated as customer facts. The first typed `identity`, which puts it in the always-in-context
block on every future turn. This is exactly the laundering the design forbids, and the prompt rule
against it was already present and being ignored.

Two fixes. A **Rule Zero** at the top of the extraction rules, stating categorically that only the
customer's own words become facts and that an authoritative-sounding assistant lookup is still
unverified model output. That took it from 0/1 to 1/3, which is not good enough for a guardrail.

So the enforcement moved into code. `_drop_ungrounded` removes any candidate containing a
distinctive token that appears in the assistant's prose and in none of the customer's messages.
Explicitly attributed facts ("the assistant advised X") are the permitted form and are kept. Drops
are logged with the offending tokens so they stay auditable.

The guard needed one correction of its own: it initially killed a legitimate fact because the
assistant had said "watch it for three nights" and the word "nights" was treated as content. It now
drops on a version-like token, which the customer demonstrably never uttered, or on two or more
shared words, which is content rather than vocabulary.

**One honest note on method.** The attribution assertion was rewritten after seeing the first
results. It originally failed on the mere presence of the words, which also failed the *permitted*
attributed form. The corrected assertion encodes the design's actual rule (never as an
unattributed customer claim, never as `identity`/`constraint`) rather than being loosened to pass.

### Results

All fourteen scenarios pass 3/3, every dimension at 1.00.

Against the pre-Release-1 revision, on the ten scenarios both can be scored on:

| scenario | before | after |
|---|---|---|
| elliptical_confirmation | 0/3 | **3/3** |
| fact_type_accuracy | 0/3 | **3/3** |
| harsh_denial | 0/3 | **3/3** |
| the other seven | 3/3 | 3/3 |
| **mean pass rate** | **0.70** | **1.00** |

Each failure maps to a specific change: "that worked" produced nothing without the assistant
context; harsh contradictions could not be expressed from the consolidation path; and a transient
status was being typed as `identity`, which would have put it in the always-in-context block.

Four further scenarios (`pending_advice`, `pending_resolved`, `dated_fact`, `undated_change`) pass
3/3 but have no baseline, because they test capabilities that did not previously exist. Those are
new capability, not improvement, and are reported separately for that reason.

**Not gated in CI.** It needs a live cluster and inference spend, so it is a pre-release check, not
a per-PR one. Saying so plainly rather than implying otherwise.

## Change summary

| Change | Breaking? | Needs ops step? |
|---|---|---|
| Core memory tier | No | No |
| Consolidation watermark | No (degrades without it) | **Yes**, create `atlas_memory_state`, grant app key r/w |
| Assistant reply as consolidation context | No | No |
| Cross-turn synthesis context | No | No |
| Unconfirmed-advice records | No | No |
| Retrieval-backed deduplication | No | No |
| Validity time (valid_from / valid_to) | No | No |
| Attribution guard (_drop_ungrounded) | No | No |
| Extraction eval | No (script only) | No |
| Retraction vs prior state | No | No |
| Procedural playbook round-trip | No (optional schema props) | No |
| Confidence in recall payload | No | No |
| Consolidation ordering / contradiction / limits | No | No |
| Opt-in superseded filter | No | No |
| Recall stat-bump refresh | No | No |
| Benchmark harness | No (script only) | No |

**Tests:** 183 passing, 99 new. **End-to-end:** 26/26 against a live cluster via
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
