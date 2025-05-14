import os
import re
import boto3
import json
import uuid
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def handler(event, context):
    batch_name = event["pathParameters"]["batchName"]
    bucket_name = event["pathParameters"]["bucketName"]

    logger.info(f"Batch Name: {batch_name}")
    logger.info(f"Bucket Name: {bucket_name}")

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
        m = re.search(r"batch[_-]([a-zA-Z]+)_", batch_name)
        if m:
            code = m.group(1).lower()
            dir_code = "vi" if code in ["vi", "va"] else "loc" if code == "lc" else code
        else:
            dir_code = batch_name

        prefix_base = os.environ.get("BATCH_BASED_PREFIX", "loc-preservation/lcbp/ndnp")
        prefix = os.path.join(prefix_base, dir_code, batch_name)
        keys = get_tif_files(bucket_name, prefix)

        # Check alternative prefixes if no TIFF files found
        if not keys:
            if dir_code == "dlc":
                alt_dir_code = "loc"
                alt_prefix = os.path.join(prefix_base, alt_dir_code, batch_name)
                keys = get_tif_files(bucket_name, alt_prefix)
                prefix = alt_prefix if keys else prefix

            elif dir_code == "vi":
                alt_dir_code = "virginia"
                alt_prefix = os.path.join(prefix_base, alt_dir_code, batch_name)
                keys = get_tif_files(bucket_name, alt_prefix)
                prefix = alt_prefix if keys else prefix

        if not keys:
            logger.error(f"No TIFF files found in prefix: {prefix}")
            return {
                "statusCode": 404,
                "body": json.dumps(f"No TIFF files found at prefix: {prefix}"),
            }

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
