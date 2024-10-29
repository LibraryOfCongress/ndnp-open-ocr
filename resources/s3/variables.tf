variable "bucket_name" {
  description = "Name of the S3 Bucket"
  type        = string
}

variable "env" {
  description = "The environment (dev, test, prod)"
  type        = string
}