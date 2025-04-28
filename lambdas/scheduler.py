import os
import re
import boto3
import json
import uuid
from datetime import datetime
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def handler(event, context):
    # Retrieve the S3 bucket and prefix from path parameters
    prefix_input = event["pathParameters"]["prefix"]
    bucket_name = event["pathParameters"]["bucketName"]

    logger.info(f"Bucket name: {bucket_name}")
    logger.info(f"Prefix input: {prefix_input}")

    s3 = boto3.client("s3")
    batch = boto3.client("batch")

    batch_job_queue = os.environ.get("BATCH_QUEUE")
    batch_job_definition = os.environ.get("BATCH_JOB_DEFINITION")

    logger.info(f"Batch Job Queue: {batch_job_queue}")
    logger.info(f"Batch Job Definition: {batch_job_definition}")

    def get_tif_files(bucket, prefix):
        """Return list of TIFF files from the specified S3 prefix."""
        keys = []
        paginator = s3.get_paginator("list_objects_v2")
        pages = paginator.paginate(Bucket=bucket, Prefix=prefix)
        for page in pages:
            if "Contents" in page:
                for obj in page["Contents"]:
                    file_name = obj["Key"]
                    if file_name.lower().endswith(".tif"):
                        keys.append(file_name)
        return keys

    try:
        # Build the S3 prefix based on the filename passed in
        batch_name = os.path.split(prefix_input.rstrip("/"))[-1]
        logger.info(f"Batch name: {batch_name}")
        # Extract the directory code from the batch name
        # Example: batch_name = "loc-preservation/lcbp/ndnp/virginia/batch_va_2023_01" should equal va
        m = re.search(r"batch[_-]([a-zA-Z]+)_", batch_name)
        if m:
            code = m.group(1).lower()
            # If the code is "va", set it to "virginia". There will be others in the future such as florida (fl vs fu, ...)
            if code == "va":
                dir_code = "virginia"
            else:
                dir_code = code
        else:
            dir_code = batch_name

        # Construct the prefix for the S3 bucket
        # Example: prefix = "loc-preservation/lcbp/ndnp/virginia/batch_va_2023_01/"
        prefix = os.path.join(
            os.environ.get("BATCH_BASED_PREFIX", "loc-preservation/lcbp/ndnp/"),
            dir_code,
            batch_name,
        )
        logger.info(f"Constructed prefix: {prefix}")

        # Retrieve TIFF files from the constructed prefix
        keys = get_tif_files(bucket_name, prefix)

        # If still no keys, then exit with error.
        if not keys:
            logger.error(f"No TIFF files found in prefix: {prefix}")
            return {
                "statusCode": 404,
                "body": json.dumps(f"No TIFF files found at prefix: {prefix}"),
            }

        # Generate a unique job name using the (potentially updated) prefix directory name
        job_name = os.path.split(prefix.rstrip("/"))[-1] + "__" + str(uuid.uuid4())
        array_size = len(keys)
        logger.info(f"Submitting AWS Batch array job with size: {array_size}")

        response = batch.submit_job(
            jobName=job_name,
            jobQueue=batch_job_queue,
            jobDefinition=batch_job_definition,
            arrayProperties={"size": array_size},
            containerOverrides={
                "environment": [
                    {"name": "BUCKET_NAME", "value": bucket_name},
                    {"name": "PREFIX", "value": prefix},
                    {"name": "OUTPUT_PREFIX", "value": job_name},
                ]
            },
        )

        logger.info(f"AWS Batch ID: {response['jobId']}")
        logger.info(f"Job Name (output prefix): {job_name}")

        return {
            "statusCode": 200,
            "body": json.dumps({"job": job_name, "num_issues": len(keys)}),
        }

    except Exception as e:
        logger.error(f"Error occurred: {e}")
        return {
            "statusCode": 400,
            "body": "An error has occurred. Please check batch and bucket names and make sure they are correct.",
        }
