# Next Steps — Things You Run Externally

> Everything in this file is for you to execute. I've staged the local artefacts; these are the actions that mutate external state (GitHub, board, PRs).

## 1. Address the persona-review items you want to action

See `persona-review-findings.md`. Critical (1 item) and important (2 items) at minimum. Optional items are your call. Edit `blog-agent-memory-elasticsearch-v2.md` (the source markdown) for any changes — the MDX regenerates from it.

After edits, ping me to re-run the MDX regen + lint.

## 2. Set the target publish date

Edit `docs/submission/labs_submission.json`:

```
"target_publish_date": "YYYY-MM-DD",
"submitted_for_review_date": "YYYY-MM-DD"
```

Pick a date that respects the Search Labs lead-time policy (typically ~2 weeks for technical review handoff).

After setting, ping me to regen MDX so the `date` field in frontmatter updates.

## 3. Design the header image

- **Spec:** 16:9 aspect ratio.
- **Destination:** `public/assets/images/building-agent-memory-on-elasticsearch/header.png` in the content PR (relative to the Search Labs repo root).
- **Frontmatter ref:** already set to `building-agent-memory-on-elasticsearch/header.png` in the MDX.

## 4. Add the video link

The article currently says `> 📹 *Watch the 90-second walkthrough → [video link]*` near the top. Once you have the URL, edit `blog-agent-memory-elasticsearch-v2.md` to replace `[video link]` with the actual URL (or remove the line if you decide to drop it).

## 5. Author file in the target repo

`_content/authors/noam-schwartz.mdx` doesn't exist in `elastic/search-labs-elastic-co`. Template in `author-and-tag-templates.md`. Two paths:

- **Bundle it with the article PR** (simpler — one PR, one review cycle).
- **Send a precursor author-only PR** (cleaner separation if editorial prefers it).

Headshot file placement: check a recent author-addition PR in the Search Labs repo for the canonical directory.

## 6. Create the topic issue (you do this)

```bash
gh issue create \
  --repo elastic/search-labs-elastic-co \
  --title "Topic: Building agent memory on Elasticsearch" \
  --body "$(cat docs/submission/labs_intake_brief.md)"
```

Capture the issue URL and put it in `docs/submission/labs_submission.json` → `board_ticket_url`, and in `docs/submission/review-context.md` under `## Board`.

## 7. Attach the issue to the board

```bash
gh project item-add 1446 --owner elastic --url <issue-url-from-step-6>
```

Verify:

```bash
gh issue view <issue-number> --repo elastic/search-labs-elastic-co --json url,projectItems
```

Confirm `Search Labs Content Process` appears under `projectItems`.

## 8. Move board status to "Article technical review" when ready

Author-controlled, your call. Once you've finished the persona-review edits, the date is set, and the header image exists.

## 9. Open the content PR

Branch suggestion: `noam/building-agent-memory-on-elasticsearch` (direct branch in `elastic/search-labs-elastic-co`, not a fork — assumes you have write access).

Files to commit:

- `_content/articles/building-agent-memory-on-elasticsearch.mdx` (copy from `docs/blog-drafts/building-agent-memory-on-elasticsearch.mdx`)
- `public/assets/images/building-agent-memory-on-elasticsearch/header.png`
- `_content/authors/noam-schwartz.mdx` (if not done in a precursor PR)
- `_content/tags/agents.mdx`, `ai.mdx`, `memory.mdx` (only if editorial accepts the new tag proposals; otherwise drop these and edit the article's frontmatter `tags` to keep only `rag`, `search`)

PR body **must include**: `Closes #<issue-number>`.

## 10. Post the handoff comment on the topic issue

A brief comment linking the PR, the live preview (Vercel will attempt it; pre-existing broken articles in the repo may fail the preview build — not necessarily yours), and any review notes.

---

## What I've already done locally

- `docs/submission/labs_intake_brief.md` — drafted from the article. Edit freely.
- `docs/submission/labs_submission.json` — populated with confirmed picks; `target_publish_date` is TBD.
- `docs/submission/review-context.md` — canonical state file (update as steps 6–10 land).
- `docs/submission/publish-branches.md` — one-PR decision documented.
- `docs/submission/author-and-tag-templates.md` — MDX scaffolds for the author + 3 new tag files.
- `docs/submission/persona-review-findings.md` — Marketing/DevRel/audience review findings.
- `docs/blog-drafts/building-agent-memory-on-elasticsearch.mdx` — MDX-converted article. Lint passes (0 errors, 1 warning: TBD date).
- Fixed two British spellings (`recognise` → `recognize`, two instances of `ageing` → `aging`) in the source markdown.

The source markdown `blog-agent-memory-elasticsearch-v2.md` is the editing surface. MDX regenerates from it whenever you want.
