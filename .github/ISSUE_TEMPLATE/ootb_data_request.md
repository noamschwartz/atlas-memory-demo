---
name: OOTB Data Request
about: Request new datasets, indices, or agents for the shared serverless project
title: '[OOTB] '
labels: ootb-data, enhancement
assignees: ''
---

## Request Type

- [ ] **New Dataset** - Add a new index with generated or sourced data
- [ ] **New Agent** - Create a new Agent Builder agent
- [ ] **Update Existing** - Modify an existing dataset or agent
- [ ] **New Search Tool** - Add a custom search tool for agents

## Dataset / Agent Details

### Name
<!-- What should this dataset/agent be called? Use ootb- prefix for consistency -->


### Description
<!-- Brief description of what this data represents or what the agent does -->


### Use Case
<!-- What demo scenario does this enable? -->


## For New Datasets

### Domain
<!-- e.g., E-commerce, Healthcare, Finance, Security, Recipes, etc. -->


### Suggested Record Count
<!-- How many records needed? Default is 100-200 for demos -->


### Key Fields Required
<!-- List the important fields this dataset should have -->

| Field | Type | Description |
|-------|------|-------------|
|       |      |             |

### Semantic Search
<!-- Which EIS endpoints should be used? -->

- [x] ELSER (`.elser-2-elastic`) - English semantic search
- [ ] jina-embeddings-v3 (`.jina-embeddings-v3`) - Multilingual dense vectors

### Geo Search?
- [ ] Yes, needs `geo_point` field for location queries
- [x] No geo search needed

### Data Source
<!-- Where should this data come from? -->

- [ ] Generate with new Python generator script
- [ ] Generate with LLM
- [ ] Use existing public dataset (link below)
- [ ] Crawl from website (URL below)

**Source details:**


## For New Agents

### Agent Purpose
<!-- What should this agent help users do? -->


### Target Index/Indices
<!-- Which ootb- indices should this agent search? -->


### Example User Queries
<!-- 3-5 example questions users might ask -->

1. 
2. 
3. 

### Special Capabilities
<!-- Any specific behaviours needed? -->


## Priority

- [ ] Critical - Blocking a demo
- [ ] High - Needed soon for upcoming demo
- [ ] Medium - Would be nice to have
- [ ] Low - Future enhancement

## Additional Context

<!-- Add any mockups, example data formats, or references here -->


## Contribution

- [ ] I can create the generator script
- [ ] I can provide sample data
- [ ] I can help test the agent
- [ ] Just requesting, please implement
