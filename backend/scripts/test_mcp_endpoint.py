#!/usr/bin/env python3
"""Test script for Elastic Agent Builder MCP Server endpoint.

This script tests connectivity and functionality of the MCP server using
proper JSON-RPC 2.0 protocol (which MCP is based on).

Usage:
    python backend/scripts/test_mcp_endpoint.py

Requirements:
    - KIBANA_URL and ELASTIC_API_KEY in backend/.env
    - Kibana version 9.2.0 or higher

References:
    - https://www.elastic.co/docs/solutions/search/agent-builder/mcp-server
    - https://modelcontextprotocol.io/specification
"""

import json
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import settings

KIBANA_URL = settings.KIBANA_URL
ELASTIC_API_KEY = settings.ELASTIC_API_KEY


def mcp_request(method: str, params: dict = None, request_id: int = 1) -> dict:
    """Send a JSON-RPC 2.0 request to the MCP server."""
    mcp_url = f"{KIBANA_URL}/api/agent_builder/mcp"

    headers = {
        "Authorization": f"ApiKey {ELASTIC_API_KEY}",
        "kbn-xsrf": "true",
        "Content-Type": "application/json",
        "Accept": "application/json",  # CRITICAL: MCP requires this header
    }

    payload = {
        "jsonrpc": "2.0",
        "method": method,
        "id": request_id,
        "params": params or {},
    }

    response = requests.post(mcp_url, headers=headers, json=payload, timeout=30)
    return response.json()


def test_mcp_endpoint():
    """Test the MCP server endpoint with proper JSON-RPC protocol."""
    print("=" * 60)
    print("Elastic Agent Builder MCP Server Test")
    print("=" * 60)
    print()

    if not KIBANA_URL or not ELASTIC_API_KEY:
        print("❌ ERROR: Missing KIBANA_URL or ELASTIC_API_KEY in .env")
        sys.exit(1)

    print(f"Kibana URL: {KIBANA_URL}")
    print(f"MCP URL: {KIBANA_URL}/api/agent_builder/mcp")
    print()

    # Test 1: MCP Initialize
    print("1. Testing MCP Initialize...")
    try:
        result = mcp_request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "mcp-test-script", "version": "1.0.0"},
            },
        )

        if "result" in result:
            server_info = result["result"].get("serverInfo", {})
            print("   ✅ MCP Server connected!")
            print(f"      Server: {server_info.get('name', 'unknown')}")
            print(f"      Version: {server_info.get('version', 'unknown')}")
            print(
                f"      Protocol: {result['result'].get('protocolVersion', 'unknown')}"
            )
        elif "error" in result:
            print(f"   ❌ MCP Error: {result['error'].get('message', 'Unknown error')}")
            return
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            print("   ❌ MCP endpoint returned 404 - feature may not be enabled")
        else:
            print(f"   ❌ HTTP Error: {e}")
        return
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return
    print()

    # Test 2: List Tools
    print("2. Listing available tools...")
    try:
        result = mcp_request("tools/list", {}, request_id=2)

        if "result" in result:
            tools = result["result"].get("tools", [])
            print(f"   ✅ Found {len(tools)} tools:")

            # Categorize tools
            builtin_tools = [t for t in tools if t["name"].startswith("platform_")]
            custom_tools = [t for t in tools if not t["name"].startswith("platform_")]

            print(f"\n   Built-in tools ({len(builtin_tools)}):")
            for tool in builtin_tools:
                print(f"      • {tool['name']}")

            print(f"\n   Custom tools ({len(custom_tools)}):")
            for tool in custom_tools:
                desc = tool.get("description", "")
                print(
                    f"      • {tool['name']}: {desc[:60]}{'...' if len(desc) > 60 else ''}"
                )
        elif "error" in result:
            print(f"   ❌ Error: {result['error'].get('message', 'Unknown error')}")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    print()

    # Test 3: Call a tool
    print("3. Testing tool execution (search-recipes-flexible)...")
    try:
        result = mcp_request(
            "tools/call",
            {
                "name": "search-recipes-flexible",
                "arguments": {"nlQuery": "quick pasta dinner"},
            },
            request_id=3,
        )

        if "result" in result:
            content = result["result"].get("content", [])
            if content:
                # Parse the nested JSON response
                text_content = content[0].get("text", "{}")
                parsed = json.loads(text_content)
                results = parsed.get("results", [])
                print("   ✅ Tool executed successfully!")
                print(f"      Returned {len(results)} results")

                # Show first result preview
                if results:
                    first = results[0]
                    if "data" in first and "content" in first["data"]:
                        highlights = first["data"]["content"].get("highlights", [])
                        if highlights:
                            # Clean HTML tags for preview
                            preview = (
                                highlights[0]
                                .replace("<em>", "")
                                .replace("</em>", "")[:80]
                            )
                            print(f"      Preview: {preview}...")
        elif "error" in result:
            print(f"   ❌ Error: {result['error'].get('message', 'Unknown error')}")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    print()

    # Test 4: List indices
    print("4. Testing list_indices tool...")
    try:
        result = mcp_request(
            "tools/call",
            {"name": "platform_core_list_indices", "arguments": {}},
            request_id=4,
        )

        if "result" in result:
            content = result["result"].get("content", [])
            if content:
                text_content = content[0].get("text", "{}")
                parsed = json.loads(text_content)
                results = parsed.get("results", [])
                if results and "data" in results[0]:
                    indices = results[0]["data"].get("indices", [])
                    print(f"   ✅ Found {len(indices)} indices:")
                    for idx in indices:
                        print(f"      • {idx.get('name', 'unknown')}")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    print()

    print("=" * 60)
    print("MCP Server Test Complete!")
    print("=" * 60)
    print()
    print("📝 To use MCP with Cursor IDE, add to ~/.cursor/mcp.json:")
    print(
        """
{
  "mcpServers": {
    "elastic-agent-builder": {
      "command": "npx",
      "args": [
        "mcp-remote",
        "%s/api/agent_builder/mcp",
        "--header",
        "Authorization:ApiKey YOUR_API_KEY"
      ]
    }
  }
}
"""
        % KIBANA_URL
    )


if __name__ == "__main__":
    test_mcp_endpoint()
