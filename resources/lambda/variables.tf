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

variable "aws_s3_bucket" {
  description = "Name of the S3 bucket that Lambda will use for processing outputs"
  type        = string
}