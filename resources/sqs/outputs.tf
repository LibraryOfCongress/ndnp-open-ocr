output "queue_url" {
  description = "The queue URL for the SQS queue"
  value = aws_sqs_queue.queue.id
}

output "queue_arn" {
    description = "The queue ARN for the SQS queue"
    value = aws_sqs_queue.queue.arn
}