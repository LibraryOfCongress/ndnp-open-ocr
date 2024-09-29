# Main Terraform file to declare NDNP Open OCR resources that have to be created
# in AWS to run the pipeline.


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
  batch_job_definition = module.ecs-fargate.batch_job_definition
  batch_job_queue      = module.ecs-fargate.batch_job_queue
  env                  = var.env
}

module "ecs-fargate" {
  source               = "./resources/ecs-fargate"
  task_family          = "ndnp-open-ocr"
  service_name         = "ndnp-open-ocr-service"
  aws_s3_output_bucket = module.s3.bucket_name
  env                  = var.env
}
