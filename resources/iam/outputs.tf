output "lambda_role_arn" {
  value = aws_iam_role.lambda_role.arn
  description = "The ARN of the lambda role"
}

output "service_role_arn" {
  value = aws_iam_role.trust_for_lambda.arn
  description = "The ARN of the service role"
}

# output "aws_iam_attachment_arn" {
#     value = aws_iam_role_policy_attachment.attach_iam_policy_to_iam_role.arn
# }