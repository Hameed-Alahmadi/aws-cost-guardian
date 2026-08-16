terraform {
  backend "s3" {
    bucket       = "cost-guardian-tfstate-771413672021"
    key          = "cost-guardian/terraform.tfstate"
    region       = "us-east-1"
    use_lockfile = true
  }

  required_providers {
    aws     = { source = "hashicorp/aws", version = "~> 5.0" }
    archive = { source = "hashicorp/archive", version = "~> 2.4" }
  }
}

provider "aws" {
  region = "us-east-1"
}

# Zip the source folder automatically on every apply
data "archive_file" "lambda_zip" {
  type        = "zip"
  source_dir  = "${path.module}/../src"
  output_path = "${path.module}/lambda.zip"
  excludes    = ["__pycache__"] # don't ship Python's cache folder
}

resource "aws_lambda_function" "scanner" {
  function_name    = "cost-guardian-scanner"
  role             = aws_iam_role.lambda.arn
  handler          = "scanner.handler" # file.function
  runtime          = "python3.12"
  timeout          = 60 # scans can take a while
  filename         = data.archive_file.lambda_zip.output_path
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256
  environment {
    variables = {
      SNS_TOPIC_ARN = aws_sns_topic.reports.arn
      DDB_TABLE     = aws_dynamodb_table.findings.name
    }
  }
}

# Keep logs cheap — delete them after 14 days
resource "aws_cloudwatch_log_group" "lambda" {
  name              = "/aws/lambda/${aws_lambda_function.scanner.function_name}"
  retention_in_days = 14
}