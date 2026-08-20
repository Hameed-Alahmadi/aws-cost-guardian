# Debugging Notes — OIDC `sts:AssumeRoleWithWebIdentity` Failure

*A real incident from Stage 7, written up because the diagnosis took six wrong turns and the
lesson is worth more than the fix.*

## The symptom

Every `deploy` job failed at the *Configure AWS credentials* step:

```text
Error: Could not assume role with OIDC: Not authorized to perform sts:AssumeRoleWithWebIdentity
```

The action retried twelve times over ~85 seconds before giving up.

## What made it hard

**Every piece of configuration was correct.** Verified individually:

| Checked | Result |
|---|---|
| IAM role exists, ARN matches the GitHub variable | ✅ |
| Trust policy: `repo:Hameed-Alahmadi/aws-cost-guardian:*` | ✅ |
| OIDC provider registered, `ClientIDList` = `sts.amazonaws.com` | ✅ |
| Only one provider in the account | ✅ |
| Workflow has `permissions: id-token: write` (top level *and* job level) | ✅ |
| `github.repository` = `Hameed-Alahmadi/aws-cost-guardian` | ✅ |
| `github.ref` = `refs/heads/main` | ✅ |

Both sides matched. The failure continued.

## The actual cause

GitHub was sending a `sub` claim in an **ID-augmented format** that no configuration check
would have revealed:

```text
sent:     repo:Hameed-Alahmadi@86168602/aws-cost-guardian@1324873909:ref:refs/heads/main
expected: repo:Hameed-Alahmadi/aws-cost-guardian:*
```

GitHub appends numeric IDs — `@<user-id>` after the owner and `@<repo-id>` after the repo
name — so the claim binds to immutable identifiers rather than renameable strings. The IAM
`StringLike` pattern matched the documented format, not the one actually being sent.

## The fix

In `infra/oidc.tf`, accept both claim formats:

```hcl
locals {
  repo_owner = split("/", var.github_repo)[0]
  repo_name  = split("/", var.github_repo)[1]
}

    condition {
      test     = "StringLike"
      variable = "token.actions.githubusercontent.com:sub"
      values = [
        "repo:${var.github_repo}:*",                        # classic format
        "repo:${local.repo_owner}@*/${local.repo_name}@*:*", # ID-augmented format
      ]
    }
```

Derived from the variable rather than hardcoding `86168602` / `1324873909`, so it works for
any repo and survives a rename.

Then `terraform apply` — **the fix lives in AWS, not in the pushed code**, so a `git push`
alone would have changed nothing.

## The diagnostic step that found it

After configuration comparison had failed repeatedly, this step printed the token's real claims:

```yaml
      - name: Inspect the OIDC token
        run: |
          echo "REQUEST_URL is set : ${ACTIONS_ID_TOKEN_REQUEST_URL:+yes}"
          echo "REQUEST_TOKEN set  : ${ACTIONS_ID_TOKEN_REQUEST_TOKEN:+yes}"
          TOKEN=$(curl -sH "Authorization: bearer $ACTIONS_ID_TOKEN_REQUEST_TOKEN" \
            "$ACTIONS_ID_TOKEN_REQUEST_URL&audience=sts.amazonaws.com" | jq -r .value)
          echo "$TOKEN" | cut -d. -f2 | base64 -d 2>/dev/null | jq '{sub, aud, iss}'
```

It answers two questions at once: *was a token issued at all* (the two `yes` lines), and
*what does it actually say*. The mismatch was visible immediately.

Remove it once deployment works — no reason to print token claims on every run.

## Wrong turns, and why each was wrong

Recording these because the reasoning failure is the instructive part:

1. **Truncated role ARN.** A real bug — the GitHub variable held `...github-actio`, missing
   two characters. Fixed, but the error persisted, which proved it wasn't the only problem.
2. **Case sensitivity.** IAM `StringLike` *is* case-sensitive, and `hameed-alahmadi` ≠
   `Hameed-Alahmadi`. Plausible, correct in principle, not the cause.
3. **Missing `id-token: write`.** The log's `GITHUB_TOKEN Permissions` group showed only
   `Contents: read` and `Metadata: read`. This looked decisive — but the permission *was*
   granted; that log group simply doesn't list `id-token`. **A confident inference from an
   absence of evidence.**
4. **Re-run vs. push.** Two runs shared commit `01c6f50`, since *Re-run* replays the same
   snapshot. Worth knowing, but not the cause here.
5. **Repo-level Actions settings.** Reasonable to check, changed nothing.
6. **Copilot's suggestion** — that the trust relationship was missing or the provider
   unregistered — was the generic answer for this error string. It had read the workflow and
   the log, but not the AWS account, so it reasoned from the message rather than the data.
   Its proposed fix also used `StringEquals` on a hardcoded `ref`, which would have been
   silently reverted by the next `terraform apply`.

## What to take from it

**When every side of a handshake looks correct and it still fails, stop comparing
configuration and print what's actually on the wire.** Configuration describes intent; the
payload is the fact. One diagnostic step surfaced in seconds what six rounds of inference
could not.

Two supporting habits:

- **Read logs from the top, not from the error.** The environment declares its state before
  anything fails.
- **Check the commit SHA in CI.** If it hasn't changed, you're testing yesterday's code.
