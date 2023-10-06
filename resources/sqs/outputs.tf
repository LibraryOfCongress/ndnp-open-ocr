output "pdf_queue_url" {
  description = "The queue URL for the SQS queue"
  value = aws_sqs_queue.pdf_queue.id
}

# output "alto_queue_url" {
#   description = "The queue URL for the SQS queue"
#   value = aws_sqs_queue.alto_queue.id
# }


# output "alto_queue_arn" {
#   description = "The queue URL for the ALTO SQS queue"
#   value = aws_sqs_queue.alto_queue.arn
# }


output "pdf_queue_arn" {
    description = "The queue ARN for the PDF SQS queue"
    value = aws_sqs_queue.pdf_queue.arn
}

output "pdf_dlq_queue_arn" {
    description = "The queue ARN for the PDF Deadletter SQS queue"
    value = aws_sqs_queue.pdf_dlq.arn
}

# output "alto_dlq_queue_arn" {
#     description = "The queue ARN for the ALTO Deadletter SQS queue"
#     value = aws_sqs_queue.alto_dlq.arn
# }