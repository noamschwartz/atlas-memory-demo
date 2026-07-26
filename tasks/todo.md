# Release 1: non-breaking memory-system improvements

Branch: `release-1-memory-improvements`
Cluster: `atlas-memory-demo-fa30d6` (ES 9.6.0 Serverless), seeded: 541 episodic / 199 semantic / 15 procedural / 11 catalog.

Goal: land every Release 1 item from the architecture review. All are non-breaking:
no reindex, no mapping retype, no external API contract change, no data migration.

Decision log for the follow-up blog lives in `docs/improvements/RELEASE-1.md`.
Every item below gets an entry there: what was wrong, why the change is better,
breaking-change status, and how it was verified.

---

## Phase 0: make the measuring instrument trustworthy (must land first)

- [x] **C8a** `eval_recall.py` deterministic sampling. `random.Random(SAMPLE_SEED + hash(str))`
      is salted per process by PYTHONHASHSEED, so every run evaluates a different 84 docs.
      Fix: `random.Random(f"{SAMPLE_SEED}:{user_id}:{memory_type}")`.
      VERIFIED: 3 separate processes -> old seed gave 3 different samples, new seed identical.
- [x] **C8b** `eval_recall.py:_doc_text` reads step text as `s.get("text") or s.get("description")`,
      but the step schema is `{order, instruction, tool}`. No step content reaches the question
      generator, which inflates procedural R@10. Fix: `s.get("instruction")`.
      VERIFIED: step instructions now render; all-blank step list no longer emits a dangling header.
- [x] **C8c** Regenerate the question cache. Old cache backed up to
      `qa_questions_cache.PRE-C8.json.bak` (481 cached docs for an 84-doc-per-run eval, which is
      itself evidence of the sampling bug).
- [ ] **C8d** Run baseline eval x3 on unmodified retrieval code to measure residual variance
      (reranker serving-side only, now that sampling is pinned). This is the real baseline.

## Phase 1: code changes (all non-breaking)

- [x] **A2** Consolidation watermark via a side index (`atlas_memory_state`), NOT a field on
      episodic docs. Avoids a backfill and avoids the scripted-bulk restriction on
      semantic_text indices. Initialize to `now` for existing users -> zero backlog on upgrade.
      BLOCKED ON OPS: app key cannot create the index (scoped to an explicit name list).
      Degrades to the legacy path until provisioned; warns once per process.
- [x] **A1** Core memory block. Query `fact_type in (constraint, identity)`, cap at 24, inject into
      `SYSTEM_PROMPT_TEMPLATE` beside `{today}`. Live: 24 facts / ~700 tokens for sarah.
- [x] **A3** Raise the 50-fact dedup window to 200 + exclude superseded from the comparison set.
- [x] **A5** `retracted` flag on harsh supersession + carve-out in the agent prompt rule, so a
      denied fact is not narrated back as personal history.
- [x] **B2** Surface `confidence` in the recall payload so the agent can actually hedge.
- [x] **C1** Add `name` / `description` / `steps` to the procedural tool schema.
      PLUS the half that only e2e testing found: `steps` were also missing from the RECALL
      payload, so a recalled playbook still arrived empty. Both halves fixed.
- [x] **C2** Oldest-first episodes into the consolidation prompt + explicit ordering statement.
- [x] **C4** Pass `contradiction=` from consolidation so the background path can express
      harsh supersession.
- [x] **C5** Parameterize the superseded filter in `list_memories` (default True preserves the
      `/api/memory/list` route and the UI inspector exactly).
- [x] **C7** `refresh="wait_for"` -> `False` on the recall stat bump.
- [x] **Extra** Consolidation was silently discarding whole passes on output truncation
      (`max_completion_tokens=2048`). Raised to 4096; truncation now distinguishable from
      malformed JSON in logs; raw payload moved to debug (it contains customer facts).
- [x] **Extra** Tightened `fact_type` guidance in the consolidation prompt, because A1 makes the
      label load-bearing and e2e showed the LLM typing a transient status as a `constraint`.

## Phase 2: verification

- [x] Unit tests pass: **109 passing, 28 new**.
- [x] End-to-end against the live cluster: **26/26 checks**
      (`scripts/atlas/verify_release1.py`, throwaway user, self-cleaning).
- [x] Confirm no regression in the `/api/memory/list` route output shape (C5 blast radius) —
      default `include_superseded=True` keeps the inspector's audit view intact, asserted by test.

## Phase 3: benchmark

- [x] Post-C8 baseline established: 3 runs, **identical to 3 decimals** (R@10 0.851, R@5 0.768,
      R@1 0.482, MRR 0.598). Spread 0.000, versus 0.101 under the old sampler.
      -> This refutes the published claim that run-to-run variance came from
      "the reranker has serving-side variance". With sampling pinned, the reranker is
      deterministic on this corpus; the variance was the sampling bug.
- [x] Post-change runs x2: identical to each other (R@10 0.869, R@5 0.804).
- [x] CONTAMINATION FOUND AND CORRECTED: the two e2e runs in between drove real chat turns for
      `sarah`, which wrote episodic + consolidated semantic docs (541->544 episodic,
      199->208 semantic, cache 84->102 docs). Corpus growth changed the sample, so
      baseline-vs-post was not a valid comparison.
- [x] Proper control: app changes stashed, same corpus + same cache, re-run. RESULT:
      control (original code, grown corpus) = **0.869 / 0.804 / 0.524 / 0.639**, which is
      EXACTLY the post-change result. Release 1 confirmed ranking-neutral to 3 decimals.
      The apparent 0.851 -> 0.869 "improvement" was 100% corpus drift.
- [x] One control run died to a transient `elastic_transport.ConnectionTimeout`. The ES client
      is built with no `request_timeout` / `max_retries` / `retry_on_timeout`, so one blip
      discards a 15-minute run (and would fail a live chat turn). Logged for Release 2.
- [x] Duplicate-fact baseline measured directly (the recall eval does not capture write quality):
      **28 near-duplicate pairs across 197 live semantic facts**, including byte-identical copies
      of seeded facts. Mechanism: 60 seeded facts per persona vs a 50-fact dedup window.
- [ ] Note: the existing 28 duplicates are historical and are NOT removed by Release 1.
      A2+A3 stop new ones being created; a cleanup pass is separate work.

## Phase 4: documentation

- [ ] `docs/improvements/RELEASE-1.md` complete for every item.
- [ ] Capture the eval-variance finding (R@10 observed 0.798-0.899 across 7 local runs; the
      published post cites 0.85/0.88/0.89/0.893) and the existing ablation table.

---

## Review

**Shipped.** Ten Release 1 changes plus two fixes that only end-to-end testing surfaced, on
branch `release-1-memory-improvements`. Nothing is committed yet.

**What changed, in one line each**
- Core memory tier built from the `fact_type` labels the system already wrote and never queried.
- Consolidation watermark, so an episode is distilled once instead of on every subsequent turn.
- Dedup window raised past the seeded corpus size and cleared of superseded facts.
- Retraction distinguished from prior state, closing a path where the agent recounted a fact the
  customer had explicitly denied.
- `confidence` finally shown to the agent that was being told to hedge on it.
- Procedural playbooks can now be written *and* read back with their steps.
- Consolidation sees events oldest-first, can express harsh supersession, and no longer discards
  a whole pass when its output is truncated.
- ~1s of `refresh="wait_for"` removed from every recall.
- Benchmark made deterministic and its procedural questions made honest.

**Results**
- Tests: 109 passing, 28 new.
- End-to-end: 26/26 against the live cluster.
- Benchmark: control == post-change to 3 decimals. Ranking-neutral, as designed.
- Corrected baseline is meaningfully harder than the published one: R@10 0.851 vs 0.89,
  procedural 0.944 vs 1.00.
- Benchmark variance collapsed from a 0.101 spread to 0.000.

**Two findings worth their own section in the follow-up post**
1. The published claim that run-to-run variance came from "the reranker has serving-side variance"
   is wrong. With sampling pinned the reranker is deterministic on this corpus; the variance was
   a `hash()`-seeded sampler.
2. We contaminated our own benchmark mid-experiment by running the agent between arms, then caught
   it because a ranking-neutral change appeared to improve recall. Written up in
   `docs/improvements/RELEASE-1.md`.

**Open / needs you**
- `atlas_memory_state` must be created and the app key granted read/write before A2 activates.
  Until then consolidation runs the previous path and warns once per process.
- The 28 existing near-duplicate facts are historical; Release 1 stops new ones, it does not
  clean up old ones.
- Beads is non-functional here (DB repo-ID mismatch, likely from the dual-remote setup).
- Nothing committed. Say the word and I will commit to the branch.
