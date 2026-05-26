# Atlas decay — built-in `gauss` reference

**Bottom line:** time decay is 100% built-in Elasticsearch `gauss`. The custom Painless script that used to live in `_decay_script` is gone. There is still one small `script_score` for the use_count boost (which is **not** decay — it's a separate ranking signal that nudges frequently-recalled facts higher).

The shared `last_active_at` date field is the only thing that made this possible. It exists on all three memory indices (episodic, semantic, procedural). The catalog index doesn't have it and doesn't need it (no decay applies to catalog).

---

## The actual code

`backend/app/atlas/memory/operations.py`, `_wrap_with_decay`:

```python
def _wrap_with_decay(query: dict[str, Any]) -> dict[str, Any]:
    """Wrap a query in a function_score that applies time-decay and a
    use_count boost to ranking.
    """
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
                            "scale": DECAY_SCALE,    # "1825d"
                            "offset": DECAY_OFFSET,  # "180d"
                            "decay": DECAY_GAUSS,    # 0.5
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

How to read it:

- `function_score.functions[]` lists ranking multipliers. Each can be filtered to specific docs.
- **Function 1: time decay.** A standard `gauss` decay on `last_active_at`. Only applies to docs in the episodic or semantic index (the `terms._index` filter). Procedurals + catalog hits multiply by 1.0 — i.e. no decay. Curve: at 180d age the multiplier is still 1.0 (the offset is a flat-zone); at 180d + 1825d = ~5.5 years old the multiplier is 0.5; older than that it tails toward 0.
- **Function 2: use_count boost.** A tiny `script_score` that returns `1.0` for unrecalled facts and `1 + log10(1 + use_count) * 0.2` once they've been recalled. A semantic fact recalled 10 times boosts ~1.21×; 100 times ~1.40×. Only applies to semantic.
- `score_mode: multiply` = combine the functions by multiplication.
- `boost_mode: multiply` = multiply the underlying RRF leg's score by the combined function result.

`_wrap_with_decay` wraps each leg of the hybrid retriever (BM25 leg, semantic leg), so the same decay applies in both halves before they go into RRF.

---

## Why `last_active_at` exists on all three indices

The date is set at write time and bumped on recall:

| index | `last_active_at` set at | `last_active_at` bumped on | net effect |
|---|---|---|---|
| episodic | write (= event time) | never | decays from event age — the obvious thing |
| semantic | write (= now) | every top-K recall hit, via `_bump_recall_stats` | recall re-anchors the decay; facts the agent uses stay fresh |
| procedural | write (= now) | every top-K recall hit (data is written but not yet applied to ranking — deferred decision) | currently no ranking effect; the data is there for future use |

This is the design point that lets us use built-in `gauss`: one field name across every index, so ES's parse-time field validation succeeds.

---

## Copy-paste Dev Tools queries

Replace `sarah` with `james` / `priya` etc. as needed. The cluster is `https://atlas-memory-demo-fa30d6.es.europe-west3.gcp.elastic.cloud:443`.

### 1. Confirm `last_active_at` is on all three indices

```
GET atlas_memory_episodic/_mapping/field/last_active_at
GET atlas_memory_semantic/_mapping/field/last_active_at
GET atlas_memory_procedural/_mapping/field/last_active_at
```

You should get `{"type": "date"}` from each.

### 2. Confirm a specific doc has `last_active_at` populated

Pick any doc id from `_search` first, then:

```
GET atlas_memory_semantic/_doc/<doc-id>?_source_includes=text,created_at,last_used_at,last_active_at,use_count
```

You should see `last_active_at` set, and (if the doc has been recalled) it will be equal to or more recent than `created_at`.

### 3. Minimal `gauss` decay — single index

The simplest possible decay query, scoped to one index so you don't have to worry about parse-time validation:

```
GET atlas_memory_semantic/_search
{
  "size": 5,
  "_source": ["text", "last_active_at", "use_count"],
  "query": {
    "function_score": {
      "query": {
        "bool": {
          "must":   [{ "match": { "text": "firmware" } }],
          "filter": [{ "term":  { "user_id": "sarah" } }]
        }
      },
      "gauss": {
        "last_active_at": {
          "origin": "now",
          "scale":  "1825d",
          "offset": "180d",
          "decay":  0.5
        }
      },
      "boost_mode": "multiply"
    }
  }
}
```

### 4. Decay across multiple indices via `_index` filter

This is what the application actually does for the BM25 leg. The `_index` filter is what makes the gauss work across indices without parser issues — `gauss` is wrapped inside a function that only applies to docs in episodic + semantic, so catalog docs (which don't carry `last_active_at`) get the neutral 1.0:

```
GET atlas_memory_episodic,atlas_memory_semantic,atlas_memory_procedural,atlas_catalog/_search
{
  "size": 10,
  "_source": ["text", "title", "last_active_at"],
  "query": {
    "function_score": {
      "query": {
        "bool": {
          "must": [
            {
              "multi_match": {
                "query":  "firmware Zigbee disconnect",
                "fields": ["text^2", "title^2", "name", "description", "trigger_text"]
              }
            }
          ],
          "filter": [
            {
              "bool": {
                "should": [
                  { "term":     { "user_id": "sarah" } },
                  { "bool":     { "must_not": { "exists": { "field": "user_id" } } } }
                ],
                "minimum_should_match": 1
              }
            },
            {
              "bool": { "must_not": { "exists": { "field": "superseded_by" } } }
            }
          ]
        }
      },
      "functions": [
        {
          "filter": {
            "terms": { "_index": ["atlas_memory_episodic", "atlas_memory_semantic"] }
          },
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
          "filter": { "term": { "_index": "atlas_memory_semantic" } },
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

You can drop the `superseded_by` clause to also see superseded docs. Drop the `user_id` clause to see across users (sanity check only — production code never does this).

### 5. The full hybrid retriever (RRF + decay + use_count boost)

This matches what `_hybrid_retriever` builds at runtime. Two RRF legs (BM25 + semantic), each wrapped with the decay-and-boost function_score:

```
GET atlas_memory_episodic,atlas_memory_semantic,atlas_memory_procedural,atlas_catalog/_search
{
  "size": 10,
  "_source": { "excludes": ["semantic_content"] },
  "retriever": {
    "rrf": {
      "retrievers": [
        {
          "standard": {
            "query": {
              "function_score": {
                "query": {
                  "bool": {
                    "must": [
                      {
                        "multi_match": {
                          "query":  "firmware Zigbee disconnect",
                          "fields": ["text^2", "title^2", "name", "description", "trigger_text"]
                        }
                      }
                    ],
                    "filter": [
                      { "term": { "user_id": "sarah" } },
                      { "bool": { "must_not": { "exists": { "field": "superseded_by" } } } }
                    ]
                  }
                },
                "functions": [
                  {
                    "filter": { "terms": { "_index": ["atlas_memory_episodic", "atlas_memory_semantic"] } },
                    "gauss": {
                      "last_active_at": {
                        "origin": "now", "scale": "1825d", "offset": "180d", "decay": 0.5
                      }
                    }
                  },
                  {
                    "filter": { "term": { "_index": "atlas_memory_semantic" } },
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
        },
        {
          "standard": {
            "query": {
              "function_score": {
                "query": {
                  "bool": {
                    "must": [
                      { "semantic": { "field": "semantic_content", "query": "firmware Zigbee disconnect" } }
                    ],
                    "filter": [
                      { "term": { "user_id": "sarah" } },
                      { "bool": { "must_not": { "exists": { "field": "superseded_by" } } } }
                    ]
                  }
                },
                "functions": [
                  {
                    "filter": { "terms": { "_index": ["atlas_memory_episodic", "atlas_memory_semantic"] } },
                    "gauss": {
                      "last_active_at": {
                        "origin": "now", "scale": "1825d", "offset": "180d", "decay": 0.5
                      }
                    }
                  },
                  {
                    "filter": { "term": { "_index": "atlas_memory_semantic" } },
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
        }
      ],
      "rank_window_size": 80,
      "rank_constant": 30
    }
  }
}
```

After PR #3 (Phase C — recall quality) merges, the application wraps this with a Jina v2 reranker over the over-fetched candidates and a Haiku query-expansion step. Those layers are orthogonal to decay — same `_wrap_with_decay` is used inside the RRF legs.

### 6. Backfill `last_active_at` (already run, but reference)

This is what `backend/scripts/atlas/backfill_last_active_at.py` runs. Idempotent — only touches docs missing the field. Safe to paste:

```
POST atlas_memory_episodic/_update_by_query?refresh=true&conflicts=proceed
{
  "script": {
    "source": "if (ctx._source.timestamp != null) { ctx._source.last_active_at = ctx._source.timestamp; }",
    "lang":   "painless"
  },
  "query": { "bool": { "must_not": [{ "exists": { "field": "last_active_at" } }] } }
}
```

```
POST atlas_memory_semantic/_update_by_query?refresh=true&conflicts=proceed
{
  "script": {
    "source": "if (ctx._source.last_used_at != null) { ctx._source.last_active_at = ctx._source.last_used_at; } else if (ctx._source.created_at != null) { ctx._source.last_active_at = ctx._source.created_at; }",
    "lang":   "painless"
  },
  "query": { "bool": { "must_not": [{ "exists": { "field": "last_active_at" } }] } }
}
```

```
POST atlas_memory_procedural/_update_by_query?refresh=true&conflicts=proceed
{
  "script": {
    "source": "if (ctx._source.last_used_at != null) { ctx._source.last_active_at = ctx._source.last_used_at; } else if (ctx._source.created_at != null) { ctx._source.last_active_at = ctx._source.created_at; }",
    "lang":   "painless"
  },
  "query": { "bool": { "must_not": [{ "exists": { "field": "last_active_at" } }] } }
}
```

### 7. Verify the decay actually changes scores

Pick a query that matches two semantic docs of different ages. Use `explain` to see the score components:

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
      "gauss": {
        "last_active_at": { "origin": "now", "scale": "1825d", "offset": "180d", "decay": 0.5 }
      },
      "boost_mode": "multiply"
    }
  }
}
```

In the `_explanation` blob, look for the `gauss` contribution — you'll see something like `"function score, computed with function: gauss(last_active_at...)"` and a multiplier that should be in `[0, 1]` depending on age.

---

## What to look for if decay isn't doing what you expect

- `last_active_at` empty on a doc → decay returns 1.0 for that doc (the `gauss` falls through). Check the backfill ran on this index.
- All docs scoring identically → the offset might be larger than every doc's age. With `offset=180d`, anything younger than 180 days gets multiplier 1.0 regardless of exact age.
- Procedural hits ranking weirdly → procedural docs are intentionally outside the gauss filter. They're not decayed; their rank comes from RRF + (eventually) success/failure counters.
- Catalog hits ranking flat → same reason. Catalog never decays.
