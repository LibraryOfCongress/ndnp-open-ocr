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
  timeout          = 500

  environment {
    variables = {
      TESSDATA_PREFIX   = "/opt/share/tessdata"
      LD_LIBRARY_PATH   = "/opt/lib"
      PATH              = "/opt/bin:/usr/local/bin:/usr/bin:/bin"
      TMP               = "/tmp",
      QUEUE_URL         = var.pdf_queue_url,
      TABLE_NAME        = var.table_name,
      ALTO_QUEUE_URL    = var.alto_queue_url
    }
  }

  layers = [
    aws_lambda_layer_version.lambda_layer.arn,
  ]

}

resource "aws_lambda_function" "get_job_function" {
  function_name    = "ndnp-open-ocr-get-job-lambda-function-dev"
  filename         = var.output_path
  handler          = "get_job.handler"
  role             = var.lambda_role_arn
  runtime          = "python3.8"
  source_code_hash = filebase64sha256(data.archive_file.zip.output_path)
  timeout          = 500

  environment {
    variables = {
      TABLE_NAME        = var.table_name,
    }
  }

}


# Consumer to catch PDF SQS messages published by the scheduler
resource "aws_lambda_function" "pdf_consumer_function" {
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
    # "arn:aws:lambda:us-east-2:764866452798:layer:ghostscript:13",
    # "arn:aws:lambda:us-east-2:445285296882:layer:perl-5-32-runtime-al2:2"
  ]

  environment {
    variables = {
      TESSDATA_PREFIX    = "/opt/share/tessdata"
      LD_LIBRARY_PATH    = "/opt/lib"
      PATH               = "/opt/bin:/usr/local/bin:/usr/bin:/bin:/opt/python/lib/python3.8/site-packages"
      PYTHONPATH         = "/opt/python/:/opt/python/lib/python3.8/site-packages:/tmp"
      OMP_THREAD_LIMIT   = 1
      TMP                = "/tmp"
      OUTPUT_BUCKET_NAME = var.aws_s3_output_bucket
      QUEUE_URL          = var.pdf_queue_url,
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
      QUEUE_URL          = var.alto_queue_url,
      TABLE_NAME         = var.table_name
    }
  }
}

# Consumer for deadletter queue to catch failed issues for PDFs
resource "aws_lambda_function" "pdf_dlq_consumer_function" {
  function_name    = "ndnp-open-ocr-pdf-dlq-consumer-function"
  filename         = var.output_path
  handler          = "pdf_dlq_consumer.handler"
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
      TESSDATA_PREFIX = "/opt/share/tessdata"
      LD_LIBRARY_PATH = "/opt/lib"
      PATH            = "/opt/bin:/usr/local/bin:/usr/bin:/bin"
      TMP             = "/tmp"
      DLQ_QUEUE_URL   = var.pdf_dlq_queue_arn
      OUTPUT_BUCKET_NAME = var.aws_s3_output_bucket
      TABLE_NAME         = var.table_name
      TABLE_NAME      = var.table_name
    }
  }
}

# Consumer for deadletter queue to catch failed issues for ALTOs
resource "aws_lambda_function" "alto_dlq_consumer_function" {
  function_name    = "ndnp-open-ocr-alto-dlq-consumer-function"
  filename         = var.output_path
  handler          = "alto_dlq_consumer.handler"
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
      TESSDATA_PREFIX = "/opt/share/tessdata"
      LD_LIBRARY_PATH = "/opt/lib"
      PATH            = "/opt/bin:/usr/local/bin:/usr/bin:/bin"
      TMP             = "/tmp"
      DLQ_QUEUE_URL   = var.alto_dlq_queue_arn
      OUTPUT_BUCKET_NAME = var.aws_s3_output_bucket
      TABLE_NAME         = var.table_name
      TABLE_NAME      = var.table_name
    }
  }
}


# AWS Lambda Layer to hold Python dependencies with pre-built layer.
# FIXME: Automate layer creation
resource "aws_lambda_layer_version" "lambda_layer" {
  filename            = "layer.zip"
  layer_name          = "ndnp-open-ocr-layer"
  compatible_runtimes = ["python3.8", "python3.9"]
  source_code_hash    = filebase64sha256("layer.zip")
}

# Log group for scheduler
resource "aws_cloudwatch_log_group" "scheduler_function_log_group" {
  name              = "/aws/lambda/${aws_lambda_function.scheduler_function.function_name}"
  retention_in_days = 14
}

# Log group for PDF consumer
resource "aws_cloudwatch_log_group" "pdf_consumer_function_log_group" {
  name              = "/aws/lambda/${aws_lambda_function.pdf_consumer_function.function_name}"
  retention_in_days = 14
}

# Log group for Deadletter Queue consumer
resource "aws_cloudwatch_log_group" "dlq_consumer_function_log_group" {
  name              = "/aws/lambda/${aws_lambda_function.pdf_dlq_consumer_function.function_name}"
  retention_in_days = 14
}

# Log group for alto_consumer
resource "aws_cloudwatch_log_group" "alto_consumer_function_log_group" {
  name              = "/aws/lambda/${aws_lambda_function.alto_consumer_function.function_name}"
  retention_in_days = 14
}

# Log group for alto_dlq_consumer
resource "aws_cloudwatch_log_group" "alto_dlq_consumer_function_log_group" {
  name              = "/aws/lambda/${aws_lambda_function.alto_dlq_consumer_function.function_name}"
  retention_in_days = 14
}


# Connect Consumer to Queue
resource "aws_lambda_event_source_mapping" "pdf_event_source_mapping" {
  event_source_arn = var.pdf_queue_arn
  function_name    = aws_lambda_function.pdf_consumer_function.function_name
  batch_size       = 1
}

# Connect PDF DLQ Consumer to PDF DLQ Queue
# resource "aws_lambda_event_source_mapping" "pdf_dlq_event_source_mapping" {
#   event_source_arn = var.pdf_dlq_queue_arn
#   function_name    = aws_lambda_function.pdf_dlq_consumer_function.function_name
#   batch_size       = 1
# }

# Connect ALTO Consumer to ALTO Queue
resource "aws_lambda_event_source_mapping" "alto_event_source_mapping" {
  event_source_arn = var.alto_queue_arn
  function_name    = aws_lambda_function.alto_consumer_function.function_name
  batch_size       = 1
}

# # Connect ALTO Consumer to ALTO DLQ Queue
# resource "aws_lambda_event_source_mapping" "alto_dlq_event_source_mapping" {
#   event_source_arn = var.alto_dlq_queue_arn
#   function_name    = aws_lambda_function.alto_dlq_consumer_function.function_name
#   batch_size       = 1
# }
