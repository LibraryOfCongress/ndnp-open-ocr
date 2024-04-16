import os
import boto3
import click
import requests
import shutil
import uuid
import logging
import subprocess
from rich import print, pretty

pretty.install()

# Creates a new batch using a combination of the old batch and new PDF and ALTO files stored in S3 with mirrored directory structure (NDNP batch)
def sync_s3_batch(bucket, job, local_batch, new_batch_dir):
    """Syncs an S3 bucket with local files and merges it with a local batch."""
    print(
        "[bold green] Syncing outputs from {} to local, and merging with local batch data.".format(
            job
        )
    )
    # Step 1: Clone S3 contents into /tmp directory
    s3_uri = f"s3://{bucket}/{job}"
    tmp_dir = "/processing/sgp/tmp"
    if not os.path.exists(tmp_dir):
        os.makedirs(tmp_dir)

    # Run AWS sync command for fast syncing with remote directory
    sync_command = f"aws s3 sync {s3_uri} {tmp_dir}"
    try:
        result = subprocess.run(
            sync_command,
            shell=True,
            check=True,
        )
        print(result.stdout)
    except subprocess.CalledProcessError as e:
        print(e.output)
    print("[bold green] S3 contents from {} cloned to {} directory.".format(s3_uri, tmp_dir))
    # Step 2: Copy local_batch contents into new_batch_dir
    if os.path.exists(local_batch):
        print(
            "[bold green] Now copying original batch data from {} (TIFFs, JP2s, etc..) into the output directory {}".format(
                local_batch, new_batch_dir
            )
        )
        shutil.copytree(local_batch, new_batch_dir, dirs_exist_ok=True)
        print(
            "[bold green] Local batch contents ({}) copied to new batch directory. ({})".format(
                local_batch, new_batch_dir
            )
        )
    else:
        print(
            f":warning: [bold red] Local batch directory {local_batch} does not exist! Please specify a valid local batch directory and try again."
        )
        return

    # Step 3: Copy /tmp directory contents into new_batch_dir, merging contents
    print(
        "[bold green] Copying new PDF and ALTO files, pulled down from S3, into new batch directory to merge with local batch data..."
    )
    for item in os.listdir(tmp_dir):
        source_path = os.path.join(tmp_dir, item)
        destination_path = os.path.join(new_batch_dir, item)
        if os.path.isdir(source_path):
            shutil.copytree(source_path, destination_path, dirs_exist_ok=True)
        else:
            shutil.copy2(source_path, destination_path)

    print("Merged /tmp and local batch contents into new batch directory.")

    # Step 4: Clean up the temporary directory
    try:
        shutil.rmtree(tmp_dir)
        print(f"Temporary directory {tmp_dir} successfully deleted.")
    except OSError as e:
        print(f"Error deleting temporary directory {tmp_dir}: {e}")

    print(
        "[bold green] Synchronization is complete. The batch is now available for validation {}".format(
            new_batch_dir
        )
    )


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
    print(f"{len(missing_keys)} MISSING PDFs total in the batch")

    return filtered_elements
