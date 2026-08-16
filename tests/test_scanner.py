"""Tests run against moto's fake AWS — no real account, no cost, no risk."""

import boto3
import pytest
from moto import mock_aws

from scanner import find_unattached_volumes, find_unassociated_eips
from pricing import price_findings, estimate_monthly_cost


@pytest.fixture
def ec2():
    with mock_aws():
        yield boto3.client("ec2", region_name="us-east-1")


def test_finds_an_unattached_volume(ec2):
    ec2.create_volume(Size=100, AvailabilityZone="us-east-1a")
    findings = find_unattached_volumes(ec2)
    assert len(findings) == 1
    assert findings[0]["type"] == "unattached_ebs_volume"
    assert findings[0]["size_gb"] == 100


def test_clean_account_has_no_findings(ec2):
    assert find_unattached_volumes(ec2) == []


def test_finds_unassociated_eip(ec2):
    ec2.allocate_address(Domain="vpc")
    findings = find_unassociated_eips(ec2)
    assert len(findings) == 1
    assert findings[0]["type"] == "unassociated_elastic_ip"


def test_prices_a_volume_correctly():
    finding = {"type": "unattached_ebs_volume", "size_gb": 100, "volume_type": "gp3"}
    assert estimate_monthly_cost(finding) == 8.0        # 100GB * $0.08


def test_totals_across_findings():
    findings = [
        {"type": "unattached_ebs_volume", "size_gb": 100, "volume_type": "gp3"},
        {"type": "unassociated_elastic_ip"},
    ]
    _, total = price_findings(findings)
    assert total == 11.60                                # 8.00 + 3.60