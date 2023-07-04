# Module: providers

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "aws_profile" {
  description = "AWS profile"
  type        = string
  default     = "loc"
}

provider "aws" {
  region  = var.aws_region
  profile = var.aws_profile
}

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 3.0"
    }
  }
}