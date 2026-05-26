# Persona-Based Review Findings — *Building agent memory on Elasticsearch*

> Run on 2026-05-25 against `docs/blog-drafts/building-agent-memory-on-elasticsearch.mdx`. Categories follow the skill's playbook: `critical` (must fix), `important` (should fix), `optional` (nice to have).

## Marketing pass (headline strength, narrative clarity, scannability)

| Severity | Finding | Suggested action |
|---|---|---|
| optional | The title is descriptive but workmanlike. "Building agent memory on Elasticsearch" tells what it is, not why a reader should care. A subtitle field (frontmatter `subtitle`) could carry the hook. | Consider adding a `subtitle` line, e.g. *"Three indices, hybrid recall with a reranker, supersession, decay, and DLS — the architecture and the empirical numbers behind a persistent memory layer for agents."* |
| optional | The intro's opening line ("Production agents fail in a predictable way") is strong. The scratch-pad-vs-memory frame at the end of the section lands cleanly. | No change. |
| optional | *Three buckets* opens with a strong abstract claim then immediately backs it with examples. Good rhythm for skim readers. | No change. |
| optional | The *Measuring what matters* section deliberately reports approximate numbers with declared variance. Honest, but a marketing skim reader might bounce off "≈ 0.87" and ask "is that good?" The CI gate framing (R@10 ≥ 0.85) helps; the variance numbers immediately after ground it. | If you want to give skim readers a single anchor: add one sentence at the start of the section like *"For a paraphrase-heavy QA-style eval, R@10 in the high 0.80s is industry-strong."* — but only if editorial is happy with that comparative framing. |

## DevRel pass (technical accuracy, reproducibility, first-use, US English, claim verifiability)

| Severity | Finding | Suggested action |
|---|---|---|
| important | "DLS is the architecture; this code-level pass costs essentially nothing at query time." — This is now operationally accurate on this specific cluster (we just armed the per-user DLS keys today), but the broader claim depends on the cluster type. On Elastic Cloud Serverless, derived API keys cannot carry explicit privileges, which means DLS-as-architecture requires Kibana-UI-minted keys (not the script-based bootstrap). The post doesn't flag this constraint. | Add one sentence to *Isolate at the cluster, not the app* acknowledging the Serverless minting path: *"On Serverless projects, per-user DLS keys are minted via Kibana UI rather than programmatically; see the bootstrap script's failure message for the Kibana recipe."* Or keep silent and let the linked code speak. Author's call. |
| optional | The reranker variance section is excellent honesty. Numbers reported: 0.85, 0.88, 0.89. We've now observed 0.798 once and 0.851 twice more since. Variance band is wider than originally reported. | Decide whether to update with the wider band (e.g. "0.80–0.89") or keep the original three-run snapshot since that's the dataset the prose was written against. |
| optional | First-use acronym expansions are mostly handled. RRF expands on first use ("Reciprocal Rank Fusion (RRF)"). BM25 is industry-standard and not expanded; usually fine for the target audience. DLS expands on first use ("Document-Level Security (DLS)"). MCP expands as "Model Context Protocol". MRR appears in *Measuring what matters* without expansion. | Expand MRR on first use: *"MRR (mean reciprocal rank)"*. |
| optional | The two ASCII diagrams (recall pipeline, gauss curve) render fine in MDX but won't be especially accessible. Each has a clear caption nearby though. | If editorial prefers SVG / actual images for accessibility, swap to images. Otherwise the captions carry the meaning. |
| optional | The post links to lots of github code references (14 links). All verified to point to correct line numbers as of this submission. If the source repo continues to evolve, those line numbers can drift. | The repo is on a stable branch; line-anchor drift is a minor risk. Worth one verification pass right before the article publishes. |
| critical | One of the editorial-confirmation items in the intake brief is the source repo's namespace: it currently lives at `noamschwartz/atlas-memory-demo` (author's personal namespace). All 16 in-article github URLs point there. Editorial may want this transferred to `elastic/` org before publish, which would invalidate every existing URL in the article. | Confirm with editorial early. If transfer is required, all 16 GitHub URLs in the article need a search-and-replace before the article PR opens. Worth raising with the reviewer upfront, not as a late surprise. |

## Audience persona pass (target: search engineer / agent builder)

| Severity | Finding | Suggested action |
|---|---|---|
| important | The *Plug in your existing catalog* section uses `bool.should` / `must_not exists` shorthand that's clear to an Elasticsearch power user, less so to someone arriving from a vector-DB background who hasn't written ES DSL. | One-sentence inline gloss could help: *"`bool.should` is Elasticsearch's logical OR; `must_not exists` checks that the named field is absent."* — but you've intentionally trimmed this section; adding a gloss back partially undoes that. Judgement call. |
| optional | The post assumes the reader knows what a cross-encoder reranker is. First-use does say "a Jina v2 cross-encoder scores the merged candidates against the user query," which is the working definition. | No change. |
| optional | The *Weight recent facts higher* section has dense ranking-function math (`offset`, `scale`, `decay`, `gauss`). The gauss-curve ASCII diagram is a good help. | No change. |
| optional | The Atlas demo isn't presented as a tutorial reproducible with a `git clone` + setup script. It's described as an architecture post. A search engineer reading this might want a "here's how to run it" bullet, or a single "If you want to reproduce, the repo's README has a 4-step setup" line. | Optional: add one sentence near the end of *Connect any agent via MCP* or just before *Measuring what matters*, e.g. *"The full demo runs locally with `./setup.sh && ./dev start`; see the repo README for prerequisites."* |

## Synthesis (cross-pass)

**Critical (1):**
1. **Repo namespace confirmation.** Decide with editorial whether `noamschwartz/atlas-memory-demo` stays or transfers to `elastic/` before publish. This affects all 16 GitHub links. Raise on the topic issue early.

**Important (2):**
1. **Serverless DLS caveat.** One sentence in *Isolate at the cluster, not the app* acknowledging the Serverless minting path (Kibana UI vs script bootstrap). The post now claims DLS-as-architecture; on this cluster that's true via Kibana-minted keys, and a reader on Serverless will want to know that.
2. **ES DSL gloss** in *Plug in your existing catalog* — one sentence for readers coming from non-ES backgrounds. Author's call.

**Optional (5):**
1. Subtitle field for a sharper hook in social previews and the article header.
2. MRR first-use expansion in *Measuring what matters*.
3. Variance band update (0.80–0.89 vs 0.85–0.89) if you want to reflect the additional measurements.
4. One-line "how to reproduce" sentence pointing at the repo README.
5. Editorial sentence on whether the lessons-learned companion ships alongside, gets folded in, or stays separate.

## What's already in good shape

- No em-dashes (just removed all three in the prior pass).
- No bare braces outside fenced code blocks. MDX will build cleanly.
- All required frontmatter fields present (only the date is TBD, intentional).
- 12 H2 sections, 3786-word body — both inside the policy's preferred bands.
- All 14 line-anchored GitHub links verify against current code.
- All discouraged marketing terms (`leverage`, `powerful`, `lightning-fast`, etc.) are absent.
