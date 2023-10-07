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

# SQS related resources
module "sqs" {
  source     = "./resources/sqs"
  queue_name = "ndnp-open-ocr-queue"
}

# Lambda related resources
# module "lambda" {
#   source               = "./resources/lambda"
#   source_dir           = "./lambdas"
#   output_path          = "./resources/lambda/functions.zip"
#   lambda_role_arn      = module.iam.lambda_role_arn
#   aws_s3_output_bucket = module.s3.bucket_name
#   pdf_queue_url        = module.sqs.pdf_queue_url
#   alto_queue_arn       = module.sqs.alto_queue_arn
#   alto_queue_url       = module.sqs.alto_queue_url
#   pdf_queue_arn        = module.sqs.pdf_queue_arn
#   pdf_dlq_queue_arn    = module.sqs.pdf_dlq_queue_arn
#   alto_dlq_queue_arn   = module.sqs.alto_dlq_queue_arn
#   table_name           = var.table_name
# }

# # DynamoDB related resources
module "dynamodb" {
  source     = "./resources/dynamodb"
  table_name = var.table_name
}

module "ecs-fargate" {
  source = "./resources/ecs-fargate"
  task_family         = "ndnp-open-ocr"
  execution_role_arn  = module.iam.lambda_role_arn
  task_role_arn       = module.iam.lambda_role_arn
  container_name      = "ndnp-open-ocr-container"
  container_image     = "420280634985.dkr.ecr.us-east-2.amazonaws.com"
  service_name        = "ndnp-open-ocr-service"
  subnets             = ["subnet-094288b377c1b73fb", "subnet-0eb39d3cafcc5fb1a"]
  security_groups     = ["sg-0656ba0feeab2cc21"]
  sqs_queue_url = module.sqs.queue_url
}
