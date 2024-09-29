variable "task_family" {
  description = "Name of the task family"
  type        = string
}

variable "execution_role_arn" {
  description = "ARN of the execution role"
  type        = string
}

variable "service_name" {
  description = "Name of the ECS service"
  type        = string
}

variable "task_role_arn" {
  description = "ARN of the task role"
  type        = string
}

variable "aws_s3_output_bucket" {
  description = "Name of the S3 output bucket"
  type        = string
}
