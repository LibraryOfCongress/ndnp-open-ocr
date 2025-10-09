import os
import csv
import json
import time
import uuid
import boto3
from botocore.exceptions import ClientError


s3 = boto3.client("s3")


def _iter_keys(bucket: str, prefix: str, suffix: str | None = None):
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []) if page else []:
            key = obj.get("Key")
            if suffix and key and not key.endswith(suffix):
                continue
            yield {
                "Key": key,
                "Size": obj.get("Size"),
                "LastModified": obj.get("LastModified").isoformat()
                if obj.get("LastModified")
                else None,
                "StorageClass": obj.get("StorageClass"),
                "ETag": obj.get("ETag"),
            }


def _sample_access(bucket: str, keys: list[str], n: int = 5):
    """Try a 1-byte range GET on up to first N keys to detect archived storage."""
    sample = keys[: max(0, min(n, len(keys)))]
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

    raw_body = event.get("body")
    try:
        body = json.loads(raw_body) if isinstance(raw_body, str) else (raw_body or {})
    except Exception:
        body = {}

    bucket = (
        body.get("bucket")
        or path.get("bucketName")
        or query.get("bucket")
    )
    if not bucket:
        return {"statusCode": 400, "body": json.dumps("Missing bucketName/bucket.")}

    # Input forms:
    #  - single prefix via path/query
    #  - list of batches/prefixes via body.batches or body.prefixes
    single_prefix = path.get("prefix") or query.get("prefix")
    batches = body.get("batches") or body.get("prefixes") or []

    def normalize_prefix(p: str) -> str:
        p = (p or "").strip()
        if p.startswith("s3://"):
            # s3://bucket/key...
            try:
                _, rest = p.split("s3://", 1)
                b2, key = rest.split("/", 1)
                if b2 != bucket:
                    # If a different bucket was embedded, ignore it and use provided bucket
                    p = key
                else:
                    p = key
            except ValueError:
                p = ""
        # Strip leading bucket name if accidentally included
        for lead in (f"{bucket}/", f"/{bucket}/", "loc-preservation/"):
            if p.startswith(lead):
                p = p[len(lead) :]
        # Strip any leading slash and ensure trailing slash
        p = p.lstrip("/")
        if p and not p.endswith("/"):
            p = p + "/"
        return p

    prefixes = []
    if single_prefix:
        prefixes.append(normalize_prefix(single_prefix))
    if isinstance(batches, list):
        prefixes.extend([normalize_prefix(x) for x in batches if isinstance(x, str)])

    if not prefixes:
        return {"statusCode": 400, "body": json.dumps("Missing prefix or batches.")}

    suffix = query.get("suffix") or body.get("suffix")  # e.g., .tif, .jp2, .pdf
    sample_n = int(
        (query.get("sample_access_check") if query else None)
        or body.get("sample_access_check", 0)
        or os.environ.get("SAMPLE_ACCESS_N", "0")
        or 0
    )

    # Decide output target
    write_to_s3 = str(
        (query.get("write_to_s3") if query else None)
        or body.get("write_to_s3", "true")
    ).lower() == "true"
    out_bucket = (
        (query.get("output_bucket") if query else None)
        or body.get("output_bucket")
        or os.environ.get("OUTPUT_BUCKET_NAME")
        or bucket
    )
    out_prefix = (
        (query.get("output_prefix") if query else None)
        or body.get("output_prefix")
        or os.environ.get("OUTPUT_PREFIX", "keys_exports")
    )

    # Build export name using first prefix and timestamp
    first_part = prefixes[0].strip("/").replace("/", "_")[:60] or "multi"
    export_name = f"keys_{first_part}_{int(time.time())}_{uuid.uuid4().hex[:8]}.csv"
    tmp_path = f"/tmp/{export_name}"

    total = 0
    first_keys = []
    per_prefix_counts = []

    with open(tmp_path, "w", newline="") as f:
        writer = csv.writer(f)
        # As requested: two columns: Bucket Name, Key
        writer.writerow(["Bucket Name", "Key"])
        for p in prefixes:
            cnt = 0
            for obj in _iter_keys(bucket, p, suffix):
                if len(first_keys) < 25:
                    first_keys.append(obj["Key"])
                writer.writerow([bucket, obj.get("Key")])
                cnt += 1
                total += 1
            per_prefix_counts.append({"prefix": p, "count": cnt})

    sample_info = _sample_access(bucket, first_keys, sample_n) if sample_n > 0 else []

    if write_to_s3:
        s3_key = f"{out_prefix.rstrip('/')}/{export_name}"
        s3.upload_file(tmp_path, out_bucket, s3_key)
        body = {
            "message": "Export complete.",
            "bucket": bucket,
            "prefixes": prefixes,
            "counts": per_prefix_counts,
            "total": total,
            "csv_s3_uri": f"s3://{out_bucket}/{s3_key}",
            "sample_access": sample_info,
        }
        return {"statusCode": 200, "body": json.dumps(body)}

    # Inline CSV (small exports only)
    with open(tmp_path, "r") as f:
        csv_text = f.read()
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "text/csv"},
        "body": csv_text,
        "isBase64Encoded": False,
    }
