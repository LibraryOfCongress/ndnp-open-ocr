variable "bucket_name" {
  description = "Name of the S3 Bucket"
  type        = string
}

variable "environment" {
  description = "Environment tag for the bucket"
  type        = string
  default = "Dev"
}