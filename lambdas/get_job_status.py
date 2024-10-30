import json
import boto3
import os
from datetime import datetime
from botocore.exceptions import ClientError

# Initialize the AWS Batch and S3 clients
batch = boto3.client("batch")
s3 = boto3.client("s3")


def handler(event, context):
    # Extract parameters from the event
    queue_name = os.environ.get("BATCH_QUEUE")
    bucket_name = os.environ.get("OUTPUT_BUCKET_NAME")
    prefix = "notvalidated"
    job_name = event["pathParameters"]["jobName"]

    if not queue_name or not bucket_name or not prefix or not job_name:
        return {
            "statusCode": 400,
            "body": json.dumps(
                "Missing required parameters: queue_name, bucket_name, prefix, job_name"
            ),
        }

    # Check for SUCCEEDED jobs
    succeeded_response = batch.list_jobs(jobQueue=queue_name, jobStatus="SUCCEEDED")
    succeeded_jobs = [
        job
        for job in succeeded_response["jobSummaryList"]
        if "arrayProperties" in job and job["jobName"] == job_name
    ]

    if succeeded_jobs:
        log_to_s3(
            bucket_name,
            job_name,
            "Job completed successfully with all TIFs processed without error.",
        )
        return {
            "statusCode": 200,
            "body": json.dumps(
                f"Job {job_name} completed successfully with all TIFs processed without error."
            ),
        }

    # Check if job is still running
    running_response = batch.list_jobs(jobQueue=queue_name, jobStatus="RUNNING")
    running_jobs = [
        job
        for job in running_response["jobSummaryList"]
        if "arrayProperties" in job and job["jobName"] == job_name
    ]

    if running_jobs:
        job = running_jobs[0]
        array_size = job["arrayProperties"]["size"]
        # Count the number of sub-jobs that haven't been processed yet
        pending_subtasks = sum(
            1
            for index in range(array_size)
            if batch.describe_jobs(jobs=[f"{job['jobId']}:{index}"])["jobs"][0][
                "status"
            ]
            not in ["SUCCEEDED", "FAILED"]
        )
        log_to_s3(
            bucket_name,
            job_name,
            f"Job is still running. {pending_subtasks} subtasks left before completion.",
        )
        return {
            "statusCode": 200,
            "body": json.dumps(
                f"Job {job_name} is still running. {pending_subtasks} subtasks left before completion."
            ),
        }

    # Check for other job statuses (STARTING, PENDING, SUBMITTED)
    other_statuses = ["STARTING", "PENDING", "SUBMITTED"]
    for status in other_statuses:
        response = batch.list_jobs(jobQueue=queue_name, jobStatus=status)
        other_jobs = [
            job
            for job in response["jobSummaryList"]
            if "arrayProperties" in job and job["jobName"] == job_name
        ]
        if other_jobs:
            job = other_jobs[0]
            array_size = job["arrayProperties"]["size"]
            log_to_s3(
                bucket_name,
                job_name,
                f"Job is in status {status}. {array_size} subtasks in total.",
            )
            return {
                "statusCode": 200,
                "body": json.dumps(
                    f"Job {job_name} is in status {status}. {array_size} subtasks in total."
                ),
            }

    # Query FAILED jobs
    response = batch.list_jobs(jobQueue=queue_name, jobStatus="FAILED")
    array_jobs = [
        job
        for job in response["jobSummaryList"]
        if "arrayProperties" in job and job["jobName"] == job_name
    ]

    if not array_jobs:
        log_to_s3(
            bucket_name,
            job_name,
            f"No FAILED array jobs found for job name: {job_name}.",
        )
        return {
            "statusCode": 200,
            "body": json.dumps(f"No FAILED array jobs found for job name: {job_name}."),
        }

    # Get list of files from S3 for job index association
    file_list = get_file_list(bucket_name, prefix)

    job_results = []

    # Loop through each array job and get details of sub-jobs
    for array_job in array_jobs:
        array_job_id = array_job["jobId"]
        job_description = batch.describe_jobs(jobs=[array_job_id])
        job = job_description["jobs"][0]
        array_size = job["arrayProperties"]["size"]

        array_failed = False
        failed_sub_jobs = []

        # Loop through sub-jobs in the array
        for index in range(array_size):
            sub_job_id = f"{array_job_id}:{index}"
            sub_job_description = batch.describe_jobs(jobs=[sub_job_id])
            sub_job = sub_job_description["jobs"][0]
            job_status = sub_job["status"]
            exit_code = sub_job["container"].get("exitCode", "N/A")
            reason = sub_job["container"].get("reason", "No reason provided")
            job_index = sub_job["arrayProperties"].get("index", None)
            file_path = (
                file_list[job_index]
                if job_index is not None and job_index < len(file_list)
                else "Unknown file path"
            )

            # Map exit codes to human-readable descriptions
            exit_code_description = {
                0: "Success",
                1: "The TIF was corrupt. JP2 used instead",
                2: "OCR Failure: No text found in PDF",
            }.get(exit_code, "Unknown error")

            # If the sub-job failed, collect its details
            if job_status == "FAILED":
                array_failed = True
                failed_sub_jobs.append(
                    {
                        "job_id": sub_job_id,
                        "status": job_status,
                        "exit_code": exit_code,
                        "reason": reason,
                        "file_path": file_path,
                        "description": exit_code_description,
                    }
                )

        # If the entire array job was successful, add a success message
        if not array_failed:
            job_results.append(
                {
                    "array_job_id": array_job_id,
                    "status": "SUCCEEDED",
                    "message": "All sub-jobs completed successfully.",
                }
            )
        else:
            job_results.append(
                {
                    "array_job_id": array_job_id,
                    "status": "FAILED",
                    "failed_sub_jobs": failed_sub_jobs,
                }
            )

    log_to_s3(bucket_name, job_name, job_results)

    # Return the details in a visually presentable JSON format
    return {"statusCode": 200, "body": json.dumps(job_results, indent=4)}


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


def log_to_s3(bucket_name, job_name, log_data):
    file_name = f"{job_name}/batch-logs-metadata.json"
    s3.put_object(
        Bucket=bucket_name,
        Key=file_name,
        Body=json.dumps(log_data, indent=2),
        ContentType="application/json",
    )
