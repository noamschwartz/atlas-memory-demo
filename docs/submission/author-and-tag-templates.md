# Author + Tag MDX templates

> These go into the content PR alongside the article. They live in `_content/authors/` and `_content/tags/` in `elastic/search-labs-elastic-co`.

## `_content/authors/noam-schwartz.mdx`

```mdx
---
title: "Noam Schwartz"
slug: "noam-schwartz"
description: "TODO: one-line role (e.g. 'Solutions Architect at Elastic')"
image: "TODO: headshot filename — check naming convention in recent author PRs (likely headshot-noam-schwartz-300x300.jpg or similar)"
---
```

**Headshot:** existing author files reference filenames like `headshot-nick-chow-300x300.jpg`. The actual image file goes somewhere under `public/assets/`. Check a recent author-addition PR for the canonical directory before placing the file.

## `_content/tags/agents.mdx`

```mdx
---
title: "Agents"
slug: agents
description: "Articles about building, deploying, and operating AI agents."
---
```

## `_content/tags/ai.mdx`

```mdx
---
title: "AI"
slug: ai
description: "Articles about AI and machine learning techniques applied to search, retrieval, and agents."
---
```

## `_content/tags/memory.mdx`

```mdx
---
title: "Memory"
slug: memory
description: "Articles about persistent state and memory architectures for AI agents."
---
```

**Note:** these three tags do not yet exist in the Search Labs taxonomy. Editorial may accept them, push back, or ask for different proposals. Fallback if rejected: drop them from the article's frontmatter and keep only `rag` + `search`.
