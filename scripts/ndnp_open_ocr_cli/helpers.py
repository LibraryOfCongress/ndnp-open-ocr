import os
import boto3
import click
import requests
import shutil

# Creates a new batch using a combination of the old batch and new PDF and ALTO files stored in S3 with mirrored directory structure (NDNP batch)
def sync_s3_batch(bucket, prefix, output_dir, overwrite, local_batch):
    """Syncs an S3 bucket with local files."""
    # Ensure the local batch directory exists
    if not os.path.isdir(local_batch):
        print(f"Local batch directory {local_batch} does not exist!")
        return

    print("Copying local batch...")
    # Copy the batch directory to output_batch directory
    shutil.copytree(local_batch, output_dir, dirs_exist_ok=True)
    print("Local batch copy complete...")

    s3 = boto3.client('s3')

    paginator = s3.get_paginator('list_objects_v2')
    for result in paginator.paginate(Bucket=bucket, Prefix=prefix):
        # Download each file individually
        for file in result.get('Contents', []):
            file_key = file['Key']

            # Only consider .pdf and .xml files
            if not file_key.endswith('.pdf') and not file_key.endswith('.xml'):
                continue

            # Skip the first component in the path
            components = file_key.split('/')
            file_key_without_prefix = '/'.join(components[1:])

            local_path = os.path.join(output_dir, file_key_without_prefix)

            print(file_key_without_prefix)

            # Ensure the folder structure for the file exists
            os.makedirs(os.path.dirname(local_path), exist_ok=True)

            # Only download the file if it does not exist, or is older than the file on S3
            if overwrite or not os.path.exists(local_path) or os.path.getmtime(local_path) < file['LastModified'].timestamp():
                print(f"Downloading {file_key} to {local_path}")
                s3.download_file(bucket, file_key, local_path)
            else:
                print(f"{local_path} is up to date")
