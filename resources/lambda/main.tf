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
  runtime          = "python3.11"
  source_code_hash = filebase64sha256(data.archive_file.zip.output_path)
  timeout          = 500

  environment {
    variables = {
      TESSDATA_PREFIX   = "/opt/share/tessdata"
      LD_LIBRARY_PATH   = "/opt/lib"
      PATH              = "/opt/bin:/usr/local/bin:/usr/bin:/bin"
      TMP               = "/tmp",
      QUEUE_URL         = var.queue_url,
      TABLE_NAME        = var.table_name,
    }
  }

}

# Get job metadata from DynamoDB to serve to CLI.
resource "aws_lambda_function" "get_job_function" {
  function_name    = "ndnp-open-ocr-get-job-lambda-function-dev"
  filename         = var.output_path
  handler          = "get_job.handler"
  role             = var.lambda_role_arn
  runtime          = "python3.11"
  source_code_hash = filebase64sha256(data.archive_file.zip.output_path)
  timeout          = 500

  environment {
    variables = {
      TESSDATA_PREFIX   = "/opt/share/tessdata"
      LD_LIBRARY_PATH   = "/opt/lib"
      PATH              = "/opt/bin:/usr/local/bin:/usr/bin:/bin"
      TMP               = "/tmp",
      # QUEUE_URL         = var.queue_url,
      TABLE_NAME        = var.table_name,
    }
  }

}


# Log group for scheduler
resource "aws_cloudwatch_log_group" "scheduler_function_log_group" {
  name              = "/aws/lambda/${aws_lambda_function.scheduler_function.function_name}"
  retention_in_days = 14
}

# # Log group for get_job
# resource "aws_cloudwatch_log_group" "get_job_function_log_group" {
#   name              = "/aws/lambda/${aws_lambda_function.get_job_function.function_name}"
#   retention_in_days = 14
# }
