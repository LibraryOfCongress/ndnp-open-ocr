import json
import os
import errno
import tempfile
import sys
import subprocess
from helpers import download_files_from_s3, upload_files_to_s3, make_directory

contents = os.listdir("/opt/bin")
print(f"Contents of /opt:")
for item in contents:
    print(item)

sys.path.append("/tmp")
try:
    import cv2

    print("OpenCV is already installed!")
except ImportError:
    print("OpenCV is not installed. Installing now...")
    subprocess.check_call(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--target",
            "/tmp",
            "opencv-python-headless",
        ]
    )
    output = subprocess.check_output(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--target",
            "/tmp",
            "-r",
            "requirements.txt",
        ],
        stderr=subprocess.STDOUT,
    )
    print(output.decode())
    # subprocess.check_call(
    #     [sys.executable, "-m", "pip", "install", "--target", "/tmp", "reportlab"]
    # )
    sys.path.append("/tmp")
sys.path.append("/tmp")
contents = os.listdir("/tmp")
print(f"Contents of /opt:")
for item in contents:
    print(item)
print(sys.path)
print(
    f"Available space in /tmp: {os.statvfs('/tmp').f_bavail * os.statvfs('/tmp').f_frsize / (1024*1024):.2f} MB"
)

from src.ndnp_open_ocr.processors import OCRProcessor, PreprocessingMethod
import boto3

dynamodb = boto3.resource("dynamodb")


def handler(event, context):
    """Generates output PDF using NDNP Open OCR pipeline"""
    print("Number of messages left in queue: {}".format(len(event["Records"])))
    for message in event["Records"]:
        message = json.loads(message["body"])
        job_id = message["JobId"]
        with tempfile.TemporaryDirectory() as temp_dir:
            input_file_path = download_files_from_s3(
                message["Bucket"], message["Key"], temp_dir
            )
            if os.path.exists(input_file_path):
                print(f"{input_file_path} has been downloaded successfully.")
                output_path = os.path.join(temp_dir, "output")
                make_directory(output_path)

                # Run NDNP Open OCR Reprocessing on this input
                processor = OCRProcessor(
                    input_file_path,
                    output_path,
                    preprocessing_method=PreprocessingMethod.ORIGINAL,
                )
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
            resp = table.update_item(
                Key={"pk": "JOB", "sk": job_id},
                UpdateExpression="SET RemainingPDFMessages = RemainingPDFMessages - :dec",
                ExpressionAttributeValues={
                    ":dec": len(event["Records"]),
                },
                ReturnValues="UPDATED_NEW",
            )

    return {"statusCode": 200, "body": "Success"}
