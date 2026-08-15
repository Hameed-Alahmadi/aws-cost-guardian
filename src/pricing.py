"""Turns findings into estimated monthly dollar costs."""

# Public on-demand prices for us-east-1 (USD). Good enough for waste estimation.
PRICE_PER_GB_MONTH = {
    "gp2": 0.10,
    "gp3": 0.08,
    "io1": 0.125,
    "io2": 0.125,
    "st1": 0.045,
    "sc1": 0.015,
    "standard": 0.05,
}
SNAPSHOT_PRICE_PER_GB_MONTH = 0.05
UNASSOCIATED_EIP_MONTHLY = 3.60


def _to_decimal(obj):
    """Recursively convert floats to Decimal for DynamoDB."""
    if isinstance(obj, float):
        return Decimal(str(obj))
    if isinstance(obj, list):
        return [_to_decimal(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _to_decimal(v) for k, v in obj.items()}
    return obj


def estimate_monthly_cost(finding):
    """Return the estimated USD/month this wasted resource is costing."""
    kind = finding["type"]

    if kind == "unattached_ebs_volume":
        gb = finding.get("size_gb", 0)
        vol_type = finding.get("volume_type", "gp2")
        return round(gb * PRICE_PER_GB_MONTH.get(vol_type, 0.10), 2)

    if kind == "old_snapshot":
        gb = finding.get("size_gb", 0)
        return round(gb * SNAPSHOT_PRICE_PER_GB_MONTH, 2)

    if kind == "unassociated_elastic_ip":
        return UNASSOCIATED_EIP_MONTHLY

    return 0.0


def price_findings(findings):
    """Add a monthly_cost to every finding and return (findings, total)."""
    total = 0.0
    for f in findings:
        cost = estimate_monthly_cost(f)
        f["monthly_cost_usd"] = cost
        total += cost
    return findings, round(total, 2)