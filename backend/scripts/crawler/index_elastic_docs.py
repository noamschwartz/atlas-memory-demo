#!/usr/bin/env python3
"""
Index crawled Elastic documentation and blog content into Elasticsearch.

This script processes JSON files from the Open Crawler and indexes them
into the shared serverless cluster with semantic fields (ELSER + jina-v3).

Usage:
    # Index crawled results
    python -m scripts.crawler.index_elastic_docs \
        --results-dir backend/scripts/crawler/results/elastic-docs \
        --index-name ootb-elastic-docs
    
    # Validate before indexing
    python -m scripts.crawler.index_elastic_docs \
        --results-dir backend/scripts/crawler/results/elastic-docs \
        --validate-only
    
    # Dry run (show what would be indexed)
    python -m scripts.crawler.index_elastic_docs \
        --results-dir backend/scripts/crawler/results/elastic-docs \
        --dry-run

Environment Variables:
    ELASTICSEARCH_URL: Elasticsearch endpoint URL
    ELASTIC_API_KEY: API key for authentication
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
import hashlib

from elasticsearch import Elasticsearch, helpers

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.config import settings

# EIS endpoints (service: "elastic" - no ML nodes required)
ELSER_ENDPOINT = ".elser-2-elastic"
JINA_ENDPOINT = ".jina-embeddings-v3"


def get_elastic_docs_mapping(use_jina: bool = True) -> Dict[str, Any]:
    """
    Get mapping for Elastic documentation index with semantic fields.
    
    Following the pattern from load_serverless_ootb.py, this mapping:
    - Uses copy_to to combine fields for semantic search
    - Only copies smaller fields (title, summary, headings) to semantic_text
    - Supports both ELSER and jina-v3 embeddings
    """
    mapping = {
        "mappings": {
            "properties": {
                # Document ID (generated from URL)
                "id": {"type": "keyword"},
                
                # Document type (docs vs blog)
                "doc_type": {"type": "keyword"},
                
                # URL fields
                "url": {"type": "keyword", "index": False},
                "url_path": {"type": "keyword"},
                
                # Documentation fields
                "doc_title": {
                    "type": "text",
                    "copy_to": ["semantic_content", "all_content"]
                },
                "doc_summary": {
                    "type": "text",
                    "copy_to": ["semantic_content", "all_content"]
                },
                "section_headings": {
                    "type": "text",
                    "copy_to": ["semantic_content", "all_content"]
                },
                "doc_body": {
                    "type": "text",
                    "copy_to": "all_content"
                    # Note: NOT copied to semantic_content - too large
                },
                
                # Blog fields
                "blog_title": {
                    "type": "text",
                    "copy_to": ["semantic_content", "all_content"]
                },
                "blog_summary": {
                    "type": "text",
                    "copy_to": ["semantic_content", "all_content"]
                },
                "blog_body": {
                    "type": "text",
                    "copy_to": "all_content"
                    # Note: NOT copied to semantic_content - too large
                },
                "author": {"type": "keyword"},
                "publish_date": {"type": "date"},
                "categories": {"type": "keyword"},
                
                # Product/component metadata
                "product_name": {"type": "keyword"},
                "version": {"type": "keyword"},
                
                # Combined searchable fields
                "all_content": {
                    "type": "text"
                },
                
                # Semantic fields (ELSER)
                "semantic_content": {
                    "type": "semantic_text",
                    "inference_id": ELSER_ENDPOINT
                }
            }
        }
    }
    
    # Add jina-v3 semantic field if enabled
    if use_jina:
        mapping["mappings"]["properties"]["semantic_jina"] = {
            "type": "semantic_text",
            "inference_id": JINA_ENDPOINT
        }
        # Also copy semantic fields to jina
        for field in ["doc_title", "doc_summary", "section_headings", 
                     "blog_title", "blog_summary"]:
            if field in mapping["mappings"]["properties"]:
                copy_to = mapping["mappings"]["properties"][field].get("copy_to", [])
                if isinstance(copy_to, str):
                    copy_to = [copy_to]
                copy_to.append("semantic_jina")
                mapping["mappings"]["properties"][field]["copy_to"] = copy_to
    
    return mapping


def generate_doc_id(url: str) -> str:
    """Generate a consistent document ID from URL."""
    return hashlib.sha256(url.encode()).hexdigest()[:32]


def normalize_crawled_doc(crawled_doc: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize a crawled document into the index format.
    
    Handles both documentation and blog post formats.
    """
    url = crawled_doc.get("url", "")
    doc_id = generate_doc_id(url)
    
    # Determine document type
    doc_type = "blog" if "/blog/" in url else "docs"
    
    # Build normalized document
    normalized = {
        "id": doc_id,
        "doc_type": doc_type,
        "url": url,
        "url_path": crawled_doc.get("url_path", ""),
        "indexed_at": datetime.utcnow().isoformat() + "Z"
    }
    
    # Add documentation fields
    if crawled_doc.get("doc_title"):
        normalized["doc_title"] = crawled_doc["doc_title"]
    if crawled_doc.get("doc_summary"):
        normalized["doc_summary"] = crawled_doc["doc_summary"]
    if crawled_doc.get("section_headings"):
        normalized["section_headings"] = crawled_doc["section_headings"]
    if crawled_doc.get("doc_body"):
        normalized["doc_body"] = crawled_doc["doc_body"]
    if crawled_doc.get("product_name"):
        normalized["product_name"] = crawled_doc["product_name"]
    if crawled_doc.get("version"):
        normalized["version"] = crawled_doc["version"]
    
    # Add blog fields
    if crawled_doc.get("blog_title"):
        normalized["blog_title"] = crawled_doc["blog_title"]
    if crawled_doc.get("blog_summary"):
        normalized["blog_summary"] = crawled_doc["blog_summary"]
    if crawled_doc.get("blog_body"):
        normalized["blog_body"] = crawled_doc["blog_body"]
    if crawled_doc.get("author"):
        normalized["author"] = crawled_doc["author"]
    if crawled_doc.get("publish_date"):
        normalized["publish_date"] = crawled_doc["publish_date"]
    if crawled_doc.get("categories"):
        normalized["categories"] = crawled_doc["categories"]
    
    return normalized


def load_crawled_files(results_dir: Path) -> List[Dict[str, Any]]:
    """Load all JSON files from crawler results directory."""
    documents = []
    
    if not results_dir.exists():
        raise FileNotFoundError(f"Results directory not found: {results_dir}")
    
    json_files = list(results_dir.glob("*.json"))
    if not json_files:
        raise ValueError(f"No JSON files found in {results_dir}")
    
    print(f"📂 Found {len(json_files)} JSON files")
    
    for json_file in json_files:
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Handle both single objects and arrays
                if isinstance(data, list):
                    documents.extend(data)
                else:
                    documents.append(data)
        except json.JSONDecodeError as e:
            print(f"⚠️  Skipping invalid JSON file {json_file}: {e}")
            continue
    
    print(f"📄 Loaded {len(documents)} documents")
    return documents


def validate_documents(documents: List[Dict[str, Any]]) -> tuple[int, List[str]]:
    """
    Validate crawled documents before indexing.
    
    Returns: (valid_count, errors)
    """
    valid_count = 0
    errors = []
    
    for i, doc in enumerate(documents):
        url = doc.get("url", "")
        if not url:
            errors.append(f"Document {i}: Missing URL")
            continue
        
        # Check for at least some content
        has_content = (
            doc.get("doc_title") or 
            doc.get("blog_title") or 
            doc.get("doc_body") or 
            doc.get("blog_body")
        )
        
        if not has_content:
            errors.append(f"Document {i} ({url}): No content fields found")
            continue
        
        valid_count += 1
    
    return valid_count, errors


def check_eis_availability(es: Elasticsearch) -> Dict[str, bool]:
    """Check which EIS endpoints are available."""
    print("\n🔍 Checking EIS endpoint availability...")
    result = {"elser": False, "jina": False}
    
    # Check ELSER
    try:
        es.inference.inference(
            inference_id=ELSER_ENDPOINT,
            input=["test"]
        )
        result["elser"] = True
        print(f"  ✓ {ELSER_ENDPOINT} available")
    except Exception as e:
        print(f"  ✗ {ELSER_ENDPOINT} not available: {e}")
    
    # Check jina-v3
    try:
        es.inference.inference(
            inference_id=JINA_ENDPOINT,
            input=["test"]
        )
        result["jina"] = True
        print(f"  ✓ {JINA_ENDPOINT} available")
    except Exception as e:
        print(f"  ✗ {JINA_ENDPOINT} not available: {e}")
    
    return result


def create_index(es: Elasticsearch, index_name: str, use_jina: bool = True, recreate: bool = False):
    """Create the index with semantic mapping."""
    if recreate and es.indices.exists(index=index_name):
        print(f"🗑️  Deleting existing index: {index_name}")
        es.indices.delete(index=index_name)
    
    if es.indices.exists(index=index_name):
        print(f"ℹ️  Index {index_name} already exists")
        return
    
    print(f"📝 Creating index: {index_name}")
    mapping = get_elastic_docs_mapping(use_jina=use_jina)
    
    es.indices.create(
        index=index_name,
        body=mapping
    )
    
    print(f"  ✓ Index created successfully")


def index_documents(
    es: Elasticsearch,
    index_name: str,
    documents: List[Dict[str, Any]],
    chunk_size: int = 100
) -> int:
    """Index documents using bulk API."""
    print(f"\n📤 Indexing {len(documents)} documents...")
    
    def generate_actions():
        for doc in documents:
            normalized = normalize_crawled_doc(doc)
            yield {
                "_index": index_name,
                "_id": normalized["id"],
                "_source": normalized
            }
    
    try:
        success, errors = helpers.bulk(
            es,
            generate_actions(),
            chunk_size=chunk_size,
            raise_on_error=False,
            request_timeout=120
        )
        
        print(f"  ✓ Indexed {success} documents")
        if errors:
            print(f"  ⚠ {len(errors)} errors occurred")
            if len(errors) <= 5:
                for error in errors:
                    print(f"    Error: {error}")
            else:
                print(f"    First error: {errors[0]}")
        
        return success
    except Exception as e:
        print(f"  ✗ Bulk indexing failed: {e}")
        raise


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Index crawled Elastic documentation into Elasticsearch',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Validate crawled results
    python -m scripts.crawler.index_elastic_docs \\
        --results-dir backend/scripts/crawler/results/elastic-docs \\
        --validate-only
    
    # Index to shared serverless cluster
    python -m scripts.crawler.index_elastic_docs \\
        --results-dir backend/scripts/crawler/results/elastic-docs \\
        --index-name ootb-elastic-docs
    
    # Dry run (show what would be indexed)
    python -m scripts.crawler.index_elastic_docs \\
        --results-dir backend/scripts/crawler/results/elastic-docs \\
        --dry-run
        """
    )
    
    # Connection arguments
    parser.add_argument(
        '--es-url',
        type=str,
        default=os.getenv('ELASTICSEARCH_URL'),
        help='Elasticsearch URL (or set ELASTICSEARCH_URL env var)'
    )
    parser.add_argument(
        '--api-key',
        type=str,
        default=os.getenv('ELASTIC_API_KEY'),
        help='API key (or set ELASTIC_API_KEY env var)'
    )
    
    # Input/output
    parser.add_argument(
        '--results-dir',
        type=str,
        required=True,
        help='Directory containing crawled JSON files'
    )
    parser.add_argument(
        '--index-name',
        type=str,
        default='ootb-elastic-docs',
        help='Elasticsearch index name (default: ootb-elastic-docs)'
    )
    
    # Options
    parser.add_argument(
        '--validate-only',
        action='store_true',
        help='Only validate documents, do not index'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be done without making changes'
    )
    parser.add_argument(
        '--recreate',
        action='store_true',
        help='Delete and recreate index if it exists'
    )
    parser.add_argument(
        '--skip-jina',
        action='store_true',
        help='Skip jina-v3 embeddings (ELSER only)'
    )
    parser.add_argument(
        '--skip-eis-check',
        action='store_true',
        help='Skip EIS availability check'
    )
    
    args = parser.parse_args()
    
    # Validate connection (unless validate-only)
    if not args.validate_only and not args.dry_run:
        if not args.es_url or not args.api_key:
            parser.error("--es-url and --api-key are required (or set ELASTICSEARCH_URL and ELASTIC_API_KEY)")
    
    # Load crawled documents
    results_dir = Path(args.results_dir)
    print(f"📂 Loading crawled documents from: {results_dir}")
    
    try:
        documents = load_crawled_files(results_dir)
    except Exception as e:
        print(f"✗ Failed to load documents: {e}")
        sys.exit(1)
    
    # Validate documents
    print(f"\n🔍 Validating documents...")
    valid_count, errors = validate_documents(documents)
    
    if errors:
        print(f"⚠️  Found {len(errors)} validation errors:")
        for error in errors[:10]:  # Show first 10
            print(f"  - {error}")
        if len(errors) > 10:
            print(f"  ... and {len(errors) - 10} more")
    
    print(f"✓ {valid_count}/{len(documents)} documents are valid")
    
    if args.validate_only:
        sys.exit(0 if valid_count == len(documents) else 1)
    
    # Show sample document (dry run)
    if args.dry_run or valid_count > 0:
        print(f"\n📄 Sample document:")
        sample = normalize_crawled_doc(documents[0])
        print(json.dumps(sample, indent=2)[:500] + "...")
    
    if args.dry_run:
        print(f"\n✓ Dry run complete. Would index {valid_count} documents to {args.index_name}")
        sys.exit(0)
    
    # Connect to Elasticsearch
    print(f"\n🔌 Connecting to Elasticsearch...")
    es = Elasticsearch(
        [args.es_url],
        api_key=args.api_key,
        request_timeout=60
    )
    
    # Check EIS availability
    if not args.skip_eis_check:
        eis_status = check_eis_availability(es)
        if not eis_status["elser"]:
            print("⚠️  Warning: ELSER endpoint not available. Semantic fields may not work.")
    
    # Create index
    use_jina = not args.skip_jina
    create_index(es, args.index_name, use_jina=use_jina, recreate=args.recreate)
    
    # Index documents
    indexed_count = index_documents(es, args.index_name, documents)
    
    # Summary
    print(f"\n✅ Indexing complete!")
    print(f"   Index: {args.index_name}")
    print(f"   Documents indexed: {indexed_count}")
    print(f"   Semantic fields: ELSER ({ELSER_ENDPOINT})" + 
          (f", jina-v3 ({JINA_ENDPOINT})" if use_jina else ""))


if __name__ == "__main__":
    main()
