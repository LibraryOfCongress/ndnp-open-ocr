import os
import sys
import boto3
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

s3 = boto3.client("s3")

# Determine if segmentation should be used based on environment variable
USE_SEGMENTATION = os.getenv("USE_SEGMENTATION", "false").lower() == "true"


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

    # Download the original TIF
    s3.download_file(bucket_name, key, input_file_path)

    # If TIF is invalid, fallback to JP2
    if not is_valid_image(input_file_path):
        input_file_path = input_file_path.replace(".tif", ".jp2")
        s3.download_file(bucket_name, key.replace(".tif", ".jp2"), input_file_path)

    # Download additional sidecar files (.pdf, .xml)
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
            logging.info(f"{current_time} - Error downloading {s3_key}. Error: {e}")

    return input_file_path


def upload_files_to_s3(
    output_dir,
    output_bucket_name,
    output_prefix,
    original_file_key,
    original_prefix,
):
    """
    Upload OCR outputs while preserving the relative folder structure from the original TIF.
    """
    # Figure out subdirectory structure relative to the prefix
    # e.g. if original_prefix = "lcbp/ndnp/loc/batch_lc_20090321_volvo/data"
    # and original_file_key = "lcbp/ndnp/loc/batch_lc_20090321_volvo/data/sn83030214/00175036945/1898120101/0001.tif"
    # Then rel_path might be "sn83030214/00175036945/1898120101/0001.tif"
    rel_path = os.path.relpath(original_file_key, original_prefix)

    rel_dir = os.path.dirname(rel_path)  # e.g. "sn83030214/00175036945/1898120101"
    file_base, _ = os.path.splitext(os.path.basename(rel_path))  # e.g. "0001"

    for output_file in os.listdir(output_dir):
        # For example, if 'output_file' is "0001.pdf", we want to store it as:
        #   output_prefix/sn83030214/00175036945/1898120101/0001.pdf
        output_file_path = os.path.join(output_dir, output_file)

        # If you want to rename the output files (e.g. "0001_ocr.pdf"), do it here. For example:
        #   new_filename = file_base + "_ocr" + os.path.splitext(output_file)[1]
        # But if they're already named the way you like, use output_file directly.

        output_key = os.path.join(output_prefix, rel_dir, output_file)
        s3.upload_file(output_file_path, output_bucket_name, output_key)
        logging.info(
            f"Successfully uploaded {output_file_path} to s3://{output_bucket_name}/{output_key}"
        )
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


def process_file(file_key, bucket_name, output_bucket_name, output_prefix, prefix):
    with tempfile.TemporaryDirectory() as temp_dir:
        input_file_path = download_files_from_s3(bucket_name, file_key, temp_dir)

        jp2_used = input_file_path.endswith(".jp2")

        # Process the file and generate OCR output
        output_path = os.path.join(temp_dir, "output")
        os.makedirs(output_path, exist_ok=True)
        processor = OCRProcessor(
            input_file_path,
            output_path,
            preprocessing_method=PreprocessingMethod.ORIGINAL,
            use_segmenter=USE_SEGMENTATION,
        )
        processor.process()

        generated_pdf_path = processor.get_postprocessed_pdf_path()
        text_found = False
        with open(generated_pdf_path, "rb") as f:
            reader = PdfReader(f)
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    text_found = True
                    break

        # Track text presence and JP2 usage
        if not text_found:
            logging.error(f"No text found in the generated PDF for {file_key}.")
            sys.exit(2)  # "No Text" error

        # Upload everything (PDF, ALTO, etc.) to S3, preserving folder structure
        upload_files_to_s3(
            output_path, output_bucket_name, output_prefix, file_key, prefix
        )

        if jp2_used:
            logging.info(f"JP2 was used instead of TIF for {file_key}.")
            sys.exit(1)  # "JP2 used" condition
        else:
            logging.info(f"File processed successfully: {file_key}")
            sys.exit(0)


if __name__ == "__main__":
    logging.info("Starting NDNP Open OCR Processing...")

    bucket_name = os.getenv("BUCKET_NAME")
    prefix = os.getenv(
        "PREFIX"
    )  # The original top-level prefix you used in get_file_list
    output_prefix = os.getenv("OUTPUT_PREFIX")
    output_bucket_name = os.getenv("OUTPUT_BUCKET_NAME")

    array_index = int(os.getenv("AWS_BATCH_JOB_ARRAY_INDEX", "0"))

    logging.info("Segmentation mode: %s", USE_SEGMENTATION)

    # Grab the files from the original prefix
    file_list = get_file_list(bucket_name, prefix)
    if array_index >= len(file_list):
        logging.error(f"Array index {array_index} out of range.")
        sys.exit(1)

    file_key = file_list[array_index]
    logging.info(f"Processing file: {file_key}")

    process_file(file_key, bucket_name, output_bucket_name, output_prefix, prefix)
