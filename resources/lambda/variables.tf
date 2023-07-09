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

variable "aws_s3_input_bucket" {
  description = "Name of the S3 bucket that Lambda will use for reading in inputs"
  type        = string
}

variable "aws_s3_output_bucket" {
  description = "Name of the S3 bucket that Lambda will use for storing outputs"
  type        = string
}

variable "queue_url" {
  description = "Queue URL of the SQS queue for processing job management"
  type = string
}

variable "queue_arn" {
  description = "Queue ARN of the SQS queue for processing job management"
  type = string
}

variable "dlq_queue_arn" {
  description = "Queue ARN of the deadletter SQS queue for catching failed job messages from the main queue."
  type = string
}


variable "table_name" {
  description = "DynamoDB table for SQS message tracking"
  type = string
}