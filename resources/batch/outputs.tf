output "repository_url" {
  value = aws_ecr_repository.repo.repository_url
}

output "batch_job_definition" {
  value = aws_batch_job_definition.batch_job_definition.arn
}

output "batch_job_queue" {
  value = aws_batch_job_queue.batch_job_queue.arn
}

output "batch_job_queue_name" {
  value = aws_batch_job_queue.batch_job_queue.name
}