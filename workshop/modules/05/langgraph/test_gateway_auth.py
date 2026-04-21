#!/usr/bin/env python3
"""
Test AgentCore Gateway with JWT Bearer Token

This script tests the MCP gateway endpoint with JWT authentication.
It sends MCP protocol requests (tools/list, tools/call) to verify:
1. JWT auth is working
2. Headers are being passed through
3. Tools are accessible

Usage:
    # Test with JWT token
    python test_gateway_auth.py --gateway-url https://xxx.gateway.bedrock-agentcore.us-east-1.amazonaws.com/mcp --token YOUR_JWT_TOKEN

    # Test without auth (for gateways with authorizerType=NONE)
    python test_gateway_auth.py --gateway-url https://xxx.gateway.bedrock-agentcore.us-east-1.amazonaws.com/mcp

    # Test specific tool
    python test_gateway_auth.py --gateway-url URL --token TOKEN --tool get_rates
"""

import argparse
import json
import requests
import sys


def test_gateway(gateway_url: str, token: str = None, tool: str = None, tool_args: dict = None):
    """Test the gateway with MCP requests."""
    
    # Build headers
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    
    if token:
        headers["Authorization"] = f"Bearer {token}"
        print(f"✓ Using JWT token (length: {len(token)} chars)")
    else:
        print("⚠ No JWT token provided - testing without auth")
    
    print(f"\n{'='*60}")
    print(f"Gateway URL: {gateway_url}")
    print(f"{'='*60}\n")
    
    # Test 1: Initialize session
    print("Test 1: Initialize MCP session...")
    init_payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "test-client", "version": "1.0.0"}
        }
    }
    
    try:
        response = requests.post(gateway_url, headers=headers, json=init_payload, timeout=30)
        print(f"  Status: {response.status_code}")
        if response.status_code == 200:
            print(f"  Response: {json.dumps(response.json(), indent=2)[:500]}")
            # Extract session ID if present
            session_id = response.headers.get("Mcp-Session-Id")
            if session_id:
                headers["Mcp-Session-Id"] = session_id
                print(f"  Session ID: {session_id}")
        else:
            print(f"  Error: {response.text[:500]}")
            if response.status_code == 401:
                print("\n❌ Authentication failed - check your JWT token")
                return False
            if response.status_code == 403:
                print("\n❌ Authorization failed - token may be invalid or expired")
                return False
    except Exception as e:
        print(f"  Error: {e}")
        return False
    
    # Test 2: List tools
    print("\nTest 2: List available tools...")
    list_payload = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/list"
    }
    
    try:
        response = requests.post(gateway_url, headers=headers, json=list_payload, timeout=30)
        print(f"  Status: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            print(f"  Response: {json.dumps(result, indent=2)[:1000]}")
            if "result" in result and "tools" in result["result"]:
                tools = result["result"]["tools"]
                print(f"\n  ✓ Found {len(tools)} tools:")
                for t in tools:
                    print(f"    - {t.get('name')}: {t.get('description', '')[:50]}...")
        else:
            print(f"  Error: {response.text[:500]}")
    except Exception as e:
        print(f"  Error: {e}")
    
    # Test 3: Call a tool (if specified)
    if tool:
        print(f"\nTest 3: Call tool '{tool}'...")
        call_payload = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": tool,
                "arguments": tool_args or {}
            }
        }
        
        try:
            response = requests.post(gateway_url, headers=headers, json=call_payload, timeout=30)
            print(f"  Status: {response.status_code}")
            if response.status_code == 200:
                result = response.json()
                print(f"  Response: {json.dumps(result, indent=2)[:2000]}")
            else:
                print(f"  Error: {response.text[:500]}")
        except Exception as e:
            print(f"  Error: {e}")
    
    print(f"\n{'='*60}")
    print("Test complete!")
    print(f"{'='*60}")
    return True


def main():
    parser = argparse.ArgumentParser(description="Test AgentCore Gateway with JWT auth")
    parser.add_argument("--gateway-url", required=True, help="Gateway MCP endpoint URL")
    parser.add_argument("--token", help="JWT Bearer token")
    parser.add_argument("--token-file", help="File containing JWT token")
    parser.add_argument("--tool", help="Tool to call (e.g., get_rates, get_customer, get_bills)")
    parser.add_argument("--tool-args", help="Tool arguments as JSON string", default="{}")
    
    args = parser.parse_args()
    
    # Get token from file if specified
    token = args.token
    if args.token_file:
        with open(args.token_file, 'r') as f:
            token = f.read().strip()
    
    # Parse tool args
    try:
        tool_args = json.loads(args.tool_args)
    except json.JSONDecodeError:
        print(f"Error: Invalid JSON for --tool-args: {args.tool_args}")
        sys.exit(1)
    
    success = test_gateway(
        gateway_url=args.gateway_url,
        token=token,
        tool=args.tool,
        tool_args=tool_args
    )
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
