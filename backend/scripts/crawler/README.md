# Elastic Documentation Crawler

This directory contains scripts and configurations for crawling Elastic documentation and blog content, then indexing it into the shared serverless cluster with semantic search capabilities.

## Overview

The workflow consists of four main steps:

1. **Crawl** - Use Open Crawler to extract content from elastic.co
2. **Validate** - Check crawled results for quality and completeness
3. **Index** - Load crawled data into Elasticsearch with semantic fields
4. **Agent** - Create an Agent Builder agent that references the documentation

## Prerequisites

- Docker Desktop installed and running
- Access to the shared serverless cluster (or your own Elasticsearch cluster)
- API key with write permissions (for indexing and creating agents)

## Quick Start

### 1. Configure Environment

Ensure your `backend/.env` has:

```bash
ELASTICSEARCH_URL=https://demo-starter-ootb-data-c601a1.es.us-east4.gcp.elastic.cloud:443
ELASTIC_API_KEY=your-api-key-here
KIBANA_URL=https://demo-starter-ootb-data-c601a1.kb.us-east4.gcp.elastic.cloud/
```

### 2. Test Crawler Configuration

Start with a single URL test (fastest feedback):

```bash
docker run -v "$(pwd)":/config docker.elastic.co/integrations/crawler:0.4.2 \
  jruby bin/crawler urltest /config/backend/scripts/crawler/elastic-docs-crawler.yml \
  https://www.elastic.co/guide/en/elasticsearch/reference/current/index.html
```

### 3. Validate Configuration

```bash
docker run -v "$(pwd)":/config docker.elastic.co/integrations/crawler:0.4.2 \
  jruby bin/crawler validate /config/backend/scripts/crawler/elastic-docs-crawler.yml
```

### 4. Run Crawl (Start with File Output)

The config is set to `output_sink: file` by default. Run the crawl:

```bash
docker run -v "$(pwd)":/config docker.elastic.co/integrations/crawler:0.4.2 \
  jruby bin/crawler crawl /config/backend/scripts/crawler/elastic-docs-crawler.yml
```

Results will be saved to `backend/scripts/crawler/results/elastic-docs/`.

### 5. Validate Crawled Results

```bash
python -m scripts.crawler.validate_crawler_results \
  --results-dir backend/scripts/crawler/results/elastic-docs
```

### 6. Index into Elasticsearch

```bash
python -m scripts.crawler.index_elastic_docs \
  --results-dir backend/scripts/crawler/results/elastic-docs \
  --index-name ootb-elastic-docs
```

### 7. Create Agent Builder Agent

```bash
python -m scripts.crawler.create_elastic_docs_agent \
  --index-name ootb-elastic-docs \
  --agent-id ootb-elastic-docs-assistant
```

### 8. Use the Agent

Set in your `backend/.env`:

```bash
AGENT_ID=ootb-elastic-docs-assistant
```

Then restart: `./dev restart`

## Files

| File | Purpose |
|------|---------|
| `elastic-docs-crawler.yml` | Open Crawler configuration for Elastic docs/blogs |
| `validate_crawler_results.py` | Validate crawled JSON files before indexing |
| `index_elastic_docs.py` | Index crawled data into Elasticsearch with semantic fields |
| `create_elastic_docs_agent.py` | Create Agent Builder agent that references the docs |

## Configuration Details

### Crawler Configuration

The `elastic-docs-crawler.yml` file configures:

- **Documentation pages** (`/guide/` URLs)
  - Extracts: title, summary, section headings, body, product name, version
- **Blog posts** (`/blog/` URLs)
  - Extracts: title, summary, author, publish date, categories, body

**Important**: Start with `output_sink: file` for testing. Only switch to `elasticsearch` when the config is validated.

### Index Mapping

The index uses semantic search with:

- **ELSER** (`.elser-2-elastic`) - Sparse embeddings for English content
- **jina-v3** (`.jina-embeddings-v3`) - Dense embeddings for multilingual support

**Semantic fields**: Only smaller fields (title, summary, headings) are copied to `semantic_content` and `semantic_jina`. Large body text is excluded to avoid timeouts.

### Agent Configuration

The agent is configured with:

- **System instructions**: Guidance on answering questions about Elastic products
- **Tool**: Index search tool that searches the documentation index using semantic search
- **Labels**: `elastic-docs`, `documentation`, `serverless`

## Workflow Best Practices

### Fast Iteration Pattern

Always follow this progression:

```
urltest → validate → console crawl → file crawl → validate results → index → create agent
```

1. **urltest** - Test single URL (seconds)
2. **validate** - Check config syntax (instant)
3. **console crawl** - See what URLs are visited (seconds)
4. **file crawl** - Inspect extracted fields (minutes)
5. **validate results** - Check data quality (seconds)
6. **index** - Load into Elasticsearch (minutes)
7. **create agent** - Set up Agent Builder (seconds)

### Testing Tips

- Start with `max_crawl_depth: 1` for faster testing
- Use `log_level: debug` for troubleshooting
- Check file output before indexing to Elasticsearch
- Validate results before indexing to catch issues early

## Troubleshooting

### Crawler Issues

**Problem**: No content extracted
- **Solution**: Check CSS selectors match the actual HTML structure
- **Debug**: Use `urltest` to see raw HTML, then adjust selectors

**Problem**: Too many/few URLs crawled
- **Solution**: Adjust `crawl_rules` and `max_crawl_depth`
- **Debug**: Use console output to see which URLs are allowed/denied

### Indexing Issues

**Problem**: Semantic fields empty
- **Solution**: Check EIS endpoints are available (`.elser-2-elastic`, `.jina-embeddings-v3`)
- **Debug**: Run with `--skip-eis-check` to see if endpoints are accessible

**Problem**: Timeout during indexing
- **Solution**: Ensure only small fields are copied to `semantic_content`
- **Debug**: Check document sizes - body text should NOT be in semantic fields

### Agent Issues

**Problem**: Agent not found
- **Solution**: Verify agent ID matches what was created
- **Debug**: List agents: `curl -H "Authorization: ApiKey $ELASTIC_API_KEY" "$KIBANA_URL/api/agent_builder/agents"`

**Problem**: Agent can't find documents
- **Solution**: Verify index name matches and contains data
- **Debug**: Test semantic search directly on the index

## Related Documentation

- [Open Crawler Quickstart](../../../hive-mind/patterns/open-crawler/OPEN_CRAWLER_QUICKSTART.md)
- [Open Crawler Elasticsearch Integration](../../../hive-mind/patterns/open-crawler/OPEN_CRAWLER_ELASTICSEARCH.md)
- [Agent Builder API Management](../../../hive-mind/patterns/agent-builder/AGENT_BUILDER_API_MANAGEMENT.md)
- [Shared Serverless Project](../../../docs/SHARED_SERVERLESS_PROJECT.md)

## Notes

- The shared serverless cluster uses read-only API keys by default. You'll need write access to index data and create agents.
- Semantic fields use Elastic Inference Service (EIS) - no ML nodes required.
- The crawler doesn't execute JavaScript - only static HTML is extracted.
- For best results, crawl documentation pages separately from blog posts (they have different structures).
