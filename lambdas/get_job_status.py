import json
import boto3
import os
from botocore.exceptions import ClientError

batch = boto3.client("batch")
s3 = boto3.client("s3")


def handler(event, context):
    # Read configuration
    queue_name = os.environ.get("BATCH_QUEUE")
    bucket_name = os.environ.get("OUTPUT_BUCKET_NAME")
    job_name = event.get("pathParameters", {}).get("jobName")

    if not job_name:
        return {
            "statusCode": 400,
            "body": json.dumps("Missing required parameter: jobName"),
        }

    s3_key = f"{job_name}/batch-logs-metadata.json"

    # 1) Try cached result in S3
    try:
        obj = s3.get_object(Bucket=bucket_name, Key=s3_key)
        stored = json.loads(obj["Body"].read())
        return {"statusCode": 200, "body": json.dumps(stored)}
    except ClientError as e:
        if e.response["Error"]["Code"] != "NoSuchKey":
            # unexpected error reading the cache
            raise

    # 2) Find the parent array-job ID by scanning statuses (including RUNNABLE)
    statuses = [
        "SUBMITTED", "PENDING", "RUNNABLE",
        "STARTING", "RUNNING", "SUCCEEDED", "FAILED",
    ]
    parent_job_id = None

    for status in statuses:
        next_token = None
        while True:
            params = {
                "jobQueue": queue_name,
                "jobStatus": status,
                "maxResults": 100,
            }
            if next_token:
                params["nextToken"] = next_token

            resp = batch.list_jobs(**params)
            for job in resp.get("jobSummaryList", []):
                if job.get("jobName") == job_name:
                    parent_job_id = job["jobId"]
                    break

            next_token = resp.get("nextToken")
            if parent_job_id or not next_token:
                break
        if parent_job_id:
            break

    if not parent_job_id:
        return {
            "statusCode": 404,
            "body": json.dumps(f"Job '{job_name}' not found in queue '{queue_name}'"),
        }

    # 3) Describe the parent job to get the arrayProperties.statusSummary
    detail = batch.describe_jobs(jobs=[parent_job_id])["jobs"][0]
    summary = detail.get("arrayProperties", {}).get("statusSummary", {})

    # 4) Build your simplified result
    total = sum(summary.values())
    succeeded = summary.get("SUCCEEDED", 0)
    failed = summary.get("FAILED", 0)
    remaining = total - succeeded - failed

    result = {
        "job_name": job_name,
        "total_tasks": total,
        "succeeded": succeeded,
        "failed": failed,
        "remaining": remaining,
    }

    # # (Optional) Cache the computed result back to S3 for next time
    # try:
    #     s3.put_object(
    #         Bucket=bucket_name,
    #         Key=s3_key,
    #         Body=json.dumps(result),
    #         ContentType="application/json",
    #     )
    # except ClientError:
    #     # if caching fails, we still return the real-time result
    #     pass

    return {"statusCode": 200, "body": json.dumps(result)}
