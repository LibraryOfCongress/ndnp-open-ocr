# Queue to serve as source messages for Lambda OCR Reprocessing consumers.
resource "aws_sqs_queue" "queue" {
  name                       = "ndnp-open-ocr-consumer-sqs-queue"
  delay_seconds              = 0
  max_message_size           = 1024
  message_retention_seconds  = 345600
  visibility_timeout_seconds = 3000
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.dlq.arn
    maxReceiveCount     = 5
  })
}

# Queue to serve as source messages for Lambda OCR Reprocessing ALTO Consumer
# resource "aws_sqs_queue" "alto_queue" {
#   name                       = "ndnp-open-ocr-alto-consumer-sqs-queue"
#   delay_seconds              = 0
#   max_message_size           = 1024
#   message_retention_seconds  = 345600
#   visibility_timeout_seconds = 900
#   redrive_policy = jsonencode({
#     deadLetterTargetArn = aws_sqs_queue.alto_dlq.arn
#     maxReceiveCount     = 1
#   })
# }

# Dead letter queue to catch failed PDF jobs
resource "aws_sqs_queue" "dlq" {
  name = "${var.queue_name}_dlq"
  visibility_timeout_seconds = 60
}

# Dead letter queue to catch failed ALTO jobs
# resource "aws_sqs_queue" "alto_dlq" {
#   name = "${var.queue_name}_alto_dlq"
#   visibility_timeout_seconds = 60
# }

# IAM policy to grant access to SQSyes
# data "aws_iam_policy_document" "sqs" {
#   statement {
#     actions   = ["sqs:*"]
#     resources = [aws_sqs_queue.pdf_dlq.arn, aws_sqs_queue.alto_dlq.arn]
#   }
# }