#!/usr/bin/env python3
"""
Query CloudWatch for AgentCore Policy evaluation data.

Retrieves policy metrics (allow/deny counts, per-tool breakdown),
gateway UserErrors (which surface policy denials), and current
policy engine configuration.

Usage:
    uv run modules/06/query_policy_logs.py \
        --gateway-id <gateway-id> \
        --region us-east-1 \
        --hours 1
"""

import argparse
import boto3
from datetime import datetime, timedelta, timezone


def get_metric_sum(cloudwatch, namespace, metric_name, dimensions, start, end, period=3600):
    """Get sum of a metric over a time range."""
    resp = cloudwatch.get_metric_statistics(
        Namespace=namespace,
        MetricName=metric_name,
        Dimensions=dimensions,
        StartTime=start,
        EndTime=end,
        Period=period,
        Statistics=["Sum"],
    )
    datapoints = resp.get("Datapoints", [])
    if not datapoints:
        return None
    return sum(d["Sum"] for d in datapoints)


def query_policy_decisions(cloudwatch, policy_engine_id, start, end):
    """Query AllowDecisions, DenyDecisions, and TotalMismatchedPolicies."""
    dims = [
        {"Name": "PolicyEngine", "Value": policy_engine_id},
        {"Name": "OperationName", "Value": "AuthorizeAction"},
    ]
    allows = get_metric_sum(cloudwatch, "AWS/Bedrock-AgentCore", "AllowDecisions", dims, start, end)
    denies = get_metric_sum(cloudwatch, "AWS/Bedrock-AgentCore", "DenyDecisions", dims, start, end)
    mismatched = get_metric_sum(cloudwatch, "AWS/Bedrock-AgentCore", "TotalMismatchedPolicies", dims, start, end)
    return allows, denies, mismatched


def query_per_tool_errors(cloudwatch, gateway_arn, start, end):
    """Query UserErrors per tool to identify which tools are being denied."""
    tools = [
        "electrify-server-function___get_bills",
        "electrify-server-function___get_rates",
        "electrify-server-function___get_customer",
        "dataviz-server-function___analyze_data_structure",
        "dataviz-server-function___create_bar_chart",
        "dataviz-server-function___create_line_chart",
        "dataviz-server-function___create_scatter_plot",
        "dataviz-server-function___create_pie_chart",
    ]
    results = []
    for tool in tools:
        dims = [
            {"Name": "Resource", "Value": gateway_arn},
            {"Name": "Operation", "Value": "InvokeGateway"},
            {"Name": "Method", "Value": "tools/call"},
            {"Name": "Protocol", "Value": "MCP"},
            {"Name": "Name", "Value": tool},
        ]
        errors = get_metric_sum(cloudwatch, "AWS/Bedrock-AgentCore", "UserErrors", dims, start, end)
        exec_time = get_metric_sum(cloudwatch, "AWS/Bedrock-AgentCore", "TargetExecutionTime", dims, start, end)
        if errors is not None or exec_time is not None:
            results.append({
                "tool": tool.split("___")[1],
                "server": tool.split("___")[0],
                "errors": errors or 0,
                "has_execution": exec_time is not None,
            })
    return results


def query_hourly_trend(cloudwatch, policy_engine_id, start, end):
    """Get hourly allow/deny trend."""
    dims = [
        {"Name": "PolicyEngine", "Value": policy_engine_id},
        {"Name": "OperationName", "Value": "AuthorizeAction"},
    ]
    trend = []
    for metric in ["AllowDecisions", "DenyDecisions"]:
        resp = cloudwatch.get_metric_statistics(
            Namespace="AWS/Bedrock-AgentCore",
            MetricName=metric,
            Dimensions=dims,
            StartTime=start,
            EndTime=end,
            Period=3600,
            Statistics=["Sum"],
        )
        for dp in resp.get("Datapoints", []):
            trend.append({
                "time": dp["Timestamp"],
                "metric": metric,
                "value": int(dp["Sum"]),
            })
    trend.sort(key=lambda x: x["time"])
    return trend


def get_policy_config(agentcore, policy_engine_id):
    """List all policies in the engine."""
    policies = agentcore.list_policies(policyEngineId=policy_engine_id).get("policies", [])
    return policies


def main():
    parser = argparse.ArgumentParser(description="Query AgentCore Policy observability data")
    parser.add_argument("--gateway-id", required=True, help="AgentCore Gateway ID")
    parser.add_argument("--policy-engine-id", default=None, help="Policy Engine ID (auto-detected if omitted)")
    parser.add_argument("--region", default="us-east-1")
    parser.add_argument("--hours", type=int, default=1, help="Lookback hours (default: 1)")
    args = parser.parse_args()

    cloudwatch = boto3.client("cloudwatch", region_name=args.region)
    agentcore = boto3.client("bedrock-agentcore-control", region_name=args.region)

    # Auto-detect policy engine
    policy_engine_id = args.policy_engine_id
    if not policy_engine_id:
        print("  Auto-detecting policy engine ID...")
        for engine in agentcore.list_policy_engines().get("policyEngines", []):
            if engine["name"] == "electrify_policy_engine":
                policy_engine_id = engine["policyEngineId"]
                break
        if not policy_engine_id:
            print("  Could not auto-detect policy engine. Use --policy-engine-id.")
            return

    # Get gateway ARN
    gw = agentcore.get_gateway(gatewayIdentifier=args.gateway_id)
    gateway_arn = gw["gatewayArn"]
    policy_config = gw.get("policyEngineConfiguration", {})

    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(hours=args.hours)

    print("=" * 60)
    print("AgentCore Policy Observability")
    print("=" * 60)
    print(f"  Gateway ID:      {args.gateway_id}")
    print(f"  Policy Engine:   {policy_engine_id}")
    print(f"  Policy Mode:     {policy_config.get('mode', 'NOT ATTACHED')}")
    print(f"  Region:          {args.region}")
    print(f"  Lookback:        {args.hours}h")
    print(f"  Time range:      {start_time.strftime('%H:%M:%S')} — {end_time.strftime('%H:%M:%S')} UTC")

    # ── Section 1: Policy Decision Metrics ──
    print(f"\n{'─' * 60}")
    print("Policy Decision Summary")
    print("─" * 60)

    allows, denies, mismatched = query_policy_decisions(cloudwatch, policy_engine_id, start_time, end_time)
    total = (allows or 0) + (denies or 0)

    print(f"  ✅ AllowDecisions:         {int(allows) if allows else 0}")
    print(f"  ❌ DenyDecisions:          {int(denies) if denies else 0}")
    print(f"  📊 Total evaluations:      {total}")
    if total > 0:
        print(f"  📈 Deny rate:              {(denies or 0) / total * 100:.1f}%")
    if mismatched is not None:
        print(f"  ⚠  MismatchedPolicies:     {int(mismatched)}")

    # ── Section 2: Per-Tool Breakdown ──
    print(f"\n{'─' * 60}")
    print("Per-Tool Gateway Activity")
    print("─" * 60)
    print(f"  {'Tool':<30s} {'Errors':>8s}  {'Executed':>8s}")
    print(f"  {'─' * 30} {'─' * 8}  {'─' * 8}")

    tool_results = query_per_tool_errors(cloudwatch, gateway_arn, start_time, end_time)
    if tool_results:
        for t in tool_results:
            err_str = str(int(t["errors"])) if t["errors"] else "0"
            exec_str = "yes" if t["has_execution"] else "—"
            marker = " ⚠" if t["errors"] and t["errors"] > 0 else ""
            print(f"  {t['tool']:<30s} {err_str:>8s}  {exec_str:>8s}{marker}")
    else:
        print("  No per-tool data found in this time range.")

    print()
    print("  Errors = UserErrors metric (includes policy denials + auth failures)")
    print("  Executed = TargetExecutionTime present (tool reached the backend)")
    print("  Tools with errors but no execution → likely policy-denied")

    # ── Section 3: Hourly Trend ──
    print(f"\n{'─' * 60}")
    print("Hourly Decision Trend")
    print("─" * 60)

    trend = query_hourly_trend(cloudwatch, policy_engine_id, start_time, end_time)
    if trend:
        # Group by hour
        hours = {}
        for t in trend:
            h = t["time"].strftime("%H:%M")
            if h not in hours:
                hours[h] = {"allow": 0, "deny": 0}
            if "Allow" in t["metric"]:
                hours[h]["allow"] = t["value"]
            else:
                hours[h]["deny"] = t["value"]

        print(f"  {'Hour':>8s}  {'Allow':>6s}  {'Deny':>6s}  {'Visual'}")
        print(f"  {'─' * 8}  {'─' * 6}  {'─' * 6}  {'─' * 30}")
        for h, v in sorted(hours.items()):
            bar_a = "█" * min(v["allow"], 30)
            bar_d = "░" * min(v["deny"], 30)
            print(f"  {h:>8s}  {v['allow']:>6d}  {v['deny']:>6d}  {bar_a}{bar_d}")
    else:
        print("  No hourly data available yet.")

    # ── Section 4: Active Policies ──
    print(f"\n{'─' * 60}")
    print("Active Cedar Policies")
    print("─" * 60)

    policies = get_policy_config(agentcore, policy_engine_id)
    if policies:
        for p in policies:
            effect = "🚫 FORBID" if "forbid" in p.get("name", "").lower() or "block" in p.get("name", "").lower() else "✅ PERMIT"
            status = p.get("status", "UNKNOWN")
            print(f"  {effect}  {p['name']:<30s}  [{status}]")
    else:
        print("  No policies found.")

    print("\n" + "=" * 60)
    print("Done.")
    print("=" * 60)


if __name__ == "__main__":
    main()
