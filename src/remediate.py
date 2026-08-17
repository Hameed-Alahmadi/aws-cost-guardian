"""Deletes wasted resources — but only ones explicitly opted in, and only when told."""

import os
import boto3
from datetime import datetime, timezone

AUTO_DELETE_TAG = "AutoDelete"
MIN_AGE_DAYS = 7


def _is_opted_in(tags):
    """Gate 1: the resource must carry AutoDelete=true."""
    for t in tags or []:
        if t.get("Key") == AUTO_DELETE_TAG and t.get("Value", "").lower() == "true":
            return True
    return False


def _is_old_enough(created_at, min_days=MIN_AGE_DAYS):
    """Gate 2: don't touch anything recent."""
    age = (datetime.now(timezone.utc) - created_at).days
    return age >= min_days


def find_deletable_volumes(ec2):
    """Return volumes that pass every safety gate."""
    candidates = []
    resp = ec2.describe_volumes(Filters=[{"Name": "status", "Values": ["available"]}])
    for vol in resp["Volumes"]:
        if not _is_opted_in(vol.get("Tags")):
            print(f"SKIP {vol['VolumeId']}: not tagged AutoDelete=true")
            continue
        if not _is_old_enough(vol["CreateTime"]):
            age = (datetime.now(timezone.utc) - vol["CreateTime"]).days
            print(f"SKIP {vol['VolumeId']}: only {age}d old, need {MIN_AGE_DAYS}d")
            continue
        candidates.append({
            "id": vol["VolumeId"],
            "size_gb": vol["Size"],
            "age_days": (datetime.now(timezone.utc) - vol["CreateTime"]).days,
        })
    return candidates


def handler(event, context):
    """Gate 3: dry-run unless dry_run=false is passed explicitly."""
    dry_run = event.get("dry_run", True)          # SAFE DEFAULT
    ec2 = boto3.client("ec2", region_name=os.environ.get("AWS_REGION", "us-east-1"))

    candidates = find_deletable_volumes(ec2)
    deleted, errors = [], []

    for c in candidates:
        if dry_run:
            print(f"[DRY RUN] would delete {c['id']} ({c['size_gb']}GB, {c['age_days']}d old)")
            continue
        try:
            ec2.delete_volume(VolumeId=c["id"])
            print(f"DELETED {c['id']} ({c['size_gb']}GB)")
            deleted.append(c["id"])
        except Exception as e:
            print(f"FAILED to delete {c['id']}: {e}")
            errors.append({"id": c["id"], "error": str(e)})

    return {
        "dryRun": dry_run,
        "candidateCount": len(candidates),
        "candidates": candidates,
        "deleted": deleted,
        "errors": errors,
    }