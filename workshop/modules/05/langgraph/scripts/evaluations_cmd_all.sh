#!/bin/bash
# =============================================================
# AgentCore Evaluations - All Commands
# =============================================================
set -e

# --- Prerequisites ---
export CLIENT_SECRET=$(aws cognito-idp describe-user-pool-client --user-pool-id $COGNITO_POOL --client-id $COGNITO_CLIENT --region $AWS_REGION --query 'UserPoolClient.ClientSecret' --output text)
export USER=$(aws cloudformation describe-stacks --stack-name $STACKNAME --region $AWS_REGION --query 'Stacks[0].Outputs[?OutputKey==`ApplicationUserEmail`].OutputValue' --output text)
export PASSWORD=$(aws cloudformation describe-stacks --stack-name $STACKNAME --region $AWS_REGION --query 'Stacks[0].Outputs[?OutputKey==`ApplicationUserPassword`].OutputValue' --output text)
export AGENT_RUNTIME_ID=$(aws bedrock-agentcore-control list-agent-runtimes --region $AWS_REGION --query "agentRuntimes[?agentRuntimeName=='electrify_assistant'].agentRuntimeId | [0]" --output text)

export TOKEN=$(aws cognito-idp initiate-auth \
  --client-id "$COGNITO_CLIENT" \
  --auth-flow USER_PASSWORD_AUTH \
  --auth-parameters "{\"USERNAME\":\"$USER\",\"PASSWORD\":\"$PASSWORD\"}" \
  --region $AWS_REGION | jq -r '.AuthenticationResult.AccessToken')

# --- Step 1: Generate Traces ---
cd ~/workshop/modules/05/langgraph

EVAL_SESSION_ID="conv-eval-00000000000000000000001"

uv run test_runtime.py --runtime-id $AGENT_RUNTIME_ID \
  --prompt "What rate plans are available?" \
  --token "$TOKEN" --stream \
  --session-id "$EVAL_SESSION_ID"

uv run test_runtime.py --runtime-id $AGENT_RUNTIME_ID \
  --prompt "Show me my last 6 bills" \
  --token "$TOKEN" --stream \
  --session-id "$EVAL_SESSION_ID"

uv run test_runtime.py --runtime-id $AGENT_RUNTIME_ID \
  --prompt "Compare the Green Energy and Standard rate plans" \
  --token "$TOKEN" --stream \
  --session-id "$EVAL_SESSION_ID"

# Wait for traces
EXPECTED_TRACES=3
echo "Waiting for traces to appear in CloudWatch..."
PREV_SPANS=0
STABLE=0
for i in $(seq 1 10); do
  OUTPUT=$(uv run agentcore obs list --session-id "$EVAL_SESSION_ID" 2>&1)
  TRACES=$(echo "$OUTPUT" | grep -oP 'Found \K\d+(?= traces)' || echo 0)
  SPANS=$(echo "$OUTPUT" | grep -oP '\d+(?= spans)' | awk '{s+=$1} END {print s+0}')
  echo "  Poll $i/10: $TRACES traces, $SPANS total spans"
  if [[ "$TRACES" -ge "$EXPECTED_TRACES" && "$SPANS" -gt 0 && "$SPANS" -eq "$PREV_SPANS" ]]; then
    STABLE=$((STABLE + 1))
    if [[ "$STABLE" -ge 2 ]]; then
      echo "Traces are ready! ($TRACES traces, $SPANS spans — stable)"
      break
    fi
    echo "  Spans unchanged, confirming stability..."
  else
    STABLE=0
  fi
  PREV_SPANS=$SPANS
  sleep 30
done

# --- Step 2: Run On-Demand Evaluation ---
cd ~/workshop/modules/05/langgraph

AGENT_ID=$(aws bedrock-agentcore-control list-agent-runtimes \
  --region $AWS_REGION \
  --query "agentRuntimes[?agentRuntimeName=='electrify_assistant'].agentRuntimeId | [0]" \
  --output text)

echo "Agent ID: $AGENT_ID"

uv run agentcore eval run \
  --agent-id $AGENT_ID \
  --session-id "$EVAL_SESSION_ID" \
  --evaluator "Builtin.GoalSuccessRate" \
  --evaluator "Builtin.Helpfulness"

# --- Step 3 (Optional): Compare Model Performance ---
export MCP_GATEWAY_URL=$(aws bedrock-agentcore-control list-gateways --region $AWS_REGION --query "items[?name=='mcp-gateway'].gatewayId | [0]" --output text | xargs -I {} aws bedrock-agentcore-control get-gateway --gateway-identifier {} --region $AWS_REGION --query 'gatewayUrl' --output text)
echo "MCP Gateway: $MCP_GATEWAY_URL"

cd ~/workshop/modules/05/langgraph

# Redeploy with Claude 3.5 Haiku
uv run agentcore launch \
  --agent electrify_assistant \
  --env MCP_GATEWAY_URL="$MCP_GATEWAY_URL" \
  --env AGENT_MODEL_ID="us.anthropic.claude-3-5-haiku-20241022-v1:0"

echo "Wait ~5 minutes for deployment before continuing..."
# Uncomment the sleep or wait manually:
# sleep 300

# Run same prompts with new session ID
COMPARE_SESSION_ID="conv-eval-model-comparison-000001"

uv run test_runtime.py --runtime-id $AGENT_RUNTIME_ID \
  --prompt "What rate plans are available?" \
  --token "$TOKEN" --stream \
  --session-id "$COMPARE_SESSION_ID"

uv run test_runtime.py --runtime-id $AGENT_RUNTIME_ID \
  --prompt "Show me my last 6 bills" \
  --token "$TOKEN" --stream \
  --session-id "$COMPARE_SESSION_ID"

uv run test_runtime.py --runtime-id $AGENT_RUNTIME_ID \
  --prompt "Compare the Green Energy and Standard rate plans" \
  --token "$TOKEN" --stream \
  --session-id "$COMPARE_SESSION_ID"

# Wait for traces
EXPECTED_TRACES=3
echo "Waiting for traces to appear in CloudWatch..."
PREV_SPANS=0
STABLE=0
for i in $(seq 1 10); do
  OUTPUT=$(uv run agentcore obs list --session-id "$COMPARE_SESSION_ID" 2>&1)
  TRACES=$(echo "$OUTPUT" | grep -oP 'Found \K\d+(?= traces)' || echo 0)
  SPANS=$(echo "$OUTPUT" | grep -oP '\d+(?= spans)' | awk '{s+=$1} END {print s+0}')
  echo "  Poll $i/10: $TRACES traces, $SPANS total spans"
  if [[ "$TRACES" -ge "$EXPECTED_TRACES" && "$SPANS" -gt 0 && "$SPANS" -eq "$PREV_SPANS" ]]; then
    STABLE=$((STABLE + 1))
    if [[ "$STABLE" -ge 2 ]]; then
      echo "Traces are ready! ($TRACES traces, $SPANS spans — stable)"
      break
    fi
    echo "  Spans unchanged, confirming stability..."
  else
    STABLE=0
  fi
  PREV_SPANS=$SPANS
  sleep 30
done

# Evaluate comparison model
uv run agentcore eval run \
  --agent-id $AGENT_ID \
  --session-id "$COMPARE_SESSION_ID" \
  --evaluator "Builtin.GoalSuccessRate" \
  --evaluator "Builtin.Helpfulness"

# Restore original model
uv run agentcore launch \
  --agent electrify_assistant \
  --env MCP_GATEWAY_URL="$MCP_GATEWAY_URL" \
  --env AGENT_MODEL_ID="global.anthropic.claude-sonnet-4-20250514-v1:0"
