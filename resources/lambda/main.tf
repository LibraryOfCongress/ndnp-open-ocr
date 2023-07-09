data "archive_file" "zip" {
  type        = "zip"
  source_dir  = var.source_dir
  output_path = var.output_path
}

resource "aws_lambda_function" "scheduler_function" {
  function_name    = "ndnp-open-ocr-scheduler-lambda-function-dev"
  filename         = var.output_path
  handler          = "scheduler.handler"
  role             = var.lambda_role_arn
  runtime          = "python3.8"
  source_code_hash = filebase64sha256(data.archive_file.zip.output_path)
  timeout          = 120

  environment {
    variables = {
      TESSDATA_PREFIX    = "/opt/share/tessdata"
      LD_LIBRARY_PATH    = "/opt/lib"
      PATH               = "/opt/bin:/usr/local/bin:/usr/bin:/bin"
      TMP                = "/tmp",
      INPUT_BUCKET_NAME = var.aws_s3_input_bucket
      QUEUE_URL = var.queue_url,
      TABLE_NAME = var.table_name
    }
  }

   layers = [
    aws_lambda_layer_version.lambda_layer.arn,
  ]

}

resource "aws_lambda_function" "consumer_function" {
  function_name    = "ndnp-open-ocr-consumer-lambda-function-dev"
  filename         = var.output_path
  handler          = "consumer.handler"
  role             = var.lambda_role_arn
  runtime          = "python3.8"
  timeout          = 900
  source_code_hash = filebase64sha256(data.archive_file.zip.output_path)
  memory_size      = 1024


  layers = [
    aws_lambda_layer_version.lambda_layer.arn,
    "arn:aws:lambda:us-east-2:764866452798:layer:ghostscript:13",
    "arn:aws:lambda:us-east-2:445285296882:layer:perl-5-32-runtime-al2:2"
  ]

  environment {
    variables = {
      TESSDATA_PREFIX    = "/opt/share/tessdata"
      LD_LIBRARY_PATH    = "/opt/lib"
      PATH               = "/opt/bin:/usr/local/bin:/usr/bin:/bin"
      TMP                = "/tmp"
      OUTPUT_BUCKET_NAME = var.aws_s3_output_bucket
      INPUT_BUCKET_NAME =  var.aws_s3_input_bucket
      QUEUE_URL = var.queue_url,
      TABLE_NAME = var.table_name
    }
  }
}

resource "aws_lambda_function" "dlq_consumer_function" {
  function_name    = "ndnp-open-ocr-dlq-consumer-function"
  filename         = var.output_path
  handler          = "dlq_consumer.handler"
  role             = var.lambda_role_arn
  runtime          = "python3.8"
  timeout          = 900
  source_code_hash = filebase64sha256(data.archive_file.zip.output_path)
  memory_size      = 1024


  layers = [
    aws_lambda_layer_version.lambda_layer.arn,
    "arn:aws:lambda:us-east-2:764866452798:layer:ghostscript:13",
    "arn:aws:lambda:us-east-2:445285296882:layer:perl-5-32-runtime-al2:2"
  ]

  environment {
    variables = {
      TESSDATA_PREFIX    = "/opt/share/tessdata"
      LD_LIBRARY_PATH    = "/opt/lib"
      PATH               = "/opt/bin:/usr/local/bin:/usr/bin:/bin"
      TMP                = "/tmp"
      DLQ_QUEUE_URL = var.dlq_queue_arn
    }
  }
}



resource "aws_lambda_layer_version" "lambda_layer" {
  filename            = "layers.zip"
  layer_name          = "ndnp-open-ocr-layer"
  compatible_runtimes = ["python3.8"]
  source_code_hash    = filebase64sha256("layers.zip")
}

resource "aws_cloudwatch_log_group" "scheduler_function_log_group" {
  name              = "/aws/lambda/${aws_lambda_function.scheduler_function.function_name}"
  retention_in_days = 14
}

resource "aws_cloudwatch_log_group" "consumer_function_log_group" {
  name              = "/aws/lambda/${aws_lambda_function.consumer_function.function_name}"
  retention_in_days = 14
}

resource "aws_lambda_permission" "apigw" {
  statement_id  = "AllowExecutionFromAPIGatewayScheduler"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.scheduler_function.function_name
  principal     = "apigateway.amazonaws.com"
}

resource "aws_lambda_event_source_mapping" "event_source_mapping" {
  event_source_arn = var.queue_arn
  function_name    = aws_lambda_function.consumer_function.function_name
  batch_size       = 3
}