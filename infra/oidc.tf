variable "github_repo" {
  description = "owner/repo allowed to deploy, e.g. hameed/aws-cost-guardian"
  type        = string
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
      values   = ["repo:${var.github_repo}:*"]     # only this repo
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