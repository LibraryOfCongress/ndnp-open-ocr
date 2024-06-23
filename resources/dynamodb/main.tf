# Table to hold all jobs we are tracking
resource "aws_dynamodb_table" "dynamodb_table" {
  name           = var.table_name
  read_capacity  = 10
  write_capacity = 10

  # Partition key for the table (i.e. "JOB").
  hash_key = "pk"
  # Sort key for the table (i.e. "JOB_ID" (uuid))
  range_key = "sk"

  attribute {
    name = "pk"
    type = "S"
  }

  attribute {
    name = "sk"
    type = "S"
  }

  lifecycle {
    prevent_destroy = false
  }
}
