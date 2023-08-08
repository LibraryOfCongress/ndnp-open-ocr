import boto3
import json
import os
import errno
import tempfile
import sys
import subprocess
sys.path.append("/opt/python/")
dir_contents = os.listdir("/opt/python/lib/python3.8/site-packages")

# Print each file or directory in the "/opt/" directory
for item in dir_contents:
    print(item)
# os.environ["PYTHONPATH"] = "/opt/python"
from src.ndnp_open_ocr.processors import OCRProcessor
import logging
import os
import shutil
logging.basicConfig(level=logging.DEBUG)
import datetime

# Directory paths to be added to the PATH
ghostscript_directory = "/opt/bin"
exiftool_directory = "/opt/bin"

# Check Tesseract version
try:
    result = subprocess.run(['tesseract', '--version'], capture_output=True, text=True, check=True)
    print(result.stdout)
except subprocess.CalledProcessError as e:
    print(f"Error occurred while checking Tesseract version: {e}")
except FileNotFoundError:
    print("Tesseract is not installed or not found in the system PATH.")


# S3 client
s3 = boto3.client("s3")
# DynamoDB resource
dynamodb = boto3.resource("dynamodb")


def update_environment_variables():
    current_path = os.environ.get("PATH")
    new_path = f"{ghostscript_directory}:{exiftool_directory}:{current_path}"
    os.environ["PATH"] = new_path
    os.environ["PYTHONPATH"] = f"{ghostscript_directory}:{'/opt/python'}"


def list_directory_contents(directory):
    logging.debug(f"Contents of {directory}:")
    for item in os.listdir(directory):
        logging.debug(f" - {item}")


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
    extensions = ['.pdf', '.xml']
    for ext in extensions:
        s3_key = os.path.join(os.path.dirname(key), file_name + ext)
        download_path = os.path.join(temp_dir, file_name + ext)

        current_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

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


def update_remaining_messages(table, job_id, event):
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
    tmp_dir = '/tmp'
    for filename in os.listdir(tmp_dir):
        file_path = os.path.join(tmp_dir, filename)
        try:
            if os.path.isfile(file_path):
                os.unlink(file_path)
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)
        except Exception as e:
            print(f"Failed to delete {file_path}. Reason: {e}")

def handler(event, context):
    print("Number of messages left in queue: {}".format(len(event["Records"])))
    for message in event["Records"]:
        message = json.loads(message["body"])
        table = dynamodb.Table(os.getenv("TABLE_NAME"))
        # raise Exception("Throw exception.")
        with tempfile.TemporaryDirectory() as temp_dir:
            input_file_path = download_files_from_s3(
                message["Bucket"], message["Key"], temp_dir
            )
            if os.path.exists(input_file_path):
                logging.debug(f"{input_file_path} has been downloaded successfully.")
                output_path = os.path.join(temp_dir, "output")
                make_directory(output_path)

                # Run NDNP Open OCR Reprocessing on this input
                processor = OCRProcessor(input_file_path, output_path)
                processor.generate_pdf()
            else:
                logging.error(f"Failed to download {input_file_path}.")

            upload_files_to_s3(
                output_path,
                os.environ.get("OUTPUT_BUCKET_NAME"),
                message["OutputPrefix"],
                os.path.relpath(
                    os.path.dirname(message["Key"]), message["InputPrefix"]
                ),
            )
    update_remaining_messages(table, message["JobId"], event)
    return {"statusCode": 200, "body": "Success"}
