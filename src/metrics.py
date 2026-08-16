"""Structured logs and CloudWatch custom metrics via Embedded Metric Format (EMF)."""

import json
from datetime import datetime, timezone


def log_event(event, **fields):
    """Emit one structured JSON log line — queryable in Logs Insights."""
    print(json.dumps({
        "event": event,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        **fields,
    }))


def emit_metrics(finding_count, monthly_waste_usd):
    """Publish custom metrics by printing EMF — CloudWatch parses it automatically."""
    print(json.dumps({
        "_aws": {
            "Timestamp": int(datetime.now(timezone.utc).timestamp() * 1000),
            "CloudWatchMetrics": [{
                "Namespace": "CostGuardian",
                "Dimensions": [[]],
                "Metrics": [
                    {"Name": "FindingCount", "Unit": "Count"},
                    {"Name": "MonthlyWasteUsd", "Unit": "None"},
                ],
            }],
        },
        "FindingCount": finding_count,
        "MonthlyWasteUsd": monthly_waste_usd,
    }))