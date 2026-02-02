output "scheduler_function_arn" {
  value = aws_lambda_function.scheduler_function.arn
}

output "scheduler_function_invoke_arn" {
  description = "The ARN to be used to invoke the Scheduler function"
  value = aws_lambda_function.scheduler_function.invoke_arn
}

output "get_job_function_name" {
  description = "The name of the GetJob function"
  value = aws_lambda_function.get_job_function.function_name
}

output "get_job_function_invoke_arn" {
  description = "The ARN to be used to invoke the GetJob function"
  value = aws_lambda_function.get_job_function.arn
}

output batch_completion_function_name {
  description = "The name of the Batch Completion function"
  value       = aws_lambda_function.batch_completion_function.function_name
}

output batch_completion_function_arn {
  description = "The ARN of the Batch Completion function"
  value       = aws_lambda_function.batch_completion_function.arn
}

output "list_keys_function_name" {
  description = "The name of the List Keys function"
  value       = aws_lambda_function.list_keys_function.function_name
}

output "list_keys_function_arn" {
  description = "The ARN of the List Keys function"
  value       = aws_lambda_function.list_keys_function.arn
}
