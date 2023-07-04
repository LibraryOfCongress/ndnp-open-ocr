data "archive_file" "zip" {
  type        = "zip"
  source_dir  = var.source_dir
  output_path = var.output_path
}

resource "aws_lambda_function" "scheduler_function" {
  function_name    = "ndnp-open-ocr-scheduler-function"
  filename         = data.archive_file.zip.output_path
  handler          = "scheduler.handler"
  role             = var.lambda_role_arn
  runtime          = "python3.8"
  source_code_hash = filebase64sha256(data.archive_file.zip.output_path)
  timeout          = 120

#   environment {
#     variables = var.environment_variables
#   }
}

resource "aws_lambda_function" "consumer_function" {
  function_name    = "ndnp-open-ocr-consumer-function"
  filename         = data.archive_file.zip.output_path
  handler          = "consumer.handler"
  role             = var.lambda_role_arn
  runtime          = "python3.8"
  timeout          = 900
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
      OUTPUT_BUCKET_NAME = var.aws_s3_bucket
    }
  }
}


resource "aws_lambda_layer_version" "lambda_layer" {
  filename            = "layers.zip"
  layer_name          = "ndnp-open-ocr-layer"
  compatible_runtimes = ["python3.8"]
  source_code_hash    = filebase64sha256("layers.zip")
}
