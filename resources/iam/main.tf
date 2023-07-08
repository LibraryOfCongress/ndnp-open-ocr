resource "aws_iam_role" "lambda_role" {
  name               = "ndnp-open-ocr-lambda-role-dev"
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
  name        = "ndnp-open-ocr-iam-policy-for-lambda-dev"
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
       "s3:*",
       "dynamodb:*"
     ],
     "Resource": "*",
     "Effect": "Allow"
 }, {
     "Action": [
       "s3:GetObject",
       "s3:ListBucket"
     ],
     "Resource": [
       "arn:aws:s3:::loc-preservation",
       "arn:aws:s3:::loc-preservation/*"
     ],
     "Effect": "Allow"
   }
 ]
}
EOF
}

resource "aws_iam_role_policy_attachment" "attach_iam_policy_to_iam_role" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = aws_iam_policy.iam_policy_for_lambda.arn
}

resource "aws_iam_role" "iam_for_lambda" {
  name = "ndnp-open-ocr-lambda-service-role-dev"

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
