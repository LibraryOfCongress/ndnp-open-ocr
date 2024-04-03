import json
import os
import errno
import tempfile
import sys
import subprocess
import boto3
from ndnp_open_ocr.processors import OCRProcessor, PreprocessingMethod
import datetime
import shutil
import logging
import threading
import pdfplumber
from PyPDF2 import PdfReader


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# S3 client
sqs = boto3.client("sqs", region_name="us-east-2")
sqs_queue_url = "https://sqs.us-east-2.amazonaws.com/342134162356/ndnp-open-ocr-consumer-sqs-queue"  # os.getenv("SQS_QUEUE_URL")
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.getenv("TABLE_NAME"))
s3 = boto3.client("s3")


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
            logging.info(f"{current_time} - Attempting to download: {s3_key}")
            s3.download_file(bucket_name, s3_key, download_path)
            logging.info(f"{current_time} - Successfully downloaded: {s3_key}")
        except Exception as e:
            logging.info(f"{current_time} - Error downloading {s3_key}. Error: {e} ")

    return input_file_path


def upload_files_to_s3(output_dir, output_bucket_name, output_prefix, difference):
    for output_file in os.listdir(output_dir):
        output_file_path = os.path.join(output_dir, output_file)
        output_key = os.path.join(output_prefix, difference, output_file)
        logging.info("OUTPUT BUCKET NAME: %s", output_bucket_name)
        s3.upload_file(output_file_path, output_bucket_name, output_key)
        logging.info(f"Successfully uploaded {output_file_path} to {output_key}")
    clear_tmp_directory()


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
            logging.info(f"Failed to delete {file_path}. Reason: {e}")


def process_message(message_body):
    """Generates output PDF using NDNP Open OCR pipeline, checks for text content, and appends to DynamoDB FailedFiles list if no text found."""
    message = json.loads(message_body)
    job_id = message["JobId"]

    with tempfile.TemporaryDirectory() as temp_dir:
        # Download files from S3
        input_file_path = download_files_from_s3(
            message["Bucket"], message["Key"], temp_dir
        )

        if os.path.exists(input_file_path):
            logging.info(f"{input_file_path} has been downloaded successfully.")
            output_path = os.path.join(temp_dir, "output")
            make_directory(output_path)

            logging.info("INPUT FILE PATH: %s", input_file_path)
            logging.info("OUTPUT PATH: %s", output_path)

            logging.info("Starting NDNP Open OCR Reprocessing...")

            # If receive count has approached maximum, save to DLQ list attribute in DynamoDB
            # for this job and let the job commence. We can solve later.
            # logging.info("Check to see if there are greater than 5 receives")
            if int(message_body["Attributes"]["ApproximateReceiveCount"]) >= 5:
                # Append current file to the DLQ_List attribute in DynamoDB for the same job item
                table.update_item(
                    Key={"pk": "JOB", "sk": job_id},
                    UpdateExpression="SET dlq_list = list_append(if_not_exists(dlq_list, :empty_list), :message)",
                    ExpressionAttributeValues={
                        ":message": [json.dumps(message)],
                        ":empty_list": [],
                    },
                    ReturnValues="UPDATED_NEW",
                )

                return True
            # Run NDNP Open OCR Reprocessing
            processor = OCRProcessor(
                input_file_path,
                output_path,
                preprocessing_method=PreprocessingMethod.ORIGINAL,
            )
            processor.generate_pdf()
            processor.generate_alto()

            # Check if the generated PDF contains text
            generated_pdf_path = processor.get_postprocessed_pdf_path()
            logging.info("GENERATED PDF PATH: {}".format(generated_pdf_path))
            text_found = False
            with open(generated_pdf_path, "rb") as f:
                reader = PdfReader(f)
                for page in range(0, len(reader.pages)):
                    text = reader.pages[page].extract_text()
                    logging.info(
                        "Text in PDF {}: {}".format(generated_pdf_path, text_found)
                    )
                    if text:
                        text_found = True
            # Update DynamoDB based on text presence
            if not text_found:
                logging.info(
                    "No text found in the generated PDF for {}.".format(message["Key"])
                )
                # Append current file to the FailedFiles list in DynamoDB
                table.update_item(
                    Key={"pk": "JOB", "sk": job_id},
                    UpdateExpression="SET FailedFiles = list_append(FailedFiles, :file)",
                    ExpressionAttributeValues={
                        ":file": [message["Key"]],
                    },
                    ReturnValues="UPDATED_NEW",
                )

                return True
            else:
                # Upload files to S3 and update DynamoDB for job completion
                upload_files_to_s3(
                    output_path,
                    os.environ.get("OUTPUT_BUCKET_NAME"),
                    message["OutputPrefix"],
                    os.path.relpath(
                        os.path.dirname(message["Key"]), message["InputPrefix"]
                    ),
                )
            table.update_item(
                Key={"pk": "JOB", "sk": job_id},
                UpdateExpression="SET RemainingMessages = RemainingMessages - :dec",
                ExpressionAttributeValues={":dec": 1},
                ReturnValues="UPDATED_NEW",
            )
            return True
        else:
            logging.info(f"Failed to process {input_file_path}.")
            return False


def poll_sqs_and_process():
    logging.info("Listening for messages on %s", sqs_queue_url)
    while True:
        response = sqs.receive_message(
            QueueUrl=sqs_queue_url,
            AttributeNames=["All"],
            MaxNumberOfMessages=1,
            WaitTimeSeconds=5,
        )

        if "Messages" in response:
            for message in response["Messages"]:
                try:
                    logging.info("Incoming Message: %s", message)
                    processed_successfully = process_message(message["Body"])
                    # Delete the processed SQS message
                    if processed_successfully:
                        sqs.delete_message(
                            QueueUrl=sqs_queue_url,
                            ReceiptHandle=message["ReceiptHandle"],
                        )
                except Exception as e:
                    logging.error(f"Failed to process message: {e}")


if __name__ == "__main__":
    logging.info("Starting NDNP Open OCR Reprocessing Consumer...")
    # threading.Thread(target=run_flask_app).start()
    poll_sqs_and_process()
