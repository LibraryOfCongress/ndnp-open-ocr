import os
import csv
import json
import time
import uuid
import random
import logging
import boto3
from botocore.exceptions import ClientError


logger = logging.getLogger(__name__)
if not logger.handlers:
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger.setLevel(os.getenv("LOG_LEVEL", "INFO"))

s3 = boto3.client("s3")


def _iter_keys(bucket: str, prefix: str):
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []) if page else []:
            yield {
                "Key": obj.get("Key"),
                "Size": obj.get("Size"),
                "LastModified": obj.get("LastModified").isoformat()
                if obj.get("LastModified")
                else None,
                "StorageClass": obj.get("StorageClass"),
                "ETag": obj.get("ETag"),
            }


def _sample_access(bucket: str, keys: list[str], n: int = 5):
    """Try a 1-byte range GET on up to N randomly-selected keys to detect archived storage."""
    sample = random.sample(keys, min(n, len(keys))) if keys else []
    out = []
    for key in sample:
        info = {"Key": key}
        try:
            # Head for storage class context
            head = s3.head_object(Bucket=bucket, Key=key)
            info["StorageClass"] = head.get("StorageClass")
            # Range GET: archived classes raise InvalidObjectState
            s3.get_object(Bucket=bucket, Key=key, Range="bytes=0-0")
            info["Accessible"] = True
        except ClientError as e:
            info["Accessible"] = False
            info["ErrorCode"] = e.response.get("Error", {}).get("Code")
        except Exception as e:  # defensive
            info["Accessible"] = False
            info["ErrorCode"] = type(e).__name__
        out.append(info)
    return out


def handler(event, context):
    # Params: bucketName, prefix OR JSON body with {bucket, batches:[...]}.
    path = event.get("pathParameters") or {}
    query = event.get("queryStringParameters") or {}

    logger.info("Received event keys: %s", list(event.keys()))
    raw_body = event.get("body")
    try:
        body = json.loads(raw_body) if isinstance(raw_body, str) else (raw_body or {})
    except Exception:
        body = {}

    # Accept top-level event fields as well (direct Lambda invoke without API Gateway)
    input_bucket = (
        body.get("bucket")
        or path.get("bucketName")
        or query.get("bucket")
        or event.get("bucket")
    )

    # Input forms:
    #  - single prefix via path/query
    #  - list of batches/prefixes via body.batches or body.prefixes
    single_prefix = (
        path.get("prefix")
        or query.get("prefix")
        or event.get("prefix")
    )
    batches = (
        body.get("batches")
        or body.get("prefixes")
        or event.get("batches")
        or event.get("prefixes")
        or []
    )

    # If input_bucket wasn't provided, try to derive it from the first batches/prefix entry
    # that looks like "<bucket>/<key>" or "s3://<bucket>/<key>".
    if not input_bucket:
        candidates: list[str] = []
        if isinstance(batches, list) and batches:
            for x in batches:
                if isinstance(x, str) and x:
                    candidates.append(x)
        if not candidates and single_prefix:
            candidates.append(single_prefix)

        def _derive_bucket(p: str) -> str | None:
            p = p.strip()
            if not p:
                return None
            if p.startswith("s3://"):
                try:
                    _, rest = p.split("s3://", 1)
                    b2, _ = rest.split("/", 1)
                    return b2
                except ValueError:
                    return None
            if "/" in p:
                return p.split("/", 1)[0]
            return None

        for cand in candidates:
            b = _derive_bucket(cand)
            if b:
                input_bucket = b
                logger.info("Derived input_bucket from batches/prefix: %s", input_bucket)
                break

    if not input_bucket:
        logger.error("Missing input bucket in event/body/path/query and could not derive from prefixes")
        return {"statusCode": 400, "body": json.dumps("Missing bucketName/bucket.")}

    def normalize_prefix(p: str) -> str:
        raw_p = (p or "").strip()
        norm = raw_p
        if norm.startswith("s3://"):
            # s3://bucket/key -> keep only key
            try:
                _, rest = norm.split("s3://", 1)
                b2, key = rest.split("/", 1)
                norm = key
            except ValueError:
                norm = ""
        elif norm.startswith(f"/{input_bucket}/"):
            # Explicit "/bucket/..." style -> strip the leading slash+bucket
            norm = norm[len(input_bucket) + 2 :]
        # NOTE: do NOT strip a plain leading "bucket/" because many LOC
        # collections intentionally include "loc-preservation/" as the first key segment.

        # Prepend special top-level directory for preservation data when missing
        if input_bucket == "loc-preservation" and not norm.startswith("loc-preservation/"):
            norm = f"loc-preservation/{norm.lstrip('/')}"

        # Ensure trailing slash for prefix-style listing
        norm = norm.lstrip("/")
        if norm and not norm.endswith("/"):
            norm = norm + "/"
        logger.info("Normalized prefix: raw=%s -> normalized=%s (bucket=%s)", raw_p, norm, input_bucket)
        return norm

    prefixes = []
    if single_prefix:
        prefixes.append(normalize_prefix(single_prefix))
    if isinstance(batches, list):
        prefixes.extend([normalize_prefix(x) for x in batches if isinstance(x, str)])

    if not prefixes:
        logger.error("No prefixes provided after normalization")
        return {"statusCode": 400, "body": json.dumps("Missing prefix or batches.")}

    include_storage_class = (
        (query.get("include_storage_class") if query else None)
        or body.get("include_storage_class", False)
        or event.get("include_storage_class", False)
    )
    # Normalize truthy string values
    if isinstance(include_storage_class, str):
        include_storage_class = include_storage_class.lower() in ("true", "1", "yes")

    suffix = None
    sample_n = int(
        (query.get("sample_access_check") if query else None)
        or body.get("sample_access_check", 0)
        or os.environ.get("SAMPLE_ACCESS_N", "0")
        or 0
    )

    # Decide output target (always write to S3)
    out_bucket = (
        (query.get("output_bucket") if query else None)
        or body.get("output_bucket")
        or event.get("output_bucket")
        or os.environ.get("OUTPUT_BUCKET_NAME")
    )
    out_prefix = (
        (query.get("output_prefix") if query else None)
        or body.get("output_prefix")
        or event.get("output_prefix")
        or os.environ.get("OUTPUT_PREFIX", "keys_exports")
    )

    logger.info(
        "Params: input_bucket=%s prefixes=%s out_bucket=%s out_prefix=%s",
        input_bucket,
        prefixes,
        out_bucket,
        out_prefix,
    )

    # Build export name using first prefix and timestamp
    first_part = prefixes[0].strip("/").replace("/", "_")[:60] or "multi"
    export_name = f"keys_{first_part}_{int(time.time())}_{uuid.uuid4().hex[:8]}.csv"
    tmp_path = f"/tmp/{export_name}"

    total = 0
    tif_keys = []
    per_prefix_counts = []

    with open(tmp_path, "w", newline="") as f:
        writer = csv.writer(f)
        if include_storage_class:
            writer.writerow(["Bucket Name", "Key", "StorageClass"])
        else:
            writer.writerow(["Bucket Name", "Key"])
        for p in prefixes:
            logger.info("Listing keys: bucket=%s prefix=%s", input_bucket, p)
            cnt = 0
            for obj in _iter_keys(input_bucket, p):
                key = obj.get("Key")
                if include_storage_class:
                    storage = obj.get("StorageClass") or "STANDARD"
                    writer.writerow([input_bucket, key, storage])
                else:
                    writer.writerow([input_bucket, key])
                cnt += 1
                total += 1
                if key and key.lower().endswith(".tif"):
                    tif_keys.append(key)
            per_prefix_counts.append({"prefix": p, "count": cnt})
            logger.info("Found %d keys under prefix %s", cnt, p)

    sample_info = _sample_access(input_bucket, tif_keys, sample_n) if sample_n > 0 else []
    if sample_info:
        logger.info("Sample access check results: %s", sample_info)
    logger.info("Total keys written: %d", total)

    # Always upload to S3 and return a summary JSON
    if not out_bucket:
        return {"statusCode": 400, "body": json.dumps("Missing output_bucket or OUTPUT_BUCKET_NAME for S3 export.")}
    s3_key = f"{out_prefix.rstrip('/')}/{export_name}"
    s3.upload_file(tmp_path, out_bucket, s3_key)
    logger.info("Uploaded CSV to s3://%s/%s", out_bucket, s3_key)

    summary = {
        "message": (
            f"Export complete: {total} keys from {len(prefixes)} prefix(es) "
            f"written to s3://{out_bucket}/{s3_key}"
        ),
        "input_bucket": input_bucket,
        "prefix_count": len(prefixes),
        "total_keys": total,
        "per_prefix_counts": per_prefix_counts,
        "csv_s3_uri": f"s3://{out_bucket}/{s3_key}",
        "output_bucket": out_bucket,
        "output_key": s3_key,
        "sample_access": sample_info,
    }
    return {"statusCode": 200, "body": json.dumps(summary)}
