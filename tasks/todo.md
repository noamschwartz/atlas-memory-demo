# Release 1: non-breaking memory-system improvements

Status: complete. See `docs/improvements/RELEASE-1.md` for the full write-up.

## Scope

Non-breaking only: no reindex, no field retype, no data migration, no external contract change.
Ranking work is deferred to Release 2 so it can be measured independently.

## Done

- [x] **Core memory tier.** Facts typed `identity` / `constraint` injected into the system prompt
      each turn: filtered term query, deduplicated, constraints first, oldest-first within a type,
      capped. `CORE_MEMORY_ENABLED` off switch.
- [x] **Incremental consolidation.** Per-user watermark in `atlas_memory_state`, so an episode is
      distilled once rather than re-read on every subsequent turn. Side index rather than a field
      on episodic docs, to avoid a backfill and the scripted-update restriction on `semantic_text`
      indices. Degrades to the previous path when unprovisioned.
- [x] **Retraction vs prior state.** Harsh contradictions mark the old fact `retracted` so a denied
      fact is not recounted as history. In-turn agent path only; consolidation cannot retract.
- [x] **Procedural playbooks round-trip.** `name` / `description` / `steps` added to the tool schema
      and returned in the recall payload.
- [x] **Confidence surfaced** to the agent, with a prompt rule for provisional values.
- [x] **Consolidation**: events oldest-first, can express harsh supersession, larger dedup window
      excluding superseded facts, higher output ceiling so a pass is not discarded on truncation.
- [x] **`list_memories`** superseded filter is opt-in; default preserves the Memory Inspector view.
- [x] **Recall stat bump** no longer blocks on `refresh="wait_for"`.
- [x] **Benchmark harness**: deterministic sampling, correct step-text extraction.

## Verification

- [x] 114 tests passing, 30 new.
- [x] End-to-end 26/26 against a live cluster (`scripts/atlas/verify_release1.py`, throwaway user,
      self-cleaning).
- [x] Retrieval quality unchanged, verified with a control run of the previous code against an
      identical corpus and question set: same numbers to three decimals.
- [x] Current benchmark: R@10 0.869, R@5 0.804, R@1 0.524, MRR 0.598, zero cross-tenant hits.

## Follow-ups

- [ ] Provision `atlas_memory_state` and grant the application API key read/write on it. Until
      then incremental consolidation is inactive and warns once per process.
- [ ] Consider a `fact_type` reclassification pass before enabling core memory on a corpus built
      by the earlier consolidation prompt.
- [ ] Release 2 (ranking, measured separately): recency / use-count / source-prior signals
      affecting final ordering rather than candidate selection only; `success_count` in procedural
      ranking; RRF window size; catalog `title` reaching the reranker; abstention floor; atomic
      `use_count` bump off the request path; `request_timeout` / `max_retries` /
      `retry_on_timeout` on the Elasticsearch client.
