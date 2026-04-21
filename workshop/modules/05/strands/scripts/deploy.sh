#!/bin/bash
# =============================================================
# Module 05 (Strands) - Deploy to AgentCore - All Commands
# =============================================================
set -e

# --- Step 1: Get CloudFormation Outputs ---
export CLUSTER_NAME=$(aws cloudformation describe-stacks --stack-name $STACKNAME --region $AWS_REGION --query 'Stacks[0].Outputs[?OutputKey==`clusterName`].OutputValue' --output text)
export PGHOSTARN="arn:aws:rds:${AWS_REGION}:$(aws sts get-caller-identity --query Account --output text):cluster:${CLUSTER_NAME}"
export PGSECRET=$(aws cloudformation describe-stacks --stack-name $STACKNAME --region $AWS_REGION --query 'Stacks[0].Outputs[?OutputKey==`secretArn`].OutputValue' --output text)
export PGDATABASE=postgres
export COGNITO_POOL=$(aws cloudformation describe-stacks --stack-name $STACKNAME --region $AWS_REGION --query 'Stacks[0].Outputs[?OutputKey==`CognitoPool`].OutputValue' --output text)
export COGNITO_CLIENT=$(aws cloudformation describe-stacks --stack-name $STACKNAME --region $AWS_REGION --query 'Stacks[0].Outputs[?OutputKey==`CognitoClient`].OutputValue' --output text)
export AGENTCORE_ROLE_ARN=$(aws cloudformation describe-stacks --stack-name $STACKNAME --region $AWS_REGION --query 'Stacks[0].Outputs[?OutputKey==`AgentCoreSDKRuntimeRoleArn`].OutputValue' --output text)
export OAUTH_ISSUER_URL="https://cognito-idp.$AWS_REGION.amazonaws.com/$COGNITO_POOL/.well-known/openid-configuration"

# Verify variables are set
[[ -z "$CLUSTER_NAME" ]] && echo "ERROR: CLUSTER_NAME is empty" || echo "CLUSTER_NAME=$CLUSTER_NAME"
[[ -z "$PGHOSTARN" ]] && echo "ERROR: PGHOSTARN is empty" || echo "PGHOSTARN=$PGHOSTARN"
[[ -z "$PGSECRET" ]] && echo "ERROR: PGSECRET is empty" || echo "PGSECRET=$PGSECRET"
[[ -z "$COGNITO_POOL" ]] && echo "ERROR: COGNITO_POOL is empty" || echo "COGNITO_POOL=$COGNITO_POOL"
[[ -z "$COGNITO_CLIENT" ]] && echo "ERROR: COGNITO_CLIENT is empty" || echo "COGNITO_CLIENT=$COGNITO_CLIENT"
[[ -z "$AGENTCORE_ROLE_ARN" ]] && echo "ERROR: AGENTCORE_ROLE_ARN is empty" || echo "AGENTCORE_ROLE_ARN=$AGENTCORE_ROLE_ARN"

# --- Step 2: Deploy MCP Servers to Lambda ---
# Note: Lambda servers are shared between LangGraph and Strands paths.
# The deploy_lambda.py and deploy_gateway_simple.py scripts are framework-agnostic.

# Deploy Electrify MCP Server
cd ~/workshop && uv run modules/05/strands/deploy_lambda.py \
  --server-name electrify-server \
  --db-cluster-arn $PGHOSTARN \
  --secret-arn $PGSECRET \
  --database $PGDATABASE \
  --mcp-server-path modules/05/strands/electrify_server.py \
  --handler electrify_server.lambda_handler \
  --region $AWS_REGION

export ELECTRIFY_LAMBDA_ARN=$(aws lambda get-function --function-name electrify-server-function --region $AWS_REGION --query 'Configuration.FunctionArn' --output text)
[[ -z "$ELECTRIFY_LAMBDA_ARN" ]] && echo "ERROR: ELECTRIFY_LAMBDA_ARN is empty" || echo "ELECTRIFY_LAMBDA_ARN=$ELECTRIFY_LAMBDA_ARN"

# Deploy DataViz MCP Server
cd ~/workshop && uv run modules/05/strands/deploy_lambda.py \
  --server-name dataviz-server \
  --mcp-server-path modules/05/strands/dataviz_server.py \
  --handler dataviz_server.lambda_handler \
  --extra-deps pandas matplotlib \
  --region $AWS_REGION

export DATAVIZ_LAMBDA_ARN=$(aws lambda get-function --function-name dataviz-server-function --region $AWS_REGION --query 'Configuration.FunctionArn' --output text)
[[ -z "$DATAVIZ_LAMBDA_ARN" ]] && echo "ERROR: DATAVIZ_LAMBDA_ARN is empty" || echo "DATAVIZ_LAMBDA_ARN=$DATAVIZ_LAMBDA_ARN"

# --- Step 3: Deploy AgentCore Gateway ---
uv run modules/05/strands/deploy_gateway_simple.py \
  --gateway-name mcp-gateway \
  --electrify-lambda-arn $ELECTRIFY_LAMBDA_ARN \
  --dataviz-lambda-arn $DATAVIZ_LAMBDA_ARN \
  --cognito-user-pool-id $COGNITO_POOL \
  --cognito-client-id $COGNITO_CLIENT \
  --region $AWS_REGION

# Get Gateway URL
export MCP_GATEWAY_URL=$(aws bedrock-agentcore-control list-gateways --region $AWS_REGION --query "items[?name=='mcp-gateway'].gatewayId | [0]" --output text | xargs -I {} aws bedrock-agentcore-control get-gateway --gateway-identifier {} --region $AWS_REGION --query 'gatewayUrl' --output text)
echo "MCP Gateway: $MCP_GATEWAY_URL"

# --- Step 4: Deploy Agent to AgentCore Runtime ---

# Configure Agent (Strands version)
cd ~/workshop/modules/05/strands && uv run agentcore configure \
  --name electrify_assistant \
  --protocol HTTP \
  --entrypoint agentcore_runtime_adapter.py \
  --requirements-file requirements.txt \
  --non-interactive \
  --region $AWS_REGION \
  --execution-role $AGENTCORE_ROLE_ARN \
  --authorizer-config "{\"customJWTAuthorizer\": {\"discoveryUrl\": \"$OAUTH_ISSUER_URL\", \"allowedClients\": [\"$COGNITO_CLIENT\"]}}"

# Launch Agent
cd ~/workshop/modules/05/strands && uv run agentcore launch \
  --agent electrify_assistant \
  --env MCP_GATEWAY_URL="$MCP_GATEWAY_URL" \
  --env AGENT_MODEL_ID="global.anthropic.claude-sonnet-4-20250514-v1:0"

# --- Step 5: Test the Agent ---

# Get Cognito Credentials
export CLIENT_SECRET=$(aws cognito-idp describe-user-pool-client --user-pool-id $COGNITO_POOL --client-id $COGNITO_CLIENT --region $AWS_REGION --query 'UserPoolClient.ClientSecret' --output text)
export USER=$(aws cloudformation describe-stacks --stack-name $STACKNAME --region $AWS_REGION --query 'Stacks[0].Outputs[?OutputKey==`ApplicationUserEmail`].OutputValue' --output text)
export PASSWORD=$(aws cloudformation describe-stacks --stack-name $STACKNAME --region $AWS_REGION --query 'Stacks[0].Outputs[?OutputKey==`ApplicationUserPassword`].OutputValue' --output text)
export AGENT_RUNTIME_ID=$(aws bedrock-agentcore-control list-agent-runtimes --region $AWS_REGION --query "agentRuntimes[?agentRuntimeName=='electrify_assistant'].agentRuntimeId | [0]" --output text)

# Get JWT Token
export TOKEN=$(aws cognito-idp initiate-auth \
  --client-id "$COGNITO_CLIENT" \
  --auth-flow USER_PASSWORD_AUTH \
  --auth-parameters "{\"USERNAME\":\"$USER\",\"PASSWORD\":\"$PASSWORD\"}" \
  --region $AWS_REGION | jq -r '.AuthenticationResult.AccessToken')

# Test Agent
cd ~/workshop/modules/05/strands
uv run test_runtime.py --runtime-id $AGENT_RUNTIME_ID --prompt "What rate plans are available?" --token "$TOKEN" --stream

uv run test_runtime.py --runtime-id $AGENT_RUNTIME_ID --prompt "What was my last months bill?" --token "$TOKEN" --stream

uv run test_runtime.py --runtime-id $AGENT_RUNTIME_ID --prompt "Show me a bar chart of my last 6 bills" --token "$TOKEN" --stream

# --- Optional: Test Gateway Directly ---

# List all tools on the gateway
uv run test_gateway_auth.py --gateway-url $MCP_GATEWAY_URL --token $TOKEN

# Invoke electrify tool
uv run test_gateway_auth.py \
  --gateway-url $MCP_GATEWAY_URL \
  --token $TOKEN \
  --tool electrify-server-function___get_bills \
  --tool-args '{"customer_username": "rroe@example.com", "limit": 5}'

# Invoke dataviz tool
uv run test_gateway_auth.py \
  --gateway-url $MCP_GATEWAY_URL \
  --token $TOKEN \
  --tool dataviz-server-function___analyze_data_structure \
  --tool-args '{"data": "month,amount\nJan,100\nFeb,120"}'
