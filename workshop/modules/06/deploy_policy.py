#!/usr/bin/env python3
"""
Deploy AgentCore Policy Engine with Cedar policies for the Electrify workshop.

This script creates a Policy Engine, adds Cedar policies for the remaining
tools (the billing limit and pie chart block policies are created manually
via CLI using natural language generation), and attaches the engine to an
existing AgentCore Gateway in ENFORCE mode.

Usage:
    uv run modules/06/deploy_policy.py \
        --gateway-id <gateway-id> \
        --gateway-arn <gateway-arn> \
        --region us-east-1

Policies created by this script (6 of 8):
    - allow_get_rates       — permits get_rates
    - allow_get_customer    — permits get_customer
    - allow_bar_chart       — permits create_bar_chart
    - allow_line_chart      — permits create_line_chart
    - allow_scatter_plot    — permits create_scatter_plot
    - allow_analyze_data    — permits analyze_data_structure

Policies created manually via CLI before running this script (2 of 8):
    - billing_query_limit   — caps get_bills limit to < 100 (NL-generated)
    - block_pie_charts      — forbids create_pie_chart (NL-generated)
"""

import argparse
import boto3
import time


def wait_for_policy_engine(client, engine_id, max_wait=120, interval=10):
    """Wait for a policy engine to become ACTIVE."""
    elapsed = 0
    while elapsed < max_wait:
        resp = client.get_policy_engine(policyEngineId=engine_id)
        status = resp.get("status", "UNKNOWN")
        print(f"  Policy engine status: {status} ({elapsed}s)")
        if status == "ACTIVE":
            return
        time.sleep(interval)
        elapsed += interval
    raise TimeoutError(f"Policy engine {engine_id} did not become ACTIVE within {max_wait}s")


def wait_for_policy(client, engine_id, policy_id, max_wait=120, interval=10):
    """Wait for a policy to become ACTIVE."""
    elapsed = 0
    while elapsed < max_wait:
        resp = client.get_policy(policyEngineId=engine_id, policyId=policy_id)
        status = resp.get("status", "UNKNOWN")
        print(f"  Policy status: {status} ({elapsed}s)")
        if status == "ACTIVE":
            return
        if status == "CREATE_FAILED":
            error_msg = resp.get("statusReasons", resp.get("failureReason", "Unknown error"))
            raise RuntimeError(f"Policy {policy_id} creation failed: {error_msg}")
        time.sleep(interval)
        elapsed += interval
    raise TimeoutError(f"Policy {policy_id} did not become ACTIVE within {max_wait}s")


def create_policy_engine(client, name="electrify_policy_engine"):
    """Create or retrieve an existing policy engine."""
    try:
        engines = client.list_policy_engines()
        for engine in engines.get("policyEngines", []):
            if engine["name"] == name:
                print(f"  Reusing existing policy engine: {engine['policyEngineId']}")
                return engine["policyEngineId"], engine["policyEngineArn"]
    except Exception:
        pass

    print(f"  Creating policy engine: {name}")
    resp = client.create_policy_engine(
        name=name,
        description="Electrify workshop policy engine — enforces billing query limits and role-based access"
    )
    engine_id = resp["policyEngineId"]
    engine_arn = resp["policyEngineArn"]
    print(f"  Engine ID: {engine_id}")

    wait_for_policy_engine(client, engine_id)
    return engine_id, engine_arn


def create_or_reuse_policy(client, engine_id, name, description, cedar_statement):
    """Create a policy or reuse if it already exists."""
    try:
        resp = client.create_policy(
            policyEngineId=engine_id,
            name=name,
            description=description,
            validationMode="IGNORE_ALL_FINDINGS",
            definition={"cedar": {"statement": cedar_statement}},
        )
        policy_id = resp["policyId"]
        wait_for_policy(client, engine_id, policy_id)
        return policy_id
    except client.exceptions.ConflictException:
        for p in client.list_policies(policyEngineId=engine_id).get("policies", []):
            if p["name"] == name:
                print(f"    Reusing existing policy: {name}")
                return p["policyId"]
        raise


def create_remaining_cedar_policies(client, engine_id, gateway_arn):
    """Create the remaining 6 Cedar policies directly (simple permits).

    The billing_query_limit and block_pie_charts policies are created
    manually via CLI using natural language generation before this script runs.
    """
    policies = []

    # Simple permit policies — these don't need conditions, so direct Cedar is fine
    simple_permits = [
        ("allow_get_rates", "get_rates", "electrify-server-function"),
        ("allow_get_customer", "get_customer", "electrify-server-function"),
        ("allow_bar_chart", "create_bar_chart", "dataviz-server-function"),
        ("allow_line_chart", "create_line_chart", "dataviz-server-function"),
        ("allow_scatter_plot", "create_scatter_plot", "dataviz-server-function"),
        ("allow_analyze_data", "analyze_data_structure", "dataviz-server-function"),
    ]

    for policy_name, tool_name, target_name in simple_permits:
        cedar = (
            f'permit(principal, '
            f'action == AgentCore::Action::"{target_name}___{tool_name}", '
            f'resource == AgentCore::Gateway::"{gateway_arn}");'
        )
        print(f"  Creating policy: {policy_name}")
        pid = create_or_reuse_policy(client, engine_id, policy_name,
                                      f"Allow {tool_name}", cedar)
        policies.append({"name": policy_name, "id": pid})

    return policies


def verify_nl_policies_exist(client, engine_id):
    """Verify that the manually-created NL-generated policies exist."""
    existing = {p["name"] for p in client.list_policies(policyEngineId=engine_id).get("policies", [])}
    required = ["billing_query_limit", "block_pie_charts"]
    missing = [p for p in required if p not in existing]

    if missing:
        print(f"\n  ⚠  Missing NL-generated policies: {', '.join(missing)}")
        print("  These should have been created via CLI before running this script.")
        print("  The script will continue, but policy enforcement may be incomplete.")
        return False
    else:
        print("  ✅ NL-generated policies found: billing_query_limit, block_pie_charts")
        return True


def attach_engine_to_gateway(client, gateway_id, engine_arn, mode="ENFORCE"):
    """Attach the policy engine to the gateway."""
    print(f"\n  Attaching policy engine to gateway in {mode} mode...")
    gw = client.get_gateway(gatewayIdentifier=gateway_id)
    update_kwargs = dict(
        gatewayIdentifier=gateway_id,
        name=gw["name"],
        roleArn=gw["roleArn"],
        protocolType=gw["protocolType"],
        authorizerType=gw["authorizerType"],
        policyEngineConfiguration={
            "mode": mode,
            "arn": engine_arn,
        },
    )
    if "authorizerConfiguration" in gw:
        update_kwargs["authorizerConfiguration"] = gw["authorizerConfiguration"]
    client.update_gateway(**update_kwargs)
    print("  Policy engine attached.")


def main():
    parser = argparse.ArgumentParser(description="Deploy AgentCore Policy Engine for Electrify workshop")
    parser.add_argument("--gateway-id", required=True, help="AgentCore Gateway ID")
    parser.add_argument("--gateway-arn", required=True, help="AgentCore Gateway ARN")
    parser.add_argument("--region", default="us-east-1", help="AWS region")
    parser.add_argument("--mode", default="ENFORCE", choices=["ENFORCE", "MONITOR"],
                        help="Policy mode: ENFORCE blocks denied requests, MONITOR only logs")
    parser.add_argument("--engine-name", default="electrify_policy_engine",
                        help="Name for the policy engine")
    args = parser.parse_args()

    client = boto3.client("bedrock-agentcore-control", region_name=args.region)

    print("=" * 60)
    print("Deploying AgentCore Policy Engine for Electrify Workshop")
    print("=" * 60)

    # Step 1: Create or reuse policy engine
    print("\nStep 1: Create policy engine")
    engine_id, engine_arn = create_policy_engine(client, name=args.engine_name)

    # Step 2: Verify NL-generated policies exist
    print("\nStep 2: Verify NL-generated policies (billing_query_limit, block_pie_charts)")
    verify_nl_policies_exist(client, engine_id)

    # Step 3: Create remaining Cedar policies
    print("\nStep 3: Create remaining Cedar policies (6 simple permits)")
    policies = create_remaining_cedar_policies(client, engine_id, args.gateway_arn)

    # Step 4: Attach to gateway
    print("\nStep 4: Attach policy engine to gateway")
    attach_engine_to_gateway(client, args.gateway_id, engine_arn, mode=args.mode)

    # Summary
    all_policies = client.list_policies(policyEngineId=engine_id).get("policies", [])
    print("\n" + "=" * 60)
    print("Deployment complete!")
    print(f"  Policy Engine ID:  {engine_id}")
    print(f"  Policy Engine ARN: {engine_arn}")
    print(f"  Mode:              {args.mode}")
    print(f"  Total policies:    {len(all_policies)}")
    for p in all_policies:
        print(f"    - {p['name']} ({p['policyId']})")
    print("=" * 60)


if __name__ == "__main__":
    main()
