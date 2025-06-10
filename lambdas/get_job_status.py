import json
import boto3
import os
from botocore.exceptions import ClientError

batch = boto3.client("batch")
s3 = boto3.client("s3")


def handler(event, context):
    queue_name = os.environ.get("BATCH_QUEUE")
    bucket_name = os.environ.get("OUTPUT_BUCKET_NAME")
    job_name = event.get("pathParameters", {}).get("jobName")

    if not job_name:
        return {
            "statusCode": 400,
            "body": json.dumps("Missing required parameter: job_name"),
        }

    s3_key = f"{job_name}/batch-logs-metadata.json"

    # First try to read from S3 (means job is already completed and results are stored)
    try:
        stored_result = json.loads(
            s3.get_object(Bucket=bucket_name, Key=s3_key)["Body"].read()
        )
        return {"statusCode": 200, "body": json.dumps(stored_result)}
    except ClientError as e:
        if e.response["Error"]["Code"] != "NoSuchKey":
            raise e

    # Quick job status check without detailed sub-job calls
    statuses = ["SUCCEEDED", "FAILED", "RUNNING", "SUBMITTED", "PENDING", "STARTING"]
    counts = {"SUCCEEDED": 0, "FAILED": 0, "REMAINING": 0}

    # List sub-jobs in the specified queue and count tasks by status. It is 1 sub-job per TIF.
    for status in statuses:
        response = batch.list_jobs(jobQueue=queue_name, jobStatus=status)
        for job in response["jobSummaryList"]:
            if job["jobName"] == job_name:
                array_size = job.get("arrayProperties", {}).get("size", 1)
                if status in ["SUCCEEDED"]:
                    counts["SUCCEEDED"] += array_size
                elif status in ["FAILED"]:
                    counts["FAILED"] += array_size
                else:
                    counts["REMAINING"] += array_size

    total_tasks = counts["SUCCEEDED"] + counts["FAILED"] + counts["REMAINING"]

    simplified_result = {
        "job_name": job_name,
        "total_tasks": total_tasks,
        "succeeded": counts["SUCCEEDED"],
        "failed": counts["FAILED"],
        "remaining": counts["REMAINING"],
    }

    return {"statusCode": 200, "body": json.dumps(simplified_result)}
