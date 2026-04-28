data "archive_file" "zip" {
  type        = "zip"
  source_dir  = var.source_dir
  output_path = var.output_path
}

# Scheduler kicks of AWS Batch jobs to kick off OCR reprocessing of an entire batch.
resource "aws_lambda_function" "scheduler_function" {
  function_name    = "ndnp-open-ocr-scheduler-lambda-function-${var.env}"
  filename         = var.output_path
  handler          = "scheduler.handler"
  role             = aws_iam_role.lambda_role.arn
  runtime          = "python3.12"
  source_code_hash = filebase64sha256(data.archive_file.zip.output_path)
  timeout          = 500

  environment {
    variables = {
      TESSDATA_PREFIX      = "/opt/share/tessdata"
      LD_LIBRARY_PATH      = "/opt/lib"
      PATH                 = "/opt/bin:/usr/local/bin:/usr/bin:/bin"
      TMP                  = "/tmp"
      BATCH_QUEUE          = var.batch_job_queue
      BATCH_JOB_DEFINITION = var.batch_job_definition
    }
  }
}

# Get job Lambda function to serve job metadata to CLI
resource "aws_lambda_function" "get_job_function" {
  function_name    = "ndnp-open-ocr-get-job-lambda-function-${var.env}"
  filename         = var.output_path
  handler          = "get_job_status.handler"
  role             = aws_iam_role.lambda_role.arn
  runtime          = "python3.12"
  source_code_hash = filebase64sha256(data.archive_file.zip.output_path)
  timeout          = 500

  environment {
    variables = {
      TESSDATA_PREFIX = "/opt/share/tessdata"
      LD_LIBRARY_PATH = "/opt/lib"
      PATH            = "/opt/bin:/usr/local/bin:/usr/bin:/bin"
      TMP             = "/tmp"
      BATCH_QUEUE          = var.batch_job_queue
      OUTPUT_BUCKET_NAME          = var.aws_s3_output_bucket
    }
  }
}


resource "aws_iam_role" "lambda_role" {
  name               = "ndnp-open-ocr-lambda-role-${var.env}"
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

resource "aws_iam_role" "trust_for_lambda" {
  name = "ndnp-open-ocr-fargate-execution-role-${var.env}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Action = "sts:AssumeRole",
        Principal = {
          Service = "lambda.amazonaws.com"
        },
        Effect = "Allow"
      },
    ]
  })
}

resource "aws_iam_policy" "iam_policy_for_lambda" {
  name        = "ndnp-open-ocr-iam-policy-for-lambda-${var.env}"
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
       "s3:*",
       "batch:*"
     ],
     "Resource": "*",
     "Effect": "Allow"
 }
 ]
}
EOF
}

resource "aws_iam_role_policy_attachment" "attach_iam_policy_to_iam_role" {
  role       = aws_iam_role.trust_for_lambda.name
  policy_arn = aws_iam_policy.iam_policy_for_lambda.arn
}

resource "aws_iam_role_policy_attachment" "attach_iam_policy_to_lambda_role" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = aws_iam_policy.iam_policy_for_lambda.arn
}

# Log group for scheduler
resource "aws_cloudwatch_log_group" "scheduler_function_log_group" {
  name              = "/aws/lambda/${aws_lambda_function.scheduler_function.function_name}"
  retention_in_days = 14
}

# Log group for get job function
resource "aws_cloudwatch_log_group" "get_job_function_log_group" {
  name              = "/aws/lambda/${aws_lambda_function.get_job_function.function_name}"
  retention_in_days = 14
}

resource "aws_lambda_function" "batch_completion_function" {
  function_name    = "ndnp-open-ocr-batch-completion-${var.env}"
  filename         = var.output_path
  handler          = "batch_completion_trigger.handler"
  role             = aws_iam_role.lambda_role.arn  # reusing existing IAM role
  runtime          = "python3.12"
  source_code_hash = filebase64sha256(data.archive_file.zip.output_path)
  timeout          = 500

  environment {
    variables = {
      OUTPUT_BUCKET_NAME = var.aws_s3_output_bucket
      BATCH_QUEUE        = var.batch_job_queue
    }
  }
}

# CloudWatch Log Group for batch completion function
resource "aws_cloudwatch_log_group" "batch_completion_function_log_group" {
  name              = "/aws/lambda/${aws_lambda_function.batch_completion_function.function_name}"
  retention_in_days = 14
}

# Lambda function to list S3 keys and export CSV
resource "aws_lambda_function" "list_keys_function" {
  function_name    = "ndnp-open-ocr-list-keys-${var.env}"
  filename         = var.output_path
  handler          = "list_keys.handler"
  role             = aws_iam_role.lambda_role.arn
  runtime          = "python3.12"
  source_code_hash = filebase64sha256(data.archive_file.zip.output_path)
  timeout          = 900
  memory_size      = 2048

  environment {
    variables = {
      OUTPUT_BUCKET_NAME = var.aws_s3_output_bucket
      OUTPUT_PREFIX      = "keys_exports"
      SAMPLE_ACCESS_N    = "5"
    }
  }
}

# Log group for list keys function
resource "aws_cloudwatch_log_group" "list_keys_function_log_group" {
  name              = "/aws/lambda/${aws_lambda_function.list_keys_function.function_name}"
  retention_in_days = 14
}
