import os
import json
import logging
import tempfile
import shutil
from PIL import Image

from ndnp_open_ocr.processors import OCRProcessor, PreprocessingMethod
from ndnp_open_ocr.storage import list_inputs, download_input, upload_outputs, record_text_blob


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


def run_local_batch():
    """Run a local batch using connector configuration from environment variables.

    Required env vars:
      SOURCE_URI='file:///path/to/batch-root' (or s3://bucket/prefix)
      SINK_URI='file:///path/to/output-root' (or s3://bucket/prefix)
    Optional:
      USE_SEGMENTATION=true|false
    """
    src_uri = os.environ.get("SOURCE_URI")
    sink_uri = os.environ.get("SINK_URI")
    if not (src_uri and sink_uri):
        raise SystemExit("Please set SOURCE_URI and SINK_URI for local runs.")

    use_segmenter = os.getenv("USE_SEGMENTATION", "false").lower() == "true"

    pattern = os.getenv("INPUT_GLOB") or "**/*.tif"
    items = list_inputs(src_uri, pattern)
    logging.info("Discovered %d input items", len(items))

    # Record tesseract version
    try:
        from pytesseract import get_tesseract_version

        record_text_blob(sink_uri, "tesseract_version.txt", str(get_tesseract_version()))
    except Exception:
        pass

    def is_valid_image(input_file_path: str) -> bool:
        try:
            with Image.open(input_file_path) as img:
                img.verify()
            return True
        except Exception:
            return False

    def download_input_local(src_uri: str, rel_path: str, temp_dir: str) -> str:
        path = download_input(src_uri, rel_path, temp_dir)
        # If the file is a TIF but invalid (e.g., remote is actually JP2), use JP2 sidecar
        if path.lower().endswith(".tif") and not is_valid_image(path):
            jp2_candidate = path[:-4] + ".jp2"
            if os.path.exists(jp2_candidate):
                return jp2_candidate
        return path

    for rel_path in items:
        with tempfile.TemporaryDirectory() as tmp:
            in_path = download_input_local(src_uri, rel_path, tmp)
            out_dir = os.path.join(tmp, "output")
            os.makedirs(out_dir, exist_ok=True)

            proc = OCRProcessor(
                in_path,
                out_dir,
                preprocessing_method=PreprocessingMethod.ORIGINAL,
                use_segmenter=use_segmenter,
            )
            proc.process()

            # pdf_path = proc.get_postprocessed_pdf_path()
            # text_found = False
            # with open(pdf_path, "rb") as f:
            #     reader = PdfReader(f)
            #     for page in reader.pages:
            #         if page.extract_text():
            #             text_found = True
            #             break
            # if not text_found:
            #     logging.warning("No text found in PDF for %s", rel_path)

            upload_outputs(sink_uri, out_dir, os.path.dirname(rel_path))

            # Cleanup tmp dir
            try:
                shutil.rmtree(tmp)
            except OSError:
                pass


if __name__ == "__main__":
    run_local_batch()
