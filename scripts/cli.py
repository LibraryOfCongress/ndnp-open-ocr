import os
import boto3
import click
import requests
import shutil

@click.group()
def cli():
    pass


@cli.command()
@click.option('--bucket', prompt='S3 bucket', help='The S3 bucket to download files from.')
@click.option('--prefix', default='', help='The prefix in S3 bucket to filter files.')
def sync_s3_bucket(bucket, prefix):
    """Syncs an S3 bucket with local files."""
    s3 = boto3.client('s3')

    paginator = s3.get_paginator('list_objects_v2')
    for result in paginator.paginate(Bucket=bucket, Prefix=prefix):
        # Download each file individually
        for file in result.get('Contents', []):
            file_key = file['Key']

            # Only consider .pdf and .xml files
            if not file_key.endswith('.pdf') and not file_key.endswith('.xml'):
                continue

            local_path = os.path.join(os.getcwd(), file_key)

            # Ensure the folder structure for the file exists
            os.makedirs(os.path.dirname(local_path), exist_ok=True)

            # Only download the file if it does not exist, or is older than the file on S3
            if not os.path.exists(local_path) or os.path.getmtime(local_path) < file['LastModified'].timestamp():
                print(f"Downloading {file_key} to {local_path}")
                s3.download_file(bucket, file_key, local_path)
            else:
                print(f"{local_path} is up to date")


@cli.command()
@click.option('--batch', default='', help='The batch argument to pass to the API.')
@click.option('--output-dir', default='output_batch', help='The directory to output the new files to.')
@click.option('--local-batch', default='', help='The path to local batch data.')
def reprocess(batch, output_dir, local_batch):
    """Kicks off reprocessing job for a certain S3 NDNP batch."""

   # Ensure the local batch directory exists
    if not os.path.isdir(local_batch):
        print(f"Local batch directory {local_batch} does not exist!")
        return

    print("Copying local batch...")
    # Copy the batch directory to output_batch directory
    shutil.copytree(local_batch, output_dir, dirs_exist_ok=True)
    print("Local batch copy complete...")

    # Call the API
    api_url = "https://wq3cr3qvo9.execute-api.us-east-1.amazonaws.com/dev/"
    response = requests.post(f'{api_url}/{batch}')
    if response.status_code == 200:
        print(f"{response.text} for {batch} batch!")
    else:
        print(
            f"Failed to trigger API endpoint: {api_url}{batch}. Status code: {response.status_code}"
        )

    # # Update the files in output_batch directory
    # sync_s3_bucket(bucket='my-bucket', prefix=f'{output_dir}/')

if __name__ == "__main__":
    cli()