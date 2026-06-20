# Main Terraform file to declare NDNP Open OCR resources that have to be created
# in AWS to run the pipeline.
terraform {
  # Partial backend configuration: supply your own state bucket/key/region at
  # init time so this repo never hardcodes a specific account's resources, e.g.
  #   terraform init -backend-config=backend.hcl   (see backend.hcl.example)
  # Remove this backend block entirely to fall back to local state.
  backend "s3" {
    encrypt = true
  }
}

# S3 bucket related resources.
module "s3" {
  source      = "./resources/s3"
  bucket_name = var.s3_bucket_name
  env         = var.env
}

# # Lambda related resources
module "lambda" {
  source               = "./resources/lambda"
  source_dir           = "./lambdas"
  output_path          = "./resources/lambda/functions.zip"
  aws_s3_output_bucket = module.s3.bucket_name
  batch_job_definition = module.batch.batch_job_definition
  batch_job_queue      = module.batch.batch_job_queue
  env                  = var.env
}

module "batch" {
  source                         = "./resources/batch"
  task_family                    = "ndnp-open-ocr"
  service_name                   = "ndnp-open-ocr-service"
  aws_s3_output_bucket           = module.s3.bucket_name
  env                            = var.env
  region                         = var.region
  get_job_function_name          = module.lambda.get_job_function_name
  get_job_function_invoke_arn    = module.lambda.get_job_function_invoke_arn
  batch_completion_function_name = module.lambda.batch_completion_function_name
  batch_completion_function_arn  = module.lambda.batch_completion_function_arn
  image_tag                      = var.batch_image_tag
}

output "ecr_repo_url" {
  value = module.batch.repository_url
}

output "output_bucket" {
  value = module.s3.bucket_name
}

output "get_job_lambda_arn" {
  value = module.lambda.get_job_function_invoke_arn
}
