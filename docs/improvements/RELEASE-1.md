# Release 1: non-breaking memory-system improvements

**Status:** in progress
**Branch:** `release-1-memory-improvements`
**Audience:** this doc is the source material for a follow-up Search Labs post. Every entry
records *what was wrong*, *why the change is an improvement*, *whether it breaks anything*,
and *how it was verified*. Written so a reader who has not seen the original post can follow it.

---

## Why there is a Release 1 at all

The original post, "Building agent memory on Elasticsearch," described an architecture that is
sound in outline: three indices by memory type, hybrid recall with RRF plus a cross-encoder,
supersession instead of deletion, time decay, and per-user Document-Level Security.

A line-by-line audit of the code against the post found three categories of gap:

1. **Mechanisms described in the post that the code does not actually produce.** The most
   significant: time decay, the use-count boost, and the catalog source prior cannot affect the
   order of results the agent sees, because the cross-encoder reranker overwrites every score
   and re-orders the candidate list after they are applied.
2. **Architectural pieces the 2026 field converged on that were missing.** Chiefly a
   core/working-memory tier, a consolidation watermark, and validity-time (as opposed to
   transaction-time) modelling of facts.
3. **Straightforward bugs**, several of which silently degraded quality or made the
   benchmark untrustworthy.

Release 1 addresses category 2 and 3 items that are **non-breaking**: no reindex, no mapping
retype, no external API contract change, no data migration. Ranking changes (category 1) are
deliberately deferred to Release 2 so that Release 1 can be shipped and measured independently.

**A note on expectations.** Release 1 is *ranking-neutral by design*. The retrieval benchmark is
used here as a **regression guard**, not as a demonstration of improvement. Flat recall numbers
are the success condition. The improvements Release 1 delivers (correctness, cost, memory
durability) are measured separately.

---

## Phase 0: making the benchmark trustworthy

Before changing any behaviour we had to be able to measure it. The benchmark could not support
that, for two independent reasons.

### C8a. The eval sampled a different corpus on every run

**What was wrong.** `eval_recall.py` selected which documents to evaluate with:

```python
rng = random.Random(SAMPLE_SEED + hash(user_id + memory_type) % (2**32))
```

CPython salts `hash()` on `str` per process (`PYTHONHASHSEED` is random by default since 3.3),
and nothing in the repo sets it. So `SAMPLE_SEED = 42` bought nothing: every run drew a
different sample. Four separate places in the file asserted the opposite, including
*"Seed for deterministic doc sampling"* and *"cached on disk so re-runs are deterministic."*

The `len(docs) <= n` fast path would have bypassed the RNG, but it is never taken: every
seeded corpus exceeds its sample size (episodic 104-215 vs 10, semantic 60 vs 15,
procedural 4 vs 3).

The on-disk question cache did **not** mask this. Sampling happens first; the cache is keyed by
`doc_id` and only avoids re-paying for question generation. The evaluated set is whatever the
current run drew.

**Evidence it was really happening.** The committed question cache had accumulated **481
distinct documents** for a benchmark that samples 84 per run. With a stable sampler that number
would be exactly 84.

**Why this matters more than it sounds.** It invalidates the published variance claim. The post
attributes run-to-run movement to *"the reranker has serving-side variance."* The dominant cause
was sampling variance from a bug. Across seven local baseline runs on an unchanged index and
unchanged retriever, R@10 ranged **0.798 to 0.899**:

| run | R@1 | R@5 | R@10 | MRR |
|---|---|---|---|---|
| 20260524T191749Z | 0.577 | 0.833 | 0.893 | 0.685 |
| 20260525T041854Z | 0.494 | 0.768 | 0.851 | 0.610 |
| 20260525T042141Z | 0.494 | 0.798 | 0.875 | 0.626 |
| 20260525T083800Z | 0.583 | 0.869 | 0.899 | 0.692 |
| 20260525T110436Z | 0.458 | 0.738 | **0.798** | 0.572 |
| 20260525T110724Z | 0.542 | 0.774 | 0.851 | 0.642 |
| 20260531T123433Z | 0.565 | 0.804 | 0.893 | 0.672 |

The published post cites 0.85 / 0.88 / 0.89 / 0.893. One local run landed at 0.798, which is
**below the repo's own CI gate of R@10 >= 0.85**. R@1 moved 12.5 points run to run. No effect
smaller than roughly 10 points could be measured at all under this sampler, which means the
BM25 ablation delta (-4.8) was never distinguishable from noise.

**The fix.** Seed from a string. `random.Random` accepts one and hashes it stably:

```python
rng = random.Random(f"{SAMPLE_SEED}:{user_id}:{memory_type}")
```

**Why it is better.** The benchmark becomes an instrument rather than a lottery. Residual
variance is now attributable to reranker serving-side non-determinism alone, which is the thing
the post claimed all along and can now actually be quantified.

**Breaking change?** No, for the deployed system: `eval_recall.py` is a developer script, not
part of the service. It **does** invalidate comparability with previously published numbers,
because the evaluated document set changes. That is the point, and it is why this landed first.

**Verified.** Three separate Python processes computing the old seed produced three different
samples; the new seed produced an identical sample in all three.

### C8b. Procedural questions were generated with no step content

**What was wrong.** `_doc_text` assembled the text handed to the question-generating LLM and read
step content as:

```python
step_texts.append(s.get("text") or s.get("description") or "")
```

The step schema everywhere in the repo is `{order, instruction, tool}` (see
`mappings/procedural.json` and the consolidation prompt). Neither `text` nor `description` exists
on a step, so `step_texts` was a list of empty strings. Because a list of empty strings is
*truthy*, the `if step_texts:` guard passed and appended a dangling literal `"Steps: "` with
nothing after it. **No step content ever reached the question generator.**

**Why this matters.** It inflates the headline procedural number. Procedural questions were being
generated from `name + description + trigger_text` only, which is a strict subset of what
`_rerank` feeds the cross-encoder for those documents (`operations.py` deliberately folds
`name + trigger_text + description + steps[0].instruction` together to stop one-sentence triggers
losing to richer episodic prose). The benchmark was asking the retriever to find a document using
only the fields it had been specifically tuned to over-weight for that document type. The
reported "procedural hits 1.0" was close to guaranteed by construction, on n=18 against a
4-document-per-persona index.

**The fix.** Read `instruction` first, keep the other two as tolerant fallbacks, and guard on
`any(step_texts)` so an all-blank step list no longer emits a dangling header.

**Why it is better.** Procedural recall now measures whether the retriever can find a playbook
from a question about *what the playbook actually does*, which is the thing a user would ask.
Expect the reported procedural number to **fall**, and that is a more honest figure.

**Breaking change?** No. Developer script only. Invalidates prior procedural numbers.

**Verified.** Both step instructions now appear in the rendered document text; an all-blank
step list produces no `Steps:` header.

### The corrected baseline

Both fixes together produce a benchmark that is harder, more honest, and reproducible. Two
pieces of evidence that the sampler is now stable:

- The regenerated question cache contains **exactly 84 documents** (28 per persona = 15 semantic
  + 10 episodic + 3 procedural), against **481** in the old accumulated cache.
- Repeated runs now draw the same document set (see the residual-variance table below).

The corrected numbers, measured against the same cluster and the same unmodified retrieval code
the original post described:

| metric | published post | post-C8 baseline | delta |
|---|---|---|---|
| R@10 overall | 0.89 | **0.851** | -3.9 |
| R@5 overall | ~0.80 | 0.768 | -3.2 |
| MRR | 0.64 | 0.598 | -4.2 |
| semantic R@10 | 0.81 | 0.778 | -3.2 |
| episodic R@10 | 0.98 | 0.933 | -4.7 |
| procedural R@10 | **1.00** | **0.944** | **-5.6** |

The procedural movement is the clearest signal that C8b was real: once questions are generated
from what a playbook actually instructs, rather than from its title and trigger sentence alone,
a perfect score stops being free.

Per-persona, the spread is wide and worth reporting in its own right: james 0.964, sarah 0.821,
priya 0.768 at R@10. A single headline number hides a 20-point range across three synthetic
users on the same corpus and the same retriever.

R@10 = 0.851 also sits **one point above the repo's own CI gate of 0.85**, which is worth saying
plainly: the gate has effectively no margin against the corrected benchmark.

---

## The duplication baseline (measured, pre-Release-1)

The recall benchmark does not measure write quality at all, so the corpus was measured directly.
Across the three personas' **197 live (non-superseded) semantic facts** on the running cluster
there are **28 near-duplicate pairs**, scored by token-set Jaccard >= 0.5 or sequence ratio
>= 0.72.

Many are byte-for-byte identical:

```
sim=1.00  "Zigbee is the primary wireless protocol used by Sarah's Lumio devices."
sim=1.00  "Sarah lives in a Victorian flat in Bristol, UK."
sim=1.00  "Priya is a residential architect based in Bengaluru, India, in her late thirties."
```

Others are the same fact re-extracted with drifted wording, and in one case with a different
`fact_type` attached to each copy:

```
[constraint] Sarah is awaiting a hub firmware update ... resolve the Zigbee regression
[identity]   Sarah is awaiting a Lumio firmware patch ... resolve the Zigbee regression
```

**Why this happens, precisely.** Consolidation's only defence against writing a fact it already
holds is a prose instruction in the prompt ("DO NOT duplicate any existing fact, even
paraphrases") evaluated against `list_memories(..., "semantic", limit=50)` - the 50 most recently
created facts. The seed ships **60** semantic facts per persona. The ten oldest are therefore
outside the comparison window before a single conversation happens, and re-extraction of those is
not merely likely, it is unpreventable. The exact duplicates above are seeded identity facts,
which is the signature of precisely this failure.

The corpus has grown from 180 seeded facts to 197 live ones, so roughly a third of the net growth
is duplication rather than new knowledge.

This is the number Release 1 is expected to move, and it is not visible in R@K at all. Recording
it here because a follow-up post that only reports retrieval metrics would miss the actual
improvement.

---

## Phase 1: code changes

Ten changes. None requires a reindex, a mapping retype, an external API contract change, or a
data migration. One (A2) requires a one-time index provisioning step and degrades to previous
behaviour without it.

### A1. Core memory: the tier that was missing

**What was wrong.** Atlas had exactly one memory tier: retrieval. `SYSTEM_PROMPT_TEMPLATE` was
static, with `{today}` as its only substitution. Everything the assistant knew about a customer
had to win a similarity contest against roughly 275 documents on that turn's query.

That is structurally unable to surface a whole class of fact. Consider a constraint like *"the
nursery must stay quiet between 19:00 and 07:00"* and the turn *"my hub keeps dropping off wifi,
what do I do?"*. The two share almost no vocabulary, so BM25 will not match; the semantic leg is
not much better; and the cross-encoder scores candidates **against the query**, which guarantees
the constraint stays out. The agent then cheerfully proposes a 2am reboot with an audible chime.
The fact was stored, correctly typed, and had no path into the context.

These are facts whose **relevance is unconditional but whose embedding is query-conditional**.
Retrieval is the wrong mechanism for them, by construction rather than by tuning.

**What made this cheap.** `fact_type` already existed with the enum
`preference | identity | constraint | world`. It was written on every semantic fact, indexed as a
keyword, surfaced to the LLM as a display label, and **used in no query, filter, boost, or
inclusion rule anywhere in the codebase**. The labels needed to build a core-memory tier had been
there all along, unused.

**The change.** A `core_memory()` query filtered to `fact_type in (constraint, identity)`,
excluding superseded facts, capped at `CORE_MEMORY_LIMIT` (24), injected into a
`<customer_profile>` block in the system prompt. It is a filtered term query, no vector search,
run once per turn (not cached: supersession and consolidation can both change it mid-conversation,
and a stale profile is worse than a slightly more expensive one).

Constraints sort ahead of identity facts. When the cap bites it should drop biography rather than
a hard limit the agent has to respect. (`"constraint" < "identity"` ascending, which is why the
sort is documented in the code as load-bearing rather than incidental.)

**Why it is better.** This is the tier Letta calls core memory, and that file-backed agent setups
get from a static profile document. It is the one structural piece of the modern two-tier design
(always-in-context core + retrieved archival) that Atlas did not have. On the live corpus it puts
24 facts, about 700 tokens, in front of the model on every turn.

**Second-order consequence, worth stating.** Making `fact_type` load-bearing gives mis-typed facts
a cost they did not previously have. In end-to-end testing the consolidation LLM typed *"Sarah's
smart home automations are stable and fully operational"* as a `constraint`, which would then be
injected into every future turn forever. The consolidation prompt's `fact_type` guidance was
tightened accordingly, with an explicit test ("would this still matter, unprompted, in an
unrelated conversation six months from now?") and worked examples of the `world` vs `constraint`
distinction. **A latent labelling problem became a live one the moment the label started doing
work.**

**Breaking change?** No. Additive read plus a prompt change. No schema, no API, no stored data.
Costs ~700 tokens per turn on this corpus.

**Verified.** Unit tests pin the filter, the superseded exclusion, the constraint-first ordering,
the cap, and blank-text handling. End-to-end against the live cluster: 24 facts for sarah, all
`identity`/`constraint`, constraints ordered first, block present in the assembled prompt, and a
`core_memory` event emitted on a real turn. A user with no profile facts renders a prompt that
states the absence explicitly rather than leaving a dangling header.

### A2. Consolidation watermark

**Design constraint discovered during implementation.** The intended design puts the watermark in
its own small index, `atlas_memory_state`, specifically to avoid mutating episodic documents (a
scripted `_update_by_query` backfill would be rejected on an index carrying a `semantic_text`
field, because it runs through the bulk path).

Probing the live cluster showed the application API key is scoped to an **explicit list of index
names**, not a wildcard:

```
atlas_memory_episodic  read/write/create_index/manage : true
atlas_*                                               : false
atlas_memory_state                                    : false
```

Creating the index with the app key fails with `403 action [indices:admin/create] is
unauthorized`, and auto-create is likewise denied. So this change carries a one-time provisioning
step: create `atlas_memory_state` and grant the application key read/write on it.

**Consequence for the code.** Because the store can legitimately be unavailable (before
provisioning, or if a deployment declines to add it), the watermark layer must degrade to the
previous behaviour rather than failing closed. Failing closed here would be severe: a watermark
that cannot be read but is treated as "now" would silently disable consolidation entirely. The
module therefore returns `None` when the store is unreachable, and the caller falls back to the
legacy "most recent N episodes" path.

That keeps A2 non-breaking with or without the provisioning step, at the cost of the improvement
being inactive until the index exists.

**What was wrong.** `consolidate()` read the 30 most recent episodic events on **every turn**, with
nothing recording what had already been distilled. Turn N+1 re-processed 29 of the 30 episodes
turn N had just seen. Two costs followed: a full LLM call on every turn regardless of whether
anything durable had happened, and complete reliance on a prose instruction to stop the same fact
being written twice.

**The change.** One document per user in `atlas_memory_state` holding `last_consolidated_at`.
Consolidation reads only episodes strictly newer than it, oldest first, and advances the watermark
to the newest episode **actually processed** (not to `now`, which would swallow anything written
while the pass was running) and only after the writes have succeeded.

**Why it is better.** A turn that produces nothing durable now costs zero LLM calls instead of one,
which inverts the dominant cost term: consolidation was a full Sonnet-class call with 30 episodes
plus 50 facts plus 20 procedures in the prompt, on every message including "thanks" and "ok". It
also removes the main engine of duplicate creation, since an episode is considered exactly once.
And it creates the `consolidated_at` notion that safe episodic eviction later depends on.

**Breaking change?** No, with a caveat. No reindex, no retype, no contract change. It needs one
provisioning step (create `atlas_memory_state`, grant the app key read/write) and does nothing
until that lands, falling back to previous behaviour. Initialising a missing watermark to *now*
rather than to the epoch is what makes upgrading safe: existing episodic history counts as already
consolidated, so no re-extraction storm.

**Verified.** Ten unit tests, most importantly the degradation contract: an unreadable *and*
unwritable store must yield `None`, never a timestamp. Treating an unavailable watermark as "now"
would make `episodes_since` match nothing and silently disable consolidation altogether, which is
strictly worse than the bug being fixed. End-to-end against a cluster where the index does not yet
exist: consolidation correctly falls back and keeps running.

**Operational note.** The first implementation logged a full stack trace on every read and every
write when the index was absent, which in production would bury real errors under one traceback
per turn per user. Expected-and-recoverable is now warned once per process, concisely, with the
remedy in the message.

### A3. Dedup comparison window

**What was wrong.** Consolidation's only defence against re-writing a fact it already held was a
prose instruction evaluated against the **50 most recently created** facts. The seed ships **60**
per persona, so the ten oldest were outside the window before a single conversation happened.
Measured consequence on the live cluster: 28 near-duplicate pairs across 197 live facts, including
byte-identical copies of seeded identity facts (see the duplication baseline above).

**The change.** `CONSOLIDATION_EXISTING_FACTS_LIMIT = 200`, and the comparison set now excludes
superseded facts (they are not duplication candidates, must not be re-superseded, and were
consuming window slots).

**Why it is better.** It covers the seeded corpus with headroom and stops the specific failure
that was actually happening. It is explicitly labelled in the code as a **mitigation, not a fix**:
the window is still finite and still recency-ordered, so the same failure returns at 200 facts.
The real answer is retrieval-backed dedup, comparing each candidate against its nearest neighbours
rather than against a recency slice. That is the design the original post describes as "the
production architecture" and it does not exist in the repo; it is Release 2 work.

**Breaking change?** No. Constant change plus an opt-in filter.

### A5. Retraction versus prior state

**What was wrong.** `contradiction="harsh"` and `contradiction="natural"` wrote **byte-identical**
updates to the superseded document. The only difference between them was 0.1 subtracted from a
confidence value that nothing read. So the system could not distinguish:

- *"We moved to Edinburgh"* — the fact **was** true and has stopped being true. Legitimate history.
- *"I never lived in Bristol, that was my sister"* — the fact was **never** true. A retraction.

And then the agent rule said: *"Hits carrying a `superseded_at` field are archived state; treat
them as the prior state."* So after a customer explicitly denied something, asking "have I ever
lived in Bristol?" would have the assistant recount the denied fact back to them as personal
history. That is a correctness bug reachable straight from the shipped system prompt, not a
missing feature.

**The change.** A harsh supersession sets `retracted: true` on the old document. The flag reaches
the agent in the recall payload, and the prompt rule now splits: a hit with `superseded_at` but no
`retracted` is prior state and may be recounted; a hit with `retracted: true` was never true and
must never be described with "you previously...".

**Why it is better.** It closes a path where the system contradicts a customer's explicit denial,
which is the fastest possible way to destroy trust in a memory feature. In bi-temporal terms it is
the difference between closing a validity interval and withdrawing an assertion. Full validity-time
modelling is Release 3; this captures the distinction that is destroyed if it is not captured at
write time.

**Breaking change?** No. Additive boolean on a `dynamic: true` index; absent on every existing
document, which reads as "not retracted", which is exactly today's behaviour.

**Verified.** Four unit tests plus live round-trip: harsh sets the flag, natural does not, omitting
`contradiction` does not, the confidence penalty still applies, and the flag reaches the agent
payload.

### B2. Surface `confidence` to the agent

**What was wrong.** Every semantic fact carried a `confidence` float, and
`SUPERSEDE_CONFIDENCE_PENALTY` reduced it on a harsh supersession. Nothing read it: not the query,
not the ranking script, not the reranker input, and **not the payload sent to the model**. The
original post says the system "hedges slightly until the new state is reinforced by further
conversation." The agent was being asked to hedge on a number it could not see.

**The change.** One line adding `confidence` to the compact recall payload, plus a prompt rule
telling the agent to treat anything below 0.7 as provisional.

**Why it is better.** It is the minimum that makes the supersession penalty mean anything at all.
It does not make confidence a ranking signal (that is Release 2) and nothing yet raises confidence
back on reinforcement, so the "until reinforced" half of the original claim remains unimplemented
and is called out as such.

**Breaking change?** No. Additive key; MCP clients and the frontend tolerate extra fields.

### C1. A procedural memory can now carry, and be read as, a playbook

**What was wrong, part one.** The `write_memory` tool schema exposed `memory_type: "procedural"`
but defined no `name`, `description`, or `steps` properties, and `dispatch` forwarded none of them.
Every agent-written playbook therefore fell through to `steps: []`, `description: ""`,
`name = text[:60]` — while the system prompt instructed the agent to *"follow its steps. Don't
invent a different troubleshooting flow."* There were never any steps to follow.

**What was wrong, part two — found only by running it.** Fixing the schema was not enough. The
compact recall payload built in `dispatch` carried `text`, `fact_type` and `timestamp` and
**dropped `steps` entirely**, so a recalled playbook still arrived empty. The end-to-end test
caught this because the model said so out loud:

> *"The procedural memory matched but didn't return steps, so let me work with what I know from
> your history."*

That is the sort of defect unit tests cannot find, because every component was behaving as
specified.

**The change.** Three optional schema properties with the real step shape
(`{order, instruction, tool}`), forwarded through `dispatch`; and `name`, `description`, `steps`,
`success_count`, `failure_count` added to the payload for procedural hits.

**Why it is better.** Procedural memory was the tier most at risk of being decorative. After the
change the same test turn produced: *"I see there's a recovery playbook that matches your issue...
Let me follow our playbook"* followed by the playbook's actual first diagnostic question, in a
reply less than half as long as the improvised one it replaced.

**Breaking change?** No. Adding **optional** properties to a JSON Schema is backward-compatible;
`required` is unchanged at `["memory_type", "text"]`, so existing MCP clients keep working (they
need a restart to see the new fields). The payload additions are additive keys.

### C2. Consolidation sees events in the order they happened

**What was wrong.** `list_memories` sorts `timestamp desc`, and the consolidation prompt rendered
that order directly under a `<recent_events>` header — newest first. The prompt then asked the
model to do two order-dependent things: decide which event supersedes which, and spot a *complete
multi-step resolution*. It was being shown resolutions last-step-first, with nothing in the prompt
stating the ordering.

**The change.** `episodes_since` sorts ascending; the legacy fallback path reverses explicitly;
and the prompt now states "Events are listed OLDEST FIRST. When two events conflict, the LATER one
wins."

**Why it is better.** It removes a silent quality tax on both supersession detection and procedure
extraction. Cost: one word and one sort direction.

**Breaking change?** No.

### C4. The background path can express harsh supersession

**What was wrong.** `consolidate()` called `write_memory(..., supersedes_id=old_id)` and **omitted
`contradiction` entirely**; the consolidation prompt had no such field either. So the harsh/natural
distinction existed only on the in-turn agent path. Since the original post recommends moving
consolidation to a background job as the production cadence, taking that advice would have silently
dropped the feature the entire contradictions section is built on.

**The change.** `contradiction` added to the prompt's output schema with explicit guidance, and
forwarded (validated against the enum) into `write_memory`.

**Why it is better.** The distinction is unrecoverable after the fact: once both cases have written
identical documents, nothing downstream can tell them apart. It has to be captured at write time,
on every write path.

**Breaking change?** No.

### C5. The superseded filter is opt-in

**What was wrong / the risk.** Consolidation needed to stop seeing archived facts, but
`list_memories` is shared with the `/api/memory/list` route that feeds the Memory Inspector.
Filtering superseded facts globally would have removed the audit view that the whole supersession
design exists to provide — the visible proof that nothing is destroyed.

**The change.** `include_superseded: bool = True` on `list_memories`. Default preserves every
existing caller exactly; consolidation passes `False`.

**Why it is better.** It fixes the consolidation input without changing the product surface. This
is the difference between a targeted fix and a regression dressed as one.

**Breaking change?** No, specifically because of the default.

**Verified.** Tests assert both that the default keeps superseded facts (the inspector contract)
and that opting out drops exactly those.

### C7. `refresh="wait_for"` removed from the read path

**What was wrong.** `_bump_recall_stats` runs synchronously inside `recall_memory`, and `dispatch`
sets `update_stats=True` unconditionally, so it ran on **every recall including the automatic
pre-recall on every turn**. It used `refresh="wait_for"`, which blocks until the shard refreshes,
up to `index.refresh_interval` (1s by default). Every recall could pay up to a second of added
latency for a fire-and-forget statistics write whose only consumer is a *future* recall's ranking.
Nothing in the current turn reads `use_count` or `last_used_at`, so there was nothing to wait for.

Elastic's own guidance: "Unless you have a good reason to wait for the change to become visible,
always use `refresh=false`."

**The change.** `refresh=False`.

**Why it is better.** Removes up to ~1s from time-to-first-token on every turn, multiplied by each
additional recall the agent issues, for no loss of function.

**Breaking change?** No. The stat updates become visible on the next ordinary refresh instead of
synchronously; nothing reads them within the turn.

**Not fixed here.** The same function still does a non-atomic read-modify-write (it reads
`use_count` from a search hit captured before a network round trip to the reranker, then writes
`current + 1`), so concurrent recalls of the same fact lose updates. The fix is a scripted
single-document `es.update` with `retry_on_conflict` — which is legal, because the
scripted-update restriction on `semantic_text` indices applies to the **bulk** API only, not to
single-document `_update`. The docstring in the code asserting otherwise is wrong and is corrected
in Release 2 along with moving the bump off the request path entirely.

### Additional fix: consolidation was silently discarding whole passes

**Found by end-to-end testing, not by unit tests.** A consolidation pass over a backlog produced
ten facts and two multi-step procedures, exceeded `max_completion_tokens=2048`, and was cut off
mid-JSON. The parse then failed, the pass returned `{"error": "bad_json"}`, and **every fact in it
was lost silently**.

Two changes: `CONSOLIDATION_MAX_TOKENS = 4096`, and the error path now distinguishes a truncated
response from genuinely malformed output. They looked identical in the logs and have completely
different fixes. The raw payload moved to `debug` (it contains the customer's stored facts, so it
does not belong at `warning` level in any case).

Worth noting this was **pre-existing**, but A3's larger comparison window makes the input bigger,
and A2 makes it rarer: with the watermark active a normal turn consolidates one or two episodes
rather than thirty.

**Breaking change?** No.

---

## An eval-hygiene lesson, recorded because we walked into it

Release 1 is ranking-neutral by construction: the benchmark calls `recall_memory` directly, and
none of the changed code sits on that path (`core_memory` is not called, `list_memories` is not
called, `dispatch` and its payload are not used, and `_bump_recall_stats` does not run because the
harness leaves `update_stats` off). The expected result was therefore *flat*, and flat would have
been the success condition.

The first post-change measurement came back at **R@10 = 0.869 against a 0.851 baseline**. An
improvement that a ranking-neutral change cannot produce is not good news, it is a warning that
the measurement is wrong.

It was. Between the two arms, the end-to-end verification script had been run twice, and each run
drove a **real chat turn for `sarah`**. That wrote episodic events and triggered consolidation,
which wrote new semantic facts:

| | at baseline | after e2e runs |
|---|---|---|
| episodic (all users) | 541 | 544 |
| semantic (all users) | 199 | 208 |
| question cache | 84 docs | 102 docs |

The question cache growing from 84 to 102 is the tell. Sampling draws `n` documents from the
user's corpus; a larger corpus means the same deterministic seed selects a **different subset**,
so 18 new documents needed fresh questions. The two arms were measured on different question sets
and were never comparable.

The fix was a proper control: stash the application changes (keeping the benchmark fixes in
place), re-run on the **current** corpus with the **current** cache, and compare that against the
post-change runs. Same corpus, same questions, only the code differs.

Two things worth carrying into the write-up:

1. **A deterministic sampler is not a frozen benchmark.** C8a made the *draw* reproducible; it
   does not make it reproducible across a *changing corpus*. For a memory system, where the
   system under test writes to its own corpus by design, that distinction is sharp. A genuinely
   stable benchmark needs the evaluated document set pinned by id, not re-derived from a live
   index each run.
2. **Never run the agent between benchmark arms.** Obvious in hindsight, easy to do when the
   end-to-end suite and the benchmark target the same cluster and the same personas. A dedicated
   eval persona that no demo path ever writes to would remove the hazard entirely.

Both are cheap fixes and neither is in Release 1. They are recorded here because the original
post's variance claim came from a subtler version of exactly this problem.

### The controlled result

| # | arm | corpus | code | R@1 | R@5 | R@10 | MRR |
|---|---|---|---|---|---|---|---|
| 1-3 | baseline | 541 ep / 199 sem | original | 0.482 | 0.768 | 0.851 | 0.598 |
| 4-5 | post-change | 544 ep / 208 sem | Release 1 | 0.524 | 0.804 | **0.869** | 0.639 |
| 6 | **control** | 544 ep / 208 sem | **original** | 0.524 | 0.804 | **0.869** | 0.639 |

**Control equals post-change, to three decimals, on every metric.** Release 1 is confirmed
ranking-neutral: it changes retrieval quality by exactly nothing, which is what a release
containing no ranking changes should do. The entire 0.851 -> 0.869 movement is attributable to
the corpus growing between the two arms.

Two further observations from the six runs:

- **Determinism held across all three configurations.** Three baseline runs identical, two
  post-change runs identical, and the control landing exactly on the post-change numbers. The
  benchmark is now an instrument.
- **A run died to a transient `elastic_transport.ConnectionTimeout` mid-search.** The client is
  constructed with no `request_timeout`, `max_retries`, or `retry_on_timeout`, so a single network
  blip discards a fifteen-minute run (and, in the running application, would surface as a failed
  chat turn). Not fixed in Release 1 because it is a client-construction change with its own
  blast radius, but it belongs near the top of Release 2.

---

## Change summary

| # | Change | Breaking? | Needs ops step? | Verified by |
|---|---|---|---|---|
| C8a | Deterministic eval sampling | No (script only; invalidates prior numbers) | No | 3 processes, identical sample |
| C8b | Procedural step text reaches question generator | No (script only) | No | rendered doc text |
| A1 | Core memory tier from `fact_type` | No | No | 5 unit + 6 live checks |
| A2 | Consolidation watermark | No (degrades without it) | **Yes** — create `atlas_memory_state`, grant app key r/w | 10 unit + live fallback |
| A3 | Dedup window 50 -> 200, excludes superseded | No | No | unit |
| A5 | `retracted` distinguishes retraction from prior state | No | No | 4 unit + live round-trip |
| B2 | `confidence` surfaced to the agent | No | No | live payload check |
| C1 | Procedural playbooks can be written **and read** | No (optional schema props) | No | 5 unit + live round-trip |
| C2 | Consolidation sees events oldest-first | No | No | unit |
| C4 | Background path can express harsh supersession | No | No | code path |
| C5 | Superseded filter opt-in, inspector unchanged | No | No | 3 unit + live |
| C7 | `refresh="wait_for"` off the read path | No | No | live latency |
| — | Consolidation truncation no longer discards passes | No | No | live |

**Test suite:** 109 passing (28 new). **End-to-end:** 26/26 checks against the live cluster via
`scripts/atlas/verify_release1.py`, which uses a throwaway user and cleans up after itself.

## Upgrade risk for an existing deployment

"Recall is unchanged" is not the same as "nothing changes". What follows is everything that could
degrade for somebody already running this, measured rather than estimated.

### Proven safe

- **Retrieval quality.** Control equals post-change to three decimals on an identical corpus.
- **Stored data.** No reindex, no field retype, no migration, no rewrite. Every new field is
  additive and absent-means-previous-behaviour.
- **API contracts.** All payload and tool-schema changes are additive; `required` is unchanged, so
  existing MCP clients keep working.
- **The Memory Inspector audit view.** `list_memories` defaults to `include_superseded=True`.

### Real costs

**1. Input tokens per turn go up.** Measured on the live corpus:

| | added per turn |
|---|---|
| core-memory block (A1) | +605 to +825 tokens |
| recall payload, 10 hits (B2 + C1) | +0 to +702 tokens, depending on how many hits are procedural |
| worst case seen: procedural-only recall, 5 hits | ~2,030 tokens total |

Roughly **+1,000 to +1,500 input tokens on a typical turn**, more if the agent issues several
recalls. Both are governed by constants (`CORE_MEMORY_LIMIT`, and `CORE_MEMORY_ENABLED` as an off
switch). Nothing here increases *output* tokens.

**2. A1 amplifies pre-existing `fact_type` mislabelling, and this bit us on the demo corpus.**

The first implementation sorted newest-first within a type. On the live corpus that produced a
block where thirteen of the twenty-four entries were historical support events mislabelled as
`identity` ("escalated beyond first-line support", "tone shifted from enthusiastic to tired"),
plus byte-identical duplicates — and it had **evicted "Sarah owns a Lumio Hub v2"** entirely,
because consolidation output is always newer than the durable facts it was derived from.

Two changes fixed most of it:

- **Oldest-first within a type.** Counter-intuitive but correct for an always-in-context block:
  stable attributes are established early and restated rarely, churn is recent. Age is a proxy for
  durability here.
- **Near-duplicate removal at selection time** (token-set Jaccard, no embedding call), applied
  after an over-fetch so duplicates cannot consume slots.

The block now leads with "lives in a Victorian flat in Bristol", "owns a Lumio Hub v2", "owns a
Border Collie named Whiskey", and the device inventory. Residual noise sits at the tail, where the
cap does the least damage.

**It is still only as good as the labels.** A deployment whose corpus was built by the older,
looser consolidation prompt will have mislabelled facts. `CORE_MEMORY_ENABLED = False` exists for
exactly that case: turn it off, run a reclassification pass over `fact_type`, turn it back on.

**3. One genuinely new failure mode.** C4 lets consolidation mark a fact `retracted`. If the
consolidation LLM misclassifies a routine update as a denial, a legitimate historical fact gets
flagged and the agent will decline to recount it on a retrospective question. This was impossible
before, because consolidation never set `contradiction` at all. It is a soft failure (the document
is untouched and still queryable, only the phrasing rule changes) but it is new, and it is the one
change here that can make an answer worse rather than merely more expensive.

**4. Benchmark numbers move.** Anyone tracking R@10 against the published 0.89 will now measure
0.851-0.869. That is the benchmark being corrected, not the system regressing.

**5. Cosmetic.** `use_count` in the Memory Inspector can lag by one refresh interval (C7).

### Recommended upgrade order for an existing deployment

1. Take everything except A1 (all low-risk, all additive).
2. Turn A1 on with `CORE_MEMORY_ENABLED`, inspect the resulting block for one real user, and
   reclassify `fact_type` if it looks like the "before" case above.
3. Provision `atlas_memory_state` last, when convenient. A2 does nothing until then.

## The one thing that needs you

`atlas_memory_state` cannot be created by the application API key. The key is scoped to an
explicit list of index names, not a wildcard:

```
atlas_memory_episodic  read/write/create_index/manage : true
atlas_*                                               : false
atlas_memory_state                                    : false
```

To activate A2:

1. Create the index with the mapping in `app/atlas/memory/mappings/state.json`
   (`uv run python -m scripts.atlas.init_memory` does this if run with a key that can create it).
2. Grant the application API key `read` + `write` on `atlas_memory_state`.

Until then consolidation runs on the previous recent-window path and logs one warning per process.

## Deferred, deliberately

**Release 2 (ranking changes, announced, re-baselined):** blend the decay / use-count / catalog
prior into the final score so they stop being inert; wire `success_count` into procedural ranking;
`rank_window_size = fetch_k` (currently 640, documented as 80); catalog `title` reaching the
reranker; abstention floor; atomic scripted `use_count` bump moved off the request path.

**Release 3 (needs a maintenance window):** aliases in front of all indices, then `bbq_hnsw`
(vector storage is ~30x the text, not "flat" as the original post states), then a retention policy
on the unbounded episodic index.

**Not attempted here:** validity-time (`valid_from`/`valid_to`) modelling, retrieval-backed dedup,
and episodic eviction. All three are real gaps; all three are larger than "non-breaking".

---

## Findings recorded along the way (not code changes)

These came out of the audit and belong in the write-up even though they are not part of
Release 1.

- **The eval never exercised DLS.** `_isolation_sweep` runs on the admin client with an
  application-level `term user_id` filter, so "zero cross-tenant leaks" validates the app filter,
  not the per-user DLS API keys the post calls "the production isolation guarantee." The sweep is
  also 18 queries (one per persona/memory-type pair, against two foreign users).
- **The eval is not gated in CI.** `.github/workflows/ci.yml` runs frontend lint/build, backend
  `pytest`, a localhost-URL grep and markdownlint. Nothing in the repo invokes `eval_recall.py`.
  The thresholds and exit codes are real when run by hand; the enforcement mechanism described in
  the post is not.
- **`backend/.env`'s key is read/write, not read-only.** Both `README.md` and `CLAUDE.md`
  describe `ELASTIC_API_KEY` as the read-only app key. A probe confirmed it can index and
  `_delete_by_query`. Worth correcting in both docs.
- **The repo carries two remotes**, `origin` (public `atlas-memory-demo`) and `agent-memory`
  (private `agent-memory-full`). Local `HEAD` does not track `backend/.env` or `.secrets/`;
  `origin/main` does. The local history is the clean one.
- **Beads is non-functional in this checkout**: database repo-ID mismatch (`ab0e1f23` vs
  `9b982927`), almost certainly a consequence of the dual-remote setup. `bd migrate
  --update-repo-id` is the documented fix but carries an explicit warning about deleting issues
  during sync, so it was left alone.
