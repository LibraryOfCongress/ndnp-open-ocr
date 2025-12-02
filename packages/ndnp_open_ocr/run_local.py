import os
import sys
import json
import logging
import tempfile
import shutil
import argparse
from typing import Optional
from PIL import Image

from ndnp_open_ocr.processors import OCRProcessor, PreprocessingMethod
from ndnp_open_ocr.storage import (
    list_source_items,
    fetch_item,
    publish_outputs,
    write_metadata,
    build_output_rel_dir,
)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

def is_valid_image(input_file_path: str) -> bool:
    try:
        with Image.open(input_file_path) as img:
            img.verify()
        return True
    except Exception:
        return False


def download_input_local(src_uri: str, rel_path: str, temp_dir: str) -> str:
    path = fetch_item(src_uri, rel_path, temp_dir)
    # If the file is a TIF but invalid (e.g., remote is actually JP2), fetch JP2 explicitly
    if path.lower().endswith(".tif") and not is_valid_image(path):
        root, _ = os.path.splitext(rel_path)
        rel_jp2 = root + ".jp2"
        try:
            return fetch_item(src_uri, rel_jp2, temp_dir)
        except Exception:
            return path
    return path


def run_local_batch_with_uris(src_uri: str, sink_uri: str, pattern: str, use_segmenter: bool, only_relpath: Optional[str] = None) -> None:
    items = [only_relpath] if only_relpath else list_source_items(src_uri, pattern)
    logging.info("Discovered %d input items", len(items))

    # Record tesseract version
    try:
        from pytesseract import get_tesseract_version
        write_metadata(sink_uri, "tesseract_version.txt", str(get_tesseract_version()))
    except Exception:
        pass

    for rel_path in items:
        if not rel_path:
            continue
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

            rel_dir = build_output_rel_dir(src_uri, rel_path)
            publish_outputs(sink_uri, out_dir, rel_dir)

            try:
                shutil.rmtree(tmp)
            except OSError:
                pass


def run_local_batch() -> None:
    """Env-based wrapper retained for compatibility with existing runners."""
    src_uri = os.environ.get("SOURCE_URI")
    sink_uri = os.environ.get("SINK_URI")
    if not (src_uri and sink_uri):
        raise SystemExit("Please set SOURCE_URI and SINK_URI for local runs.")
    use_segmenter = os.getenv("USE_SEGMENTATION", "false").lower() == "true"
    pattern = os.getenv("INPUT_GLOB") or "**/*.tif"
    run_local_batch_with_uris(src_uri, sink_uri, pattern, use_segmenter)


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="NDNP Open OCR batch runner (URI-based)")
    # Accept both --input/--output and legacy --source/--sink
    parser.add_argument("--source", "--input", dest="input_uri", required=False,
                        help="Input URI (file:///... or s3://bucket/prefix)")
    parser.add_argument("--sink", "--output", dest="output_uri", required=False,
                        help="Output URI (file:///... or s3://bucket/prefix)")
    parser.add_argument("--glob", default=None, help="Input glob (e.g., '**/*.tif' or '**/*.jp2')")
    parser.add_argument("--segmentation", default=None, choices=["true", "false"], help="Enable segmentation")
    parser.add_argument("--relpath", default=None, help="Process only this single relative path under SOURCE_URI")

    args = parser.parse_args(argv)

    # Resolve URIs with new names first, then legacy envs
    src_uri = args.input_uri or os.environ.get("INPUT_URI") or os.environ.get("SOURCE_URI")
    sink_uri = args.output_uri or os.environ.get("OUTPUT_URI") or os.environ.get("SINK_URI")
    if not (src_uri and sink_uri):
        parser.error("--input/--output (or --source/--sink) are required, or set INPUT_URI/OUTPUT_URI")

    pattern = args.glob or os.environ.get("INPUT_GLOB") or "**/*.tif"
    seg_env = os.environ.get("USE_SEGMENTATION", "false").lower()
    use_segmenter = (args.segmentation or seg_env) == "true"

    run_local_batch_with_uris(src_uri, sink_uri, pattern, use_segmenter, args.relpath)
    return 0


if __name__ == "__main__":
    sys.exit(main())
