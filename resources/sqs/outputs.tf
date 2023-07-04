output "queue_url" {
  description = "The ARN to be used to invoke the Scheduler function"
  value = aws_sqs_queue.queue.id
}