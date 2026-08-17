# A SEPARATE role — the scanner never gains delete rights
resource "aws_iam_role" "remediator" {
  name               = "cost-guardian-remediator-role"
  assume_role_policy = data.aws_iam_policy_document.assume.json   # reuse the Lambda trust
}

resource "aws_cloudwatch_log_group" "remediator" {
  name              = "/aws/lambda/cost-guardian-remediator"
  retention_in_days = 30                # keep the audit trail longer
}

data "aws_iam_policy_document" "remediator" {
  statement {
    effect    = "Allow"
    actions   = ["ec2:DescribeVolumes"]
    resources = ["*"]
  }

  # The ONLY destructive permission in the whole project — and it's
  # limited to volumes tagged AutoDelete=true.
  statement {
    effect    = "Allow"
    actions   = ["ec2:DeleteVolume"]
    resources = ["*"]
    condition {
      test     = "StringEquals"
      variable = "aws:ResourceTag/AutoDelete"
      values   = ["true"]
    }
  }

  statement {
    effect    = "Allow"
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["${aws_cloudwatch_log_group.remediator.arn}:*"]
  }
}

resource "aws_iam_role_policy" "remediator" {
  name   = "cost-guardian-remediator-policy"
  role   = aws_iam_role.remediator.id
  policy = data.aws_iam_policy_document.remediator.json
}

resource "aws_lambda_function" "remediator" {
  function_name    = "cost-guardian-remediator"
  role             = aws_iam_role.remediator.arn
  handler          = "remediate.handler"
  runtime          = "python3.12"
  timeout          = 60
  filename         = data.archive_file.lambda_zip.output_path
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256
}