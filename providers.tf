# Module: providers

# variable "aws_region" {
#   description = "AWS region"
#   type        = string
#   default     = "us-east-2"
# }

# variable "aws_profile" {
#   description = "AWS profile"
#   type        = string
#   default     = "loc1"
# }

# provider "aws" {
#   region = var.aws_region
# }

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}