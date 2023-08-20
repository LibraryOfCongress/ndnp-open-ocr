data "archive_file" "zip" {
  type        = "zip"
  source_dir  = var.source_dir
  output_path = var.output_path
}

# Scheduler to create 1 message per issue that needs to be processed by a
# NDNP Open OCR consumer/worker.
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
      TESSDATA_PREFIX   = "/opt/share/tessdata"
      LD_LIBRARY_PATH   = "/opt/lib"
      PATH              = "/opt/bin:/usr/local/bin:/usr/bin:/bin"
      TMP               = "/tmp",
      INPUT_BUCKET_NAME = var.aws_s3_input_bucket
      QUEUE_URL         = var.queue_url,
      TABLE_NAME        = var.table_name,
      ALTO_QUEUE_URL    = var.alto_queue_url
    }
  }

  layers = [
    aws_lambda_layer_version.lambda_layer.arn,
  ]

}


# Consumer to catch PDF SQS messages published by the scheduler
resource "aws_lambda_function" "consumer_function" {
  function_name    = "ndnp-open-ocr-pdf-consumer-lambda-function-dev"
  filename         = var.output_path
  handler          = "pdf_consumer.handler"
  role             = var.lambda_role_arn
  runtime          = "python3.8"
  timeout          = 900
  source_code_hash = filebase64sha256(data.archive_file.zip.output_path)
  memory_size      = 4000


  layers = [
    aws_lambda_layer_version.lambda_layer.arn,
    "arn:aws:lambda:us-east-2:764866452798:layer:ghostscript:13",
    "arn:aws:lambda:us-east-2:445285296882:layer:perl-5-32-runtime-al2:2"
  ]

  environment {
    variables = {
      TESSDATA_PREFIX    = "/opt/share/tessdata"
      LD_LIBRARY_PATH    = "/opt/lib"
      PATH               = "/opt/bin:/usr/local/bin:/usr/bin:/bin:/opt/python/lib/python3.8/site-packages"
      PYTHONPATH         = "/opt/python/:/opt/python/lib/python3.8/site-packages"
      OMP_THREAD_LIMIT   = 1
      TMP                = "/tmp"
      OUTPUT_BUCKET_NAME = var.aws_s3_output_bucket
      INPUT_BUCKET_NAME  = var.aws_s3_input_bucket
      QUEUE_URL          = var.queue_url,
      ALTO_QUEUE_URL     = var.alto_queue_url,
      TABLE_NAME         = var.table_name
    }
  }
}

# Consumer to catch ALTO SQS messages published by the scheduler
resource "aws_lambda_function" "alto_consumer_function" {
  function_name    = "ndnp-open-ocr-alto-consumer-lambda-function-dev"
  filename         = var.output_path
  handler          = "alto_consumer.handler"
  role             = var.lambda_role_arn
  runtime          = "python3.8"
  timeout          = 900
  source_code_hash = filebase64sha256(data.archive_file.zip.output_path)
  memory_size      = 4000


  layers = [
    aws_lambda_layer_version.lambda_layer.arn,
    "arn:aws:lambda:us-east-2:764866452798:layer:ghostscript:13",
    "arn:aws:lambda:us-east-2:445285296882:layer:perl-5-32-runtime-al2:2"
  ]

  environment {
    variables = {
      TESSDATA_PREFIX    = "/opt/share/tessdata"
      LD_LIBRARY_PATH    = "/opt/lib"
      PATH               = "/opt/bin:/usr/local/bin:/usr/bin:/bin:/opt/python/lib/python3.8/site-packages"
      PYTHONPATH         = "/opt/python/:/opt/python/lib/python3.8/site-packages"
      TMP                = "/tmp"
      OUTPUT_BUCKET_NAME = var.aws_s3_output_bucket
      INPUT_BUCKET_NAME  = var.aws_s3_input_bucket
      QUEUE_URL          = var.alto_queue_url,
      TABLE_NAME         = var.table_name
    }
  }
}

# Consumer for deadletter queue to catch failed issues.
resource "aws_lambda_function" "dlq_consumer_function" {
  function_name    = "ndnp-open-ocr-dlq-consumer-function"
  filename         = var.output_path
  handler          = "dlq_consumer.handler"
  role             = var.lambda_role_arn
  runtime          = "python3.8"
  timeout          = 15
  source_code_hash = filebase64sha256(data.archive_file.zip.output_path)
  memory_size      = 1024


  layers = [
    aws_lambda_layer_version.lambda_layer.arn,
    "arn:aws:lambda:us-east-2:764866452798:layer:ghostscript:13",
    "arn:aws:lambda:us-east-2:445285296882:layer:perl-5-32-runtime-al2:2"
  ]

  environment {
    variables = {
      TESSDATA_PREFIX = "/opt/share/tessdata"
      LD_LIBRARY_PATH = "/opt/lib"
      PATH            = "/opt/bin:/usr/local/bin:/usr/bin:/bin"
      TMP             = "/tmp"
      DLQ_QUEUE_URL   = var.dlq_queue_arn
      TABLE_NAME      = var.table_name
    }
  }
}


# AWS Lambda Layer to hold Python dependencies with pre-built layer.
# FIXME: Automate layer creation
resource "aws_lambda_layer_version" "lambda_layer" {
  filename            = "Tesseract5.3.2Layer.zip"
  layer_name          = "ndnp-open-ocr-layer"
  compatible_runtimes = ["python3.8"]
  source_code_hash    = filebase64sha256("new-layer.zip")
}

# Log group for scheduler
resource "aws_cloudwatch_log_group" "scheduler_function_log_group" {
  name              = "/aws/lambda/${aws_lambda_function.scheduler_function.function_name}"
  retention_in_days = 14
}

# Log group for PDF consumer
resource "aws_cloudwatch_log_group" "consumer_function_log_group" {
  name              = "/aws/lambda/${aws_lambda_function.consumer_function.function_name}"
  retention_in_days = 14
}

# Log group for Deadletter Queue consumer
resource "aws_cloudwatch_log_group" "dlq_consumer_function_log_group" {
  name              = "/aws/lambda/${aws_lambda_function.dlq_consumer_function.function_name}"
  retention_in_days = 14
}

# Log group for alto_consumer
resource "aws_cloudwatch_log_group" "alto_consumer_function_log_group" {
  name              = "/aws/lambda/${aws_lambda_function.alto_consumer_function.function_name}"
  retention_in_days = 14
}

# Permission for API Gateway to invoke the scheduler function
resource "aws_lambda_permission" "apigw" {
  statement_id  = "AllowExecutionFromAPIGatewayScheduler"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.scheduler_function.function_name
  principal     = "apigateway.amazonaws.com"
}

# Connect Consumer to Queue
resource "aws_lambda_event_source_mapping" "event_source_mapping" {
  event_source_arn = var.queue_arn
  function_name    = aws_lambda_function.consumer_function.function_name
  batch_size       = 1
}

# Connect DLQ Consumer to DLQ Queue
resource "aws_lambda_event_source_mapping" "dlq_event_source_mapping" {
  event_source_arn = var.dlq_queue_arn
  function_name    = aws_lambda_function.dlq_consumer_function.function_name
  batch_size       = 1
}

# Connect ALTO Consumer to ALTO Queue
resource "aws_lambda_event_source_mapping" "alto_event_source_mapping" {
  event_source_arn = var.alto_queue_arn
  function_name    = aws_lambda_function.alto_consumer_function.function_name
  batch_size       = 1
}
