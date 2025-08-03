import json
import boto3
import os
from datetime import datetime
from botocore.exceptions import ClientError

# Initialize AWS clients
batch = boto3.client("batch")
s3 = boto3.client("s3")


def handler(event, context):
    # Extract job details from the AWS Batch event
    job_id = event["detail"]["jobId"]
    job_name = event["detail"]["jobName"]
    job_status = event["detail"]["status"]

    # Explicitly trigger only for parent jobs, not sub-jobs
    if ":" in job_id:
        print(f"Ignoring sub-job completion event for sub-job ID: {job_id}")
        return {"statusCode": 200, "body": "Ignored sub-job event."}

    # Only proceed if the parent job is in a final state
    if job_status not in ["SUCCEEDED", "FAILED"]:
        print(f"Ignoring intermediate job status update: {job_status}")
        return {"statusCode": 200, "body": "Intermediate update ignored."}

    bucket_name = os.environ.get("OUTPUT_BUCKET_NAME")
    batch_name = job_name.split("__")[0]
    current_date = datetime.utcnow().strftime("%Y-%m-%d")
    s3_key = f"{job_name}/log_{batch_name}_{current_date}.json"

    # Try to read the tesseract version written by the workers
    tesseract_version = "unknown"
    try:
        obj = s3.get_object(Bucket=bucket_name, Key=f"{job_name}/tesseract_version.txt")
        tesseract_version = obj["Body"].read().decode().strip()
    except ClientError:
        pass

    # Describe the parent job to extract original input bucket and prefix.
    job_description = batch.describe_jobs(jobs=[job_id])
    job = job_description["jobs"][0]
    container_env = job.get("container", {}).get("environment", [])
    env_map = {e["name"]: e["value"] for e in container_env}
    input_bucket = env_map.get(
        "BUCKET_NAME", os.environ.get("INPUT_BUCKET_NAME", "loc-preservation")
    )
    prefix = env_map.get("PREFIX", job_name)

    # Retrieve file paths associated with this job for error tracking -- order is the same as in the job array
    file_list = get_file_list(input_bucket, prefix)

    summary = job.get("arrayProperties", {}).get("statusSummary", {})
    total_tasks = sum(summary.values())
    succeeded = summary.get("SUCCEEDED", 0)
    failed = summary.get("FAILED", 0)
    remaining = total_tasks - succeeded - failed

    # Initialize the result object
    job_results = {
        "job_id": job_id,
        "job_name": job_name,
        "batch_name": batch_name,
        "created": current_date,
        "ndnp_open_ocr_version": "1.1",
        "tesseract_version": tesseract_version,
        "status": job_status,
        "summary": {
            "total_tasks": total_tasks,
            "succeeded": succeeded,
            "failed": failed,
            "remaining": remaining,
        },
        "details": [],
    }

    if job_status == "SUCCEEDED":
        job_results["message"] = (
            "Job completed successfully with all TIFs processed without error."
        )

    elif job_status == "FAILED":
        # Use the previously fetched job description to inspect sub-jobs
        array_size = job.get("arrayProperties", {}).get("size", 1)
        failed_sub_jobs = []

        for index in range(array_size):
            sub_job_id = f"{job_id}:{index}"
            sub_job_description = batch.describe_jobs(jobs=[sub_job_id])
            sub_job = sub_job_description["jobs"][0]

            status = sub_job["status"]
            exit_code = sub_job["container"].get("exitCode", "N/A")
            job_index = sub_job.get("arrayProperties", {}).get("index", index)
            file_path = (
                file_list[job_index]
                if job_index is not None and job_index < len(file_list)
                else "Unknown file path"
            )

            exit_code_description = {
                0: "Success",
                1: "The TIF was corrupt. JP2 used instead",
                2: "OCR Failure: No text found in PDF",
            }.get(exit_code, "Unknown error")

            if status == "FAILED":
                failed_sub_jobs.append(
                    {
                        "file_path": file_path,
                        "description": exit_code_description,
                    }
                )
        # Add Full details of failed sub-jobs to the job results
        job_results["details"] = failed_sub_jobs

    # Write structured logs explicitly to S3
    log_to_s3(bucket_name, s3_key, job_results)

    return {
        "statusCode": 200,
        "body": json.dumps({"message": "Batch job metadata logged successfully."}),
    }


def get_file_list(bucket_name, prefix):
    s3_keys = []
    paginator = s3.get_paginator("list_objects_v2")
    pages = paginator.paginate(Bucket=bucket_name, Prefix=prefix)

    for page in pages:
        if "Contents" in page:
            for obj in page["Contents"]:
                key = obj["Key"]
                if key.lower().endswith(".tif"):
                    s3_keys.append(key)
    return s3_keys


def log_to_s3(bucket_name, s3_key, log_data):
    s3.put_object(
        Bucket=bucket_name,
        Key=s3_key,
        Body=json.dumps(log_data, indent=2),
        ContentType="application/json",
    )


# if __name__ == "__main__":
#     # Mock event for testing with the given job name
#     # You can change job_status to "SUCCEEDED" or "FAILED" for different scenarios
#     mock_event = {
#         "detail": {
#             "jobId": "9d39dbe9-fb16-4cc6-a760-3378a639d324",
#             "jobName": "batch_va_styx_ver01__ac22bfbc-7fb6-44e6-8a10-c5020dfc2333",
#             "status": "FAILED"  # Change to "SUCCEEDED" to test success case
#         }
#     }
#     mock_context = None

#     # Set environment variables if needed
#     os.environ["OUTPUT_BUCKET_NAME"] = "ndnp-open-ocr-output-bucket-development-deployment"
#     os.environ["INPUT_BUCKET_NAME"] = "loc-preservation"

#     result = handler(mock_event, mock_context)
#     print("Handler result:")
#     print(json.dumps(result, indent=2))
