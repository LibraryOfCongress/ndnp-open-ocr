output "scheduler_function_invoke_arn" {
  description = "The ARN to be used to invoke the Scheduler function"
  value = aws_lambda_function.scheduler_function.invoke_arn
}