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
    use_segmenter = False
    if event.get("queryStringParameters"):
        flag = event["queryStringParameters"].get("use_segmenter", "false")
        use_segmenter = str(flag).lower() == "true"
        # Optional: connector wiring
        source_uri = event["queryStringParameters"].get("source_uri")
        sink_uri = event["queryStringParameters"].get("sink_uri")
        array_size_override = event["queryStringParameters"].get("array_size")
    logger.info(f"Use segmenter: {use_segmenter}")

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
        else:
            # Handle non-standard batch names like "dlc_alpha_ver01"
            m = re.match(r"([a-zA-Z]+)_", batch_name)
            code = m.group(1).lower() if m else batch_name

        code_to_dir = {
            "lc": "loc",
            "vi": "vi",
            "va": "vi",
            "lv": "vi",
        }
        dir_code = code_to_dir.get(code, code)

        # If custom connectors provided, pass them through and compute array size from override
        # Otherwise, default to S3 discovery using historical NDNP layout.
        prefix = None
        keys = []

        if source_uri:
            logger.info("source_uri provided; will pass-through without listing.")
            if array_size_override is not None:
                try:
                    keys = [None] * int(array_size_override)
                except Exception:
                    logger.warning(
                        "Invalid array_size override; falling back to S3 prefix discovery if possible."
                    )
        if not keys:
            # Organization-agnostic default; override via BATCH_BASED_PREFIX
            prefix_base = os.environ.get("BATCH_BASED_PREFIX", "loc-preservation/lcbp/ndnp")
            # Require an exact batch directory by adding a trailing slash to the prefix.
            prefix = os.path.join(prefix_base, dir_code, batch_name, "")
            keys = get_tif_files(bucket_name, prefix)

        # Check alternative prefixes if no TIFF files found
        if not keys:
            if dir_code == "dlc":
                alt_dir_code = "loc"
                alt_prefix = os.path.join(prefix_base, alt_dir_code, batch_name, "")
                keys = get_tif_files(bucket_name, alt_prefix)
                prefix = alt_prefix if keys else prefix

            elif dir_code == "vi":
                alt_dir_code = "virginia"
                alt_prefix = os.path.join(prefix_base, alt_dir_code, batch_name, "")
                keys = get_tif_files(bucket_name, alt_prefix)
                prefix = alt_prefix if keys else prefix

        if not keys:
            msg = f"No TIFF files found in source data at s3://{bucket_name}/{prefix}"
            logger.error(msg)
            return {
                "statusCode": 404,
                "body": json.dumps(msg),
            }

        job_name = os.path.split(prefix.rstrip("/"))[-1] + "__" + str(uuid.uuid4())
        array_size = len(keys)
        logger.info(f"Submitting AWS Batch array job with size: {array_size}")

        env_overrides = [
            {"name": "BUCKET_NAME", "value": bucket_name},
            {"name": "PREFIX", "value": prefix or ""},
            {"name": "OUTPUT_PREFIX", "value": job_name},
            {"name": "USE_SEGMENTATION", "value": str(use_segmenter).lower()},
            # Flatten batch_* under job_id for worker outputs
            {"name": "DROP_BATCH_SUBDIR", "value": "true"},
        ]

        # Preferred: URI-style envs
        if not source_uri and prefix:
            # build default S3 source uri from discovery
            source_uri = f"s3://{bucket_name}/{prefix}"
        if not sink_uri:
            out_bucket = os.environ.get("OUTPUT_BUCKET_NAME", "")
            if out_bucket:
                sink_uri = f"s3://{out_bucket}/{job_name}"

        if source_uri:
            env_overrides.append({"name": "SOURCE_URI", "value": source_uri})
        if sink_uri:
            env_overrides.append({"name": "SINK_URI", "value": sink_uri})

        # No connector-specific envs; we prefer URI-based config only

        response = batch.submit_job(
            jobName=job_name,
            jobQueue=batch_job_queue,
            jobDefinition=batch_job_definition,
            arrayProperties={"size": array_size},
            containerOverrides={"environment": env_overrides},
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
