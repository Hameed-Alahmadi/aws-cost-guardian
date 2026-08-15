variable "alert_email" {
  description = "Where to send the daily report"
  type        = string
}

# The topic: a mailbox other things publish into
resource "aws_sns_topic" "reports" {
  name = "cost-guardian-reports"
}

# Your email subscribes to it (you must confirm via the email AWS sends)
resource "aws_sns_topic_subscription" "email" {
  topic_arn = aws_sns_topic.reports.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

# The daily trigger — 08:00 UTC every day
resource "aws_cloudwatch_event_rule" "daily" {
  name                = "cost-guardian-daily"
  description         = "Run the cost scanner every morning"
  schedule_expression = "cron(0 8 * * ? *)"
}

resource "aws_cloudwatch_event_target" "lambda" {
  rule      = aws_cloudwatch_event_rule.daily.name
  target_id = "scanner"
  arn       = aws_lambda_function.scanner.arn
}

# EventBridge needs explicit permission to invoke the function
resource "aws_lambda_permission" "allow_eventbridge" {
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.scanner.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.daily.arn
}