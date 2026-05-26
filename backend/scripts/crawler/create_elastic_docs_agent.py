#!/usr/bin/env python3
"""
Create an Agent Builder agent that references the indexed Elastic documentation.

This script creates an agent in Kibana Agent Builder that can answer questions
about Elastic products, features, and best practices using the crawled documentation.

Usage:
    python -m scripts.crawler.create_elastic_docs_agent \\
        --index-name ootb-elastic-docs \\
        --agent-id ootb-elastic-docs-assistant

Environment Variables:
    KIBANA_URL: Kibana endpoint URL
    ELASTIC_API_KEY: API key for authentication
"""

import argparse
import json
import os
import sys
from typing import Dict, Any

import requests

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.config import settings


def create_index_search_tool(
    kibana_url: str,
    api_key: str,
    tool_id: str,
    index_pattern: str,
    description: str
) -> Dict[str, Any]:
    """
    Create an index_search tool for the agent.
    
    Returns the created tool configuration.
    """
    url = f"{kibana_url}/api/agent_builder/tools"
    
    payload = {
        "id": tool_id,
        "type": "index_search",
        "description": description,
        "tags": ["elastic-docs", "documentation"],
        "configuration": {
            "pattern": index_pattern
        }
    }
    
    headers = {
        "Authorization": f"ApiKey {api_key}",
        "kbn-xsrf": "true",
        "Content-Type": "application/json"
    }
    
    print(f"🔧 Creating index search tool: {tool_id}")
    print(f"   Pattern: {index_pattern}")
    
    response = requests.post(url, json=payload, headers=headers)
    
    if response.status_code == 201:
        print(f"   ✓ Tool created successfully")
        return response.json()
    elif response.status_code == 409:
        print(f"   ℹ️  Tool already exists, using existing tool")
        # Try to get existing tool
        get_url = f"{kibana_url}/api/agent_builder/tools/{tool_id}"
        get_response = requests.get(get_url, headers=headers)
        if get_response.status_code == 200:
            return get_response.json()
        else:
            raise Exception(f"Tool exists but could not retrieve: {get_response.status_code}")
    else:
        error_msg = response.text
        raise Exception(f"Failed to create tool: {response.status_code} - {error_msg}")


def create_agent(
    kibana_url: str,
    api_key: str,
    agent_id: str,
    agent_name: str,
    description: str,
    instructions: str,
    tool_ids: list[str]
) -> Dict[str, Any]:
    """Create an Agent Builder agent."""
    url = f"{kibana_url}/api/agent_builder/agents"
    
    payload = {
        "id": agent_id,
        "name": agent_name,
        "description": description,
        "labels": ["elastic-docs", "documentation", "serverless"],
        "avatar_color": "#006BB4",  # Elastic blue
        "avatar_symbol": "ED",  # Elastic Docs
        "configuration": {
            "instructions": instructions,
            "tools": [
                {
                    "tool_ids": tool_ids
                }
            ]
        }
    }
    
    headers = {
        "Authorization": f"ApiKey {api_key}",
        "kbn-xsrf": "true",
        "Content-Type": "application/json"
    }
    
    print(f"\n🤖 Creating agent: {agent_id}")
    print(f"   Name: {agent_name}")
    
    response = requests.post(url, json=payload, headers=headers)
    
    if response.status_code == 201:
        print(f"   ✓ Agent created successfully")
        return response.json()
    elif response.status_code == 409:
        print(f"   ℹ️  Agent already exists")
        # Try to get existing agent
        get_url = f"{kibana_url}/api/agent_builder/agents/{agent_id}"
        get_response = requests.get(get_url, headers=headers)
        if get_response.status_code == 200:
            print(f"   ✓ Retrieved existing agent")
            return get_response.json()
        else:
            raise Exception(f"Agent exists but could not retrieve: {get_response.status_code}")
    else:
        error_msg = response.text
        raise Exception(f"Failed to create agent: {response.status_code} - {error_msg}")


def get_default_instructions() -> str:
    """Get default system instructions for Elastic documentation agent."""
    return """You are a helpful assistant that answers questions about Elastic products, features, and best practices using official Elastic documentation and blog posts.

Your knowledge comes from:
- Official Elastic documentation (Elasticsearch, Kibana, Observability, Security, Enterprise Search)
- Elastic blog posts and technical articles

Guidelines:
- Always cite sources when providing information
- If you're unsure about something, say so rather than guessing
- Focus on providing accurate, up-to-date information from the documentation
- When discussing features, mention which Elastic product they belong to
- For version-specific information, note the version if available

You can search the documentation using semantic search to find relevant information."""


def main():
    parser = argparse.ArgumentParser(
        description='Create Agent Builder agent for Elastic documentation',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Create agent with default settings
    python -m scripts.crawler.create_elastic_docs_agent \\
        --index-name ootb-elastic-docs \\
        --agent-id ootb-elastic-docs-assistant
    
    # Custom agent name and description
    python -m scripts.crawler.create_elastic_docs_agent \\
        --index-name ootb-elastic-docs \\
        --agent-id my-elastic-assistant \\
        --agent-name "My Elastic Assistant" \\
        --description "Custom description"
        """
    )
    
    # Connection arguments
    parser.add_argument(
        '--kibana-url',
        type=str,
        default=os.getenv('KIBANA_URL'),
        help='Kibana URL (or set KIBANA_URL env var)'
    )
    parser.add_argument(
        '--api-key',
        type=str,
        default=os.getenv('ELASTIC_API_KEY'),
        help='API key (or set ELASTIC_API_KEY env var)'
    )
    
    # Agent configuration
    parser.add_argument(
        '--index-name',
        type=str,
        default='ootb-elastic-docs',
        help='Elasticsearch index name (default: ootb-elastic-docs)'
    )
    parser.add_argument(
        '--agent-id',
        type=str,
        default='ootb-elastic-docs-assistant',
        help='Agent ID (default: ootb-elastic-docs-assistant)'
    )
    parser.add_argument(
        '--agent-name',
        type=str,
        help='Agent display name (default: "Elastic Documentation Assistant")'
    )
    parser.add_argument(
        '--description',
        type=str,
        help='Agent description (default: auto-generated)'
    )
    parser.add_argument(
        '--instructions',
        type=str,
        help='Custom system instructions (default: use built-in)'
    )
    parser.add_argument(
        '--tool-id',
        type=str,
        help='Custom tool ID (default: search-{index-name}-flexible)'
    )
    
    args = parser.parse_args()
    
    # Validate connection
    if not args.kibana_url or not args.api_key:
        parser.error("--kibana-url and --api-key are required (or set KIBANA_URL and ELASTIC_API_KEY)")
    
    # Set defaults
    agent_name = args.agent_name or "Elastic Documentation Assistant"
    description = args.description or (
        f"Answers questions about Elastic products and features using official documentation "
        f"indexed from elastic.co. Searches the {args.index_name} index for relevant information."
    )
    instructions = args.instructions or get_default_instructions()
    tool_id = args.tool_id or f"search-{args.index_name}-flexible"
    
    print("=" * 60)
    print("CREATING ELASTIC DOCUMENTATION AGENT")
    print("=" * 60)
    
    try:
        # Create index search tool
        tool = create_index_search_tool(
            kibana_url=args.kibana_url,
            api_key=args.api_key,
            tool_id=tool_id,
            index_pattern=args.index_name,
            description=f"Search Elastic documentation and blog posts from the {args.index_name} index using semantic search."
        )
        
        # Create agent
        agent = create_agent(
            kibana_url=args.kibana_url,
            api_key=args.api_key,
            agent_id=args.agent_id,
            agent_name=agent_name,
            description=description,
            instructions=instructions,
            tool_ids=[tool_id]
        )
        
        print("\n" + "=" * 60)
        print("✅ SUCCESS")
        print("=" * 60)
        print(f"\nAgent created successfully!")
        print(f"   Agent ID: {args.agent_id}")
        print(f"   Agent Name: {agent_name}")
        print(f"   Tool ID: {tool_id}")
        print(f"   Index: {args.index_name}")
        print(f"\nTo use this agent, set in your backend/.env:")
        print(f"   AGENT_ID={args.agent_id}")
        print(f"\nThen restart your backend: ./dev restart")
        
    except Exception as e:
        print(f"\n✗ Failed to create agent: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
