"""Persists each scan result to DynamoDB so we can see trends over time."""

import os
import boto3
from boto3.dynamodb.conditions import Key      # needed for query() — import it explicitly
from decimal import Decimal
from datetime import datetime, timezone, timedelta

def _to_decimal(obj):
    """Recursively convert floats to Decimal for DynamoDB."""
    if isinstance(obj, float):
        return Decimal(str(obj))
    if isinstance(obj, list):
        return [_to_decimal(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _to_decimal(v) for k, v in obj.items()}
    return obj

def save_scan(findings, total_waste, actual_spend):
    """Write one scan summary. Returns False if no table is configured."""
    table_name = os.environ.get("DDB_TABLE")
    if not table_name:
        print("No DDB_TABLE set — skipping save")
        return False

    table = boto3.resource("dynamodb").Table(table_name)
    now = datetime.now(timezone.utc)

    table.put_item(Item={
        "scan_date": now.date().isoformat(),          # partition key
        "timestamp": now.isoformat(),                  # sort key
        "finding_count": len(findings),
        # DynamoDB stores decimals, not floats
        "monthly_waste_usd": Decimal(str(total_waste)),
        "last_30d_spend_usd": Decimal(str(actual_spend)),
        "findings": _to_decimal(findings),
        # auto-delete this item after 90 days
        "expires_at": int((now + timedelta(days=90)).timestamp()),
    })
    print(f"Saved scan to {table_name}")
    return True


def recent_scans(days=7):
    """Read the last N days of scans, newest first — used to show a trend."""
    table_name = os.environ.get("DDB_TABLE")
    if not table_name:
        return []

    table = boto3.resource("dynamodb").Table(table_name)
    results = []
    for i in range(days):
        day = (datetime.now(timezone.utc) - timedelta(days=i)).date().isoformat()
        resp = table.query(
            KeyConditionExpression=Key("scan_date").eq(day),
            ScanIndexForward=False,      # newest scan of that day first
        )
        results.extend(resp.get("Items", []))
    return results       # results[0] is the most recent scan