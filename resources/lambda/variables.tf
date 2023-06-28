variable "source_dir" {
  description = "The source directory of the lambda function"
  type        = string
}

variable "output_path" {
  description = "The output path of the lambda function"
  type        = string
}

variable "lambda_role_arn" {
  description = "ARN of the IAM role for the Lambda function"
  type        = string
}