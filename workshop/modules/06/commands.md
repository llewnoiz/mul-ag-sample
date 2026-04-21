# Module 06 - AgentCore Policies

All commands assume you have the environment variables from Module 05 still set. Set your stack name and region first if needed:

```bash
export STACKNAME=electrify-us-east-1
export AWS_REGION=us-east-1
```

## Step 1: Review the Code

Review the Cedar policies and deployment script:

- `modules/06/deploy_policy.py` — creates policy engine, Cedar policies, attaches to gateway
- `modules/06/test_policy.py` — test suite verifying allow/deny behavior

## Step 2: Get Gateway Info

```bash
export GATEWAY_ID=$(aws bedrock-agentcore-control list-gateways --region $AWS_REGION --query "items[?name=='mcp-gateway'].gatewayId | [0]" --output text)
export GATEWAY_ARN=$(aws bedrock-agentcore-control get-gateway --gateway-identifier $GATEWAY_ID --region $AWS_REGION --query 'gatewayArn' --output text)
echo "Gateway ID: $GATEWAY_ID"
echo "Gateway ARN: $GATEWAY_ARN"
```

## Step 3: Deploy Policy Engine and Cedar Policies

```bash
cd ~/workshop && uv run modules/06/deploy_policy.py \
  --gateway-id $GATEWAY_ID \
  --gateway-arn $GATEWAY_ARN \
  --region $AWS_REGION \
  --mode ENFORCE
```

## Step 4: Test Policy Enforcement

```bash
export TOKEN=$(aws cognito-idp initiate-auth \
  --client-id "$COGNITO_CLIENT" \
  --auth-flow USER_PASSWORD_AUTH \
  --auth-parameters "{\"USERNAME\":\"$USER\",\"PASSWORD\":\"$PASSWORD\"}" \
  --region $AWS_REGION | jq -r '.AuthenticationResult.AccessToken')

cd ~/workshop && uv run modules/06/test_policy.py \
  --gateway-url $MCP_GATEWAY_URL \
  --token "$TOKEN"
```

## Step 5: Query Policy Observability Data

```bash
cd ~/workshop && uv run modules/06/query_policy_logs.py \
  --gateway-id $GATEWAY_ID \
  --region $AWS_REGION \
  --hours 1
```

## Optional: Emergency Shutdown

### Enable shutdown (block all tools)

```bash
export POLICY_ENGINE_ID=$(aws bedrock-agentcore-control list-policy-engines --region $AWS_REGION --query "policyEngines[?name=='electrify-policy-engine'].policyEngineId | [0]" --output text)

aws bedrock-agentcore-control create-policy \
  --policy-engine-id $POLICY_ENGINE_ID \
  --name emergency_shutdown \
  --description "Block all tool calls — emergency use only" \
  --definition '{"cedar": {"statement": "forbid(principal, action, resource);"}}' \
  --region $AWS_REGION
```

### Disable shutdown (restore access)

```bash
export SHUTDOWN_POLICY_ID=$(aws bedrock-agentcore-control list-policies --policy-engine-id $POLICY_ENGINE_ID --region $AWS_REGION --query "policies[?name=='emergency_shutdown'].policyId | [0]" --output text)

aws bedrock-agentcore-control delete-policy \
  --policy-engine-id $POLICY_ENGINE_ID \
  --policy-id $SHUTDOWN_POLICY_ID \
  --region $AWS_REGION
```

## Cleanup

```bash
# Detach policy engine from gateway
aws bedrock-agentcore-control update-gateway \
  --gateway-identifier $GATEWAY_ID \
  --region $AWS_REGION

# Delete all policies then the engine
for POLICY_ID in $(aws bedrock-agentcore-control list-policies --policy-engine-id $POLICY_ENGINE_ID --region $AWS_REGION --query "policies[].policyId" --output text); do
  echo "Deleting policy: $POLICY_ID"
  aws bedrock-agentcore-control delete-policy --policy-engine-id $POLICY_ENGINE_ID --policy-id $POLICY_ID --region $AWS_REGION
done

aws bedrock-agentcore-control delete-policy-engine --policy-engine-id $POLICY_ENGINE_ID --region $AWS_REGION
```
