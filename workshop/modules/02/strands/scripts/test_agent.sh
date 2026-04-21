#!/usr/bin/env bash
# Launch the Strands agent with the custom MCP server
# Usage: ./test_agent.sh [username] [thread_id] [model_id]
# Example: ./test_agent.sh rroe@example.com conv-001

set -euo pipefail

USERNAME="${1:-${USER:-unknown}}"
THREAD="${2:-conv-001}"
MODEL="${3:-global.anthropic.claude-sonnet-4-20250514-v1:0}"

echo "Starting Strands agent..."
echo "  User:   ${USERNAME}"
echo "  Thread: ${THREAD}"
echo "  Model:  ${MODEL}"
echo ""

uv run modules/02/strands/agent.py \
  -p modules/02/langgraph/system.md \
  -m "${MODEL}" \
  -s uv \
  -a "run modules/02/strands/server.py -e ${PGHOST} -u ${PGUSER} --password \"${PGPASSWORD}\"" \
  -u "${USERNAME}" \
  -t "${THREAD}"
