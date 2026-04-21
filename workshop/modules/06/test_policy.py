#!/usr/bin/env python3
"""
Test AgentCore Policy Engine enforcement on the Electrify gateway.

Sends tool calls through the gateway and verifies that Cedar policies
are correctly allowing or denying requests.

Usage:
    uv run modules/06/test_policy.py \
        --gateway-url <url> \
        --token <jwt-token>
"""

import argparse
import json
import requests


def call_tool(gateway_url: str, token: str, tool_name: str, arguments: dict) -> dict:
    """Invoke a tool on the gateway and return the response."""
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": tool_name,
            "arguments": arguments,
        },
    }
    resp = requests.post(
        gateway_url,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
        json=payload,
        timeout=30,
    )
    return {"status_code": resp.status_code, "body": resp.json()}


def run_test(name: str, gateway_url: str, token: str, tool: str, args: dict, expect_allowed: bool):
    """Run a single policy test and print results."""
    print(f"\n{'─' * 50}")
    print(f"Test: {name}")
    print(f"  Tool: {tool}")
    print(f"  Args: {json.dumps(args)}")
    print(f"  Expected: {'ALLOW' if expect_allowed else 'DENY'}")

    result = call_tool(gateway_url, token, tool, args)
    status = result["status_code"]
    body = result["body"]

    # A denied request returns 403 or an error body with a policy-related message
    is_denied = status == 403 or (
        "error" in body and any(
            kw in json.dumps(body["error"]).lower()
            for kw in ("denied", "forbidden", "policy")
        )
    )

    if expect_allowed and not is_denied:
        print(f"  Result: ✅ ALLOWED (status {status})")
    elif not expect_allowed and is_denied:
        print(f"  Result: ✅ DENIED as expected (status {status})")
    elif expect_allowed and is_denied:
        print(f"  Result: ❌ UNEXPECTEDLY DENIED (status {status})")
        print(f"  Body: {json.dumps(body, indent=2)}")
    else:
        print(f"  Result: ❌ UNEXPECTEDLY ALLOWED (status {status})")
        print(f"  Body: {json.dumps(body, indent=2)}")

    return result


def main():
    parser = argparse.ArgumentParser(description="Test AgentCore Policy Engine")
    parser.add_argument("--gateway-url", required=True, help="MCP Gateway URL")
    parser.add_argument("--token", required=True, help="JWT access token")
    parser.add_argument("--expect-all-denied", action="store_true",
                        help="Expect every tool call to be denied (e.g. emergency shutdown)")
    args = parser.parse_args()

    all_denied = args.expect_all_denied

    print("=" * 50)
    print("AgentCore Policy Engine — Test Suite")
    if all_denied:
        print("  Mode: EXPECT ALL DENIED (emergency shutdown)")
    print("=" * 50)

    # Test 1: get_bills with limit=5 (normally ALLOWED — under 100)
    run_test(
        name="Billing query with small limit",
        gateway_url=args.gateway_url,
        token=args.token,
        tool="electrify-server-function___get_bills",
        args={"customer_username": "rroe@example.com", "limit": 5},
        expect_allowed=False if all_denied else True,
    )

    # Test 2: get_bills with limit=500 (should be DENIED — over 100)
    run_test(
        name="Billing query with excessive limit",
        gateway_url=args.gateway_url,
        token=args.token,
        tool="electrify-server-function___get_bills",
        args={"customer_username": "rroe@example.com", "limit": 500},
        expect_allowed=False,
    )

    # Test 3: get_rates (normally ALLOWED — read-only tool)
    run_test(
        name="Read-only tool: get_rates",
        gateway_url=args.gateway_url,
        token=args.token,
        tool="electrify-server-function___get_rates",
        args={},
        expect_allowed=False if all_denied else True,
    )

    # Test 4: get_customer (normally ALLOWED — read-only tool)
    run_test(
        name="Read-only tool: get_customer",
        gateway_url=args.gateway_url,
        token=args.token,
        tool="electrify-server-function___get_customer",
        args={"customer_username": "rroe@example.com"},
        expect_allowed=False if all_denied else True,
    )

    # Test 5: DataViz analyze_data_structure (normally ALLOWED)
    run_test(
        name="DataViz tool: analyze_data_structure",
        gateway_url=args.gateway_url,
        token=args.token,
        tool="dataviz-server-function___analyze_data_structure",
        args={"data": "month,amount\nJan,100\nFeb,120"},
        expect_allowed=False if all_denied else True,
    )

    # Test 6: DataViz create_pie_chart (should be DENIED — blocked by forbid policy)
    run_test(
        name="DataViz tool: create_pie_chart (blocked)",
        gateway_url=args.gateway_url,
        token=args.token,
        tool="dataviz-server-function___create_pie_chart",
        args={"data": "category,value\nA,40\nB,35\nC,25", "title": "Test Pie"},
        expect_allowed=False,
    )

    print(f"\n{'=' * 50}")
    print("Test suite complete.")
    print("=" * 50)


if __name__ == "__main__":
    main()
