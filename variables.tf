variable "s3_bucket_name" {
  description = "The name of the S3 bucket to store OCR outputs."
  type        = string
  default     = "ndnp-open-ocr-output-bucket" # Optional, you can remove the default if you want to set it manually each time
}

variable "env" {
  description = "The environment (dev, test, prod) from CI"
  type        = string
  default     = "development-deployment"
}

variable "batch_image_tag" {
  description = "Docker image tag used by AWS Batch job definition"
  type        = string
  default     = "opensource1.1"
}
