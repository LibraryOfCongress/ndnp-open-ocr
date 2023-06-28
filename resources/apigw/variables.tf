variable "api_name" {
  description = "The name of the API"
  type        = string
}

variable "api_tag_name" {
  description = "The name tag of the API"
  type        = string
}

variable "api_tag_environment" {
  description = "The environment tag of the API"
  type        = string
}

variable "lambda_invoke_arn" {
  description = "The ARN of the Lambda function to be invoked by the API Gateway"
  type        = string
}

variable "api_stage_name" {
  description = "The name of the stage for the API"
  type        = string
}

variable "api_stage_description" {
  description = "The description of the stage for the API"
  type        = string
}

variable "api_stage_throttling_burst_limit" {
  description = "The throttling burst limit for the API stage"
  type        = number
}

variable "api_stage_throttling_rate_limit" {
  description = "The throttling rate limit for the API stage"
  type        = number
}