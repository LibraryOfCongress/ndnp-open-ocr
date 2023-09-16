
import json
import os
from PIL import Image
import tempfile
import logging
import os
import subprocess
import sys
from helpers import \
    download_files_from_s3, \
    update_remaining_messages, \
    upload_files_to_s3, \
    make_directory
import boto3
try:
    import cv2
    print("OpenCV is already installed!")
except ImportError:
    print("OpenCV is not installed. Installing now...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "--target", "/tmp", "opencv-python-headless"])
    subprocess.check_call([sys.executable, "-m", "pip", "install", "--target", "/tmp", "hocker"])
    subprocess.check_call([sys.executable, "-m", "pip", "install", "--target", "/tmp", "reportlab"])
    sys.path.append('/tmp')

from src.ndnp_open_ocr.processors import OCRProcessor, PreprocessingMethod

dynamodb = boto3.resource("dynamodb")
queue_url = os.environ.get("QUEUE_URL")


def handler(event, context):
    logging.info("Number of failed messages: {}".format(len(event["Records"])))
    table = dynamodb.Table(os.getenv("TABLE_NAME"))

    for message in event["Records"]:
        message = json.loads(message["body"])
        job_id = message['JobId']
        with tempfile.TemporaryDirectory() as temp_dir:
            input_file_path = download_files_from_s3(
                message["Bucket"], message["Key"], temp_dir
            )
            if os.path.exists(input_file_path):
                print(f"{input_file_path} has been downloaded successfully.")
                output_path = os.path.join(temp_dir, "output")
                make_directory(output_path)

                # Run NDNP Open OCR Reprocessing on this input
                processor = OCRProcessor(input_file_path, output_path, preprocessing_method=PreprocessingMethod.ADAPTIVE)
                processor.generate_pdf()
            else:
                print("Failed to download {input_file_path}.")

            upload_files_to_s3(
                output_path,
                os.environ.get("OUTPUT_BUCKET_NAME"),
                message["OutputPrefix"],
                os.path.relpath(
                    os.path.dirname(message["Key"]), message["InputPrefix"]
                ),
            )
        table = dynamodb.Table(os.getenv("TABLE_NAME"))

        try:
            # Log the failed message
            # logging.error(f"Processing of message {message['MessageId']} failed.")
            table.update_item(
                Key={"pk": "JOB", "sk": job_id},
                UpdateExpression="SET #pdf_failed_messages = list_append(if_not_exists(#pdf_failed_messages, :empty_list), :message)",
                ExpressionAttributeNames={
                    "#pdf_failed_messages": "pdf_failed_messages"
                },
                ExpressionAttributeValues={
                    ":message": [message],  # Wrap the message in a list
                    ":empty_list": [],
                },
            )
        except Exception as e:
            logging.error(f"Failed to update job summary for message {message}: {e}")

    return {"statusCode": 200, "body": "DLQ processing complete"}
