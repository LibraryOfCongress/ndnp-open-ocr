import os
import boto3
import click
import requests
import shutil
import uuid
import logging
import subprocess

# Creates a new batch using a combination of the old batch and new PDF and ALTO files stored in S3 with mirrored directory structure (NDNP batch)

def sync_s3_batch(bucket, job, local_batch, new_batch_dir):
    """Syncs an S3 bucket with local files and merges it with a local batch."""
    # Step 1: Clone S3 contents into /tmp directory
    s3_uri = f"s3://{bucket}/{job}"
    tmp_dir = "/tmp/s3_contents"
    if not os.path.exists(tmp_dir):
        os.makedirs(tmp_dir)

    sync_command = f"aws s3 sync {s3_uri} {tmp_dir}"
    subprocess.run(sync_command, shell=True, check=True)
    print("S3 contents cloned to /tmp directory.")

    # Step 2: Copy local_batch contents into new_batch_dir
    if os.path.exists(local_batch):
        shutil.copytree(local_batch, new_batch_dir, dirs_exist_ok=True)
        print("Local batch contents copied to new batch directory.")
    else:
        print(f"Local batch directory {local_batch} does not exist!")

    # Step 3: Copy /tmp directory contents into new_batch_dir, merging contents
    for item in os.listdir(tmp_dir):
        source_path = os.path.join(tmp_dir, item)
        destination_path = os.path.join(new_batch_dir, item)
        if os.path.isdir(source_path):
            shutil.copytree(source_path, destination_path, dirs_exist_ok=True)
        else:
            shutil.copy2(source_path, destination_path)

    print("Merged /tmp and local batch contents into new batch directory.")


def find_missing_pdfs(input_bucket, input_prefix, output_bucket, output_prefix):
    """Finds missing PDFs in the output bucket and sends them to the SQS queue. FIXME: Move to AWS Lambda function at later date."""

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
