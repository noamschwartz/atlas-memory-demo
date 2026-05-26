# Atlas: lessons learned

A companion to *Building agent memory on Elasticsearch*. Three things were tested while building this and are worth a paragraph each, all about the gap between "this is the industry-standard recipe" and "this is what actually earns its place on this corpus." Numbers below come from the QA-style passage retrieval eval ([`eval_recall.py`](https://github.com/noamschwartz/atlas-memory-demo/blob/main/backend/scripts/atlas/eval_recall.py)) — LLM-generated questions whose answers live in the corpus, the MS MARCO / BEIR / RAGAS convention.

## Query expansion: sometimes more is less

An earlier version of this pipeline ran a query-expansion stage in front of RRF: gpt-5.4-mini producing two paraphrases per query, three retrievals fused by doc id. The ablation said remove it: deterministic R@10 climbed once it was gone. The hybrid leg was already doing the job: BM25 caught the exact tokens, Jina v5 caught the paraphrase. A strong hybrid retriever doesn't need to be told what to look for twice.

## Hybrid search: dense carries the weight, BM25 earns its margin

The "BM25 + dense vectors fused with RRF" recipe is everywhere in 2026 retrieval architectures. We measured how much each leg was actually contributing on this corpus by [toggling them one at a time](https://github.com/noamschwartz/atlas-memory-demo/blob/main/backend/scripts/atlas/eval_recall.py#L500) — all numbers from the same eval session for fair comparison:

| config | R@10 | R@5 | MRR |
|---|---|---|---|
| hybrid (baseline) | **0.893** | **0.833** | **0.685** |
| dense only (no BM25) | 0.845 | 0.804 | 0.659 |
| BM25 only (no dense) | 0.708 | 0.643 | 0.512 |

Dense semantic is the workhorse. Removing BM25 costs 0.048 R@10 — a real but modest hit. Removing dense costs 0.185 R@10, more than triple the magnitude.

The per-persona breakdown is more nuanced. sarah drops 0.071 R@10 without BM25; priya drops 0.071; james doesn't budge at all (0.821 → 0.821). One read is that james happens to ask semantically clean questions; another, more honest read is that the eval itself understates BM25 by construction. LLM-generated questions paraphrase the rare tokens — `Sixhaven`, `shore-power`, `firmware 3.1.4-beta`, `ERR_5BC2` — into more natural phrasings, exactly where BM25 would otherwise pull its weight. Production users typing those literal tokens will hit cases the QA-style eval doesn't probe; that's where BM25 keeps earning its keep even when this number doesn't show it.

We kept hybrid. The lesson is to be honest about magnitude rather than recite the recipe: on a corpus like this, dense does the lion's share, BM25 earns about 5 points on the QA-style eval, and the eval methodology itself caps BM25's measurable contribution by paraphrasing the queries it would help most with.

## Reranker: load-bearing here, but the eval doesn't test scale

Disabling the Jina v2 cross-encoder drops R@10 from 0.893 to 0.655, a 24-point collapse. Unlike the other two ablations, there's no graceful fallback: nothing else in the system substitutes for the reranker's per-pair scoring. The cross-encoder is the one component that earned its place by an unambiguous margin. Procedural recall in particular goes from R@10 = 1.000 to 0.278 without it — procedural docs surface at top under the reranker's per-pair scoring but get drowned out by RRF alone when many docs share token overlap with the query.

The honest caveat is corpus size. The eval has ~250 documents per persona, and we over-fetch 80 candidates per query, so the reranker is scoring ~32% of one user's corpus on every call. RRF only has to put the gold doc inside the top third for the reranker to rescue it. That's a low bar.

At production scale (10⁴–10⁷ docs per user), 80 candidates is a tiny sliver and the burden shifts to first-stage retrieval. The cross-encoder's per-call cost stays fixed, but its rescue power depends entirely on what RRF surfaces in the first place. This eval doesn't probe that boundary, and we shouldn't pretend it does. At scale you'd want to widen `RECALL_OVER_FETCH_K`, invest more in first-stage retrieval, or both.

For this corpus, with this candidate window: keep the reranker. For your corpus, run the eval.
