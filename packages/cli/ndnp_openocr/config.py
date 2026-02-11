"""CLI Configuration - loads from .env file in current working directory."""
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path.cwd() / ".env")
except ImportError:
    pass

AWS_ACCOUNT_ID = os.getenv("AWS_ACCOUNT_ID", "")
AWS_REGION = os.getenv("AWS_REGION", "us-east-2")
ENVIRONMENT = os.getenv("ENVIRONMENT", "development-deployment")
S3_OUTPUT_BUCKET_PREFIX = os.getenv("S3_OUTPUT_BUCKET_PREFIX", "ndnp-open-ocr-output-bucket")

OUTPUT_BUCKET_NAME = f"{S3_OUTPUT_BUCKET_PREFIX}-{ENVIRONMENT}"
SCHEDULER_ARN = f"arn:aws:lambda:{AWS_REGION}:{AWS_ACCOUNT_ID}:function:ndnp-open-ocr-scheduler-lambda-function-{ENVIRONMENT}"
GET_JOB_ARN = f"arn:aws:lambda:{AWS_REGION}:{AWS_ACCOUNT_ID}:function:ndnp-open-ocr-get-job-lambda-function-{ENVIRONMENT}"
LIST_KEYS_ARN = f"arn:aws:lambda:{AWS_REGION}:{AWS_ACCOUNT_ID}:function:ndnp-open-ocr-list-keys-{ENVIRONMENT}"
