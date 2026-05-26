# Publish Branches — *Building agent memory on Elasticsearch*

## Decision

**One PR only.** Article is markdown-only (no notebook), so no second PR on `elastic/elasticsearch-labs` is needed. The post links to the existing demo repo (`noamschwartz/atlas-memory-demo`) for runnable code.

## Content PR

- **Repo:** `elastic/search-labs-elastic-co`
- **Branch:** `noam/building-agent-memory-on-elasticsearch` (suggested; final name is author's call)
- **Target:** `main`
- **Files:**
  - `_content/articles/building-agent-memory-on-elasticsearch.mdx` (the article)
  - `public/assets/images/building-agent-memory-on-elasticsearch/header.png` (16:9 header)
  - `public/assets/images/building-agent-memory-on-elasticsearch/<any-inline-images>.png` (none in the current draft, but reserve the directory)
  - `_content/authors/noam-schwartz.mdx` (NEW — author file does not yet exist on Search Labs)
  - `_content/tags/agents.mdx`, `_content/tags/ai.mdx`, `_content/tags/memory.mdx` (NEW — three proposed tags; editorial may push back, fallback is to drop them and keep `rag` + `search` only)
- **PR body must include:** `Closes #<issue-number>` (after the topic issue is created)
- **Vercel preview:** pre-existing broken articles can fail the preview build; not a blocker if other open PRs show the same failure.

## Code PR

**Not required.** Article is repo-linked, not notebook-sourced. The Atlas demo lives at `noamschwartz/atlas-memory-demo`. Editorial confirmation pending on whether that repo should transfer to `elastic/` before publish.

## Branch publishing for review

The `hive-branch-publish-tagging` companion skill describes how to publish markdown + images together to a review branch for asynchronous reviewer access. For Atlas, this is optional — the content PR itself serves as the review artefact.
