# Module 02 - Strands Version Test Commands

## Test the MCP Server

```bash
uv run modules/02/strands/test_server.py rroe@example.com
```

## Launch the Strands Agent

```bash
uv run modules/02/strands/agent.py -p modules/02/langgraph/system.md -m "global.anthropic.claude-sonnet-4-20250514-v1:0" -s uv -a "run modules/02/strands/server.py -e $PGHOST -u $PGUSER --password \"$PGPASSWORD\"" -u rroe@example.com -t conv-001
```
