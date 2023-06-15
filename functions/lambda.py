# !pip install -r requirements.txt
# !pip install boto3
import boto3

# %%
from src.ndnp_open_ocr.processors import AltoProcessor, PDFProcessor
from rich import print

import errno
import pytesseract
from PIL import Image
import os
import subprocess
import pikepdf
# from src.helpers import transfer_xmp, postprocess_pdf
import typer
import time
import multiprocessing as mp
from multiprocessing import Pool, cpu_count
import glob
import subprocess
import tempfile

# Directory paths to be added to the PATH
ghostscript_directory = "/opt/bin"
exiftool_directory = "/opt/bin"

# Get the current PATH
current_path = os.environ.get("PATH")

# Append the new directories to the PATH
new_path = f"{ghostscript_directory}:{exiftool_directory}:{current_path}"

# Set the modified PATH as the new environment variable
os.environ["PATH"] = new_path

TIFF_MODE = True

# Runs the OCR process on a single file
s3 = boto3.client("s3")


def run_tesseract_worker(input_file_path, output_path):
    input_file_name = os.path.splitext(os.path.basename(input_file_path))[0]

    old_pdf = os.path.join(os.path.dirname(input_file_path), f"{input_file_name}.pdf")
    alto_file_path = os.path.join(output_path, f"{input_file_name}.xml")

    # List the contents of the input_file_path directory
    input_directory = os.path.dirname(input_file_path)
    directory_contents = os.listdir(input_directory)

    # Print the contents of the directory
    print(f"Contents of {input_directory}:")
    for item in directory_contents:
        print(f" - {item}")

    try:
        os.makedirs(output_path)
    except OSError as exc:
        if exc.errno != errno.EEXIST:
            raise
        pass

    new_pdf = os.path.join(output_path, f'{input_file_name}_output.pdf')

    tmp_img = input_file_path
    print("TEMP IMAGE PATH", tmp_img)

    try:
        pdf = pytesseract.image_to_pdf_or_hocr(tmp_img, extension='pdf')
        print("NEW PDF", new_pdf)
        with open(new_pdf, 'w+b') as f:
            f.write(pdf)
            f.close()
        del pdf
    except Exception as e:
        print(f"PDF generation failed: {input_file_name} {e}")

    postprocessed_pdf = os.path.join(output_path, f'{input_file_name}.pdf')
    # Create an instance of PDFProcessor and use its methods
    processor = PDFProcessor(new_pdf, postprocessed_pdf)
    processor.postprocess_pdf()
    processor.transfer_xmp()

    try:
        with pikepdf.Pdf.open(postprocessed_pdf, allow_overwriting_input=True) as pdf:
            pdf.save(postprocessed_pdf, linearize=True)
    except Exception as e:
        print(f"PDF Linearization failed: {input_file_name} {e}")

    try:
        print("TRY TO GENERATE ALTO")
        xml = pytesseract.image_to_alto_xml(tmp_img)
        with open(alto_file_path, 'w+b') as f:
            f.write(xml)
            f.close()

        # fix_alto_file_hyphenation(alto_file_path)
        input_file = alto_file_path

        image = Image.open(tmp_img)
        dpi = image.info.get("dpi", (96, 96))

        print(dpi)

        alto_processor = AltoProcessor(input_file)
        alto_processor.add_description_tags()
        alto_processor.convert_pixels_to_inches(dpi)
        alto_processor.save(alto_file_path)
        del xml
    except Exception as e:
        print(f"ALTO generation failed: {input_file_name} {e}")

    os.remove(new_pdf)


# Write code that will loop through all files in the input directory and run tesseract on each file.
# If the file is not a valid image file, then skip it.
# Outputs ALTO and PDF files from Tesseract

def handler(event, context):
    return {
        "statusCode": 200,
        "body": "Success"
    }