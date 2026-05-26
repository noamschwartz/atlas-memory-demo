"""Constants for the Atlas memory layer."""

INDEX_EPISODIC = "atlas_memory_episodic"
INDEX_SEMANTIC = "atlas_memory_semantic"
INDEX_PROCEDURAL = "atlas_memory_procedural"
INDEX_CATALOG = "atlas_catalog"

MEMORY_INDICES = {
    "episodic": INDEX_EPISODIC,
    "semantic": INDEX_SEMANTIC,
    "procedural": INDEX_PROCEDURAL,
}

EMBEDDING_INFERENCE_ID = ".jina-embeddings-v5-text-small"
LLM_INFERENCE_ID = ".anthropic-claude-4.6-opus-chat_completion"
LLM_INFERENCE_ID_FAST = ".anthropic-claude-4.6-sonnet-chat_completion"

# Reranker (second-stage re-ordering of RRF candidates).
RERANKER_INFERENCE_ID = ".jina-reranker-v2-base-multilingual"

# How many candidates to fetch from RRF before reranking. The reranker can only
# re-order what's in the candidate set; if the right doc isn't here, no amount
# of reranking saves it. 80 was needed on this corpus (vs 40) to catch needles
# that share a topic with multiple consolidation-derived near-duplicates.
RECALL_OVER_FETCH_K = 80

# Time-decay tuning for recall (gauss-shaped script_score).
# At scale + offset from "now", the decay multiplier hits DECAY_GAUSS (0.5).
# Tuned for a corpus where needles can be up to 720 days old AND recent
# consolidation outputs compete for ranking. With episodic_scale=1825d, a
# 720-day-old episodic memory gets ~0.92x — present but de-emphasized —
# instead of ~0.59x which buried legitimate old needles. Semantic stays
# tighter since semantic facts already get a use_count boost on recall.
DECAY_EPISODIC_SCALE = "1825d"
DECAY_EPISODIC_OFFSET = "180d"
DECAY_SEMANTIC_SCALE = "1825d"
DECAY_SEMANTIC_OFFSET = "180d"
DECAY_GAUSS = 0.5

# Use-count boost: semantic facts that have been recalled often rank higher.
# multiplier = 1 + log10(1 + use_count) * weight
# At weight=0.2, a fact with use_count=10 boosts ~1.21x; use_count=100 ~1.40x.
USE_COUNT_BOOST_WEIGHT = 0.2

# Confidence penalty applied to a new semantic fact that supersedes an older one
# when the contradiction is harsh (the customer explicitly denied or corrected
# the prior fact). A harshly-superseded claim is treated as slightly less
# certain than an unchallenged one. Natural updates (moved, upgraded,
# preference change) do not incur the penalty. Clamped at 0.0 by write_memory.
SUPERSEDE_CONFIDENCE_PENALTY = 0.1

# Source prior on catalog docs in mixed-source recalls. Catalog hits get a
# flat sub-1.0 multiplier so user memory wins when relevance is close.
# Not a routing rule — when catalog's relevance signal is clearly stronger,
# the reranker still picks it. Only fires when include_catalog=True.
CATALOG_SOURCE_PRIOR = 0.85
