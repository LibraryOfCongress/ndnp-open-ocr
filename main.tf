terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 3.0"
    }
  }
}

provider "aws" {
  region  = "us-east-1"
  profile = "NDNP_OPEN_OCR_DEVELOPER_DEV_profile"
}

data "aws_iam_policy_document" "s3" {
  statement {
    actions   = ["s3:*"]
    resources = ["arn:aws:s3:::ndnp-open-ocr-outputs-bucket/*"]
  }
}

resource "aws_s3_bucket" "bucket" {
  bucket = "ndnp-open-ocr-outputs-bucket"
  acl    = "private"

  tags = {
    Environment = "Dev"
  }
}

resource "aws_lambda_layer_version" "lambda_layer" {
  filename            = "layers.zip"
  layer_name          = "ndnp-open-ocr-layer"
  compatible_runtimes = ["python3.8"]
  source_code_hash    = filebase64sha256("layers.zip")
}

resource "aws_sqs_queue" "queue" {
  name                       = "ndnp-open-ocr-queue"
  delay_seconds              = 0
  max_message_size           = 1024
  message_retention_seconds  = 345600
  visibility_timeout_seconds = 900
}

data "aws_iam_policy_document" "sqs" {
  statement {
    actions   = ["sqs:*"]
    resources = [aws_sqs_queue.queue.arn]
  }
}

resource "aws_iam_role" "iam_for_lambda" {
  name = "ndnp-open-ocr-lambda-service-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Action = "sts:AssumeRole",
        Principal = {
          Service = "lambda.amazonaws.com"
        },
        Effect = "Allow",
      },
    ]
  })
}

data "archive_file" "zip" {
  type        = "zip"
  source_dir  = "${path.module}/functions"
  output_path = "${path.module}/functions.zip"
}

resource "aws_iam_role" "lambda" {
  name               = "ndnp-open-ocr-worker-function"
  assume_role_policy = data.aws_iam_policy_document.policy.json
}

resource "aws_iam_role" "lambda_role" {
  name               = "ndnp-open-ocr-lambda-execution-role"
  assume_role_policy = <<EOF
{
 "Version": "2012-10-17",
 "Statement": [
   {
     "Action": "sts:AssumeRole",
     "Principal": {
       "Service": "lambda.amazonaws.com"
     },
     "Effect": "Allow",
     "Sid": ""
   }
 ]
}
EOF
}


resource "aws_iam_policy" "iam_policy_for_lambda" {

  name        = "ndnp-open-ocr-iam-policy-for-lambdas"
  path        = "/"
  description = "AWS IAM Policy for managing aws lambda role"
  policy      = <<EOF
{
 "Version": "2012-10-17",
 "Statement": [
   {
     "Action": [
       "logs:CreateLogGroup",
       "logs:CreateLogStream",
       "logs:PutLogEvents",
       "sqs:ReceiveMessage",
       "sqs:SendMessage",
       "sqs:DeleteMessage",
       "sqs:*",
       "s3:*"
     ],
     "Resource": "*",
     "Effect": "Allow"
   },
   "Action": [
    "s3:*"
   ],
   "Resource": "s3://loc-preservation"
 ]
}
EOF
}

resource "aws_iam_role_policy_attachment" "attach_iam_policy_to_iam_role" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = aws_iam_policy.iam_policy_for_lambda.arn
}

resource "aws_lambda_function" "scheduler_function" {
  function_name = "ndnp-open-ocr-scheduler-function"
  filename      = data.archive_file.zip.output_path
  handler       = "scheduler.handler"
  role          = aws_iam_role.lambda_role.arn
  runtime       = "python3.8"
  timeout       = 120

  environment {
    variables = {
      QUEUE_URL          = aws_sqs_queue.queue.id
      OUTPUT_BUCKET_NAME = aws_s3_bucket.bucket.bucket
    }
  }

  layers = [
    aws_lambda_layer_version.lambda_layer.arn
  ]

  depends_on = [aws_iam_role_policy_attachment.attach_iam_policy_to_iam_role]
}

resource "aws_cloudwatch_log_group" "scheduler_function_log_group" {
  name              = "/aws/lambda/${aws_lambda_function.scheduler_function.function_name}"
  retention_in_days = 14
}

resource "aws_lambda_permission" "scheduler_apigw" {
  statement_id  = "AllowExecutionFromAPIGatewayScheduler"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.scheduler_function.function_name
  principal     = "apigateway.amazonaws.com"
}


resource "aws_lambda_function" "consumer_function" {
  function_name    = "ndnp-open-ocr-worker-function"
  filename         = data.archive_file.zip.output_path
  handler          = "consumer.handler"
  role             = aws_iam_role.lambda_role.arn
  runtime          = "python3.8"
  timeout          = 600
  depends_on       = [aws_iam_role_policy_attachment.attach_iam_policy_to_iam_role]
  source_code_hash = filebase64sha256(data.archive_file.zip.output_path)
  memory_size      = 1024


  layers = [
    aws_lambda_layer_version.lambda_layer.arn,
    "arn:aws:lambda:us-east-1:764866452798:layer:ghostscript:13",
    "arn:aws:lambda:us-east-1:445285296882:layer:perl-5-32-runtime-al2:2"
  ]

  environment {
    variables = {
      TESSDATA_PREFIX    = "/opt/share/tessdata"
      LD_LIBRARY_PATH    = "/opt/lib"
      PATH               = "/opt/bin:/usr/local/bin:/usr/bin:/bin"
      TMP                = "/tmp"
      OUTPUT_BUCKET_NAME = aws_s3_bucket.bucket.bucket
    }
  }
}

data "aws_iam_policy_document" "policy" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_cloudwatch_log_group" "consumer_function_log_group" {
  name              = "/aws/lambda/${aws_lambda_function.consumer_function.function_name}"
  retention_in_days = 14
}

resource "aws_lambda_permission" "apigw" {
  statement_id  = "AllowExecutionFromAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.consumer_function.function_name
  principal     = "apigateway.amazonaws.com"
}

resource "aws_lambda_permission" "sqs" {
  statement_id  = "AllowExecutionFromSQS"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.consumer_function.function_name
  principal     = "sqs.amazonaws.com"
  source_arn    = aws_sqs_queue.queue.arn
}

resource "aws_apigatewayv2_api" "http" {
  name          = "ndnp-open-ocr-api"
  protocol_type = "HTTP"

  tags = {
    Name        = "ndnp-open-ocr"
    Environment = "Dev"
  }
}

resource "aws_apigatewayv2_integration" "lambda" {
  api_id           = aws_apigatewayv2_api.http.id
  integration_type = "AWS_PROXY"

  connection_type      = "INTERNET"
  description          = "Lambda integration"
  integration_method   = "POST"
  integration_uri      = aws_lambda_function.scheduler_function.invoke_arn
  passthrough_behavior = "WHEN_NO_MATCH"
}

resource "aws_apigatewayv2_route" "default_route" {
  api_id    = aws_apigatewayv2_api.http.id
  route_key = "POST /{prefix}"
  target    = "integrations/${aws_apigatewayv2_integration.lambda.id}"
}

resource "aws_apigatewayv2_deployment" "deployment" {
  api_id = aws_apigatewayv2_api.http.id

  depends_on = [
    aws_apigatewayv2_integration.lambda,
    aws_apigatewayv2_route.default_route,
  ]

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_apigatewayv2_stage" "stage" {
  api_id        = aws_apigatewayv2_api.http.id
  name          = "dev"
  description   = "My test stage"
  deployment_id = aws_apigatewayv2_deployment.deployment.id

  default_route_settings {
    data_trace_enabled       = true
    detailed_metrics_enabled = true
    logging_level            = "INFO"
    throttling_burst_limit   = 5000
    throttling_rate_limit    = 10000
  }
}

resource "aws_lambda_event_source_mapping" "event_source_mapping" {
  event_source_arn = aws_sqs_queue.queue.arn
  function_name    = aws_lambda_function.consumer_function.function_name
  batch_size       = 3
}

output "api_endpoint" {
  description = "API endpoint URL"
  value       = aws_apigatewayv2_api.http.api_endpoint
}

output "bucket_name" {
  description = "S3 bucket name"
  value       = aws_s3_bucket.bucket.id
}
