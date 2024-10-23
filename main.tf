# Main Terraform file to declare NDNP Open OCR resources that have to be created
# in AWS to run the pipeline.
# terraform {
#   backend "http" {
#     address        = "https://git.loc.gov/api/v4/projects/2983/terraform/state/dev"
#     lock_address   = "https://git.loc.gov/api/v4/projects/2983/terraform/state/dev/lock"
#     unlock_address = "https://git.loc.gov/api/v4/projects/2983/terraform/state/dev/lock"
#     username       = "gitlab-ci-token"
#     password       = "${CI_JOB_TOKEN}"
#   }
# }

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
  source               = "./resources/batch"
  task_family          = "ndnp-open-ocr"
  service_name         = "ndnp-open-ocr-service"
  aws_s3_output_bucket = module.s3.bucket_name
  env                  = var.env
}

output "ecr_repo_url" {
  value = module.batch.repository_url
  description = "The URI of the ECR repository for Docker images"
}