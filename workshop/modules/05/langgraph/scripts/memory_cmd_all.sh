#!/bin/bash
# =============================================================
# Agent Memory Patterns - All Commands
# =============================================================
set -e

# --- Step 1: Create Memory Resource ---
cd ~/workshop/modules/05/langgraph

uv run agentcore memory create electrify_ltm \
  --strategies '[
    {"semanticMemoryStrategy": {"name": "Facts", "description": "Extract and store customer facts from conversations"}},
    {"userPreferenceMemoryStrategy": {"name": "Preferences", "description": "Extract user preferences, choices, and communication styles"}},
    {"summaryMemoryStrategy": {"name": "Summaries", "namespaces": ["/summaries/{actorId}/{sessionId}/"]}},
    {"episodicMemoryStrategy": {"name": "Episodes", "namespaces": ["/strategy/{memoryStrategyId}/actors/{actorId}/sessions/{sessionId}/"], "reflectionConfiguration": {"namespaces": ["/strategy/{memoryStrategyId}/actors/{actorId}/"]}}}
  ]' \
  --description "Electrify agent memory with all LTM strategies" \
  --wait

export LTM_MEMORY_ID=$(aws bedrock-agentcore-control list-memories --region $AWS_REGION --query "memories[?starts_with(id, 'electrify_ltm')].id | [0]" --output text)
echo "LTM Memory ID: $LTM_MEMORY_ID"

# --- Step 2: Redeploy Agent with LTM ---
sed -i "s/memory_id: .*/memory_id: $LTM_MEMORY_ID/" .bedrock_agentcore.yaml
sed -i "s/mode: STM_ONLY/mode: STM_AND_LTM/" .bedrock_agentcore.yaml

export MCP_GATEWAY_URL=$(aws bedrock-agentcore-control list-gateways --region $AWS_REGION --query "items[?name=='mcp-gateway'].gatewayId | [0]" --output text | xargs -I {} aws bedrock-agentcore-control get-gateway --gateway-identifier {} --region $AWS_REGION --query 'gatewayUrl' --output text)

uv run agentcore launch \
  --agent electrify_assistant \
  --env MCP_GATEWAY_URL="$MCP_GATEWAY_URL" \
  --env AGENT_MODEL_ID="global.anthropic.claude-sonnet-4-20250514-v1:0"

echo "Wait ~5 minutes for deployment before continuing..."
# sleep 300

# --- Refresh Auth Token ---
export CLIENT_SECRET=$(aws cognito-idp describe-user-pool-client --user-pool-id $COGNITO_POOL --client-id $COGNITO_CLIENT --region $AWS_REGION --query 'UserPoolClient.ClientSecret' --output text)
export USER=$(aws cloudformation describe-stacks --stack-name $STACKNAME --region $AWS_REGION --query 'Stacks[0].Outputs[?OutputKey==`ApplicationUserEmail`].OutputValue' --output text)
export PASSWORD=$(aws cloudformation describe-stacks --stack-name $STACKNAME --region $AWS_REGION --query 'Stacks[0].Outputs[?OutputKey==`ApplicationUserPassword`].OutputValue' --output text)
export AGENT_RUNTIME_ID=$(aws bedrock-agentcore-control list-agent-runtimes --region $AWS_REGION --query "agentRuntimes[?agentRuntimeName=='electrify_assistant'].agentRuntimeId | [0]" --output text)

export TOKEN=$(aws cognito-idp initiate-auth \
  --client-id "$COGNITO_CLIENT" \
  --auth-flow USER_PASSWORD_AUTH \
  --auth-parameters "{\"USERNAME\":\"$USER\",\"PASSWORD\":\"$PASSWORD\"}" \
  --region $AWS_REGION | jq -r '.AuthenticationResult.AccessToken')

# --- Session 1: Establish Preferences ---
cd ~/workshop/modules/05/langgraph

uv run test_runtime.py --runtime-id $AGENT_RUNTIME_ID \
  --prompt "I'm interested in eco-friendly rate plans. What do you have? I'd prefer the Green Energy plan. Also, please always show me costs in monthly format and contact me via email for billing updates." \
  --token "$TOKEN" --stream \
  --session-id "ltm-session-000000000000000000001"

# --- Session 2: Troubleshooting (Two Turns) ---
uv run test_runtime.py --runtime-id $AGENT_RUNTIME_ID \
  --prompt "Which month in the last year had my highest electricity bill?" \
  --token "$TOKEN" --stream \
  --session-id "ltm-session-000000000000000000002"

uv run test_runtime.py --runtime-id $AGENT_RUNTIME_ID \
  --prompt "Could that have been because of the space heater I was using a lot that month?" \
  --token "$TOKEN" --stream \
  --session-id "ltm-session-000000000000000000002"

# --- Wait for Extraction ---
echo "Waiting 90 seconds for memory extraction..."
sleep 90

# Verify extraction
uv run test_memory.py --memory-id $LTM_MEMORY_ID --list-memories

# --- Session 3: Cross-Session Recall ---
uv run test_runtime.py --runtime-id $AGENT_RUNTIME_ID \
  --prompt "What rate plan am I interested in, and how do I prefer to be contacted?" \
  --token "$TOKEN" --stream \
  --session-id "ltm-session-000000000000000000003"

# --- Session 4: Recall Past Troubleshooting ---
uv run test_runtime.py --runtime-id $AGENT_RUNTIME_ID \
  --prompt "My bill seems high again. Have we looked into this before? What was the cause last time?" \
  --token "$TOKEN" --stream \
  --session-id "ltm-session-000000000000000000004"
