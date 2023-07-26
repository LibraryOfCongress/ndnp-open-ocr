output "queue_url" {
  description = "The queue URL for the SQS queue"
  value = aws_sqs_queue.queue.id
}

output "alto_queue_url" {
  description = "The queue URL for the SQS queue"
  value = aws_sqs_queue.alto_queue.id
}


output "alto_queue_arn" {
  description = "The queue URL for the SQS queue"
  value = aws_sqs_queue.alto_queue.arn
}


output "queue_arn" {
    description = "The queue ARN for the SQS queue"
    value = aws_sqs_queue.queue.arn
}

output "dlq_queue_arn" {
    description = "The queue ARN for the Deadletter SQS queue"
    value = aws_sqs_queue.dlq.arn
}