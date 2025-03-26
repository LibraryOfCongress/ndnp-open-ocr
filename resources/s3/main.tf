data "aws_iam_policy_document" "s3" {
  statement {
    actions   = ["s3:*"]
    resources = [
      "arn:aws:s3:::${var.bucket_name}/*"
    ]
  }
  # Enforce SSL
  statement {
    sid    = "AllowSSLRequestsOnly"
    effect = "Deny"
    actions   = ["s3:*"]
    # TODO: Should the environment name be included in the bucket name?
    resources = [
      "arn:aws:s3:::${var.bucket_name}",
      "arn:aws:s3:::${var.bucket_name}/*"
    ]

    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}

resource "aws_s3_bucket" "bucket" {
  bucket = "${var.bucket_name}-${var.env}"
  acl    = "private"

  tags = {
    Environment = var.env
  }
}