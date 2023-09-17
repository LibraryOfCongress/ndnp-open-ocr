import os
import boto3
import click
import requests
import shutil
import uuid
import logging


# Creates a new batch using a combination of the old batch and new PDF and ALTO files stored in S3 with mirrored directory structure (NDNP batch)
def sync_s3_batch(bucket, prefix, output_dir, overwrite, local_batch):
    """Syncs an S3 bucket with local files."""
    # Ensure the local batch directory exists
    if not os.path.isdir(local_batch):
        print(f"Local batch directory {local_batch} does not exist!")
        return

    print("Copying local batch...")
    # Copy the batch directory to output_batch directory
    try:
        shutil.copytree(local_batch, output_dir, dirs_exist_ok=False)
    except Exception as e:
        print(e)
    print("Local batch copy complete...")

    s3 = boto3.client("s3")

    paginator = s3.get_paginator("list_objects_v2")
    for result in paginator.paginate(Bucket=bucket, Prefix=prefix):
        # Download each file individually
        for file in result.get("Contents", []):
            file_key = file["Key"]

            # Only consider .pdf and .xml files
            if not file_key.endswith(".pdf") and not file_key.endswith(".xml"):
                continue

            # Skip the first component in the path
            components = file_key.split("/")
            file_key_without_prefix = "/".join(components[1:])

            local_path = os.path.join(output_dir, file_key_without_prefix)

            print(file_key_without_prefix)

            # Ensure the folder structure for the file exists
            os.makedirs(os.path.dirname(local_path), exist_ok=True)

            # Only download the file if it does not exist, or is older than the file on S3
            if (
                overwrite
                or not os.path.exists(local_path)
                or os.path.getmtime(local_path) < file["LastModified"].timestamp()
            ):
                print(f"Downloading {file_key} to {local_path}")
                s3.download_file(bucket, file_key, local_path)
            else:
                print(f"{local_path} is up to date")


def find_missing_pdfs(input_bucket, input_prefix, output_bucket, output_prefix):
    """Finds missing PDFs in the output bucket and sends them to the SQS queue."""

    # Initialize boto3 clients and resources
    session = boto3.Session(profile_name=os.environ["AWS_PROFILE"])
    s3 = session.resource("s3")
    # Collect keys from input and output buckets
    input_keys, output_keys = set(), set()
    for obj in s3.Bucket(input_bucket).objects.filter(Prefix=input_prefix):
        if obj.key.lower().endswith(".pdf"):
            input_keys.add(obj.key)

    for obj in s3.Bucket(output_bucket).objects.filter(Prefix=output_prefix):
        if obj.key.lower().endswith(".pdf"):
            output_keys.add(obj.key)

    # Clean keys to only retain the filenames
    cleaned_inputs = {key.split("data", 1)[-1] for key in input_keys}
    cleaned_outputs = {key.split("data", 1)[-1] for key in output_keys}

    # Find missing keys and filter them
    missing_keys = cleaned_inputs - cleaned_outputs
    filtered_elements = {
        element.replace(".pdf", ".tif")
        for element in input_keys
        if any(element.endswith(prefix) for prefix in missing_keys)
    }
    logging.info(f"{len(missing_keys)} MISSING PDFs total in the batch")

    return filtered_elements
