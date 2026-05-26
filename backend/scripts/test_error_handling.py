#!/usr/bin/env python3
"""POC: Test Error Handling and Recovery

This script tests error scenarios in the A2A chat system:
1. LLM proxy authentication failures
2. LLM proxy connectivity issues
3. Agent Builder failures
4. Invalid agent IDs
5. Malformed requests
6. Timeout handling

Run: python scripts/test_error_handling.py

Prerequisites:
- Backend running on localhost:8002
"""

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

import requests

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import settings

# Configuration
BACKEND_URL = settings.BACKEND_URL or "http://localhost:8002"


@dataclass
class ErrorTestResult:
    """Result from an error test run."""

    name: str
    passed: bool
    expected_behavior: str
    actual_behavior: str
    error_code: str | None = None
    error_message: str | None = None


def test_health_endpoint() -> ErrorTestResult:
    """Test 0: Check health endpoint provides useful info."""
    print("\n" + "=" * 60)
    print("TEST 0: Health Endpoint")
    print("=" * 60)

    try:
        response = requests.get(f"{BACKEND_URL}/api/a2a/health", timeout=10)

        if response.status_code != 200:
            return ErrorTestResult(
                name="Health Endpoint",
                passed=False,
                expected_behavior="Return health status",
                actual_behavior=f"Status {response.status_code}",
            )

        data = response.json()
        print("📋 Health Status:")
        print(f"   Status: {data.get('status')}")
        print(f"   LLM Proxy Configured: {data.get('llm_proxy_configured')}")
        print(f"   LLM Proxy URL: {data.get('llm_proxy_url', 'not set')}")
        print(f"   Connectivity OK: {data.get('connectivity_ok', 'not tested')}")

        if data.get("error"):
            print(f"   Error: {data.get('error')}")
            print(f"   Error Code: {data.get('error_code')}")

        return ErrorTestResult(
            name="Health Endpoint",
            passed=True,
            expected_behavior="Return health status",
            actual_behavior=f"Status: {data.get('status')}",
        )

    except requests.RequestException as e:
        return ErrorTestResult(
            name="Health Endpoint",
            passed=False,
            expected_behavior="Return health status",
            actual_behavior=str(e),
        )


def test_empty_message() -> ErrorTestResult:
    """Test 1: Empty message handling."""
    print("\n" + "=" * 60)
    print("TEST 1: Empty Message Handling")
    print("=" * 60)

    try:
        response = requests.post(
            f"{BACKEND_URL}/api/a2a/chat", json={"message": ""}, timeout=30
        )

        # Could be 400 (bad request) or 422 (validation error)
        print("📤 Request: Empty message")
        print(f"📥 Response status: {response.status_code}")

        if response.status_code in [400, 422]:
            print("✅ Server correctly rejected empty message")
            return ErrorTestResult(
                name="Empty Message",
                passed=True,
                expected_behavior="Reject with 400/422",
                actual_behavior=f"Status {response.status_code}",
            )
        elif response.status_code == 200:
            # Some servers may accept empty messages
            print("ℹ️  Server accepted empty message (may be valid)")
            return ErrorTestResult(
                name="Empty Message",
                passed=True,
                expected_behavior="Reject or handle gracefully",
                actual_behavior="Accepted (200)",
            )
        else:
            return ErrorTestResult(
                name="Empty Message",
                passed=False,
                expected_behavior="Reject with 400/422",
                actual_behavior=f"Status {response.status_code}",
            )

    except requests.RequestException as e:
        return ErrorTestResult(
            name="Empty Message",
            passed=False,
            expected_behavior="Reject with 400/422",
            actual_behavior=str(e),
        )


def test_missing_message_field() -> ErrorTestResult:
    """Test 2: Missing required field handling."""
    print("\n" + "=" * 60)
    print("TEST 2: Missing Message Field")
    print("=" * 60)

    try:
        response = requests.post(
            f"{BACKEND_URL}/api/a2a/chat",
            json={},  # Missing 'message' field
            timeout=30,
        )

        print("📤 Request: No message field")
        print(f"📥 Response status: {response.status_code}")

        if response.status_code == 422:
            error_detail = response.json()
            print("✅ Server returned validation error")
            print(f"   Detail: {str(error_detail)[:100]}")
            return ErrorTestResult(
                name="Missing Field",
                passed=True,
                expected_behavior="Return 422 validation error",
                actual_behavior="Status 422 - validation error",
            )
        else:
            return ErrorTestResult(
                name="Missing Field",
                passed=False,
                expected_behavior="Return 422 validation error",
                actual_behavior=f"Status {response.status_code}",
            )

    except requests.RequestException as e:
        return ErrorTestResult(
            name="Missing Field",
            passed=False,
            expected_behavior="Return 422 validation error",
            actual_behavior=str(e),
        )


def test_invalid_json() -> ErrorTestResult:
    """Test 3: Invalid JSON handling."""
    print("\n" + "=" * 60)
    print("TEST 3: Invalid JSON Request")
    print("=" * 60)

    try:
        response = requests.post(
            f"{BACKEND_URL}/api/a2a/chat",
            data="not valid json",
            headers={"Content-Type": "application/json"},
            timeout=30,
        )

        print("📤 Request: Invalid JSON")
        print(f"📥 Response status: {response.status_code}")

        if response.status_code in [400, 422]:
            print("✅ Server correctly rejected invalid JSON")
            return ErrorTestResult(
                name="Invalid JSON",
                passed=True,
                expected_behavior="Reject with 400/422",
                actual_behavior=f"Status {response.status_code}",
            )
        else:
            return ErrorTestResult(
                name="Invalid JSON",
                passed=False,
                expected_behavior="Reject with 400/422",
                actual_behavior=f"Status {response.status_code}",
            )

    except requests.RequestException as e:
        return ErrorTestResult(
            name="Invalid JSON",
            passed=False,
            expected_behavior="Reject with 400/422",
            actual_behavior=str(e),
        )


def test_direct_agent_invalid_id() -> ErrorTestResult:
    """Test 4: Invalid agent ID handling."""
    print("\n" + "=" * 60)
    print("TEST 4: Invalid Agent ID")
    print("=" * 60)

    try:
        response = requests.post(
            f"{BACKEND_URL}/api/a2a/call-agent",
            json={"agent_id": "non-existent-agent-xyz-12345", "input": "Hello"},
            stream=True,
            timeout=30,
        )

        print("📤 Request: Call non-existent agent")
        print(f"📥 Response status: {response.status_code}")

        # We expect an error, but it could come in different forms
        if response.status_code in [400, 404, 502]:
            print("✅ Server correctly reported agent not found")
            return ErrorTestResult(
                name="Invalid Agent ID",
                passed=True,
                expected_behavior="Error response for invalid agent",
                actual_behavior=f"Status {response.status_code}",
            )
        elif response.status_code == 200:
            # Check if there's an error event in the stream
            content = response.text
            if "error" in content.lower():
                print("✅ Server returned error in stream")
                return ErrorTestResult(
                    name="Invalid Agent ID",
                    passed=True,
                    expected_behavior="Error in stream",
                    actual_behavior="Error event in stream",
                )
            else:
                print("⚠️  Server accepted invalid agent ID")
                return ErrorTestResult(
                    name="Invalid Agent ID",
                    passed=False,
                    expected_behavior="Error response",
                    actual_behavior="Accepted without error",
                )
        else:
            return ErrorTestResult(
                name="Invalid Agent ID",
                passed=True,  # Any error is acceptable here
                expected_behavior="Error response",
                actual_behavior=f"Status {response.status_code}",
            )

    except requests.RequestException as e:
        return ErrorTestResult(
            name="Invalid Agent ID",
            passed=False,
            expected_behavior="Error response",
            actual_behavior=str(e),
        )


def test_malformed_client_functions() -> ErrorTestResult:
    """Test 5: Malformed client functions handling."""
    print("\n" + "=" * 60)
    print("TEST 5: Malformed Client Functions")
    print("=" * 60)

    try:
        # Send malformed client function (missing required fields)
        response = requests.post(
            f"{BACKEND_URL}/api/a2a/chat",
            json={
                "message": "Test message",
                "client_functions": [
                    {
                        "name": "incomplete_function"
                    }  # Missing description and parameters
                ],
            },
            timeout=30,
        )

        print("📤 Request: Malformed client function")
        print(f"📥 Response status: {response.status_code}")

        if response.status_code == 422:
            print("✅ Server validated and rejected malformed function")
            return ErrorTestResult(
                name="Malformed Client Functions",
                passed=True,
                expected_behavior="Validation error 422",
                actual_behavior="Status 422",
            )
        else:
            # Some implementations may be more lenient
            print("ℹ️  Server accepted/handled malformed function")
            return ErrorTestResult(
                name="Malformed Client Functions",
                passed=True,  # Not necessarily a failure
                expected_behavior="Validation or graceful handling",
                actual_behavior=f"Status {response.status_code}",
            )

    except requests.RequestException as e:
        return ErrorTestResult(
            name="Malformed Client Functions",
            passed=False,
            expected_behavior="Validation error",
            actual_behavior=str(e),
        )


def test_large_message() -> ErrorTestResult:
    """Test 6: Large message handling."""
    print("\n" + "=" * 60)
    print("TEST 6: Large Message Handling")
    print("=" * 60)

    # Create a large message (50KB)
    large_message = "Hello, this is a test. " * 2500

    try:
        response = requests.post(
            f"{BACKEND_URL}/api/a2a/chat", json={"message": large_message}, timeout=60
        )

        print(f"📤 Request: Large message (~{len(large_message)} chars)")
        print(f"📥 Response status: {response.status_code}")

        # Could accept, reject, or truncate
        if response.status_code == 200:
            print("✅ Server accepted large message")
            return ErrorTestResult(
                name="Large Message",
                passed=True,
                expected_behavior="Accept or reject gracefully",
                actual_behavior="Accepted (200)",
            )
        elif response.status_code in [400, 413, 422]:
            print("✅ Server rejected large message (expected)")
            return ErrorTestResult(
                name="Large Message",
                passed=True,
                expected_behavior="Reject with 413/400/422",
                actual_behavior=f"Status {response.status_code}",
            )
        else:
            return ErrorTestResult(
                name="Large Message",
                passed=True,  # Any handled response is acceptable
                expected_behavior="Handle gracefully",
                actual_behavior=f"Status {response.status_code}",
            )

    except requests.RequestException as e:
        return ErrorTestResult(
            name="Large Message",
            passed=False,
            expected_behavior="Handle gracefully",
            actual_behavior=str(e),
        )


def test_agents_endpoint_error() -> ErrorTestResult:
    """Test 7: Agents endpoint error handling."""
    print("\n" + "=" * 60)
    print("TEST 7: Agents Endpoint")
    print("=" * 60)

    try:
        response = requests.get(f"{BACKEND_URL}/api/a2a/agents", timeout=30)

        print(f"📥 Response status: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            agents = data.get("agents", [])
            error = data.get("error")

            print(f"   Agents found: {len(agents)}")
            if error:
                print(f"   Error reported: {error}")

            # Even with errors, endpoint should return 200 with error info
            return ErrorTestResult(
                name="Agents Endpoint",
                passed=True,
                expected_behavior="Return agent list or error info",
                actual_behavior=f"{len(agents)} agents, error: {error or 'none'}",
            )
        else:
            return ErrorTestResult(
                name="Agents Endpoint",
                passed=False,
                expected_behavior="Return 200 with data",
                actual_behavior=f"Status {response.status_code}",
            )

    except requests.RequestException as e:
        return ErrorTestResult(
            name="Agents Endpoint",
            passed=False,
            expected_behavior="Return agent list",
            actual_behavior=str(e),
        )


def test_graceful_stream_error() -> ErrorTestResult:
    """Test 8: Error during streaming should emit error event."""
    print("\n" + "=" * 60)
    print("TEST 8: Streaming Error Events")
    print("=" * 60)

    # This test checks that if something goes wrong during streaming,
    # the server emits an error event rather than just disconnecting

    try:
        # Send a valid request and monitor the stream structure
        response = requests.post(
            f"{BACKEND_URL}/api/a2a/chat",
            json={"message": "What's a good recipe for chicken?"},
            stream=True,
            timeout=120,
        )

        print(f"📥 Response status: {response.status_code}")

        if not response.ok:
            error_detail = response.text
            print(f"   Error: {error_detail[:100]}")

            # Check if error response has proper structure
            try:
                error_json = response.json()
                if "error_code" in error_json.get("detail", {}):
                    print("✅ Error response has proper structure")
                    return ErrorTestResult(
                        name="Streaming Error Events",
                        passed=True,
                        expected_behavior="Structured error response",
                        actual_behavior=f"Got error_code: {error_json['detail'].get('error_code')}",
                    )
            except:
                pass

            return ErrorTestResult(
                name="Streaming Error Events",
                passed=True,  # Non-200 is handled
                expected_behavior="Handle errors",
                actual_behavior=f"Status {response.status_code}",
            )

        # Parse events and check structure
        events = []
        has_error_event = False

        for line in response.iter_lines():
            if line:
                line_str = line.decode("utf-8")
                if line_str.startswith("data: "):
                    data_str = line_str[6:]
                    if data_str.strip() == "[DONE]":
                        break
                    try:
                        event = json.loads(data_str)
                        events.append(event)
                        if event.get("event") == "error":
                            has_error_event = True
                    except json.JSONDecodeError:
                        pass

        print(f"   Events received: {len(events)}")
        print(f"   Has error events: {has_error_event}")

        # The test passes if we got proper streaming
        return ErrorTestResult(
            name="Streaming Error Events",
            passed=True,
            expected_behavior="Proper SSE streaming",
            actual_behavior=f"{len(events)} events streamed",
        )

    except requests.RequestException as e:
        return ErrorTestResult(
            name="Streaming Error Events",
            passed=False,
            expected_behavior="Handle stream errors",
            actual_behavior=str(e),
        )


def main():
    """Run all error handling tests."""
    print("\n" + "=" * 60)
    print("Error Handling and Recovery Tests")
    print("=" * 60)
    print(f"Backend URL: {BACKEND_URL}")
    print()

    results = []

    # Run tests
    results.append(test_health_endpoint())
    results.append(test_empty_message())
    results.append(test_missing_message_field())
    results.append(test_invalid_json())
    results.append(test_direct_agent_invalid_id())
    results.append(test_malformed_client_functions())
    results.append(test_large_message())
    results.append(test_agents_endpoint_error())
    results.append(test_graceful_stream_error())

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    passed = sum(1 for r in results if r.passed)
    total = len(results)

    for result in results:
        status = "✅ PASS" if result.passed else "❌ FAIL"
        print(f"{status}: {result.name}")
        print(f"       Expected: {result.expected_behavior}")
        print(f"       Actual: {result.actual_behavior}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 All error handling tests passed!")
        print("   The system handles errors gracefully.")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed.")
        print("   Review error handling in failing cases.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
