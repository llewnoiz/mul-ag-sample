#!/usr/bin/env python3
"""
Simple test script for MCP server using stdin/stdout
"""

import json
import subprocess
import sys
import time

def test_server():
    """Test the MCP server with proper JSON-RPC messages."""
    
    # Start the server
    process = subprocess.Popen(
        [sys.executable, "modules/02/langgraph/server.py"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=0
    )
    
    def send_message(message):
        """Send a JSON-RPC message and get response."""
        json_str = json.dumps(message)
        print(f"→ Sending: {json_str}")
        
        process.stdin.write(json_str + '\n')
        process.stdin.flush()
        
        # Read response
        try:
            response = process.stdout.readline().strip()
            if response:
                print(f"← Received: {response}")
                return json.loads(response)
        except Exception as e:
            print(f"Error reading response: {e}")
        return None
    
    try:
        # 1. Initialize
        init_msg = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "clientInfo": {
                    "name": "test-client",
                    "version": "1.0.0"
                }
            }
        }
        
        response = send_message(init_msg)
        if not response:
            print("Failed to get initialization response")
            return
        
        print("✓ Initialization successful\n")
        
        # 2. List tools
        list_msg = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {}
        }
        
        response = send_message(list_msg)
        if response:
            print("✓ Tools listed successfully\n")
        
        # 3. Call get_rates tool
        call_msg = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "get_rates",
                "arguments": {"limit": 3}
            }
        }
        
        response = send_message(call_msg)
        if response:
            print("✓ Tool call successful\n")

        # 4. Call get_customer tool
        call_msg = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "get_customer",
                "arguments": {"customer_username": "rroe"}
            }
        }
        
        response = send_message(call_msg)
        if response:
            print("✓ Tool call successful\n")

        # 5. Call get_bills tool
        call_msg = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "get_bills",
                "arguments": {"customer_username": "rroe", "limit": 3}
            }
        }
        
        response = send_message(call_msg)
        if response:
            print("✓ Tool call successful\n")
        
    except Exception as e:
        print(f"Test failed: {e}")
        # Print any stderr output
        stderr_output = process.stderr.read()
        if stderr_output:
            print(f"Server stderr: {stderr_output}")
    
    finally:
        process.terminate()
        process.wait()

if __name__ == "__main__":
    test_server()