# AWS Cost Guardian

![CI](https://github.com/Hameed-Alahmadi/aws-cost-guardian/actions/workflows/ci.yml/badge.svg)
![Python](https://img.shields.io/badge/python-3.12-blue)
![Terraform](https://img.shields.io/badge/terraform-AWS-844FBA)
![License](https://img.shields.io/badge/license-MIT-green)

A serverless tool that scans an AWS account for resources that cost money while doing nothing
— unattached EBS volumes, unassociated Elastic IPs, stale snapshots — prices each one, tracks
the trend over time, and emails a daily report.

**Result on my own account:** found **$2.00/month** of waste across three forgotten EBS
volumes. I deleted them, and it now reports a clean account — which is the point: the
number is supposed to go to zero. Small figures here because it's a personal learning
account; the same scan against a team's account is where a tool like this pays for itself.

---

## Architecture

```text
        ⏰ EventBridge  (cron: 08:00 UTC daily)
                 │
                 ▼
        🔍 Lambda: scanner ──────────► 💵 Cost Explorer
        (boto3, read-only IAM role)      (actual account spend)
                 │
                 ├──────► 📦 DynamoDB      findings history, 90-day TTL
                 ├──────► 📧 SNS           email report with trend line
                 └──────► 📊 CloudWatch    EMF metrics · dashboard · alarms

        🧹 Lambda: remediator   ← separate function, separate role
           four independent gates before anything is deleted
```

Everything above is defined in Terraform and deployed by GitHub Actions using OIDC —
**no AWS credentials are stored anywhere.**

---

## What it does

| Step | How |
|---|---|
| **Wakes up** | EventBridge rule fires daily at 08:00 UTC |
| **Scans** | `boto3` describe calls across EBS volumes, Elastic IPs, snapshots |
| **Prices** | static per-GB price map + real spend from Cost Explorer |
| **Remembers** | writes each scan to DynamoDB with a 90-day TTL |
| **Reports** | SNS email: findings, monthly waste, and whether it went up or down |
| **Cleans up** | optional remediator function, behind four safety gates |

Sample report:

```text
💰 AWS Cost Guardian — Daily Report

Findings:        3
Monthly waste:   $2.0
Last 30d spend:  $0.0
Trend:           🔺 up $0.5 since last scan

Details:
  • $   1.00/mo  [unattached_ebs_volume] vol-04112b… — 10GB gp2 volume attached to nothing
  • $   0.50/mo  [unattached_ebs_volume] vol-0c956d… — 5GB gp2 volume attached to nothing
  • $   0.50/mo  [unattached_ebs_volume] vol-02b5a6… — 5GB gp2 volume attached to nothing
```

Once those volumes were deleted, the next scan reported nothing:

```text
✅ AWS Cost Guardian

No waste found — your account is clean!
```

---

## Safety design

The interesting part of this project isn't finding waste — it's deleting it without ever
deleting the wrong thing. Four independent gates, and **only the last one is outside my code**:

| Gate | Mechanism | Enforced by |
|---|---|---|
| 1. Opt-in tag | resource must carry `AutoDelete=true` | application code |
| 2. Age threshold | must be unused ≥ 7 days | application code |
| 3. Dry-run default | reports without acting unless `dry_run:false` is passed | application code |
| 4. **IAM condition** | `ec2:DeleteVolume` permitted **only** on `AutoDelete=true` resources | **AWS** |

Gate 4 is the one that matters. I verified it by disabling gates 1–3, pointing the function at
an untagged volume, and running with deletion explicitly enabled. The code called
`delete_volume`; AWS refused:

```json
"errors": [{"error": "UnauthorizedOperation ... is not authorized to perform:
             ec2:DeleteVolume ... because no identity-based policy allows"}]
```

The volume survived. **A bug in my code cannot delete a resource that isn't opted in** —
that guarantee lives in the permission boundary, not in an `if` statement.

The scanner is a separate function with a separate role that has **no delete permission at
all**, so the read path can never become a write path.

---

## Screenshots

### What it produces

The daily report, with every finding priced individually and the trend against the
previous scan:

![Daily SNS report showing three findings totalling $2.00 per month](docs/screenshots/sns-report.png)

And the state most tools get wrong — nothing found. An empty report is still a report;
silence would be indistinguishable from a broken scanner:

![SNS report showing zero findings and a clean account](docs/screenshots/sns-clean.png)

The CloudWatch dashboard over an hour of scans. The step down is a real deletion:
waste falls from $2.00 to $1.00 and the finding count from 3 to 2 in the same scan,
with the function's own invocation and duration metrics plotted underneath.

![CloudWatch dashboard showing monthly waste dropping from $2 to $1 after a volume was deleted](docs/screenshots/dashboard.png)

### How the safety gates hold

Two functions, two roles. The split is structural, not a convention:

![AWS Lambda console listing cost-guardian-scanner and cost-guardian-remediator](docs/screenshots/lambda-functions.png)

Their permissions side by side. On the left, the scanner: six read-only actions, plus
scoped writes to its own log group, SNS topic, and DynamoDB table — **no `Delete` action
of any kind**. On the right, the remediator: `ec2:DeleteVolume`, immediately followed by
the condition that constrains it to resources tagged `AutoDelete=true`.

![Scanner and remediator IAM policies shown side by side](docs/screenshots/iam-policies.png)

And the proof that the condition is real. I disabled the three code-level gates, pointed
the remediator at an **untagged** volume, and ran it with deletion explicitly enabled.
The code called `delete_volume`. AWS refused:

![Terminal output showing AWS returning UnauthorizedOperation for ec2:DeleteVolume](docs/screenshots/iam-refusal.png)

The volume survived. That guarantee doesn't depend on my code being correct.

### How it ships

Every push runs the tests, then deploys. The credentials step is the one worth looking
at — it mints a short-lived token from GitHub's OIDC provider, so there is no AWS secret
stored in this repository to leak or rotate:

![GitHub Actions deploy job with the OIDC credentials step succeeded](docs/screenshots/oidc-deploy.png)

---

## Getting started

**Prerequisites:** AWS account, AWS CLI configured, Terraform, Python 3.12.

```bash
git clone https://github.com/Hameed-Alahmadi/aws-cost-guardian.git
cd aws-cost-guardian

cd infra
terraform init
terraform apply \
  -var="alert_email=you@example.com" \
  -var="github_repo=<your-username>/aws-cost-guardian"
```

Confirm the SNS subscription email AWS sends you, then trigger a scan:

```bash
aws lambda invoke --function-name cost-guardian-scanner \
  --cli-binary-format raw-in-base64-out --payload '{}' out.json && cat out.json
```

**Tests** run against mocked AWS — no credentials, no cost:

```bash
pip install -r requirements-dev.txt
pytest -v
```

---

## Engineering decisions

**Least privilege, split by function.** The scanner's IAM policy contains no write action of
any kind. Remediation is a *separate* Lambda with its own role. Two functions instead of one
is more moving parts — deliberately, because it makes "the scanner can't delete" a structural
fact rather than a promise.

**Static price map instead of the Pricing API.** Per-GB prices change rarely, and this avoids
an API call and an extra permission on every scan. *Trade-off:* the prices are us-east-1
on-demand only and need manual updating — a real limitation I accepted for simplicity.

**No stored credentials.** CI authenticates to AWS via GitHub OIDC with a trust policy scoped
to this repository. Nothing to leak, nothing to rotate. (See the debugging note below — this
took the longest to get right.)

**Remote state in S3, versioned.** Local state works until CI needs it too. The bucket has
versioning enabled so a corrupted state file can be rolled back.

**Data lifecycle from day one.** DynamoDB items carry a TTL and expire after 90 days, so the
table can't grow unbounded. Easy to add at the start, awkward to retrofit.

**Alarms on absence, not just errors.** `cost-guardian-errors` catches loud failures.
`cost-guardian-not-running` catches the silent one — no invocations in 24 hours — configured
with `treat_missing_data = "breaching"` so missing data *is* the alert. A monitoring tool that
quietly stops is worse than no tool, because you think you're covered.

**Structured JSON logs.** Every event is logged as JSON, so CloudWatch Logs Insights can query
behaviour directly instead of parsing prose with regex.

---

## A debugging note: the OIDC `sub` claim

Worth recording because the diagnosis was harder than the fix.

CI failed for hours with `Not authorized to perform sts:AssumeRoleWithWebIdentity` while
*every* piece of configuration checked out: role ARN correct, trust policy correct, OIDC
provider registered with the right audience, `id-token: write` present in the workflow.

The cause only appeared after printing the token's actual claims from inside the runner:

```text
sent:     repo:Hameed-Alahmadi@86168602/aws-cost-guardian@1324873909:ref:refs/heads/main
expected: repo:Hameed-Alahmadi/aws-cost-guardian:*
```

GitHub was sending an **ID-augmented `sub` claim** — numeric user and repo IDs embedded in the
string, so the claim binds to immutable identifiers rather than renameable names. The IAM
`StringLike` pattern matched the documented format, not the one actually being sent. The fix
accepts both, derived from the repo variable so it survives a rename:

```hcl
values = [
  "repo:${var.github_repo}:*",
  "repo:${local.repo_owner}@*/${local.repo_name}@*:*",
]
```

**The lesson:** when both sides of a handshake look correctly configured and it still fails,
stop comparing configuration and print what's actually on the wire. Configuration describes
intent; the payload is the fact.

📄 **[Full write-up in TROUBLESHOOTING-oidc.md](TROUBLESHOOTING-oidc.md)** — including the six
wrong turns and why each looked convincing at the time.

---

## Cost

Runs at roughly **$0.30/month** — Cost Explorer bills $0.01 per API request, and the scanner
makes one call per daily run. Lambda (~30 invocations), DynamoDB, SNS, EventBridge and
CloudWatch Logs all sit inside the free tier.

It's a fitting detail for a project about waste: **the tool that watches your bill also adds to
it.** To run at true zero, drop the Cost Explorer call and keep the static price estimates, or
pause the schedule:

```bash
aws events disable-rule --name cost-guardian-daily   # stop; enable-rule to resume
```

---

## Limitations

- Scans a **single account** and a **single region** (`us-east-1`).
- Prices come from a static map — accurate for us-east-1 on-demand only.
- Detects three resource types. Idle load balancers, NAT Gateways and oversized instances
  follow the same pattern but aren't implemented.
- Remediation handles **EBS volumes only**.
- Built and tested on a personal learning account, not at production scale or volume.
- No human-approval step before deletion — appropriate for one account, not for a team's.

---

## Roadmap

- More detectors: idle load balancers, unused NAT Gateways, oversized instances
- Multi-region scanning via `ec2.describe_regions()`
- Multi-account via cross-account role assumption
- Slack delivery as an additional SNS subscriber (no code change needed)
- A manual approval gate before any deletion

---

## Tech

`AWS Lambda` `EventBridge` `DynamoDB` `SNS` `Cost Explorer` `CloudWatch` `IAM`
`Terraform` `GitHub Actions (OIDC)` `Python 3.12` `boto3` `pytest` `moto` `ruff`
