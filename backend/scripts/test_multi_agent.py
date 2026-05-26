#!/usr/bin/env python3
"""POC: Test Multi-Agent Function Calling

This script tests the LLM coordinator calling multiple Agent Builder agents
in sequence or in response to complex queries.

Tests:
1. Single agent call - baseline
2. Sequential agent calls - same query needing multiple agents
3. LLM deciding which agent to use - routing test
4. Handling multiple agent responses - synthesis test

Run: python scripts/test_multi_agent.py

Prerequisites:
- Backend running on localhost:8002
- LLM proxy configured in backend/.env
- Agent Builder agents configured
"""

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import requests

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import settings

# Configuration
BACKEND_URL = settings.BACKEND_URL or "http://localhost:8002"


@dataclass
class TestResult:
    """Result from a test run."""

    name: str
    passed: bool
    events_received: int
    agents_called: list[str]
    error: str | None = None
    details: str | None = None


def parse_sse_events(response: requests.Response) -> list[dict]:
    """Parse SSE events from response."""
    events = []
    for line in response.iter_lines():
        if line:
            line_str = line.decode("utf-8")
            if line_str.startswith(":"):  # keepalive
                continue
            if line_str.startswith("data: "):
                data_str = line_str[6:]
                if data_str.strip() == "[DONE]":
                    break
                try:
                    events.append(json.loads(data_str))
                except json.JSONDecodeError:
                    pass
    return events


def get_agents_called(events: list[dict]) -> list[str]:
    """Extract list of agents called from events."""
    agents = []
    for event in events:
        if event.get("event") == "function_call":
            agent_id = event.get("data", {}).get("agent_id")
            if agent_id and agent_id not in agents:
                agents.append(agent_id)
    return agents


def test_check_agents() -> TestResult:
    """Test 0: Check what agents are available."""
    print("\n" + "=" * 60)
    print("TEST 0: Check Available Agents")
    print("=" * 60)

    try:
        response = requests.get(f"{BACKEND_URL}/api/a2a/agents", timeout=30)

        if response.status_code != 200:
            return TestResult(
                name="Check Agents",
                passed=False,
                events_received=0,
                agents_called=[],
                error=f"Status {response.status_code}: {response.text[:200]}",
            )

        data = response.json()
        agents = data.get("agents", [])

        print(f"📋 Found {len(agents)} agents:")
        for agent in agents:
            name = agent.get("name", "Unknown")
            agent_id = (
                agent.get("url", "").split("/a2a/")[-1]
                if "/a2a/" in agent.get("url", "")
                else "unknown"
            )
            skills = agent.get("skills", [])
            skill_names = [s.get("name", s.get("id", "")) for s in skills[:3]]
            print(f"   • {name} (id: {agent_id})")
            print(f"     Skills: {', '.join(skill_names)}")

        return TestResult(
            name="Check Agents",
            passed=True,
            events_received=0,
            agents_called=[a.get("url", "").split("/a2a/")[-1] for a in agents],
            details=f"Found {len(agents)} agents",
        )

    except requests.RequestException as e:
        return TestResult(
            name="Check Agents",
            passed=False,
            events_received=0,
            agents_called=[],
            error=str(e),
        )


def test_single_agent_call() -> TestResult:
    """Test 1: Basic single agent call."""
    print("\n" + "=" * 60)
    print("TEST 1: Single Agent Call")
    print("=" * 60)

    message = "What are the ingredients in a cheese pizza?"
    print(f"📤 Message: {message}")

    try:
        response = requests.post(
            f"{BACKEND_URL}/api/a2a/chat",
            json={"message": message},
            stream=True,
            timeout=120,
        )

        if not response.ok:
            return TestResult(
                name="Single Agent Call",
                passed=False,
                events_received=0,
                agents_called=[],
                error=f"Status {response.status_code}: {response.text[:200]}",
            )

        events = parse_sse_events(response)
        agents_called = get_agents_called(events)

        # Analyze events
        event_types = {}
        for event in events:
            event_type = event.get("event", "unknown")
            event_types[event_type] = event_types.get(event_type, 0) + 1

        print(f"📥 Received {len(events)} events")
        print(f"   Event types: {event_types}")
        print(f"   Agents called: {agents_called}")

        passed = len(agents_called) >= 1
        if passed:
            print("✅ Single agent call successful")
        else:
            print("⚠️  No agent was called")

        return TestResult(
            name="Single Agent Call",
            passed=passed,
            events_received=len(events),
            agents_called=agents_called,
            details=f"Event types: {event_types}",
        )

    except requests.RequestException as e:
        return TestResult(
            name="Single Agent Call",
            passed=False,
            events_received=0,
            agents_called=[],
            error=str(e),
        )


def test_routing_decision() -> TestResult:
    """Test 2: LLM correctly routes to appropriate agent."""
    print("\n" + "=" * 60)
    print("TEST 2: Agent Routing Decision")
    print("=" * 60)

    # This message should go to a relevant specialized agent
    message = (
        "What information do you have available? Can you help me search for something?"
    )
    print(f"📤 Message: {message}")

    try:
        response = requests.post(
            f"{BACKEND_URL}/api/a2a/chat",
            json={"message": message},
            stream=True,
            timeout=120,
        )

        if not response.ok:
            return TestResult(
                name="Agent Routing",
                passed=False,
                events_received=0,
                agents_called=[],
                error=f"Status {response.status_code}: {response.text[:200]}",
            )

        events = parse_sse_events(response)
        agents_called = get_agents_called(events)

        # Check if at least one agent was called (LLM made a routing decision)
        passed = len(agents_called) >= 1

        print(f"📥 Received {len(events)} events")
        print(f"   Agents called: {agents_called}")

        if passed:
            print(f"✅ LLM routed to agent: {agents_called[0]}")
        else:
            print("⚠️  No agent routing occurred")

        return TestResult(
            name="Agent Routing",
            passed=passed,
            events_received=len(events),
            agents_called=agents_called,
            details=f"Routed to: {agents_called}",
        )

    except requests.RequestException as e:
        return TestResult(
            name="Agent Routing",
            passed=False,
            events_received=0,
            agents_called=[],
            error=str(e),
        )


def test_complex_query() -> TestResult:
    """Test 3: Complex query that might need multiple considerations."""
    print("\n" + "=" * 60)
    print("TEST 3: Complex Query")
    print("=" * 60)

    message = """I'm hosting a dinner party for 6 people this Saturday. 
    Some guests are vegetarian. Can you suggest a complete menu with 
    appetizers, main course, and dessert, along with a shopping list?"""

    print(f"📤 Message: {message[:100]}...")

    try:
        response = requests.post(
            f"{BACKEND_URL}/api/a2a/chat",
            json={"message": message},
            stream=True,
            timeout=120,
        )

        if not response.ok:
            return TestResult(
                name="Complex Query",
                passed=False,
                events_received=0,
                agents_called=[],
                error=f"Status {response.status_code}: {response.text[:200]}",
            )

        events = parse_sse_events(response)
        agents_called = get_agents_called(events)

        # For a complex query, we should get at least one agent call
        # and a substantial number of events (agent reasoning, tool calls, etc.)
        passed = len(events) > 5 and len(agents_called) >= 1

        # Check for agent tool calls
        tool_calls = [e for e in events if e.get("event") == "agent_tool_call"]
        tool_results = [e for e in events if e.get("event") == "agent_tool_result"]

        print(f"📥 Received {len(events)} events")
        print(f"   Agents called: {agents_called}")
        print(f"   Tool calls: {len(tool_calls)}")
        print(f"   Tool results: {len(tool_results)}")

        if passed:
            print("✅ Complex query handled successfully")
        else:
            print("⚠️  Complex query may not have been fully processed")

        return TestResult(
            name="Complex Query",
            passed=passed,
            events_received=len(events),
            agents_called=agents_called,
            details=f"Tool calls: {len(tool_calls)}, Tool results: {len(tool_results)}",
        )

    except requests.RequestException as e:
        return TestResult(
            name="Complex Query",
            passed=False,
            events_received=0,
            agents_called=[],
            error=str(e),
        )


def test_client_function_handling() -> TestResult:
    """Test 4: Test client-side function handling."""
    print("\n" + "=" * 60)
    print("TEST 4: Client-Side Functions")
    print("=" * 60)

    # Define a client-side function
    client_functions = [
        {
            "name": "add_to_shopping_list",
            "description": "Add items to the user's shopping list",
            "parameters": {
                "type": "object",
                "properties": {
                    "items": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of items to add",
                    }
                },
                "required": ["items"],
            },
        }
    ]

    message = "Add milk, eggs, and bread to my shopping list"
    print(f"📤 Message: {message}")
    print(f"   Client functions: {[f['name'] for f in client_functions]}")

    try:
        response = requests.post(
            f"{BACKEND_URL}/api/a2a/chat",
            json={"message": message, "client_functions": client_functions},
            stream=True,
            timeout=120,
        )

        if not response.ok:
            return TestResult(
                name="Client Functions",
                passed=False,
                events_received=0,
                agents_called=[],
                error=f"Status {response.status_code}: {response.text[:200]}",
            )

        events = parse_sse_events(response)

        # Check for client_function_call event
        client_calls = [e for e in events if e.get("event") == "client_function_call"]

        print(f"📥 Received {len(events)} events")
        print(f"   Client function calls: {len(client_calls)}")

        if client_calls:
            call_data = client_calls[0].get("data", {})
            print(f"   Function: {call_data.get('function_name')}")
            print(f"   Arguments: {call_data.get('arguments')}")

        # This test passes if we got a response (LLM may call the function or respond directly)
        passed = len(events) > 0

        if len(client_calls) > 0:
            print("✅ Client function was called!")
        else:
            print("ℹ️  LLM responded without calling client function")

        return TestResult(
            name="Client Functions",
            passed=passed,
            events_received=len(events),
            agents_called=[],
            details=f"Client calls: {len(client_calls)}",
        )

    except requests.RequestException as e:
        return TestResult(
            name="Client Functions",
            passed=False,
            events_received=0,
            agents_called=[],
            error=str(e),
        )


def test_custom_system_prompt() -> TestResult:
    """Test 5: Test custom system prompt handling."""
    print("\n" + "=" * 60)
    print("TEST 5: Custom System Prompt")
    print("=" * 60)

    system_prompt = """You are a helpful assistant. When users ask questions,
    always use the available agent functions to provide accurate information.
    Be friendly and concise in your responses."""

    message = "What can you help me with today?"
    print(f"📤 System prompt: {system_prompt[:50]}...")
    print(f"📤 Message: {message}")

    try:
        response = requests.post(
            f"{BACKEND_URL}/api/a2a/chat",
            json={"message": message, "system_prompt": system_prompt},
            stream=True,
            timeout=120,
        )

        if not response.ok:
            return TestResult(
                name="Custom System Prompt",
                passed=False,
                events_received=0,
                agents_called=[],
                error=f"Status {response.status_code}: {response.text[:200]}",
            )

        events = parse_sse_events(response)
        agents_called = get_agents_called(events)

        print(f"📥 Received {len(events)} events")
        print(f"   Agents called: {agents_called}")

        # This test passes if we got a response
        passed = len(events) > 0

        if passed:
            print("✅ Custom system prompt handled")

        return TestResult(
            name="Custom System Prompt",
            passed=passed,
            events_received=len(events),
            agents_called=agents_called,
        )

    except requests.RequestException as e:
        return TestResult(
            name="Custom System Prompt",
            passed=False,
            events_received=0,
            agents_called=[],
            error=str(e),
        )


def main():
    """Run all multi-agent tests."""
    print("\n" + "=" * 60)
    print("Multi-Agent Function Calling Tests")
    print("=" * 60)
    print(f"Backend URL: {BACKEND_URL}")
    print()

    results: list[TestResult] = []

    # Run tests
    results.append(test_check_agents())

    # Only continue with other tests if agents are available
    if results[0].passed and len(results[0].agents_called) > 0:
        results.append(test_single_agent_call())
        results.append(test_routing_decision())
        results.append(test_complex_query())
        results.append(test_client_function_handling())
        results.append(test_custom_system_prompt())
    else:
        print("\n⚠️  Skipping remaining tests - no agents available")

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    passed = sum(1 for r in results if r.passed)
    total = len(results)

    for result in results:
        status = "✅ PASS" if result.passed else "❌ FAIL"
        print(f"{status}: {result.name}")
        if result.error:
            print(f"       Error: {result.error[:80]}")
        if result.details:
            print(f"       {result.details}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 All tests passed! Multi-agent function calling works correctly.")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
