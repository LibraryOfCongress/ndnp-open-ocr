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

variable "aws_s3_output_bucket" {
  description = "Name of the S3 bucket that Lambda will use for storing outputs"
  type        = string
}

variable "batch_job_definition" {
  description = ""
  type = string
}

variable "batch_job_queue" {
  description = ""
  type = string
}