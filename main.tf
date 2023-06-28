module "iam" {
  source = "./resources/iam"

  lambda_iam_role_name = "my_lambda_role"
  lambda_iam_policy_name = "my_lambda_policy"
}

module "s3" {
  source = "./resources/s3"
  bucket_name = "ndnp-open-ocr-outputs-bucket"
}

module "sqs" {
  source = "./resources/sqs"
  queue_name = "ndnp-open-ocr-queue"
}

module "lambda" {
  source = "./resources/lambda"
  source_dir = "${path.module}/functions"
  output_path = "${path.module}/functions.zip"
  lambda_role_arn = module.iam.lambda_role_arn
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