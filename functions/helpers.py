import os
import errno
import logging
import os
import shutil
import datetime
import boto3

# S3 client
s3 = boto3.client("s3")
# DynamoDB resource
dynamodb = boto3.resource("dynamodb")


def make_directory(path):
    try:
        os.makedirs(path)
    except OSError as exc:
        if exc.errno != errno.EEXIST:
            raise


def download_files_from_s3(bucket_name, key, temp_dir):
    file_name, file_ext = os.path.splitext(os.path.basename(key))
    input_file_path = os.path.join(temp_dir, file_name + file_ext)
    logging.debug("INPUT FILE PATH: %s", input_file_path)

    # Download the original file as specified by the key
    s3.download_file(bucket_name, key, input_file_path)

    # Download the .pdf, .tiff, and .xml files
    extensions = [".pdf", ".xml"]
    for ext in extensions:
        s3_key = os.path.join(os.path.dirname(key), file_name + ext)
        download_path = os.path.join(temp_dir, file_name + ext)

        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        try:
            print(f"{current_time} - Attempting to download:", s3_key)
            s3.download_file(bucket_name, s3_key, download_path)
            print(f"{current_time} - Successfully downloaded:", s3_key)
        except Exception as e:
            print(f"{current_time} - Error downloading", s3_key, ". Error:", str(e))

    return input_file_path


def upload_files_to_s3(output_dir, output_bucket_name, output_prefix, difference):
    for output_file in os.listdir(output_dir):
        print(output_file)
        output_file_path = os.path.join(output_dir, output_file)
        output_key = os.path.join(output_prefix, difference, output_file)
        print("OUTPUT KEY", output_key)
        s3.upload_file(output_file_path, output_bucket_name, output_key)
    clear_tmp_directory()


def update_remaining_messages(job_id, event):
    table = dynamodb.Table(os.getenv("TABLE_NAME"))
    resp = table.update_item(
        Key={"pk": "JOB", "sk": job_id},
        UpdateExpression="SET RemainingMessages = RemainingMessages - :dec",
        ExpressionAttributeValues={
            ":dec": len(event["Records"]),
        },
        ReturnValues="UPDATED_NEW",
    )
    logging.debug(resp)


def clear_tmp_directory():
    tmp_dir = "/tmp"
    for filename in os.listdir(tmp_dir):
        file_path = os.path.join(tmp_dir, filename)
        try:
            if os.path.isfile(file_path):
                os.unlink(file_path)
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)
        except Exception as e:
            print(f"Failed to delete {file_path}. Reason: {e}")
