module "iam" {
  source = "./resources/iam"

  lambda_iam_role_name = "ndnp-open-ocr-lambda-role"
  lambda_iam_policy_name = "ndnp-open-ocr-lambda-policy"
}

module "s3" {
  source = "./resources/s3"
  bucket_name = "ndnp-open-ocr-output-bucket-test"
}

module "sqs" {
  source = "./resources/sqs"
  queue_name = "ndnp-open-ocr-queue"
}

module "lambda" {
  source = "./resources/lambda"
  source_dir = "./functions"
  output_path = "./resources/lambda/functions.zip"
  lambda_role_arn = module.iam.lambda_role_arn
  aws_s3_input_bucket = module.s3.bucket_name
  aws_s3_output_bucket = module.s3.bucket_name
  queue_url = module.sqs.queue_url
  queue_arn = module.sqs.queue_arn
  table_name = var.table_name
}

module "apigw" {
  source = "./resources/apigw"
  api_name = "ndnp-open-ocr-api"
  api_tag_name = "ndnp-open-ocr"
  api_stage_name = "dev"
  api_tag_environment = "Dev"
  api_stage_description = "My test stage"
  api_stage_throttling_burst_limit = 5000
  api_stage_throttling_rate_limit = 10000
  lambda_invoke_arn = module.lambda.scheduler_function_invoke_arn
}

module "dynamodb" {
  source = "./resources/dynamodb"
  table_name = var.table_name
}