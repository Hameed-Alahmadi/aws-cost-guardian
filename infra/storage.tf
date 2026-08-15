resource "aws_dynamodb_table" "findings" {
  name         = "cost-guardian-findings"
  billing_mode = "PAY_PER_REQUEST"     # no capacity planning, free-tier friendly

  hash_key  = "scan_date"              # partition key
  range_key = "timestamp"              # sort key

  attribute {
    name = "scan_date"
    type = "S"
  }
  attribute {
    name = "timestamp"
    type = "S"
  }

  ttl {
    attribute_name = "expires_at"      # items auto-delete after this epoch time
    enabled        = true
  }

  tags = {
    Project = "cost-guardian"
  }
}