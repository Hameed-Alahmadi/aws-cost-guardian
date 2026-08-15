# WHO can assume this role: the Lambda service, and nothing else
data "aws_iam_policy_document" "assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "lambda" {
  name               = "cost-guardian-scanner-role"
  assume_role_policy = data.aws_iam_policy_document.assume.json
}

# WHAT the role may do: read-only describes + write its own logs. Nothing destructive.
data "aws_iam_policy_document" "scanner" {
  statement {
    effect = "Allow"
    actions = [
      "ec2:DescribeVolumes",
      "ec2:DescribeAddresses",
      "ec2:DescribeSnapshots",
      "ec2:DescribeInstances",
      "sts:GetCallerIdentity",
      "ce:GetCostAndUsage",
    ]
    resources = ["*"] # describe calls can't be scoped to specific ARNs
  }

  statement {
    effect    = "Allow"
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["${aws_cloudwatch_log_group.lambda.arn}:*"]
  }

  statement {
    effect    = "Allow"
    actions   = ["sns:Publish"]
    resources = [aws_sns_topic.reports.arn]
  }

  statement {
    effect    = "Allow"
    actions   = ["dynamodb:PutItem", "dynamodb:Query"]
    resources = [aws_dynamodb_table.findings.arn]
  }
}

resource "aws_iam_role_policy" "scanner" {
  name   = "cost-guardian-scanner-policy"
  role   = aws_iam_role.lambda.id
  policy = data.aws_iam_policy_document.scanner.json
}