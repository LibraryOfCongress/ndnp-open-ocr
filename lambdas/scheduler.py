import os
import re
import random
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
    source_uri = None
    sink_uri = None
    array_size_override = None
    img_extension = None
    if event.get("queryStringParameters"):
        flag = event["queryStringParameters"].get("use_segmenter", "false")
        use_segmenter = str(flag).lower() == "true"
        # Optional: connector wiring
        source_uri = event["queryStringParameters"].get("source_uri")
        sink_uri = event["queryStringParameters"].get("sink_uri")
        array_size_override = event["queryStringParameters"].get("array_size")
        # Optional: image extension (e.g., "jp2" or "tif" - defaults to "tif")
        img_extension = event["queryStringParameters"].get("img_extension")

    VALID_IMG_EXTENSIONS = {"jp2", "tif"}
    if img_extension and img_extension.lower() not in VALID_IMG_EXTENSIONS:
        msg = f"Invalid img_extension '{img_extension}'. Must be one of: {', '.join(sorted(VALID_IMG_EXTENSIONS))}"
        logger.error(msg)
        return {
            "statusCode": 400,
            "body": json.dumps(msg),
        }

    logger.info(f"Use segmenter: {use_segmenter}")

    logger.info(f"Batch Name: {batch_name}")
    logger.info(f"Bucket Name: {bucket_name}")

    s3 = boto3.client("s3")
    batch = boto3.client("batch")

    batch_job_queue = os.environ.get("BATCH_QUEUE")
    batch_job_definition = os.environ.get("BATCH_JOB_DEFINITION")

    logger.info(f"Batch Job Queue: {batch_job_queue}")
    logger.info(f"Batch Job Definition: {batch_job_definition}")

    def get_image_files(bucket, prefix, extension=".tif"):
        """Return list of image files from the specified S3 prefix.

        Args:
            bucket: S3 bucket name
            prefix: S3 prefix to search
            extension: File extension to match (case-insensitive)
        """
        keys = []
        paginator = s3.get_paginator("list_objects_v2")
        pages = paginator.paginate(Bucket=bucket, Prefix=prefix)
        for page in pages:
            if "Contents" in page:
                for obj in page["Contents"]:
                    file_name = obj["Key"]
                    if file_name.lower().endswith(extension):
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

        # Determine file extension to search for based on img_extension
        # Supports: "jp2" or "tif" (default)
        if img_extension and "jp2" in img_extension.lower():
            file_extension = ".jp2"
            worker_glob = "**/*.[jJ][pP]2"
        else:
            file_extension = ".tif"
            worker_glob = "**/*.[tT][iI][fF]"

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
            # For loc-preservation bucket, use LOC-specific directory structure
            # For other buckets, use batch_name directly as prefix
            if bucket_name == "loc-preservation":
                prefix_base = os.environ.get("BATCH_BASED_PREFIX", "loc-preservation/lcbp/ndnp")
                prefix = os.path.join(prefix_base, dir_code, batch_name, "")
            else:
                prefix = f"{batch_name}/"
            keys = get_image_files(bucket_name, prefix, file_extension)

        # Check alternative prefixes if no image files found (LOC-specific)
        if not keys and bucket_name == "loc-preservation":
            prefix_base = os.environ.get("BATCH_BASED_PREFIX", "loc-preservation/lcbp/ndnp")
            if dir_code == "dlc":
                alt_dir_code = "loc"
                alt_prefix = os.path.join(prefix_base, alt_dir_code, batch_name, "")
                keys = get_image_files(bucket_name, alt_prefix, file_extension)
                prefix = alt_prefix if keys else prefix

            elif dir_code == "vi":
                alt_dir_code = "virginia"
                alt_prefix = os.path.join(prefix_base, alt_dir_code, batch_name, "")
                keys = get_image_files(bucket_name, alt_prefix, file_extension)
                prefix = alt_prefix if keys else prefix

        if not keys:
            msg = f"No image files ({file_extension}) found in source data at s3://{bucket_name}/{prefix}"
            logger.error(msg)
            return {
                "statusCode": 404,
                "body": json.dumps(msg),
            }

        # Sample up to 5 random TIFs and check storage class + accessibility before submitting
        sample_keys = random.sample(keys, min(5, len(keys)))
        frozen_samples = []
        for key in sample_keys:
            info = {"Key": key}
            try:
                head = s3.head_object(Bucket=bucket_name, Key=key)
                info["StorageClass"] = head.get("StorageClass") or "STANDARD"
                # Attempt a 1-byte range GET to verify the object is actually accessible
                # (restored DEEP_ARCHIVE objects still report DEEP_ARCHIVE in StorageClass)
                s3.get_object(Bucket=bucket_name, Key=key, Range="bytes=0-0")
                info["Accessible"] = True
            except s3.exceptions.InvalidObjectState:
                info["Accessible"] = False
            except Exception as e:
                error_code = getattr(e, "response", {}).get("Error", {}).get("Code", type(e).__name__)
                if error_code == "InvalidObjectState":
                    info["Accessible"] = False
                else:
                    info.setdefault("StorageClass", "UNKNOWN")
                    info["Accessible"] = False
                    info["Error"] = str(e)
            frozen_samples.append(info)

        inaccessible = [s for s in frozen_samples if not s.get("Accessible", False)]
        if inaccessible:
            msg = {
                "error": "Batch is in frozen (Glacier) storage and cannot be processed",
                "detail": f"{len(inaccessible)} of {len(frozen_samples)} sampled TIFs are inaccessible. "
                          f"Submit a Platform Services ticket to restore the batch to standard storage and try again.",
                "sampled": frozen_samples,
            }
            logger.error("Storage class check failed: %s", msg)
            return {
                "statusCode": 409,
                "body": json.dumps(msg),
            }
        logger.info("Storage class check passed: %s", frozen_samples)

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
            {"name": "INPUT_GLOB", "value": worker_glob},
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
