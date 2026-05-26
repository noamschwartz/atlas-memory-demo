# `_wrap_with_decay` — walkthrough + a query you can run

In one sentence: every recall query is multiplied by two ranking signals — a built-in `gauss` time decay on `last_active_at`, and a small `script_score` use_count boost — both applied via Elasticsearch's `function_score`.

## The function

`backend/app/atlas/memory/operations.py`:

```python
def _wrap_with_decay(query):
    return {
        "function_score": {
            "query": query,
            "functions": [
                {
                    "filter": {
                        "terms": {"_index": [INDEX_EPISODIC, INDEX_SEMANTIC]},
                    },
                    "gauss": {
                        "last_active_at": {
                            "origin": "now",
                            "scale":  DECAY_SCALE,    # "1825d"
                            "offset": DECAY_OFFSET,   # "180d"
                            "decay":  DECAY_GAUSS,    # 0.5
                        },
                    },
                },
                {
                    "filter": {"term": {"_index": INDEX_SEMANTIC}},
                    "script_score": {
                        "script": {
                            "source": (
                                "doc['use_count'].empty ? 1.0 : "
                                "1.0 + Math.log10(1.0 + doc['use_count'].value) * params.w"
                            ),
                            "params": {"w": USE_COUNT_BOOST_WEIGHT},  # 0.2
                        },
                    },
                },
            ],
            "score_mode": "multiply",
            "boost_mode": "multiply",
        }
    }
```

## Walkthrough

### The outer `function_score`

```
function_score
├── query        ← the underlying query (BM25 leg or semantic leg of RRF)
├── functions[]  ← ranking multipliers, evaluated per doc
├── score_mode   ← how to combine the function results with each other
└── boost_mode   ← how to combine the combined function result with the underlying query score
```

The pattern: run the underlying query to get a base relevance score, then *multiply* it by however the `functions[]` array evaluates for that doc. The two `multiply` modes mean **final_score = underlying_score × gauss × use_count_boost**.

### Function 1 — `gauss` time decay

```python
{
    "filter": {"terms": {"_index": [INDEX_EPISODIC, INDEX_SEMANTIC]}},
    "gauss": {
        "last_active_at": {
            "origin": "now",
            "scale":  "1825d",
            "offset": "180d",
            "decay":  0.5,
        },
    },
}
```

- **`filter`** — this function only applies to docs in the episodic or semantic index. Procedurals and catalog docs get the function's neutral value (1.0), i.e. no decay. That's the whole reason we can use built-in `gauss` cross-index: filtered functions return 1.0 when the filter doesn't match.
- **`gauss`** — Elasticsearch's built-in gaussian decay primitive. Multiplier shape:
  - **`origin: "now"`** — the curve is centered at the current time.
  - **`offset: "180d"`** — flat zone. Docs younger than 180 days get multiplier 1.0 regardless of exact age.
  - **`scale: "1825d"`** — distance past the offset at which the multiplier hits `decay`. So a doc at age `180d + 1825d ≈ 5.5 years` gets 0.5.
  - **`decay: 0.5`** — the multiplier value at `offset + scale`. Standard half-life shape.
- **The field, `last_active_at`** — set at write time for every doc; bumped to `now` for top-K semantic/procedural hits on every recall (see `_bump_recall_stats`). For episodic, it's set once at the event time and never bumped → episodic decays by event age. For semantic, the bump re-anchors the decay so facts the agent actually uses stay fresh.

### Function 2 — use_count `script_score`

```python
{
    "filter": {"term": {"_index": INDEX_SEMANTIC}},
    "script_score": {
        "script": {
            "source": "doc['use_count'].empty ? 1.0 : 1.0 + Math.log10(1.0 + doc['use_count'].value) * params.w",
            "params": {"w": 0.2},
        },
    },
}
```

- **`filter`** — semantic only. Procedurals receive a `use_count` write today but the boost isn't applied to their ranking (deferred decision).
- **`script_score`** — runs a tiny Painless expression per doc:
  - If the doc has no `use_count` (never recalled), return `1.0` — no effect.
  - Otherwise return `1 + log10(1 + use_count) × 0.2`. So `use_count=10` → ~1.21×, `use_count=100` → ~1.40×, `use_count=1000` → ~1.60×. Logarithmic so a doc never blows up.

### `score_mode: multiply` × `boost_mode: multiply`

`score_mode` is how the functions combine with **each other**:

```
combined_function_score = gauss(doc) × use_count_boost(doc)
```

`boost_mode` is how the combined function score then combines with the **underlying query score**:

```
final_score = underlying_query_score × combined_function_score
```

Concrete example for one semantic doc: BM25 says it's a 4.2 match; it was last recalled 30 days ago (well inside the 180d offset, so gauss = 1.0); it's been recalled 10 times (use_count boost = 1.21). Final score: `4.2 × 1.0 × 1.21 = 5.08`.

For a procedural doc with the same BM25 4.2: gauss filter doesn't match → 1.0; use_count filter doesn't match → 1.0. Final: `4.2 × 1.0 × 1.0 = 4.2`.

## Copy-paste query for Kibana Dev Tools

This runs the function against `atlas_memory_semantic` and asks Elasticsearch to *explain* the score so you can see the gauss + use_count contributions in the breakdown:

```
GET atlas_memory_semantic/_search?explain=true
{
  "size": 3,
  "_source": ["text", "last_active_at", "use_count"],
  "query": {
    "function_score": {
      "query": {
        "bool": {
          "must":   [{ "match": { "text": "firmware" } }],
          "filter": [{ "term":  { "user_id": "sarah" } }]
        }
      },
      "functions": [
        {
          "gauss": {
            "last_active_at": {
              "origin": "now",
              "scale":  "1825d",
              "offset": "180d",
              "decay":  0.5
            }
          }
        },
        {
          "script_score": {
            "script": {
              "source": "doc['use_count'].empty ? 1.0 : 1.0 + Math.log10(1.0 + doc['use_count'].value) * params.w",
              "params": { "w": 0.2 }
            }
          }
        }
      ],
      "score_mode": "multiply",
      "boost_mode": "multiply"
    }
  }
}
```

Note this query is scoped to one index, so the `_index` filters from the production version are unnecessary here — they only exist to keep procedural/catalog docs out of the decay when the query spans multiple indices.

### What to look for in the response

For each hit you'll get a `_score` and an `_explanation` object. Inside `_explanation.details` you'll see entries like:

```
"description": "function score, computed with function:",
"details": [
  {
    "description": "function score, score mode [multiply]",
    "details": [
      { "description": "gauss(last_active_at,origin=...,scale=1825d,...)", "value": 0.93 },
      { "description": "script score function, computed with script", "value": 1.21 }
    ]
  }
]
```

The `value` next to the `gauss` line is the time-decay multiplier (between 0 and 1). The `value` next to the `script score function` is the use_count multiplier (≥ 1). The final `_score` is `underlying_score × gauss × use_count_boost`.

If you want the same shape but spanning all three memory indices + catalog (with the production `_index` filters), see `decay-reference.md` § 4.
