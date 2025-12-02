data "aws_caller_identity" "current" {}

locals {
  bucket_name = "${var.bucket_name}-${var.env}"
  bucket_arn  = "arn:aws:s3:::${local.bucket_name}"
}

data "aws_iam_policy_document" "s3" {
  # Deny non-SSL
  statement {
    sid     = "AllowSSLRequestsOnly"
    effect  = "Deny"
    actions = ["s3:*"]

    resources = [
      local.bucket_arn,
      "${local.bucket_arn}/*",
    ]

    principals {
      type        = "*"
      identifiers = ["*"]
    }

    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }

  # --- Include these only if this bucket is a server access logs target ---

  # Matches existing "S3ServerAccessLogsPolicy"
  statement {
    sid     = "S3ServerAccessLogsPolicy"
    effect  = "Allow"
    actions = ["s3:PutObject"]
    resources = [
      # match your current prefix exactly (as in the plan diff)
      "${local.bucket_arn}/s3-server-access-logs/*",
    ]

    principals {
      type        = "Service"
      identifiers = ["logging.s3.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [data.aws_caller_identity.current.account_id]
    }

    condition {
      test     = "ArnLike"
      variable = "aws:SourceArn"
      values   = [local.bucket_arn]
    }
  }

  # Matches existing "S3PolicyStmt-DO-NOT-MODIFY-1758763656648"
  statement {
    sid     = "S3PolicyStmt-DO-NOT-MODIFY-1758763656648"
    effect  = "Allow"
    actions = ["s3:PutObject"]
    resources = ["${local.bucket_arn}/*"]

    principals {
      type        = "Service"
      identifiers = ["logging.s3.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [data.aws_caller_identity.current.account_id]
    }
  }
}

resource "aws_s3_bucket" "bucket" {
  bucket = local.bucket_name
  tags = { Environment = var.env }
}

resource "aws_s3_bucket_public_access_block" "block_public_access" {
  bucket                  = aws_s3_bucket.bucket.id
  block_public_acls       = true
  ignore_public_acls      = true
  block_public_policy     = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_policy" "bucket_policy" {
  bucket = aws_s3_bucket.bucket.id
  policy = data.aws_iam_policy_document.s3.json
}
