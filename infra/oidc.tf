variable "github_repo" {
  description = "owner/repo allowed to deploy, e.g. Hameed-Alahmadi/aws-cost-guardian"
  type        = string
}

locals {
  repo_owner = split("/", var.github_repo)[0]
  repo_name  = split("/", var.github_repo)[1]
}

# Tell AWS to trust GitHub's identity provider
resource "aws_iam_openid_connect_provider" "github" {
  url             = "https://token.actions.githubusercontent.com"
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = ["6938fd4d98bab03faadb97b34396831e3780aea1"]
}

# A role GitHub Actions may assume — but ONLY from your repo
data "aws_iam_policy_document" "gha_assume" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]
    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.github.arn]
    }
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }
    condition {
      test     = "StringLike"
      variable = "token.actions.githubusercontent.com:sub"
      values = [
        # classic claim format
        "repo:${var.github_repo}:*",
        # ID-augmented format: repo:owner@<user-id>/name@<repo-id>:...
        "repo:${local.repo_owner}@*/${local.repo_name}@*:*",
      ]
    }
  }
}

resource "aws_iam_role" "github_actions" {
  name               = "cost-guardian-github-actions"
  assume_role_policy = data.aws_iam_policy_document.gha_assume.json
}

# Deploy permissions. Broad for a learning project — scope down in a company.
resource "aws_iam_role_policy_attachment" "gha_admin" {
  role       = aws_iam_role.github_actions.name
  policy_arn = "arn:aws:iam::aws:policy/PowerUserAccess"
}

resource "aws_iam_role_policy_attachment" "gha_iam" {
  role       = aws_iam_role.github_actions.name
  policy_arn = "arn:aws:iam::aws:policy/IAMFullAccess"
}

output "github_actions_role_arn" {
  value = aws_iam_role.github_actions.arn
}