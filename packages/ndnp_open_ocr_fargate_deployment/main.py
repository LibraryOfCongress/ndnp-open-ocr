import os
import sys
import json
import boto3
import tempfile
import logging
import datetime
import shutil
from PyPDF2 import PdfReader
from PIL import Image
import pytesseract
from ndnp_open_ocr.processors import OCRProcessor, PreprocessingMethod
from ndnp_open_ocr.storage import (
    env_sink_fallback,
    env_source_fallback,
    list_source_items,
    fetch_item,
    publish_outputs,
    write_metadata,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# Keep an S3 client for legacy paths where needed
s3 = boto3.client("s3")

# Exit codes
EXIT_CODE_SUCCESS = 0
EXIT_CODE_ARRAY_INDEX_ERROR = 1
EXIT_CODE_OCR_FAILURE = 2
EXIT_CODE_JP2_FALLBACK = 3

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


def get_file_list():
    """List items using the configured source URI (or legacy S3 fallback)."""
    src_uri = os.getenv("SOURCE_URI") or env_source_fallback()
    pattern = os.getenv("INPUT_GLOB") or "**/*.tif"
    return src_uri, list_source_items(src_uri, pattern)


def download_input_local(src_uri, rel_path, temp_dir):
    path = fetch_item(src_uri, rel_path, temp_dir)
    # If the .tif is corrupt or missing, try fetching the .jp2 from source
    if path.lower().endswith(".tif") and not is_valid_image(path):
        root, _ = os.path.splitext(rel_path)
        rel_jp2 = root + ".jp2"
        try:
            jp2_path = fetch_item(src_uri, rel_jp2, temp_dir)
            return jp2_path
        except Exception:
            pass
    return path


def upload_outputs_local(sink_uri, output_dir: str, rel_dir: str) -> None:
    publish_outputs(sink_uri, output_dir, rel_dir)
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

def record_tesseract_version_local(sink_uri):
    try:
        version = str(pytesseract.get_tesseract_version())
        write_metadata(sink_uri, "tesseract_version.txt", version)
        logging.info(f"Recorded tesseract version {version}")
    except Exception as e:
        logging.error(f"Failed to record tesseract version: {e}")


def process_item(src_uri, sink_uri, rel_path):
    with tempfile.TemporaryDirectory() as temp_dir:
        input_file_path = download_input_local(src_uri, rel_path, temp_dir)

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

        # if not text_found:
        #     logging.error(f"No text found in the generated PDF for {rel_path}.")
        #     sys.exit(EXIT_CODE_OCR_FAILURE)

        # Upload outputs preserving relative directory
        upload_outputs_local(sink_uri, output_path, os.path.dirname(rel_path))

        if jp2_used:
            logging.info(f"JP2 was used instead of TIF for {rel_path}.")
            sys.exit(EXIT_CODE_JP2_FALLBACK)
        else:
            logging.info(f"File processed successfully: {rel_path}")
            sys.exit(EXIT_CODE_SUCCESS)


if __name__ == "__main__":
    logging.info("Starting NDNP Open OCR Processing...")

    # Build connectors from env (or legacy fallbacks)
    src_uri = os.getenv("SOURCE_URI") or env_source_fallback()
    sink_uri = os.getenv("SINK_URI") or env_sink_fallback()

    array_index = int(os.getenv("AWS_BATCH_JOB_ARRAY_INDEX", "0"))

    logging.info("Segmentation mode: %s", USE_SEGMENTATION)

        # Record the tesseract version once for the batch on the first array index
    if array_index == 0:
        record_tesseract_version_local(sink_uri)

    # Grab the files from the source
    src_uri, rel_items = get_file_list()
    if array_index >= len(rel_items):
        logging.error(f"Array index {array_index} out of range.")
        sys.exit(EXIT_CODE_ARRAY_INDEX_ERROR)

    rel_path = rel_items[array_index]
    logging.info(f"Processing item: {rel_path}")

    process_item(src_uri, sink_uri, rel_path)
