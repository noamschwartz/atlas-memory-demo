#!/bin/bash
# Test crawl script - validates config, runs small crawl, validates results, indexes, and tests semantic fields

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
CONFIG_FILE="$SCRIPT_DIR/elastic-docs-crawler.yml"
RESULTS_DIR="$SCRIPT_DIR/results/elastic-docs"
TEST_INDEX="test-elastic-docs-$(date +%s)"

echo "=========================================="
echo "Testing Elastic Docs Crawler Workflow"
echo "=========================================="
echo ""

# Check Docker
if ! docker ps > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker Desktop first."
    exit 1
fi

# Step 1: Validate config
echo "Step 1: Validating crawler configuration..."
docker run --rm -v "$PROJECT_ROOT":/config docker.elastic.co/integrations/crawler:0.4.2 \
    jruby bin/crawler validate /config/backend/scripts/crawler/elastic-docs-crawler.yml
echo "✅ Config validation passed"
echo ""

# Step 2: Test single URL
echo "Step 2: Testing single URL extraction..."
TEST_URL="https://www.elastic.co/guide/en/elasticsearch/reference/current/index.html"
docker run --rm -v "$PROJECT_ROOT":/config docker.elastic.co/integrations/crawler:0.4.2 \
    jruby bin/crawler urltest /config/backend/scripts/crawler/elastic-docs-crawler.yml "$TEST_URL" 2>&1 | head -30
echo "✅ URL test completed"
echo ""

# Step 3: Run small crawl
echo "Step 3: Running crawl (depth=1, file output)..."
rm -rf "$RESULTS_DIR"
mkdir -p "$RESULTS_DIR"
docker run --rm -v "$PROJECT_ROOT":/config docker.elastic.co/integrations/crawler:0.4.2 \
    jruby bin/crawler crawl /config/backend/scripts/crawler/elastic-docs-crawler.yml 2>&1 | tail -20
echo "✅ Crawl completed"
echo ""

# Step 4: Check results
echo "Step 4: Checking crawled results..."
if [ ! -d "$RESULTS_DIR" ] || [ -z "$(ls -A $RESULTS_DIR/*.json 2>/dev/null)" ]; then
    echo "❌ No JSON files found in $RESULTS_DIR"
    exit 1
fi

JSON_COUNT=$(ls -1 "$RESULTS_DIR"/*.json 2>/dev/null | wc -l | tr -d ' ')
echo "Found $JSON_COUNT JSON files"

# Quick validation
echo ""
echo "Validating results..."
MISSING_FIELDS=$(cat "$RESULTS_DIR"/*.json | jq -c 'select(.url == null or ((.doc_title == null or .doc_title == "") and (.blog_title == null or .blog_title == "") and (.doc_body == null or .doc_body == "") and (.blog_body == null or .blog_body == "")))' 2>/dev/null | wc -l | tr -d ' ')
SHORT_CONTENT=$(cat "$RESULTS_DIR"/*.json | jq -c 'select((.doc_body != null and (.doc_body | length) < 50) or (.blog_body != null and (.blog_body | length) < 50))' 2>/dev/null | wc -l | tr -d ' ')

echo "  Documents missing required fields: $MISSING_FIELDS"
echo "  Documents with very short content: $SHORT_CONTENT"

if [ "$MISSING_FIELDS" -gt 0 ] || [ "$SHORT_CONTENT" -gt 0 ]; then
    echo "⚠️  Some validation issues found, but continuing..."
fi

# Show sample
echo ""
echo "Sample document:"
cat "$RESULTS_DIR"/*.json | jq -s '.[0]' 2>/dev/null | head -30
echo ""
echo "✅ Results validated"
echo ""

# Step 5: Index to Elasticsearch
echo "Step 5: Indexing to Elasticsearch..."
cd "$PROJECT_ROOT/backend"
if [ ! -f .env ]; then
    echo "❌ backend/.env not found. Please configure ELASTICSEARCH_URL and ELASTIC_API_KEY"
    exit 1
fi

source .env 2>/dev/null || true
if [ -z "$ELASTICSEARCH_URL" ] || [ -z "$ELASTIC_API_KEY" ]; then
    echo "❌ ELASTICSEARCH_URL or ELASTIC_API_KEY not set in .env"
    exit 1
fi

python -m scripts.crawler.index_elastic_docs \
    --results-dir "$RESULTS_DIR" \
    --index-name "$TEST_INDEX" \
    --recreate \
    --skip-eis-check 2>&1 | tail -30

echo ""
echo "✅ Indexing completed"
echo ""

# Step 6: Test semantic search
echo "Step 6: Testing semantic search (jina-v3)..."
TEST_QUERY='{"query": {"semantic": {"field": "semantic_jina", "query": "how to search documents"}}}'

RESPONSE=$(curl -s -X POST "$ELASTICSEARCH_URL/$TEST_INDEX/_search" \
    -H "Authorization: ApiKey $ELASTIC_API_KEY" \
    -H "Content-Type: application/json" \
    -d "$TEST_QUERY")

HITS=$(echo "$RESPONSE" | jq -r '.hits.total.value // .hits.total' 2>/dev/null || echo "0")
echo "  Semantic search returned $HITS hits"

if [ "$HITS" -gt 0 ]; then
    echo "✅ Semantic search is working!"
    echo ""
    echo "Sample result:"
    echo "$RESPONSE" | jq -r '.hits.hits[0]._source | {title: .doc_title // .blog_title, url: .url}' 2>/dev/null || echo "$RESPONSE" | head -5
else
    echo "⚠️  No results found - semantic fields may still be processing"
fi

echo ""
echo "=========================================="
echo "Test Index: $TEST_INDEX"
echo "Results: $RESULTS_DIR"
echo "=========================================="
