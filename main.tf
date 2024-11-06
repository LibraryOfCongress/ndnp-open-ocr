# Main Terraform file to declare NDNP Open OCR resources that have to be created
# in AWS to run the pipeline.
terraform {
  backend "s3" {
    bucket         = "ndnp-open-ocr-dependencies"  # Your S3 bucket name
    key            = "ndnp-open-ocr-tf-state-files/dev/terraform.tfstate"  # The file path inside the bucket for your state
    region         = "us-east-1"  # Specify the AWS region of the bucket
    encrypt        = true  # Encrypt the state file
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
  source               = "./resources/batch"
  task_family          = "ndnp-open-ocr"
  service_name         = "ndnp-open-ocr-service"
  aws_s3_output_bucket = module.s3.bucket_name
  env                  = var.env
  get_job_function_name = module.lambda.get_job_function_name
  get_job_function_invoke_arn = module.lambda.get_job_function_invoke_arn
}

output "ecr_repo_url" {
  value = module.batch.repository_url
  description = "The URI of the ECR repository for Docker images"
}