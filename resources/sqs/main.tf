resource "aws_sqs_queue" "queue" {
  name                       = var.queue_name
  delay_seconds              = 0
  max_message_size           = 1024
  message_retention_seconds  = 345600
  visibility_timeout_seconds = 900
}

data "aws_iam_policy_document" "sqs" {
  statement {
    actions   = ["sqs:*"]
    resources = [aws_sqs_queue.queue.arn]
  }
}