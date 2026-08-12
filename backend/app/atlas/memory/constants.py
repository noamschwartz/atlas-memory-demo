"""Constants for the Atlas memory layer."""

INDEX_EPISODIC = "atlas_memory_episodic"
INDEX_SEMANTIC = "atlas_memory_semantic"
INDEX_PROCEDURAL = "atlas_memory_procedural"
INDEX_CATALOG = "atlas_catalog"

# Small side index holding one document per user: the consolidation watermark.
# Deliberately separate from the memory indices — it carries no `semantic_text`
# field, so it is free of the scripted-update restrictions that apply to
# indices containing one, and stamping progress here avoids having to backfill
# a `consolidated_at` field onto every historical episodic document.
INDEX_STATE = "atlas_memory_state"

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

# How many existing semantic facts are shown to the consolidation LLM as the
# "do not duplicate these" comparison set. This was 50 while the seed corpus
# ships 60 facts per persona, so the ten oldest sat outside the window and were
# re-extracted as duplicates — measured at 28 near-duplicate pairs across 197
# live facts before this was raised. 200 covers the seeded corpus with headroom.
# This is a mitigation, not a fix: the window is still finite, and the real
# answer is retrieval-backed dedup (compare each candidate against its nearest
# neighbours rather than against a recency slice).
CONSOLIDATION_EXISTING_FACTS_LIMIT = 200

# How many core facts (identity + constraint) are injected into the system
# prompt each turn. Sarah's corpus carries 42 such facts (~930 tokens if all
# were injected), so this is capped. Constraints are ordered ahead of identity
# facts because they are the class retrieval is least able to reach: a nursery
# quiet-hours constraint shares almost no vocabulary with "my hub keeps
# dropping off wifi", so it will never win a similarity contest on that turn,
# yet it must still shape the answer.
CORE_MEMORY_LIMIT = 24

# How the core-memory slots are divided.
#
# Sorting purely by age protects foundational facts but buries new ones: a fact
# the customer stated today sorts last and is the first thing the cap cuts. On
# the live corpus that was already happening, with 17 of Sarah's 41 eligible
# facts dropped, all of them her most recent. Sorting purely by recency has the
# mirror failure, which is what this originally did: consolidation output is
# always newer than the facts it was derived from, so churn evicted "owns a
# Lumio Hub v2" in favour of "tone shifted from enthusiastic to tired".
#
# Neither end alone is right, and neither covers the middle. So the block is
# filled from three directions:
#
#   recent    the newest facts, so today's news is never invisible
#   salient   the most-recalled facts, which is earned importance rather than
#             a guess: a fact the agent has actually needed nine times has
#             demonstrated its worth
#   founding  the oldest, which is where stable attributes live
#
# Remaining slots after the first two go to founding facts.
CORE_MEMORY_RECENT_SLOTS = 6
CORE_MEMORY_SALIENT_SLOTS = 6

# The only values `fact_type` may take.
#
# The agent's `write_memory` tool declares these as a JSON-schema enum, so that
# path is constrained before a call is ever made. Consolidation is not: it hands
# `write_memory` the extractor's raw JSON, so a misspelled or invented type is
# stored verbatim.
#
# That failure is quiet rather than loud, which is what makes it worth closing.
# An unrecognised value matches no core-memory filter, so a fact the model meant
# as a constraint simply never reaches the always-in-context block, and nothing
# says so. It also silently breaks every aggregation over the field.
VALID_FACT_TYPES = frozenset({"preference", "identity", "constraint", "world"})

# Where an unrecognised value lands. Deliberately the one type that is NOT
# injected into every future turn: a value we failed to recognise must never be
# promoted into the always-in-context block on a guess.
DEFAULT_FACT_TYPE = "preference"

# Master switch for the core-memory block. ON by default, but exposed because
# the block is only as good as `fact_type` hygiene, and on a corpus built by the
# older, looser consolidation prompt that hygiene can be poor: historical events
# ("escalated to second-line support", "tone shifted to frustrated") were
# routinely written as `identity`, and duplicates were written freely. Injecting
# that into every turn costs tokens and adds noise. An operator upgrading an
# existing deployment can set this False, run a reclassification pass over
# `fact_type`, then turn it back on.
CORE_MEMORY_ENABLED = True

# Near-duplicate threshold for the core block. The corpus measured 28
# near-duplicate pairs across 197 live facts, and several land in the same core
# block ("shares her home with her partner and their newborn son Theo" appeared
# twice, byte-identical). Deduplicating at selection time is far cheaper than
# paying for both copies on every single turn.
CORE_MEMORY_DEDUP_THRESHOLD = 0.82

# Output ceiling for one consolidation pass. At 2048 a catch-up pass over a
# backlog was being cut off mid-JSON, and because the parse then failed the
# entire pass was discarded — every fact in it lost, silently. Consolidation
# output scales with the number of episodes considered, so the ceiling has to
# cover the catch-up and legacy-fallback cases, not the steady state.
CONSOLIDATION_MAX_TOKENS = 4096

# How many recent assistant turns are handed to consolidation as context.
#
# One turn is not enough, and the reason is a timing mismatch. The customer
# confirms a fix one turn AFTER the advice was given ("it worked"), so at the
# moment the confirmation arrives, the steps it refers to are in the PREVIOUS
# reply. Passing only the current turn's reply means the extractor sees the
# confirmation and the acknowledgement of it, never the procedure being
# confirmed. Four turns covers the usual advise / try / report / confirm shape
# with room to spare.
CONSOLIDATION_ASSISTANT_CONTEXT_TURNS = 4

# Character budget for that context. Replies run to a 2048-token ceiling, so
# four of them unbounded could add ~30k characters to the consolidation prompt.
# Oldest turns are dropped first when the budget binds, since the confirmation
# a customer just gave refers to the most recent advice.
CONSOLIDATION_ASSISTANT_CONTEXT_CHARS = 6000

# How many already-consolidated episodes are shown to the extractor as
# synthesis context (never as material to extract from).
#
# The watermark means a pass normally sees a single new user message, which is
# correct for cost but too narrow for facts that only exist across turns: a
# customer mentions a dog in turn two and chewed cabling in turn seven, and the
# constraint ("mounts sensors high because the dog chews cable") is in neither
# message alone. Twelve covers a typical support exchange without reintroducing
# the per-turn reprocessing cost the watermark removed, because these episodes
# are read for context, not re-extracted.
CONSOLIDATION_CONTEXT_EPISODES = 12

# Retrieval-backed dedup.
#
# Handing the extractor a recency-ordered slice of existing facts is a window,
# and a window has a cliff: the fact one position past the limit is invisible,
# so it can be neither deduplicated against nor superseded. That cliff is not
# theoretical. The seeded corpus measured 28 near-duplicate pairs across 197
# live facts, including byte-identical copies of seeded facts, because the
# window was smaller than the corpus.
#
# So each candidate fact is also checked against its nearest existing
# neighbours, found with the same hybrid retriever the agent uses for recall.
# Nearest by meaning rather than by age, which removes the cliff entirely and
# catches the case a recency window structurally cannot: two facts that
# contradict each other while sharing almost no vocabulary.
DEDUP_NEIGHBOUR_K = 5

# Token-overlap above which two facts are the same fact and no LLM call is
# needed. Deliberately high: this path drops a candidate outright, so it must
# only fire on near-identical text. Anything below goes to a judgment call.
DEDUP_CERTAIN_SIMILARITY = 0.85
