#!/bin/bash
# =============================================================================
# Full End-to-End Workshop Smoke Test — Strands Track (Modules 02-10)
# =============================================================================
# Runs on the deployed workshop environment after make infra-deploy.
# Walks through ALL modules:
#   Phase 1 (Modules 02-04): Local agent tests — restore .backup, test agents
#   Phase 2 (Module 05):     Deploy Lambda + Gateway + AgentCore Runtime, test
#   Phase 3 (Module 06/10):  Deploy policies, test enforcement
#
# Prerequisites:
#   - Deployed workshop environment (make infra-deploy)
#   - PGHOST, PGUSER, PGPASSWORD, STACKNAME, AWS_REGION env vars set
#   - COGNITO_POOL, COGNITO_CLIENT, PGHOSTARN, PGSECRET, PGDATABASE env vars set
#   - AGENTCORE_ROLE_ARN, OAUTH_ISSUER_URL env vars set (for agent deployment)
#   - uv installed, dependencies synced
#
# Usage:
#   ./test_strands_full.sh [username]
#   username defaults to rroe@example.com
#
# You can also start from a specific phase:
#   ./test_strands_full.sh [username] --skip-local     # Skip Phase 1
#   ./test_strands_full.sh [username] --phase2-only     # Only Phase 2
#   ./test_strands_full.sh [username] --phase3-only     # Only Phase 3 (requires Phase 2 done)
# =============================================================================

set -o pipefail

USERNAME="${1:-rroe@example.com}"
MODEL="global.anthropic.claude-sonnet-4-20250514-v1:0"
LOGFILE="test_strands_full_$(date +%Y%m%d_%H%M%S).log"
PASS=0
FAIL=0
SKIP=0
FRAMEWORK="strands"

# Parse flags
SKIP_LOCAL=false
PHASE2_ONLY=false
PHASE3_ONLY=false
for arg in "$@"; do
    case "$arg" in
        --skip-local) SKIP_LOCAL=true ;;
        --phase2-only) PHASE2_ONLY=true ;;
        --phase3-only) PHASE3_ONLY=true ;;
    esac
done

# ── helpers ──────────────────────────────────────────────────────────────────

log()     { echo "$1" | tee -a "$LOGFILE"; }
pass()    { log "  PASS: $1"; ((PASS++)); }
fail()    { log "  FAIL: $1"; ((FAIL++)); }
skip()    { log "  SKIP: $1"; ((SKIP++)); }
section() { log ""; log "==================================================="; log "  $1"; log "==================================================="; }

run_with_timeout() {
    local timeout=$1; shift
    timeout "$timeout" "$@" 2>&1
    return $?
}

require_var() {
    local var_name=$1
    if [ -z "${!var_name}" ]; then
        fail "$var_name not set"
        return 1
    else
        pass "$var_name is set"
        return 0
    fi
}

# ── preflight ────────────────────────────────────────────────────────────────

section "PREFLIGHT"
log "  Log:       $LOGFILE"
log "  Username:  $USERNAME"
log "  Model:     $MODEL"
log "  Framework: $FRAMEWORK"

PREFLIGHT_OK=true
for var in PGHOST PGUSER PGPASSWORD; do
    require_var "$var" || PREFLIGHT_OK=false
done

command -v uv &>/dev/null && pass "uv found" || { fail "uv not found"; exit 1; }

if [ "$PREFLIGHT_OK" != "true" ]; then
    log ""; log "  Preflight failed. Set required env vars and retry."; exit 1
fi

# =============================================================================
# PHASE 1: Local Agent Tests (Modules 02-04)
# =============================================================================

if [ "$PHASE2_ONLY" = "true" ] || [ "$PHASE3_ONLY" = "true" ]; then
    SKIP_LOCAL=true
fi

if [ "$SKIP_LOCAL" = "true" ]; then
    section "PHASE 1: SKIPPED (local agent tests)"
    skip "Phase 1 skipped by flag"
else
    section "PHASE 1: Local Agent Tests (Modules 02-04)"

    # ── Step 1: Restore solutions ────────────────────────────────────────
    log ""; log "  --- Restore .backup solutions ---"

    for f in modules/02/strands/server.py \
             modules/02/strands/agent.py \
             modules/03/strands/dataviz.py \
             modules/04/strands/orchestrator_agent.py; do
        if [ -f "$f.backup" ]; then
            cp "$f.backup" "$f" && pass "Restored $f" || fail "cp failed: $f"
        else
            fail "$f.backup not found"
        fi
    done

    # ── Step 2: MCP Server ────────────────────────────────────────────────
    log ""; log "  --- MCP Server test (modules/02/strands) ---"

    OUTPUT=$(run_with_timeout 30 uv run modules/02/strands/test_server.py "$USERNAME" 2>&1)
    echo "$OUTPUT" >> "$LOGFILE"

    if [ $? -eq 0 ] && echo "$OUTPUT" | grep -q "All tests passed"; then
        pass "test_server.py — get_bills works"
    else
        fail "test_server.py"
        log "$(echo "$OUTPUT" | tail -5)"
    fi

    # ── Step 3: Electrify Agent ───────────────────────────────────────────
    log ""; log "  --- Electrify Agent (modules/02/strands) ---"

    OUTPUT=$(printf 'What are the available rate plans?\nquit\n' | \
        run_with_timeout 120 uv run modules/02/strands/agent.py \
        -p modules/02/langgraph/system.md \
        -m "$MODEL" \
        -s uv \
        -a "run modules/02/strands/server.py -e $PGHOST -u $PGUSER --password $PGPASSWORD" \
        -u "$USERNAME" \
        -t "smoketest-strands-agent-$$" 2>&1)
    echo "$OUTPUT" >> "$LOGFILE"

    if echo "$OUTPUT" | grep -qi "rate\|plan\|kwh\|price"; then
        pass "Agent returned rate plan data"
    else
        fail "Agent did not return expected data"
        log "$(echo "$OUTPUT" | tail -10)"
    fi

    rm -rf modules/02/strands/.sessions/smoketest-strands-agent-$$ 2>/dev/null

    # ── Step 4: DataViz Agent ─────────────────────────────────────────────
    log ""; log "  --- DataViz Agent (modules/03/strands) ---"

    OUTPUT=$(printf '"Month,Sales\nJan,1000\nFeb,1200\nMar,800\nApr,1500"\n\nCreate a bar chart showing sales by month\nEND\nquit\n' | \
        run_with_timeout 120 uv run modules/03/strands/dataviz.py \
        -m "$MODEL" 2>&1)
    echo "$OUTPUT" >> "$LOGFILE"

    if echo "$OUTPUT" | grep -qi "chart\|bar\|saved\|created\|visualization"; then
        pass "DataViz agent created a chart"
    else
        fail "DataViz agent did not produce chart output"
        log "$(echo "$OUTPUT" | tail -10)"
    fi

    # ── Step 5: Orchestrator Agent ────────────────────────────────────────
    log ""; log "  --- Orchestrator Agent (modules/04/strands) ---"

    OUTPUT=$(run_with_timeout 30 uv run modules/04/strands/test_orchestrator.py 2>&1)
    echo "$OUTPUT" >> "$LOGFILE"
    [ $? -eq 0 ] && pass "Orchestrator import test" || fail "Orchestrator import test"

    OUTPUT=$(printf 'What rate plans are available?\nquit\n' | \
        run_with_timeout 180 uv run modules/04/strands/orchestrator_agent.py \
        -m "$MODEL" \
        -u "$USERNAME" \
        -t "smoketest-strands-orch-$$" 2>&1)
    echo "$OUTPUT" >> "$LOGFILE"

    if echo "$OUTPUT" | grep -qi "rate\|plan\|kwh\|electrify\|agent"; then
        pass "Orchestrator returned data"
    else
        fail "Orchestrator did not return expected data"
        log "$(echo "$OUTPUT" | tail -10)"
    fi
fi

# =============================================================================
# PHASE 2: Deploy & Test AgentCore (Module 05)
# =============================================================================

if [ "$PHASE3_ONLY" = "true" ]; then
    section "PHASE 2: SKIPPED (AgentCore deployment)"
    skip "Phase 2 skipped by flag"
else
    section "PHASE 2: Deploy & Test AgentCore (Module 05)"

    # ── Preflight for Phase 2 ─────────────────────────────────────────────
    PHASE2_OK=true
    for var in AWS_REGION STACKNAME COGNITO_POOL COGNITO_CLIENT PGHOSTARN PGSECRET PGDATABASE AGENTCORE_ROLE_ARN OAUTH_ISSUER_URL; do
        require_var "$var" || PHASE2_OK=false
    done

    if [ "$PHASE2_OK" != "true" ]; then
        log ""; log "  Phase 2 preflight failed — missing env vars. Skipping."
        skip "Phase 2 skipped due to missing env vars"
    else

    # ── Step 6: Deploy Electrify Lambda ───────────────────────────────────
    log ""; log "  --- Deploy Electrify Lambda ---"

    OUTPUT=$(run_with_timeout 300 uv run modules/05/strands/deploy_lambda.py \
        --server-name electrify-server \
        --db-cluster-arn "$PGHOSTARN" \
        --secret-arn "$PGSECRET" \
        --database "$PGDATABASE" \
        --mcp-server-path modules/05/strands/electrify_server.py \
        --handler electrify_server.lambda_handler \
        --region "$AWS_REGION" 2>&1)
    echo "$OUTPUT" >> "$LOGFILE"

    ELECTRIFY_LAMBDA_ARN=$(aws lambda get-function --function-name electrify-server-function --region "$AWS_REGION" --query 'Configuration.FunctionArn' --output text 2>/dev/null)
    if [ -n "$ELECTRIFY_LAMBDA_ARN" ] && [ "$ELECTRIFY_LAMBDA_ARN" != "None" ]; then
        pass "Electrify Lambda deployed: $ELECTRIFY_LAMBDA_ARN"
    else
        fail "Electrify Lambda deployment failed"
        log "$(echo "$OUTPUT" | tail -10)"
    fi

    # ── Step 7: Deploy DataViz Lambda ─────────────────────────────────────
    log ""; log "  --- Deploy DataViz Lambda ---"

    OUTPUT=$(run_with_timeout 300 uv run modules/05/strands/deploy_lambda.py \
        --server-name dataviz-server \
        --mcp-server-path modules/05/strands/dataviz_server.py \
        --handler dataviz_server.lambda_handler \
        --extra-deps pandas matplotlib \
        --region "$AWS_REGION" 2>&1)
    echo "$OUTPUT" >> "$LOGFILE"

    DATAVIZ_LAMBDA_ARN=$(aws lambda get-function --function-name dataviz-server-function --region "$AWS_REGION" --query 'Configuration.FunctionArn' --output text 2>/dev/null)
    if [ -n "$DATAVIZ_LAMBDA_ARN" ] && [ "$DATAVIZ_LAMBDA_ARN" != "None" ]; then
        pass "DataViz Lambda deployed: $DATAVIZ_LAMBDA_ARN"
    else
        fail "DataViz Lambda deployment failed"
        log "$(echo "$OUTPUT" | tail -10)"
    fi

    # ── Step 8: Deploy AgentCore Gateway ──────────────────────────────────
    log ""; log "  --- Deploy AgentCore Gateway ---"

    if [ -n "$ELECTRIFY_LAMBDA_ARN" ] && [ -n "$DATAVIZ_LAMBDA_ARN" ]; then
        OUTPUT=$(run_with_timeout 600 uv run modules/05/strands/deploy_gateway_simple.py \
            --gateway-name mcp-gateway \
            --electrify-lambda-arn "$ELECTRIFY_LAMBDA_ARN" \
            --dataviz-lambda-arn "$DATAVIZ_LAMBDA_ARN" \
            --cognito-user-pool-id "$COGNITO_POOL" \
            --cognito-client-id "$COGNITO_CLIENT" \
            --region "$AWS_REGION" 2>&1)
        echo "$OUTPUT" >> "$LOGFILE"

        MCP_GATEWAY_URL=$(aws bedrock-agentcore-control list-gateways --region "$AWS_REGION" \
            --query "items[?name=='mcp-gateway'].gatewayId | [0]" --output text 2>/dev/null | \
            xargs -I {} aws bedrock-agentcore-control get-gateway --gateway-identifier {} \
            --region "$AWS_REGION" --query 'gatewayUrl' --output text 2>/dev/null)

        if [ -n "$MCP_GATEWAY_URL" ] && [ "$MCP_GATEWAY_URL" != "None" ]; then
            pass "Gateway deployed: $MCP_GATEWAY_URL"
            export MCP_GATEWAY_URL
        else
            fail "Gateway deployment failed"
            log "$(echo "$OUTPUT" | tail -10)"
        fi
    else
        fail "Skipping gateway — Lambda ARNs missing"
    fi

    # ── Step 9: Get Cognito JWT Token ─────────────────────────────────────
    log ""; log "  --- Authenticate with Cognito ---"

    CLIENT_SECRET=$(aws cognito-idp describe-user-pool-client \
        --user-pool-id "$COGNITO_POOL" --client-id "$COGNITO_CLIENT" \
        --region "$AWS_REGION" --query 'UserPoolClient.ClientSecret' --output text 2>/dev/null)
    COGNITO_USER=$(aws cloudformation describe-stacks --stack-name "$STACKNAME" \
        --region "$AWS_REGION" \
        --query 'Stacks[0].Outputs[?OutputKey==`ApplicationUserEmail`].OutputValue' --output text 2>/dev/null)
    COGNITO_PASSWORD=$(aws cloudformation describe-stacks --stack-name "$STACKNAME" \
        --region "$AWS_REGION" \
        --query 'Stacks[0].Outputs[?OutputKey==`ApplicationUserPassword`].OutputValue' --output text 2>/dev/null)

    if [ -n "$COGNITO_USER" ] && [ -n "$COGNITO_PASSWORD" ]; then
        TOKEN=$(aws cognito-idp initiate-auth \
            --client-id "$COGNITO_CLIENT" \
            --auth-flow USER_PASSWORD_AUTH \
            --auth-parameters "{\"USERNAME\":\"$COGNITO_USER\",\"PASSWORD\":\"$COGNITO_PASSWORD\"}" \
            --region "$AWS_REGION" 2>/dev/null | jq -r '.AuthenticationResult.AccessToken')

        if [ -n "$TOKEN" ] && [ "$TOKEN" != "null" ]; then
            pass "Cognito JWT token obtained (len=${#TOKEN})"
        else
            fail "Failed to get JWT token"
        fi
    else
        fail "Could not retrieve Cognito credentials from stack outputs"
    fi

    # ── Step 10: Test Gateway ─────────────────────────────────────────────
    log ""; log "  --- Test Gateway (tool discovery + invocation) ---"

    if [ -n "$MCP_GATEWAY_URL" ] && [ -n "$TOKEN" ]; then
        OUTPUT=$(run_with_timeout 60 uv run modules/05/strands/test_gateway_auth.py \
            --gateway-url "$MCP_GATEWAY_URL" \
            --token "$TOKEN" 2>&1)
        echo "$OUTPUT" >> "$LOGFILE"

        if echo "$OUTPUT" | grep -qi "Found.*tools\|tools:"; then
            pass "Gateway tool discovery works"
        else
            fail "Gateway tool discovery failed"
            log "$(echo "$OUTPUT" | tail -10)"
        fi

        # Test get_bills via gateway
        OUTPUT=$(run_with_timeout 60 uv run modules/05/strands/test_gateway_auth.py \
            --gateway-url "$MCP_GATEWAY_URL" \
            --token "$TOKEN" \
            --tool "electrify-server-function___get_bills" \
            --tool-args '{"customer_username": "rroe@example.com", "limit": 3}' 2>&1)
        echo "$OUTPUT" >> "$LOGFILE"

        if echo "$OUTPUT" | grep -qi "bill\|amount\|result"; then
            pass "Gateway get_bills invocation works"
        else
            fail "Gateway get_bills invocation failed"
            log "$(echo "$OUTPUT" | tail -10)"
        fi
    else
        skip "Gateway test skipped — missing URL or token"
    fi

    # ── Step 11: Deploy Agent to AgentCore Runtime ────────────────────────
    log ""; log "  --- Deploy Agent to AgentCore Runtime ---"

    if [ -n "$MCP_GATEWAY_URL" ]; then
        cd ~/workshop/modules/05/strands 2>/dev/null || cd modules/05/strands

        OUTPUT=$(run_with_timeout 60 uv run agentcore configure \
            --name electrify_assistant \
            --protocol HTTP \
            --entrypoint agentcore_runtime_adapter.py \
            --requirements-file requirements.txt \
            --non-interactive \
            --region "$AWS_REGION" \
            --execution-role "$AGENTCORE_ROLE_ARN" \
            --authorizer-config "{\"customJWTAuthorizer\": {\"discoveryUrl\": \"$OAUTH_ISSUER_URL\", \"allowedClients\": [\"$COGNITO_CLIENT\"]}}" 2>&1)
        echo "$OUTPUT" >> "$LOGFILE"
        pass "Agent configured"

        OUTPUT=$(run_with_timeout 600 uv run agentcore launch \
            --agent electrify_assistant \
            --env MCP_GATEWAY_URL="$MCP_GATEWAY_URL" \
            --env AGENT_MODEL_ID="$MODEL" 2>&1)
        echo "$OUTPUT" >> "$LOGFILE"

        cd ~/workshop 2>/dev/null || cd - >/dev/null

        AGENT_RUNTIME_ID=$(aws bedrock-agentcore-control list-agent-runtimes --region "$AWS_REGION" \
            --query "agentRuntimes[?agentRuntimeName=='electrify_assistant'].agentRuntimeId | [0]" --output text 2>/dev/null)

        if [ -n "$AGENT_RUNTIME_ID" ] && [ "$AGENT_RUNTIME_ID" != "None" ]; then
            pass "Agent deployed to runtime: $AGENT_RUNTIME_ID"
        else
            fail "Agent deployment to runtime failed"
            log "$(echo "$OUTPUT" | tail -10)"
        fi
    else
        skip "Agent deployment skipped — no gateway URL"
    fi

    # ── Step 12: Test Agent via Runtime ───────────────────────────────────
    log ""; log "  --- Test Agent via AgentCore Runtime ---"

    if [ -n "$AGENT_RUNTIME_ID" ] && [ -n "$TOKEN" ]; then
        # Test 1: Rate plans query
        OUTPUT=$(run_with_timeout 120 uv run modules/05/strands/test_runtime.py \
            --runtime-id "$AGENT_RUNTIME_ID" \
            --prompt "What rate plans are available?" \
            --token "$TOKEN" \
            --stream 2>&1)
        echo "$OUTPUT" >> "$LOGFILE"

        if echo "$OUTPUT" | grep -qi "rate\|plan\|kwh\|price\|standard\|green"; then
            pass "Runtime agent: rate plans query"
        else
            fail "Runtime agent: rate plans query"
            log "$(echo "$OUTPUT" | tail -10)"
        fi

        # Test 2: User-specific billing query
        OUTPUT=$(run_with_timeout 120 uv run modules/05/strands/test_runtime.py \
            --runtime-id "$AGENT_RUNTIME_ID" \
            --prompt "What was my last month's bill?" \
            --token "$TOKEN" \
            --stream 2>&1)
        echo "$OUTPUT" >> "$LOGFILE"

        if echo "$OUTPUT" | grep -qi "bill\|amount\|\$\|kwh\|usage"; then
            pass "Runtime agent: billing query"
        else
            fail "Runtime agent: billing query"
            log "$(echo "$OUTPUT" | tail -10)"
        fi
    else
        skip "Runtime agent test skipped — missing runtime ID or token"
    fi

    fi # end PHASE2_OK
fi # end Phase 2

# =============================================================================
# PHASE 3: Policies (Module 06 / Content 10)
# =============================================================================

if [ "$PHASE2_ONLY" = "true" ]; then
    section "PHASE 3: SKIPPED (policies)"
    skip "Phase 3 skipped by flag"
else
    section "PHASE 3: Policy Engine (Module 06)"

    # Get gateway info if not already set
    if [ -z "$MCP_GATEWAY_URL" ]; then
        MCP_GATEWAY_URL=$(aws bedrock-agentcore-control list-gateways --region "$AWS_REGION" \
            --query "items[?name=='mcp-gateway'].gatewayId | [0]" --output text 2>/dev/null | \
            xargs -I {} aws bedrock-agentcore-control get-gateway --gateway-identifier {} \
            --region "$AWS_REGION" --query 'gatewayUrl' --output text 2>/dev/null)
    fi

    GATEWAY_ID=$(aws bedrock-agentcore-control list-gateways --region "$AWS_REGION" \
        --query "items[?name=='mcp-gateway'].gatewayId | [0]" --output text 2>/dev/null)
    GATEWAY_ARN=$(aws bedrock-agentcore-control get-gateway --gateway-identifier "$GATEWAY_ID" \
        --region "$AWS_REGION" --query 'gatewayArn' --output text 2>/dev/null)

    # Get token if not already set
    if [ -z "$TOKEN" ]; then
        COGNITO_USER=$(aws cloudformation describe-stacks --stack-name "$STACKNAME" \
            --region "$AWS_REGION" \
            --query 'Stacks[0].Outputs[?OutputKey==`ApplicationUserEmail`].OutputValue' --output text 2>/dev/null)
        COGNITO_PASSWORD=$(aws cloudformation describe-stacks --stack-name "$STACKNAME" \
            --region "$AWS_REGION" \
            --query 'Stacks[0].Outputs[?OutputKey==`ApplicationUserPassword`].OutputValue' --output text 2>/dev/null)
        TOKEN=$(aws cognito-idp initiate-auth \
            --client-id "$COGNITO_CLIENT" \
            --auth-flow USER_PASSWORD_AUTH \
            --auth-parameters "{\"USERNAME\":\"$COGNITO_USER\",\"PASSWORD\":\"$COGNITO_PASSWORD\"}" \
            --region "$AWS_REGION" 2>/dev/null | jq -r '.AuthenticationResult.AccessToken')
    fi

    if [ -z "$GATEWAY_ID" ] || [ "$GATEWAY_ID" = "None" ] || [ -z "$TOKEN" ] || [ "$TOKEN" = "null" ]; then
        log "  Phase 3 requires a deployed gateway and valid token."
        skip "Phase 3 skipped — gateway or token not available"
    else

    # ── Step 13: Add IAM permission for policy engine ─────────────────────
    log ""; log "  --- Add IAM permission for policy engine ---"

    ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
    aws iam put-role-policy \
        --role-name mcp-gateway-role \
        --policy-name mcp-gateway-policy-engine \
        --policy-document "{
            \"Version\": \"2012-10-17\",
            \"Statement\": [{
                \"Effect\": \"Allow\",
                \"Action\": [
                    \"bedrock-agentcore:AuthorizeAction\",
                    \"bedrock-agentcore:GetPolicyEngine\",
                    \"bedrock-agentcore:CheckAuthorizePermissions\",
                    \"bedrock-agentcore:PartiallyAuthorizeActions\"
                ],
                \"Resource\": [
                    \"arn:aws:bedrock-agentcore:${AWS_REGION}:${ACCOUNT_ID}:gateway/*\",
                    \"arn:aws:bedrock-agentcore:${AWS_REGION}:${ACCOUNT_ID}:policy-engine/*\"
                ]
            }]
        }" --region "$AWS_REGION" 2>&1 | tee -a "$LOGFILE"
    [ ${PIPESTATUS[0]} -eq 0 ] && pass "IAM policy for policy engine" || fail "IAM policy for policy engine"

    # ── Step 14: Deploy Policy Engine ─────────────────────────────────────
    log ""; log "  --- Deploy Policy Engine ---"

    OUTPUT=$(run_with_timeout 300 uv run modules/06/deploy_policy.py \
        --gateway-id "$GATEWAY_ID" \
        --gateway-arn "$GATEWAY_ARN" \
        --region "$AWS_REGION" 2>&1)
    echo "$OUTPUT" >> "$LOGFILE"

    if echo "$OUTPUT" | grep -qi "Deployment complete\|Policy Engine ID"; then
        pass "Policy engine deployed"
    else
        fail "Policy engine deployment"
        log "$(echo "$OUTPUT" | tail -10)"
    fi

    # ── Step 15: Test Policy Enforcement ──────────────────────────────────
    log ""; log "  --- Test Policy Enforcement ---"

    OUTPUT=$(run_with_timeout 120 uv run modules/06/test_policy.py \
        --gateway-url "$MCP_GATEWAY_URL" \
        --token "$TOKEN" 2>&1)
    echo "$OUTPUT" >> "$LOGFILE"

    if echo "$OUTPUT" | grep -qi "ALLOWED\|DENIED"; then
        pass "Policy test suite ran"
        # Check for unexpected results
        if echo "$OUTPUT" | grep -qi "UNEXPECTEDLY"; then
            fail "Policy test had unexpected results"
            log "$(echo "$OUTPUT" | grep -i "UNEXPECTEDLY")"
        else
            pass "All policy tests matched expectations"
        fi
    else
        fail "Policy test suite failed to run"
        log "$(echo "$OUTPUT" | tail -10)"
    fi

    # ── Step 16: Query Policy Observability ───────────────────────────────
    log ""; log "  --- Query Policy Observability ---"

    OUTPUT=$(run_with_timeout 60 uv run modules/06/query_policy_logs.py \
        --gateway-id "$GATEWAY_ID" \
        --region "$AWS_REGION" \
        --hours 1 2>&1)
    echo "$OUTPUT" >> "$LOGFILE"

    if echo "$OUTPUT" | grep -qi "Policy Decision Summary\|Active Cedar Policies\|Done"; then
        pass "Policy observability query"
    else
        fail "Policy observability query"
        log "$(echo "$OUTPUT" | tail -10)"
    fi

    # ── Step 17: Clean Up Policy Engine ───────────────────────────────────
    log ""; log "  --- Clean Up Policy Engine ---"

    POLICY_ENGINE_ID=$(aws bedrock-agentcore-control list-policy-engines --region "$AWS_REGION" \
        --query "policyEngines[?name=='electrify_policy_engine'].policyEngineId | [0]" --output text 2>/dev/null)

    if [ -n "$POLICY_ENGINE_ID" ] && [ "$POLICY_ENGINE_ID" != "None" ]; then
        # Delete all policies
        for POLICY_ID in $(aws bedrock-agentcore-control list-policies \
            --policy-engine-id "$POLICY_ENGINE_ID" --region "$AWS_REGION" \
            --query "policies[].policyId" --output text 2>/dev/null); do
            aws bedrock-agentcore-control delete-policy \
                --policy-engine-id "$POLICY_ENGINE_ID" \
                --policy-id "$POLICY_ID" \
                --region "$AWS_REGION" 2>/dev/null
        done

        # Wait for policies to be deleted
        for i in $(seq 1 24); do
            REMAINING=$(aws bedrock-agentcore-control list-policies \
                --policy-engine-id "$POLICY_ENGINE_ID" --region "$AWS_REGION" \
                --query "length(policies)" --output text 2>/dev/null)
            if [ "$REMAINING" = "0" ] || [ "$REMAINING" = "None" ] || [ -z "$REMAINING" ]; then
                break
            fi
            sleep 5
        done
        pass "All policies deleted"

        # Detach policy engine from gateway (update gateway without policyEngineConfiguration)
        GW_NAME=$(aws bedrock-agentcore-control get-gateway --gateway-identifier "$GATEWAY_ID" --region "$AWS_REGION" --query 'name' --output text 2>/dev/null)
        GW_ROLE=$(aws bedrock-agentcore-control get-gateway --gateway-identifier "$GATEWAY_ID" --region "$AWS_REGION" --query 'roleArn' --output text 2>/dev/null)
        GW_PROTOCOL=$(aws bedrock-agentcore-control get-gateway --gateway-identifier "$GATEWAY_ID" --region "$AWS_REGION" --query 'protocolType' --output text 2>/dev/null)
        GW_AUTH_TYPE=$(aws bedrock-agentcore-control get-gateway --gateway-identifier "$GATEWAY_ID" --region "$AWS_REGION" --query 'authorizerType' --output text 2>/dev/null)
        GW_AUTH_CONFIG=$(aws bedrock-agentcore-control get-gateway --gateway-identifier "$GATEWAY_ID" --region "$AWS_REGION" --query 'authorizerConfiguration' --output json 2>/dev/null)

        aws bedrock-agentcore-control update-gateway \
            --gateway-identifier "$GATEWAY_ID" \
            --name "$GW_NAME" \
            --role-arn "$GW_ROLE" \
            --protocol-type "$GW_PROTOCOL" \
            --authorizer-type "$GW_AUTH_TYPE" \
            --authorizer-configuration "$GW_AUTH_CONFIG" \
            --region "$AWS_REGION" 2>&1 >> "$LOGFILE"
        pass "Policy engine detached from gateway"

        # Delete the policy engine
        aws bedrock-agentcore-control delete-policy-engine \
            --policy-engine-id "$POLICY_ENGINE_ID" \
            --region "$AWS_REGION" 2>&1 >> "$LOGFILE"
        pass "Policy engine deleted"
    else
        skip "No policy engine to clean up"
    fi

    fi # end gateway/token check
fi # end Phase 3

# ── Summary ─────────────────────────────────────────────────────────────────

section "RESULTS"
log "  Passed:  $PASS"
log "  Failed:  $FAIL"
log "  Skipped: $SKIP"
log "  Log:     $LOGFILE"

if [ $FAIL -gt 0 ]; then
    log ""; log "  $FAIL test(s) failed. See $LOGFILE"; exit 1
else
    log ""; log "  All $PASS tests passed! ($SKIP skipped)"; exit 0
fi
