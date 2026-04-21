#!/usr/bin/env bash
# Test the ElectrifyMCPServer get_bills tool (Strands version)
# Usage: ./test_server.sh <username>
# Example: ./test_server.sh rroe@example.com

set -euo pipefail

USERNAME="${1:?Usage: $0 <customer_username>}"

echo "Testing MCP server (strands) for user: ${USERNAME}"
uv run modules/02/strands/test_server.py "${USERNAME}"
