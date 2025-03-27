data "aws_iam_policy_document" "s3" {
  statement {
    actions   = ["s3:*"]
    resources = [
      "arn:aws:s3:::${var.bucket_name}-${var.env}/*"
    ]
    principals {
      type        = "*"
      identifiers = ["*"]
    }
  }
  # Enforce SSL
  statement {
    sid    = "AllowSSLRequestsOnly"
    effect = "Deny"
    actions   = ["s3:*"]
    # TODO: Should the environment name be included in the bucket name?
    resources = [
      "arn:aws:s3:::${var.bucket_name}-${var.env}",
      "arn:aws:s3:::${var.bucket_name}-${var.env}/*"
    ]

    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}
# seperate ACL
# commenting this out for now since the bucket doesn't
# allow acls
# resource "aws_s3_bucket_acl" "bucket_acl" {
#   bucket = aws_s3_bucket.bucket.id
#   acl    = "private"
# }

# Add public access block
resource "aws_s3_bucket_public_access_block" "block_public_access" {
  bucket = aws_s3_bucket.bucket.id
  block_public_acls       = true
  ignore_public_acls      = true
  block_public_policy     = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket" "bucket" {
  bucket = "${var.bucket_name}-${var.env}"
  tags = {
    Environment = var.env
  }
}

# Attach the policy to the bucket
resource "aws_s3_bucket_policy" "bucket_policy" {
  bucket = aws_s3_bucket.bucket.id
  policy = data.aws_iam_policy_document.s3.json
}