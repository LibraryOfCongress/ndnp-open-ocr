variable "task_family" {
  description = "Name of the task family"
  type        = string
}

variable "service_name" {
  description = "Name of the ECS service"
  type        = string
}

variable "aws_s3_output_bucket" {
  description = "Name of the S3 output bucket"
  type        = string
}

variable "env" {
  description = "The environment (dev, test, prod)"
  type        = string
}