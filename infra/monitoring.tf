# 1) Alarm: the Lambda errored
resource "aws_cloudwatch_metric_alarm" "lambda_errors" {
  alarm_name          = "cost-guardian-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = 300
  statistic           = "Sum"
  threshold           = 0
  alarm_description   = "The cost scanner Lambda failed"
  dimensions          = { FunctionName = aws_lambda_function.scanner.function_name }
  alarm_actions       = [aws_sns_topic.reports.arn]
}

# 2) Alarm: the scan didn't run at all in 24h (the silent failure)
resource "aws_cloudwatch_metric_alarm" "not_running" {
  alarm_name          = "cost-guardian-not-running"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 1
  metric_name         = "Invocations"
  namespace           = "AWS/Lambda"
  period              = 86400                 # 24 hours
  statistic           = "Sum"
  threshold           = 1
  alarm_description   = "The scanner hasn't run in 24h — the schedule may be broken"
  treat_missing_data  = "breaching"           # no data = something's wrong
  dimensions          = { FunctionName = aws_lambda_function.scanner.function_name }
  alarm_actions       = [aws_sns_topic.reports.arn]
}

# 3) A dashboard you can actually look at
resource "aws_cloudwatch_dashboard" "main" {
  dashboard_name = "cost-guardian"
  dashboard_body = jsonencode({
    widgets = [
      {
        type = "metric", width = 12, height = 6, x = 0, y = 0,
        properties = {
          title  = "Monthly waste found (USD)"
          region = "us-east-1"
          metrics = [["CostGuardian", "MonthlyWasteUsd"]]
          view   = "timeSeries"
        }
      },
      {
        type = "metric", width = 12, height = 6, x = 12, y = 0,
        properties = {
          title  = "Findings per scan"
          region = "us-east-1"
          metrics = [["CostGuardian", "FindingCount"]]
          view   = "timeSeries"
        }
      },
      {
        type = "metric", width = 24, height = 6, x = 0, y = 6,
        properties = {
          title  = "Scanner health"
          region = "us-east-1"
          metrics = [
            ["AWS/Lambda", "Invocations", "FunctionName", aws_lambda_function.scanner.function_name],
            [".", "Errors", ".", "."],
            [".", "Duration", ".", "."]
          ]
          view = "timeSeries"
        }
      }
    ]
  })
}