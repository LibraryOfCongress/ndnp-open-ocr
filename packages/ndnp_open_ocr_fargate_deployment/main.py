import os
import sys
import boto3
import json
import tempfile
import logging
import datetime
import shutil
from PyPDF2 import PdfReader
from PIL import Image
from ndnp_open_ocr.processors import OCRProcessor, PreprocessingMethod

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# Initialize AWS clients
s3 = boto3.client("s3")
# dynamodb = boto3.resource("dynamodb")
# table = dynamodb.Table(os.getenv("TABLE_NAME"))


def is_valid_image(input_file_path):
    try:
        with Image.open(input_file_path) as img:
            img.verify()  # Verify that the file is a valid image
        return True
    except Exception as e:
        logging.error(
            f"Image file is invalid or corrupted: {input_file_path}, error: {e}"
        )
        return False


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


def download_files_from_s3(bucket_name, key, temp_dir):
    file_name, file_ext = os.path.splitext(os.path.basename(key))
    input_file_path = os.path.join(temp_dir, file_name + file_ext)
    logging.debug("INPUT FILE PATH: %s", input_file_path)

    # Download the original file as specified by the key
    s3.download_file(bucket_name, key, input_file_path)

    if not is_valid_image(input_file_path):
        input_file_path = input_file_path.replace(".tif", ".jp2")
        s3.download_file(bucket_name, key.replace(".tif", ".jp2"), input_file_path)

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


def upload_files_to_s3(output_dir, output_bucket_name, output_prefix):
    for output_file in os.listdir(output_dir):
        print(output_file)
        print(output_dir)
        output_file_path = os.path.join(output_dir, output_file)
        print(output_prefix)
        output_key = os.path.join(output_prefix, output_file)
        print(output_key)
        s3.upload_file(output_file_path, output_bucket_name, output_key)
        logging.info(f"Successfully uploaded {output_file_path} to {output_key}")
        print("Success")
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


def update_dynamodb(job_id, key, success):
    if success:
        table.update_item(
            Key={"pk": "JOB", "sk": job_id},
            UpdateExpression="SET RemainingMessages = RemainingMessages - :dec",
            ExpressionAttributeValues={":dec": 1},
            ReturnValues="UPDATED_NEW",
        )
    else:
        table.update_item(
            Key={"pk": "JOB", "sk": job_id},
            UpdateExpression="SET FailedFiles = list_append(if_not_exists(FailedFiles, :empty_list), :file)",
            ExpressionAttributeValues={":file": [key], ":empty_list": []},
            ReturnValues="UPDATED_NEW",
        )


def process_file(file_key, bucket_name, output_bucket_name, output_prefix, job_id):
    with tempfile.TemporaryDirectory() as temp_dir:
        # Download the file
        input_file_path = download_files_from_s3(bucket_name, file_key, temp_dir)

        # Process the file
        output_path = os.path.join(temp_dir, "output")
        os.makedirs(output_path, exist_ok=True)

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
            print(reader)
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    text_found = True
                    break

        if text_found:
            # Upload files to S3
            print("TEXT FOUND")
            upload_files_to_s3(output_path, output_bucket_name, output_prefix)
            # update_dynamodb(job_id, file_key, success=True)
        else:
            logging.error(f"No text found in the generated PDF for {file_key}.")
            # update_dynamodb(job_id, file_key, success=False)


if __name__ == "__main__":
    logging.info("Starting NDNP Open OCR Processing...")

    # Retrieve environment variables
    bucket_name = os.getenv("BUCKET_NAME")
    prefix = os.getenv("PREFIX")
    output_prefix = os.getenv("OUTPUT_PREFIX")
    job_id = os.getenv("JOB_ID")
    output_bucket_name = os.environ.get("OUTPUT_BUCKET_NAME")

    array_index = int(os.getenv("AWS_BATCH_JOB_ARRAY_INDEX", "0"))

    # Get the list of files to process
    file_list = get_file_list(bucket_name, prefix)

    if array_index >= len(file_list):
        logging.error(f"Array index {array_index} out of range.")
        sys.exit(1)

    file_key = file_list[array_index]
    logging.info(f"Processing file: {file_key}")

    process_file(file_key, bucket_name, output_bucket_name, output_prefix, job_id)
