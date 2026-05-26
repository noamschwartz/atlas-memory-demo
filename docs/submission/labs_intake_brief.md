# Search Labs Intake Brief — *Building agent memory on Elasticsearch*

> Draft generated from the article on 2026-05-25. Edit freely before submission.

## Blog aim

Why this post exists, and the outcome the reader should leave with.

> *"Production agents fail in a predictable way: they forget. The standard workaround (stuff prior context into the prompt) breaks on cost, latency, and the lost-in-the-middle effect. This post shows how to build a real, persistent agent memory on Elasticsearch — three indices (episodic / semantic / procedural), hybrid recall with RRF and a cross-encoder reranker, supersession to retire stale facts, time-decay weighting, DLS for per-user isolation, and an MCP endpoint so any agent can plug in unchanged. By the end the reader should be able to make architecture decisions on memory shape, retrieval composition, isolation model, and consolidation cadence for their own agent."*

## Topic scope

**In scope:**
- Three-bucket memory taxonomy (episodic / semantic / procedural) and why each gets its own index.
- Hybrid recall pipeline: RRF over BM25 + Jina v5 dense, over-fetched, then sharpened by a Jina v2 cross-encoder reranker.
- Same-turn write visibility (`refresh=True`).
- Supersession-not-deletion for contradictions, with harsh vs natural confidence handling.
- Time-decay and use-count scoring with a Painless script that branches per index.
- Federation between per-user memory and a shared catalog through one query.
- Per-user isolation via Document-Level Security (DLS) API keys.
- MCP endpoint so any MCP-speaking client can use the same memory layer.
- Measurement: QA-style passage retrieval eval, headline numbers, reranker-variance acknowledgement.

**Out of scope:**
- Specific LLM agent framework comparisons.
- Building the chat UI; the post links to the demo repo for that.
- Production-scale tuning beyond the corpus probed in the eval.
- Comparisons against other vector databases or commercial memory products.

## Target audience

Primary: **engineers building agents that need long-term memory** — search engineers, platform engineers, ML/RAG developers comfortable with Elasticsearch concepts but not necessarily expert in the specific primitives (RRF, semantic_text, DLS).

Secondary: technical leaders evaluating Elasticsearch as a memory layer for agent products.

Reader assumptions: familiar with hybrid search and embeddings at a high level; can read Python and JSON snippets; not necessarily familiar with reranker mechanics, supersession patterns, or Elastic Serverless API-key semantics.

## Success criteria

A reader can:
1. Decide whether three memory shapes is the right model for their agent (or whether their workload collapses to fewer).
2. Reproduce the recall pipeline shape (RRF + over-fetch + reranker) and explain to a teammate which leg does what.
3. Recognise the contradiction-handling pattern (supersession, not deletion) and apply it.
4. Understand when DLS-as-architecture works on Serverless and when backend-enforced filtering is the right pattern.
5. Run the demo themselves from the linked repo if curious.

A skim reader (~3 minutes) leaves knowing:
- Memory has three shapes, not one.
- Recall is hybrid + reranked, not pure vector.
- Old facts get superseded, not deleted.
- Isolation is enforced at the cluster, not the application.
- The system can be reached from any MCP client.

## Editorial confirmation needed

Items to flag for editorial sign-off:

- The headline metric framing. The post reports R@10 ≈ 0.87 with reranker-induced variance (0.85, 0.88, 0.89 across three runs) and chooses to report the average rather than a peak. Confirm editorial is comfortable with "≈ 0.87" approximation framing over a single precise figure.
- The semantic ceiling honesty (R@10 ≈ 0.78 vs episodic 0.96 vs procedural 1.0). The post leans into the bottleneck rather than hiding it. Confirm this is acceptable framing for Search Labs.
- The new (proposed) tags `agents`, `ai`, `memory` — not yet in the Search Labs tag taxonomy. Editorial may push back. Fallback is to drop these and keep `rag`, `search` only.
- The lessons-learned companion file is currently a separate local document (`lessons-learned.md`). Decide whether it ships alongside, gets merged into the post as an appendix, or stays separate.
- The post draws on a github repo (`noamschwartz/atlas-memory-demo`) under the author's personal namespace. Confirm whether editorial wants the repo transferred to `elastic/` org before publish or whether linking to the author's namespace is acceptable.
