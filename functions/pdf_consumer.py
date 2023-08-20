import json
import os
import errno
import tempfile
import sys
import subprocess
from helpers import \
    download_files_from_s3, \
    update_remaining_messages, \
    upload_files_to_s3, \
    make_directory

sys.path.append("/opt/python/")
dir_contents = os.listdir("/opt/python/lib/python3.8/site-packages")

try:
    import cv2
    print("OpenCV is already installed!")
except ImportError:
    print("OpenCV is not installed. Installing now...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "--target", "/tmp", "opencv-python-headless"])
    sys.path.append('/tmp')

from src.ndnp_open_ocr.processors import OCRProcessor

def handler(event, context):
    print("Number of messages left in queue: {}".format(len(event["Records"])))
    for message in event["Records"]:
        message = json.loads(message["body"])
        # raise Exception("Throw exception.")
        with tempfile.TemporaryDirectory() as temp_dir:
            input_file_path = download_files_from_s3(
                message["Bucket"], message["Key"], temp_dir
            )
            if os.path.exists(input_file_path):
                print(f"{input_file_path} has been downloaded successfully.")
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
    update_remaining_messages(message["JobId"], event)
    return {"statusCode": 200, "body": "Success"}
