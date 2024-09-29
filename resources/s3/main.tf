data "aws_iam_policy_document" "s3" {
  statement {
    actions   = ["s3:*"]
    resources = ["arn:aws:s3:::${var.bucket_name}/*"]
  }
}

resource "aws_s3_bucket" "bucket" {
  bucket = var.bucket_name
  acl    = "private"

  tags = {
    Environment = var.env
  }
}