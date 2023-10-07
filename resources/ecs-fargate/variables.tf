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

variable "container_name" {
  description = "Name of the container"
  type        = string
}

variable "container_image" {
  description = "Docker image for the container"
  type        = string
}

variable "container_port" {
  description = "Container exposed port"
  type        = number
  default     = 80
}

variable "desired_count" {
  description = "Number of desired tasks for the service"
  type        = number
  default     = 1
}

variable "subnets" {
  description = "List of subnets for the service"
  type        = list(string)
}

variable "security_groups" {
  description = "List of security groups for the service"
  type        = list(string)
}

variable "sqs_queue_url" {
  description = "Source SQS Queue Url"
  type        = string
}