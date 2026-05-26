# Search Labs Review Context — *Building agent memory on Elasticsearch*

> Canonical state for the submission. Update this file as each external step lands.

## Stage

`in_progress` (local artefacts being assembled). Target next stage: `technical_review`.

## Board

- **Repo (default):** `elastic/search-labs-elastic-co`
- **Board project:** `elastic/1446` (`Search Labs Content Process`), URL `https://github.com/orgs/elastic/projects/1446`
- **Issue:** not yet created. Title convention: `Topic: Building agent memory on Elasticsearch`
- **Author-controlled stages:** `Article in progress`, `Article technical review`, `Article editorial review`, `Changes required`
- **Blog-owner stages:** `Ready to publish`, `Done`

## Branches

- **Content PR (`elastic/search-labs-elastic-co`):** not yet created. Branch name suggestion: `noam/building-agent-memory-on-elasticsearch`
- **Code PR (`elastic/elasticsearch-labs`):** N/A. Article is repo-linked, not notebook-sourced.

## Local artefacts

- Source markdown: `blog-agent-memory-elasticsearch-v2.md` (gitignored in the source repo per local convention)
- Lessons-learned companion: `lessons-learned.md` (currently separate; editorial decision pending)
- MDX draft: `docs/blog-drafts/building-agent-memory-on-elasticsearch.mdx`
- Submission metadata: `docs/submission/labs_submission.json`
- Intake brief: `docs/submission/labs_intake_brief.md`
- Publish branches: `docs/submission/publish-branches.md`

## Header image

Not yet designed. Requirements: **16:9 aspect ratio**, placed at `public/assets/images/building-agent-memory-on-elasticsearch/header.png` in the content PR.

## Last compliance status

Local lint not yet run. Skill ships a reference policy at `~/.claude/hive-mind/skills/hive-search-labs-blog/labs_blog_policy.json`.

## Outstanding decisions (open with the author/editor)

See `editorial_confirmation_needed` in `labs_submission.json`.

## Author file

`_content/authors/noam-schwartz.mdx` does **not** currently exist in `elastic/search-labs-elastic-co`. To unblock the article PR, either:
1. Create the author file in the same PR as the article (small extra file in `_content/authors/`).
2. Send a precursor PR with just the author file.

Schema reference (from `nick-chow.mdx`):

```mdx
---
title: "<Full name>"
slug: "<slug>"
description: "<one-line role>"
image: "<headshot filename, e.g. headshot-<slug>-300x300.jpg>"
---
```

Headshot image lives somewhere under `public/assets/`; check existing author PRs for the canonical path before placing the file.
