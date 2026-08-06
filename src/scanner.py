"""Scans an AWS account for resources that cost money but aren't being used."""

import boto3
from datetime import datetime, timezone


def find_unattached_volumes(ec2):
    """EBS volumes in 'available' state are not attached to anything — pure waste."""
    findings = []
    response = ec2.describe_volumes(
        Filters=[{"Name": "status", "Values": ["available"]}]
    )
    for vol in response["Volumes"]:
        findings.append({
            "type": "unattached_ebs_volume",
            "id": vol["VolumeId"],
            "region": ec2.meta.region_name,
            "size_gb": vol["Size"],
            "created": vol["CreateTime"].isoformat(),
            "detail": f"{vol['Size']}GB {vol['VolumeType']} volume attached to nothing",
        })
    return findings


def find_unassociated_eips(ec2):
    """Elastic IPs are free while attached to a running instance — and billed when not."""
    findings = []
    response = ec2.describe_addresses()
    for addr in response["Addresses"]:
        if "AssociationId" not in addr:          # not attached to anything
            findings.append({
                "type": "unassociated_elastic_ip",
                "id": addr.get("AllocationId", addr.get("PublicIp")),
                "region": ec2.meta.region_name,
                "detail": f"Elastic IP {addr.get('PublicIp')} allocated but not associated",
            })
    return findings


def find_old_snapshots(ec2, account_id, days=90):
    """Snapshots you own that are older than `days` — often forgotten backups."""
    findings = []
    now = datetime.now(timezone.utc)
    paginator = ec2.get_paginator("describe_snapshots")
    for page in paginator.paginate(OwnerIds=[account_id]):
        for snap in page["Snapshots"]:
            age_days = (now - snap["StartTime"]).days
            if age_days > days:
                findings.append({
                    "type": "old_snapshot",
                    "id": snap["SnapshotId"],
                    "region": ec2.meta.region_name,
                    "size_gb": snap["VolumeSize"],
                    "detail": f"{age_days} days old, {snap['VolumeSize']}GB",
                })
    return findings


def scan_account(region="us-east-1"):
    """Run every check and return a combined list of findings."""
    ec2 = boto3.client("ec2", region_name=region)
    account_id = boto3.client("sts").get_caller_identity()["Account"]

    findings = []
    findings += find_unattached_volumes(ec2)
    findings += find_unassociated_eips(ec2)
    findings += find_old_snapshots(ec2, account_id)
    return findings


def handler(event, context):
    """Entry point AWS Lambda calls."""
    findings = scan_account()
    print(f"Scan complete — {len(findings)} finding(s)")
    for f in findings:
        print(f"  [{f['type']}] {f['id']} — {f['detail']}")
    return {
        "statusCode": 200,
        "findingCount": len(findings),
        "findings": findings,
    }


if __name__ == "__main__":
    results = scan_account()
    print(f"\n🔍 Scan complete — {len(results)} finding(s)\n")
    for f in results:
        print(f"  [{f['type']}] {f['id']} — {f['detail']}")
    if not results:
        print("  ✅ No waste found. Your account is clean!")