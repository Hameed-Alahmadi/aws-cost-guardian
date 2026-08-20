"""Reads what the account actually spent, via Cost Explorer."""

import boto3
from datetime import date, timedelta


def last_30_days_spend():
    """Total unblended cost for the last 30 days. Returns 0.0 if unavailable."""
    ce = boto3.client("ce", region_name="us-east-1")
    end = date.today()
    start = end - timedelta(days=30)
    try:
        resp = ce.get_cost_and_usage(
            TimePeriod={"Start": start.isoformat(), "End": end.isoformat()},
            Granularity="MONTHLY",
            Metrics=["UnblendedCost"],
        )
        total = sum(
            float(r["Total"]["UnblendedCost"]["Amount"]) for r in resp["ResultsByTime"]
        )
        return max(0.0, round(total, 2))
    except Exception as e:      # Cost Explorer not enabled yet, or no permission
        print(f"Cost Explorer unavailable: {e}")
        return 0.0