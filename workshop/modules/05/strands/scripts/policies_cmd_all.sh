#!/bin/bash
# =============================================================
# AgentCore Policies - All Commands
# =============================================================
set -e

# --- Step 3: Add IAM Permission for Policy Engine ---
aws iam put-role-policy \
  --role-name mcp-gateway-role \
  --policy-name mcp-gateway-policy-engine \
  --policy-document '{
    "Version": "2012-10-17",
    "Statement": [
      {
        "Effect": "Allow",
        "Action": [
          "bedrock-agentcore:AuthorizeAction",
          "bedrock-agentcore:GetPolicyEngine"
        ],
        "Resource": [
          "arn:aws:bedrock-agentcore:'"$AWS_REGION"':'"$(aws sts get-caller-identity --query Account --output text)"':gateway/*",
          "arn:aws:bedrock-agentcore:'"$AWS_REGION"':'"$(aws sts get-caller-identity --query Account --output text)"':policy-engine/*"
        ]
      }
    ]
  }' --region $AWS_REGION

# --- Step 4: Deploy the Policy Engine ---
export GATEWAY_ID=$(aws bedrock-agentcore-control list-gateways --region $AWS_REGION --query "items[?name=='mcp-gateway'].gatewayId | [0]" --output text)
export GATEWAY_ARN=$(aws bedrock-agentcore-control get-gateway --gateway-identifier $GATEWAY_ID --region $AWS_REGION --query 'gatewayArn' --output text)
echo "Gateway ID: $GATEWAY_ID"
echo "Gateway ARN: $GATEWAY_ARN"

cd ~/workshop && uv run modules/06/deploy_policy.py \
  --gateway-id $GATEWAY_ID \
  --gateway-arn $GATEWAY_ARN \
  --region $AWS_REGION \
  --mode ENFORCE

# --- Step 5: Test Policy Enforcement ---
export MCP_GATEWAY_URL=$(aws bedrock-agentcore-control list-gateways --region $AWS_REGION --query "items[?name=='mcp-gateway'].gatewayId | [0]" --output text | xargs -I {} aws bedrock-agentcore-control get-gateway --gateway-identifier {} --region $AWS_REGION --query 'gatewayUrl' --output text)
echo "MCP Gateway: $MCP_GATEWAY_URL"

export CLIENT_SECRET=$(aws cognito-idp describe-user-pool-client --user-pool-id $COGNITO_POOL --client-id $COGNITO_CLIENT --region $AWS_REGION --query 'UserPoolClient.ClientSecret' --output text)
export USER=$(aws cloudformation describe-stacks --stack-name $STACKNAME --region $AWS_REGION --query 'Stacks[0].Outputs[?OutputKey==`ApplicationUserEmail`].OutputValue' --output text)
export PASSWORD=$(aws cloudformation describe-stacks --stack-name $STACKNAME --region $AWS_REGION --query 'Stacks[0].Outputs[?OutputKey==`ApplicationUserPassword`].OutputValue' --output text)

export TOKEN=$(aws cognito-idp initiate-auth \
  --client-id "$COGNITO_CLIENT" \
  --auth-flow USER_PASSWORD_AUTH \
  --auth-parameters "{\"USERNAME\":\"$USER\",\"PASSWORD\":\"$PASSWORD\"}" \
  --region $AWS_REGION | jq -r '.AuthenticationResult.AccessToken')

cd ~/workshop && uv run modules/06/test_policy.py \
  --gateway-url $MCP_GATEWAY_URL \
  --token "$TOKEN"

# --- Agent Queries That Get Blocked ---
export AGENT_RUNTIME_ID=$(aws bedrock-agentcore-control list-agent-runtimes --region $AWS_REGION --query "agentRuntimes[?agentRuntimeName=='electrify_assistant'].agentRuntimeId | [0]" --output text)

cd ~/workshop/modules/05/strands
uv run test_runtime.py --runtime-id $AGENT_RUNTIME_ID --prompt "Show me the last 200 bills for rroe@example.com" --token "$TOKEN" --stream

cd ~/workshop/modules/05/strands
uv run test_runtime.py --runtime-id $AGENT_RUNTIME_ID --prompt "Get the rate plans and create a pie chart comparing their prices" --token "$TOKEN" --stream

cd ~/workshop/modules/05/strands
uv run test_runtime.py --runtime-id $AGENT_RUNTIME_ID --prompt "Get all bills for rroe@example.com and show them as a pie chart" --token "$TOKEN" --stream

# --- Emergency Shutdown (Optional) ---
export POLICY_ENGINE_ID=$(aws bedrock-agentcore-control list-policy-engines --region $AWS_REGION --query "policyEngines[?name=='electrify_policy_engine'].policyEngineId | [0]" --output text)

aws bedrock-agentcore-control create-policy \
  --policy-engine-id $POLICY_ENGINE_ID \
  --name emergency_shutdown \
  --description "Block all tool calls — emergency use only" \
  --validation-mode IGNORE_ALL_FINDINGS \
  --definition '{"cedar": {"statement": "forbid(principal, action, resource is AgentCore::Gateway);"}}' \
  --region $AWS_REGION

cd ~/workshop && uv run modules/06/test_policy.py \
  --gateway-url $MCP_GATEWAY_URL \
  --token "$TOKEN" \
  --expect-all-denied

# Restore access
export SHUTDOWN_POLICY_ID=$(aws bedrock-agentcore-control list-policies --policy-engine-id $POLICY_ENGINE_ID --region $AWS_REGION --query "policies[?name=='emergency_shutdown'].policyId | [0]" --output text)

aws bedrock-agentcore-control delete-policy \
  --policy-engine-id $POLICY_ENGINE_ID \
  --policy-id $SHUTDOWN_POLICY_ID \
  --region $AWS_REGION

# =============================================================
# Part 2: Policy Observability
# =============================================================

# --- Step 1: Generate Traffic ---
export MCP_GATEWAY_URL=$(aws bedrock-agentcore-control list-gateways --region $AWS_REGION --query "items[?name=='mcp-gateway'].gatewayId | [0]" --output text | xargs -I {} aws bedrock-agentcore-control get-gateway --gateway-identifier {} --region $AWS_REGION --query 'gatewayUrl' --output text)

export TOKEN=$(aws cognito-idp initiate-auth \
  --client-id "$COGNITO_CLIENT" \
  --auth-flow USER_PASSWORD_AUTH \
  --auth-parameters "{\"USERNAME\":\"$USER\",\"PASSWORD\":\"$PASSWORD\"}" \
  --region $AWS_REGION | jq -r '.AuthenticationResult.AccessToken')

cd ~/workshop && uv run modules/06/test_policy.py \
  --gateway-url $MCP_GATEWAY_URL \
  --token "$TOKEN"

# --- Step 2: Query Policy Metrics ---
cd ~/workshop && uv run modules/06/query_policy_logs.py \
  --gateway-id $GATEWAY_ID \
  --region $AWS_REGION \
  --hours 1

# --- Step 4: Clean Up Policies ---
# Delete all policies
for POLICY_ID in $(aws bedrock-agentcore-control list-policies --policy-engine-id $POLICY_ENGINE_ID --region $AWS_REGION --query "policies[].policyId" --output text); do
  echo "Deleting policy: $POLICY_ID"
  aws bedrock-agentcore-control delete-policy \
    --policy-engine-id $POLICY_ENGINE_ID \
    --policy-id $POLICY_ID \
    --region $AWS_REGION
done

# Wait for all policies to finish deleting
echo "Waiting for policies to be deleted..."
while true; do
  REMAINING=$(aws bedrock-agentcore-control list-policies --policy-engine-id $POLICY_ENGINE_ID --region $AWS_REGION --query "length(policies)" --output text)
  if [ "$REMAINING" = "0" ] || [ "$REMAINING" = "None" ]; then
    echo "All policies deleted"
    break
  fi
  echo "  $REMAINING policies still deleting..."
  sleep 5
done

# Detach the policy engine from the gateway
export GW_NAME=$(aws bedrock-agentcore-control get-gateway --gateway-identifier $GATEWAY_ID --region $AWS_REGION --query 'name' --output text)
export GW_ROLE=$(aws bedrock-agentcore-control get-gateway --gateway-identifier $GATEWAY_ID --region $AWS_REGION --query 'roleArn' --output text)
export GW_PROTOCOL=$(aws bedrock-agentcore-control get-gateway --gateway-identifier $GATEWAY_ID --region $AWS_REGION --query 'protocolType' --output text)
export GW_AUTH_TYPE=$(aws bedrock-agentcore-control get-gateway --gateway-identifier $GATEWAY_ID --region $AWS_REGION --query 'authorizerType' --output text)
export GW_AUTH_CONFIG=$(aws bedrock-agentcore-control get-gateway --gateway-identifier $GATEWAY_ID --region $AWS_REGION --query 'authorizerConfiguration' --output json)

aws bedrock-agentcore-control update-gateway \
  --gateway-identifier $GATEWAY_ID \
  --name "$GW_NAME" \
  --role-arn "$GW_ROLE" \
  --protocol-type "$GW_PROTOCOL" \
  --authorizer-type "$GW_AUTH_TYPE" \
  --authorizer-configuration "$GW_AUTH_CONFIG" \
  --region $AWS_REGION

# Delete the policy engine
aws bedrock-agentcore-control delete-policy-engine \
  --policy-engine-id $POLICY_ENGINE_ID \
  --region $AWS_REGION

echo "Policy engine detached and deleted"
