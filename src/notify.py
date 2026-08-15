"""Formats findings into a readable report and publishes it to SNS."""

import os
import boto3


def build_report(findings, total_waste, actual_spend):
    """Turn findings into a human-readable email body."""
    if not findings:
        return "✅ AWS Cost Guardian\n\nNo waste found — your account is clean!"

    lines = [
        "💰 AWS Cost Guardian — Daily Report",
        "",
        f"Findings:        {len(findings)}",
        f"Monthly waste:   ${total_waste}",
        f"Last 30d spend:  ${actual_spend}",
        "",
        "Details:",
    ]
    # most expensive first — that's what people act on
    for f in sorted(findings, key=lambda x: x.get("monthly_cost_usd", 0), reverse=True):
        lines.append(
            f"  • ${f.get('monthly_cost_usd', 0):>7.2f}/mo  "
            f"[{f['type']}] {f['id']} — {f['detail']}"
        )
    lines += ["", "Review these resources and delete anything you no longer need."]
    return "\n".join(lines)


def send_report(subject, body):
    """Publish the report to the SNS topic (ARN comes from an env var)."""
    topic_arn = os.environ.get("SNS_TOPIC_ARN")
    if not topic_arn:
        print("No SNS_TOPIC_ARN set — skipping notification")
        return
    boto3.client("sns").publish(
        TopicArn=topic_arn, Subject=subject[:100], Message=body
    )
    print("Report sent to SNS")