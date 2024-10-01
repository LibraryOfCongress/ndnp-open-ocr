import os
import boto3
import json
import uuid
from datetime import datetime
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def handler(event, context):
    prefix = event["pathParameters"]["prefix"]
    bucket_name = event["pathParameters"]["bucketName"]

    logger.info(f"Bucket name: {bucket_name}")
    logger.info(f"Prefix: {prefix}")

    s3 = boto3.client("s3")
    batch = boto3.client("batch")

    batch_job_queue = os.environ.get("BATCH_QUEUE")
    batch_job_definition = os.environ.get("BATCH_JOB_DEFINITION")

    logger.info(f"Batch Job Queue: {batch_job_queue}")
    logger.info(f"Batch Job Definition: {batch_job_definition}")

    # Get list of TIF keys in the specified S3 prefix
    def get_tif_files(bucket, prefix):
        """Get list of .tif files in the specified S3 prefix."""
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
        # First, try the /ndnp/dlc/ prefix
        keys = get_tif_files(bucket_name, prefix)

        # If no files are found, try the alternative /ndnp/loc/ prefix. There are a handful of batches
        # that are stored in the /ndnp/loc/ prefix instead of /ndnp/dlc/
        if not keys:
            alternative_prefix = prefix.replace("/ndnp/dlc/", "/ndnp/loc/")
            logger.info(f"No files found at {prefix}, trying {alternative_prefix} instead.")
            keys = get_tif_files(bucket_name, alternative_prefix)

        # If no files are found in both prefixes, return an error
        if not keys:
            logger.error(f"No TIFF files found in both {prefix} and {alternative_prefix}.")
            return {
                "statusCode": 404,
                "body": json.dumps(f"No TIFF files found at {prefix} or {alternative_prefix}."),
            }

        # Name of AWS Batch job
        job_name = os.path.split(prefix)[1] + "__" + str(uuid.uuid4())

        # Submit AWS Batch Array Job
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
