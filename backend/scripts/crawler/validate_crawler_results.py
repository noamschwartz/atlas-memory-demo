#!/usr/bin/env python3
"""
Validate crawled results before indexing.

This script checks crawled JSON files for:
- Required fields (URL, content)
- Data quality issues
- Extraction completeness

Usage:
    python -m scripts.crawler.validate_crawler_results \\
        --results-dir backend/scripts/crawler/results/elastic-docs
"""

import argparse
import json
from pathlib import Path
from typing import Dict, Any, List
from collections import defaultdict


def validate_document(doc: Dict[str, Any], index: int) -> List[str]:
    """Validate a single document and return list of errors."""
    errors = []
    url = doc.get("url", "")
    
    if not url:
        errors.append(f"Document {index}: Missing URL")
        return errors
    
    # Check for content
    has_doc_content = bool(
        doc.get("doc_title") or 
        doc.get("doc_summary") or 
        doc.get("doc_body")
    )
    
    has_blog_content = bool(
        doc.get("blog_title") or 
        doc.get("blog_summary") or 
        doc.get("blog_body")
    )
    
    if not (has_doc_content or has_blog_content):
        errors.append(f"Document {index} ({url}): No content fields found")
    
    # Check for very short content (might indicate extraction failure)
    if has_doc_content:
        title = doc.get("doc_title", "")
        body = doc.get("doc_body", "")
        if len(title) < 5 and len(body) < 100:
            errors.append(f"Document {index} ({url}): Very short content (possible extraction failure)")
    
    if has_blog_content:
        title = doc.get("blog_title", "")
        body = doc.get("blog_body", "")
        if len(title) < 5 and len(body) < 100:
            errors.append(f"Document {index} ({url}): Very short content (possible extraction failure)")
    
    return errors


def analyze_documents(documents: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Analyze document collection for statistics."""
    stats = {
        "total": len(documents),
        "docs": 0,
        "blogs": 0,
        "with_title": 0,
        "with_summary": 0,
        "with_body": 0,
        "with_author": 0,
        "with_categories": 0,
        "urls": set()
    }
    
    for doc in documents:
        url = doc.get("url", "")
        if url:
            stats["urls"].add(url)
        
        if "/blog/" in url:
            stats["blogs"] += 1
        else:
            stats["docs"] += 1
        
        if doc.get("doc_title") or doc.get("blog_title"):
            stats["with_title"] += 1
        if doc.get("doc_summary") or doc.get("blog_summary"):
            stats["with_summary"] += 1
        if doc.get("doc_body") or doc.get("blog_body"):
            stats["with_body"] += 1
        if doc.get("author"):
            stats["with_author"] += 1
        if doc.get("categories"):
            stats["with_categories"] += 1
    
    stats["unique_urls"] = len(stats["urls"])
    del stats["urls"]  # Remove set, not JSON serializable
    
    return stats


def main():
    parser = argparse.ArgumentParser(
        description='Validate crawled results',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        '--results-dir',
        type=str,
        required=True,
        help='Directory containing crawled JSON files'
    )
    parser.add_argument(
        '--output',
        type=str,
        help='Output JSON file for validation report'
    )
    
    args = parser.parse_args()
    
    results_dir = Path(args.results_dir)
    
    if not results_dir.exists():
        print(f"✗ Results directory not found: {results_dir}")
        return 1
    
    # Load all JSON files
    json_files = list(results_dir.glob("*.json"))
    if not json_files:
        print(f"✗ No JSON files found in {results_dir}")
        return 1
    
    print(f"📂 Found {len(json_files)} JSON files")
    
    documents = []
    for json_file in json_files:
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, list):
                    documents.extend(data)
                else:
                    documents.append(data)
        except json.JSONDecodeError as e:
            print(f"⚠️  Skipping invalid JSON file {json_file}: {e}")
            continue
    
    print(f"📄 Loaded {len(documents)} documents\n")
    
    # Validate
    all_errors = []
    for i, doc in enumerate(documents):
        errors = validate_document(doc, i)
        all_errors.extend(errors)
    
    # Analyze
    stats = analyze_documents(documents)
    
    # Report
    print("=" * 60)
    print("VALIDATION REPORT")
    print("=" * 60)
    
    print(f"\n📊 Statistics:")
    print(f"   Total documents: {stats['total']}")
    print(f"   Unique URLs: {stats['unique_urls']}")
    print(f"   Documentation pages: {stats['docs']}")
    print(f"   Blog posts: {stats['blogs']}")
    print(f"   With title: {stats['with_title']} ({stats['with_title']/stats['total']*100:.1f}%)")
    print(f"   With summary: {stats['with_summary']} ({stats['with_summary']/stats['total']*100:.1f}%)")
    print(f"   With body: {stats['with_body']} ({stats['with_body']/stats['total']*100:.1f}%)")
    print(f"   With author: {stats['with_author']} ({stats['with_author']/stats['total']*100:.1f}%)")
    print(f"   With categories: {stats['with_categories']} ({stats['with_categories']/stats['total']*100:.1f}%)")
    
    print(f"\n🔍 Validation Results:")
    if all_errors:
        print(f"   ⚠️  Found {len(all_errors)} errors:")
        for error in all_errors[:20]:  # Show first 20
            print(f"      - {error}")
        if len(all_errors) > 20:
            print(f"      ... and {len(all_errors) - 20} more")
    else:
        print(f"   ✓ No errors found!")
    
    valid_count = stats['total'] - len(all_errors)
    print(f"\n✅ {valid_count}/{stats['total']} documents are valid ({valid_count/stats['total']*100:.1f}%)")
    
    # Save report if requested
    if args.output:
        report = {
            "statistics": stats,
            "errors": all_errors,
            "valid_count": valid_count,
            "total_count": stats['total']
        }
        with open(args.output, 'w') as f:
            json.dump(report, f, indent=2)
        print(f"\n📄 Report saved to: {args.output}")
    
    return 0 if len(all_errors) == 0 else 1


if __name__ == "__main__":
    exit(main())
