import os
import boto3
import json
import uuid
from datetime import datetime
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def handler(event, context):
    # Retrieve the S3 bucket and prefix from path parameters
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
        # Use the original prefix first
        original_prefix = prefix
        keys = get_tif_files(bucket_name, original_prefix)

        # List of alternative prefixes to try if no TIFF files are found.
        # Always do replacements on the original to avoid cascading changes.
        alternatives = [
            original_prefix.replace("/ndnp/dlc/", "/ndnp/loc/"),
            original_prefix.replace("/ndnp/dlc/", "/ndnp/vi/"),
            original_prefix.replace("/ndnp/dlc/", "/ndnp/virginia/"),
        ]

        for alt_prefix in alternatives:
            if keys:
                # We already found some TIFF files, no need to continue alternatives.
                break
            logger.info(f"No files found at {prefix}. Trying alternative prefix: {alt_prefix}.")
            keys = get_tif_files(bucket_name, alt_prefix)
            # Update the prefix to the one that yielded files if found.
            if keys:
                prefix = alt_prefix

        # If still no keys, then exit with error.
        if not keys:
            logger.error(
                f"No TIFF files found in any of the tested prefixes: {original_prefix}, "
                f"{alternatives[0]}, {alternatives[1]}, {alternatives[2]}."
            )
            return {
                "statusCode": 404,
                "body": json.dumps(
                    f"No TIFF files found at any of the prefixes: {original_prefix}, "
                    f"{alternatives[0]}, {alternatives[1]}, {alternatives[2]}."
                ),
            }

        # Generate a unique job name using the (potentially updated) prefix directory name
        job_name = os.path.split(prefix)[1] + "__" + str(uuid.uuid4())
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
