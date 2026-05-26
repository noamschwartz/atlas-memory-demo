#!/usr/bin/env python3
"""
Load out-of-the-box demo data into a Serverless Elasticsearch project.

This script creates indices with semantic_text fields (using EIS) and loads
demo data for products, knowledge base, support tickets, and store locations.

Usage:
    # Load all datasets with defaults
    python -m scripts.load_serverless_ootb
    
    # Specify connection details
    python -m scripts.load_serverless_ootb \
        --es-url https://your-project.es.region.gcp.elastic.cloud:443 \
        --api-key YOUR_API_KEY
    
    # Load specific datasets
    python -m scripts.load_serverless_ootb --datasets products knowledge
    
    # Custom record counts
    python -m scripts.load_serverless_ootb --products 500 --knowledge 200

Environment Variables:
    ELASTICSEARCH_URL: Elasticsearch endpoint URL
    ELASTIC_API_KEY: API key for authentication
"""

import argparse
import os
import sys
import json
from typing import Dict, Any, List, Optional

from elasticsearch import Elasticsearch, helpers

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.generators.product_generator import ProductGenerator
from scripts.generators.document_generator import DocumentGenerator
from scripts.generators.support_generator import SupportGenerator
from scripts.generators.store_generator import StoreGenerator


# =============================================================================
# EIS Configuration
# =============================================================================

# EIS endpoints (service: "elastic" - no ML nodes required)
ELSER_ENDPOINT = ".elser-2-elastic"
JINA_ENDPOINT = ".jina-embeddings-v3"

# Index configurations
INDEX_CONFIGS = {
    'products': {
        'name': 'ootb-products',
        'description': 'E-commerce product catalogue',
        'generator': ProductGenerator,
        'default_count': 200,
        'semantic_fields': ['title', 'description'],
        'use_jina': True  # Also add jina embeddings for comparison
    },
    'knowledge': {
        'name': 'ootb-knowledge',
        'description': 'Documentation and FAQ articles',
        'generator': DocumentGenerator,
        'default_count': 150,
        'generator_config': {'content_type': 'mixed'},
        'semantic_fields': ['question', 'answer', 'title', 'content'],
        'use_jina': True  # Enable jina for multilingual/comparison demos
    },
    'support': {
        'name': 'ootb-support',
        'description': 'Customer support tickets',
        'generator': SupportGenerator,
        'default_count': 150,
        'semantic_fields': ['subject', 'description'],
        'use_jina': True  # Enable jina for multilingual/comparison demos
    },
    'stores': {
        'name': 'ootb-stores',
        'description': 'Retail store locations',
        'generator': StoreGenerator,
        'default_count': 100,
        'semantic_fields': ['name'],
        'use_jina': True,  # For multilingual store names
        'has_geo': True
    }
}


# =============================================================================
# Index Mappings
# =============================================================================

def get_products_mapping(use_jina: bool = True) -> Dict[str, Any]:
    """Get mapping for products index."""
    mapping = {
        "mappings": {
            "properties": {
                "id": {"type": "keyword"},
                "title": {
                    "type": "text",
                    "copy_to": "semantic_content"
                },
                "brand": {"type": "keyword"},
                "description": {
                    "type": "text",
                    "copy_to": "semantic_content"
                },
                "price": {"type": "float"},
                "currency": {"type": "keyword"},
                "image_url": {"type": "keyword", "index": False},
                "categories": {"type": "keyword"},
                "attrs": {"type": "flattened"},
                "attr_keys": {"type": "keyword"},
                "in_stock": {"type": "boolean"},
                "rating": {"type": "float"},
                "review_count": {"type": "integer"},
                "semantic_content": {
                    "type": "semantic_text",
                    "inference_id": ELSER_ENDPOINT
                }
            }
        }
    }
    
    if use_jina:
        mapping["mappings"]["properties"]["semantic_jina"] = {
            "type": "semantic_text",
            "inference_id": JINA_ENDPOINT
        }
    
    return mapping


def get_knowledge_mapping(use_jina: bool = True) -> Dict[str, Any]:
    """Get mapping for knowledge base index."""
    mapping = {
        "mappings": {
            "properties": {
                "id": {"type": "keyword"},
                "type": {"type": "keyword"},
                # FAQ fields
                "question": {
                    "type": "text",
                    "copy_to": "semantic_content"
                },
                "answer": {
                    "type": "text",
                    "copy_to": "semantic_content"
                },
                # Article fields
                "title": {
                    "type": "text",
                    "copy_to": "semantic_content"
                },
                "summary": {"type": "text"},
                "content": {
                    "type": "text",
                    "copy_to": "semantic_content"
                },
                "sections": {"type": "keyword"},
                # Common fields
                "category": {"type": "keyword"},
                "tags": {"type": "keyword"},
                "related_topics": {"type": "keyword"},
                "helpful_count": {"type": "integer"},
                "view_count": {"type": "integer"},
                "last_updated": {"type": "date"},
                "created": {"type": "date"},
                "author": {"type": "keyword"},
                "difficulty": {"type": "keyword"},
                "read_time_minutes": {"type": "integer"},
                "semantic_content": {
                    "type": "semantic_text",
                    "inference_id": ELSER_ENDPOINT
                }
            }
        }
    }
    
    if use_jina:
        mapping["mappings"]["properties"]["semantic_jina"] = {
            "type": "semantic_text",
            "inference_id": JINA_ENDPOINT
        }
    
    return mapping


def get_support_mapping(use_jina: bool = True) -> Dict[str, Any]:
    """Get mapping for support tickets index."""
    mapping = {
        "mappings": {
            "properties": {
                "id": {"type": "keyword"},
                "subject": {
                    "type": "text",
                    "copy_to": "semantic_content"
                },
                "description": {
                    "type": "text",
                    "copy_to": "semantic_content"
                },
                "product": {"type": "keyword"},
                "issue_type": {"type": "keyword"},
                "status": {"type": "keyword"},
                "priority": {"type": "keyword"},
                "sentiment": {"type": "keyword"},
                "customer_name": {"type": "keyword"},
                "customer_email": {"type": "keyword"},
                "assigned_to": {"type": "keyword"},
                "conversation": {"type": "nested"},
                "message_count": {"type": "integer"},
                "created_at": {"type": "date"},
                "updated_at": {"type": "date"},
                "resolved_at": {"type": "date"},
                "tags": {"type": "keyword"},
                "satisfaction_score": {"type": "integer"},
                "semantic_content": {
                    "type": "semantic_text",
                    "inference_id": ELSER_ENDPOINT
                }
            }
        }
    }
    
    if use_jina:
        mapping["mappings"]["properties"]["semantic_jina"] = {
            "type": "semantic_text",
            "inference_id": JINA_ENDPOINT
        }
    
    return mapping


def get_stores_mapping(use_jina: bool = True) -> Dict[str, Any]:
    """Get mapping for stores index with geo_point."""
    mapping = {
        "mappings": {
            "properties": {
                "id": {"type": "keyword"},
                "name": {
                    "type": "text",
                    "copy_to": "semantic_content"
                },
                "type": {"type": "keyword"},
                "location": {"type": "geo_point"},
                "delivery_zone": {"type": "geo_shape"},
                "address": {"type": "text"},
                "city": {"type": "keyword"},
                "state": {"type": "keyword"},
                "zip_code": {"type": "keyword"},
                "phone": {"type": "keyword"},
                "features": {"type": "keyword"},
                "services": {"type": "keyword"},
                "hours": {"type": "object"},
                "rating": {"type": "float"},
                "review_count": {"type": "integer"},
                "is_open_now": {"type": "boolean"},
                "semantic_content": {
                    "type": "semantic_text",
                    "inference_id": ELSER_ENDPOINT
                }
            }
        }
    }
    
    if use_jina:
        mapping["mappings"]["properties"]["semantic_jina"] = {
            "type": "semantic_text",
            "inference_id": JINA_ENDPOINT
        }
    
    return mapping


MAPPINGS = {
    'products': get_products_mapping,
    'knowledge': get_knowledge_mapping,
    'support': get_support_mapping,
    'stores': get_stores_mapping
}


# =============================================================================
# Loader Functions
# =============================================================================

def check_eis_availability(es: Elasticsearch) -> Dict[str, bool]:
    """Check which EIS endpoints are available."""
    print("\n🔍 Checking EIS endpoint availability...")
    result = {"elser": False, "jina": False}
    
    # Check ELSER
    try:
        es.inference.inference(
            inference_id=ELSER_ENDPOINT,
            input=["test"],
            task_type="sparse_embedding"
        )
        result["elser"] = True
        print(f"  ✓ {ELSER_ENDPOINT} available (ELSER sparse embeddings)")
    except Exception as e:
        print(f"  ✗ {ELSER_ENDPOINT} not available: {e}")
    
    # Check jina
    try:
        es.inference.inference(
            inference_id=JINA_ENDPOINT,
            input=["test"],
            task_type="text_embedding"
        )
        result["jina"] = True
        print(f"  ✓ {JINA_ENDPOINT} available (1024-dim dense vectors)")
    except Exception as e:
        print(f"  ✗ {JINA_ENDPOINT} not available: {e}")
    
    return result


def create_index(
    es: Elasticsearch,
    index_name: str,
    mapping: Dict[str, Any],
    recreate: bool = False
) -> bool:
    """Create an index with the given mapping."""
    if es.indices.exists(index=index_name):
        if recreate:
            print(f"  Deleting existing index '{index_name}'...")
            es.indices.delete(index=index_name)
        else:
            print(f"  Index '{index_name}' already exists, skipping creation")
            return True
    
    print(f"  Creating index '{index_name}'...")
    try:
        es.indices.create(index=index_name, body=mapping)
        print(f"  ✓ Index '{index_name}' created")
        return True
    except Exception as e:
        print(f"  ✗ Failed to create index '{index_name}': {e}")
        return False


def prepare_document(doc: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
    """Prepare a document for indexing (add semantic field copies if needed)."""
    # For jina, we need to copy content to the semantic_jina field
    if config.get('use_jina'):
        semantic_fields = config.get('semantic_fields', [])
        content_parts = []
        for field in semantic_fields:
            if field in doc and doc[field]:
                content_parts.append(str(doc[field]))
        if content_parts:
            doc['semantic_jina'] = ' '.join(content_parts)
    
    return doc


def load_dataset(
    es: Elasticsearch,
    dataset_key: str,
    count: int,
    recreate: bool = False,
    eis_status: Dict[str, bool] = None
) -> int:
    """Load a single dataset."""
    config = INDEX_CONFIGS[dataset_key]
    index_name = config['name']
    
    print(f"\n📦 Loading {dataset_key} ({count} records)...")
    print(f"   Index: {index_name}")
    print(f"   Description: {config['description']}")
    
    # Adjust config based on EIS availability
    use_jina = config.get('use_jina', False) and (eis_status or {}).get('jina', False)
    
    # Get mapping - all mappings now support use_jina parameter
    mapping_fn = MAPPINGS[dataset_key]
    mapping = mapping_fn(use_jina=use_jina)
    
    # Create index
    if not create_index(es, index_name, mapping, recreate):
        return 0
    
    # Generate and index data
    generator_class = config['generator']
    generator_config = config.get('generator_config', {})
    generator = generator_class(generator_config)
    
    print(f"  Generating and indexing {count} documents...")
    
    chunk_size = 50
    
    def generate_actions():
        for i, doc in enumerate(generator.generate(count)):
            doc = prepare_document(doc, {**config, 'use_jina': use_jina})
            yield {
                "_index": index_name,
                "_id": doc.get('id'),
                "_source": doc
            }
            if (i + 1) % chunk_size == 0:
                print(f"    Generated {i + 1}/{count}...")
    
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
            print(f"    First error: {errors[0]}")
        
        return success
    except Exception as e:
        print(f"  ✗ Bulk indexing failed: {e}")
        return 0


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Load OOTB demo data into Serverless Elasticsearch',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Load all datasets
    python -m scripts.load_serverless_ootb
    
    # Load specific datasets
    python -m scripts.load_serverless_ootb --datasets products knowledge
    
    # Custom counts
    python -m scripts.load_serverless_ootb --products 500 --support 200
    
    # Recreate indices (delete if exists)
    python -m scripts.load_serverless_ootb --recreate
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
    
    # Dataset selection
    parser.add_argument(
        '--datasets',
        type=str,
        nargs='+',
        choices=list(INDEX_CONFIGS.keys()),
        default=list(INDEX_CONFIGS.keys()),
        help='Datasets to load (default: all)'
    )
    
    # Count overrides
    parser.add_argument('--products', type=int, help='Number of products')
    parser.add_argument('--knowledge', type=int, help='Number of knowledge articles')
    parser.add_argument('--support', type=int, help='Number of support tickets')
    parser.add_argument('--stores', type=int, help='Number of stores')
    
    # Options
    parser.add_argument(
        '--recreate',
        action='store_true',
        help='Delete and recreate indices if they exist'
    )
    parser.add_argument(
        '--skip-eis-check',
        action='store_true',
        help='Skip EIS availability check'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be done without making changes'
    )
    
    args = parser.parse_args()
    
    # Validate connection
    if not args.es_url or not args.api_key:
        print("❌ Error: Elasticsearch URL and API key required")
        print("   Set ELASTICSEARCH_URL and ELASTIC_API_KEY environment variables")
        print("   Or use --es-url and --api-key arguments")
        sys.exit(1)
    
    print("=" * 60)
    print("🚀 Serverless OOTB Data Loader")
    print("=" * 60)
    print(f"\nElasticsearch: {args.es_url}")
    print(f"Datasets: {', '.join(args.datasets)}")
    
    if args.dry_run:
        print("\n⚠️  DRY RUN - No changes will be made")
        for dataset in args.datasets:
            config = INDEX_CONFIGS[dataset]
            count = getattr(args, dataset, None) or config['default_count']
            print(f"\n  {dataset}:")
            print(f"    Index: {config['name']}")
            print(f"    Count: {count}")
            print(f"    Semantic: ELSER" + (" + jina" if config.get('use_jina') else ""))
        sys.exit(0)
    
    # Connect to Elasticsearch
    print("\n🔌 Connecting to Elasticsearch...")
    try:
        es = Elasticsearch(args.es_url, api_key=args.api_key)
        info = es.info()
        print(f"  ✓ Connected to cluster: {info['cluster_name']}")
        print(f"    Version: {info['version']['number']}")
    except Exception as e:
        print(f"  ✗ Connection failed: {e}")
        sys.exit(1)
    
    # Check EIS availability
    eis_status = {"elser": True, "jina": True}
    if not args.skip_eis_check:
        eis_status = check_eis_availability(es)
        
        if not eis_status["elser"]:
            print("\n❌ ELSER EIS endpoint not available. Cannot proceed.")
            print("   Ensure you're using a Serverless project with EIS enabled.")
            sys.exit(1)
    
    # Load datasets
    total_docs = 0
    for dataset in args.datasets:
        config = INDEX_CONFIGS[dataset]
        count = getattr(args, dataset, None) or config['default_count']
        
        docs = load_dataset(
            es,
            dataset,
            count,
            recreate=args.recreate,
            eis_status=eis_status
        )
        total_docs += docs
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 Summary")
    print("=" * 60)
    print(f"\nTotal documents indexed: {total_docs}")
    print("\nIndices created:")
    for dataset in args.datasets:
        config = INDEX_CONFIGS[dataset]
        print(f"  - {config['name']}")
    
    print("\n✅ Data loading complete!")
    print("\nNext steps:")
    print("  1. Create agents and tools via the backend proxy (POST /api/agent/agents, /api/agent/tools)")
    print("     See: hive-mind/patterns/agent-builder/AGENT_BUILDER_API_MANAGEMENT.md")
    print("  2. Set AGENT_ID in backend/.env")
    print("  3. Run ./dev start to launch the demo")


if __name__ == '__main__':
    main()
