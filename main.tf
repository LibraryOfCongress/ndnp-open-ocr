# Main Terraform file to declare NDNP Open OCR resources that have to be created
# in AWS to run the pipeline.

# IAM roles and permissions
module "iam" {
  source = "./resources/iam"

  lambda_iam_role_name   = "ndnp-open-ocr-lambda-role"
  lambda_iam_policy_name = "ndnp-open-ocr-lambda-policy"
}

# S3 bucket related resources.
module "s3" {
  source      = "./resources/s3"
  bucket_name = "ndnp-open-ocr-output-bucket-test-2"
}

# # Lambda related resources
module "lambda" {
  source               = "./resources/lambda"
  source_dir           = "./lambdas"
  output_path          = "./resources/lambda/functions.zip"
  lambda_role_arn      = module.iam.service_role_arn
  aws_s3_output_bucket = module.s3.bucket_name
  batch_job_definition = module.ecs-fargate.batch_job_definition
  batch_job_queue      = module.ecs-fargate.batch_job_queue
}

module "ecs-fargate" {
  source = "./resources/ecs-fargate"
  task_family         = "ndnp-open-ocr"
  execution_role_arn  = module.iam.service_role_arn
  task_role_arn       = module.iam.service_role_arn
  service_name        = "ndnp-open-ocr-service"
  aws_s3_output_bucket = module.s3.bucket_name
}
