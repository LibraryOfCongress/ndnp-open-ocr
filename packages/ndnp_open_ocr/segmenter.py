import os
import sys
import json
import logging
import cv2
import numpy as np
from typing import List, Tuple
import xml.etree.ElementTree as ET
import copy


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# === derive REPO_ROOT from this file’s location ===
THIS_DIR  = os.path.dirname(__file__)  # e.g. /app/ndnp_open_ocr
REPO_ROOT = os.path.abspath(os.path.join(THIS_DIR,"vendor", "AmericanStories"))
SRC_DIR   = os.path.join(REPO_ROOT, "src")

if not os.path.isdir(SRC_DIR):
    raise FileNotFoundError(f"Cannot find segmentation sources: {SRC_DIR}")

if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

import onnx
import onnxruntime as ort
import torch
from torchvision.ops import nms
from effocr.engines.yolov8_ops import non_max_suppression as nms_yolov8

# Used as the segmentation model that generates the crops for the TIF image
layout_model_path = os.path.join(
    REPO_ROOT, "american_stories_models", "layout_model_new.onnx"
)
NS_ALTO = "http://www.loc.gov/standards/alto/ns-v3#"
NS_XSI = "http://www.w3.org/2001/XMLSchema-instance"
cv2.setNumThreads(0)

# ----------------------------------------------------------------------
# Utilities from the sample segmentation script
# ----------------------------------------------------------------------


def letterbox(im, new_shape=(640, 640), color=(114, 114, 114), auto=False):
    """Resize ``im`` to ``new_shape`` with padding to maintain aspect ratio for model input."""
    shape = im.shape[:2]
    r = min(new_shape[0] / shape[0], new_shape[1] / shape[1])
    new_unpad = (int(round(shape[1] * r)), int(round(shape[0] * r)))
    dw, dh = new_shape[1] - new_unpad[0], new_shape[0] - new_unpad[1]
    dw /= 2
    dh /= 2
    im = cv2.resize(im, new_unpad, interpolation=cv2.INTER_LINEAR)
    top, bottom = int(round(dh - 0.1)), int(round(dh + 0.1))
    left, right = int(round(dw - 0.1)), int(round(dw + 0.1))
    im = cv2.copyMakeBorder(
        im, top, bottom, left, right, cv2.BORDER_CONSTANT, value=color
    )
    return im, (r, r), (dw, dh)


def get_onnx_input_name(model):
    """Return the name of the first input tensor for the ONNX model."""
    inputs = [n.name for n in model.graph.input]
    inits = [n.name for n in model.graph.initializer]
    feed = list(set(inputs) - set(inits))
    return feed[0]


def non_max_suppression(pred, conf_thres=0.25, iou_thres=0.45):
    """Thin out overlapping detections using torchvision's NMS."""
    # very minimal wrapper around torchvision nms
    pred = pred[pred[:, 4] > conf_thres]
    if not pred.shape[0]:
        return []
    boxes = pred[:, :4]
    scores = pred[:, 4]
    keep = nms(boxes, scores, iou_thres)
    return pred[keep]


def get_layout_predictions(session, img, input_name, backend="yolov8"):
    """
    Returns:
      crops: [(region_id, crop_np), ...]
      boxes: [(x0,y0,x1,y1), ...] in original image coords
    """
    # 1) letterbox
    im, (r_x, r_y), (dw, dh) = letterbox(img, (1280, 1280), auto=False)

    # 2) prep for model: BGR→RGB, HWC→CHW, 0–1
    im_model = im[:, :, ::-1].transpose(2, 0, 1)[None].astype(np.float32) / 255.0

    # 3) ONNX inference
    raw = session.run(None, {input_name: im_model})[0]
    preds = torch.from_numpy(raw)[0]
    logger.debug("Raw ONNX out shape: %s", raw.shape)

    # 4) NMS
    if backend == "yolo":
        det = non_max_suppression(preds, conf_thres=0.15, iou_thres=0.45)
    elif backend == "yolov8":
        # v8 NMS expects (bs, boxes, 6) → list of 1 tensor
        out = nms_yolov8(
            preds.unsqueeze(0),
            conf_thres=0.005,
            iou_thres=0.06,
            max_det=1000,
            agnostic=True,
        )
        det = out[0]
    else:
        raise ValueError(f"Unknown backend: {backend}")

    logger.debug("Post-NMS detections: %s", det.shape if isinstance(det, torch.Tensor) else len(det))

    # 5) map back to original coords
    h, w = img.shape[:2]
    boxes, crops = [], []
    for i, d in enumerate(det):
        x0, y0, x1, y1 = d[:4]
        ox0 = int((x0 - dw) / r_x)
        oy0 = int((y0 - dh) / r_y)
        ox1 = int((x1 - dw) / r_x)
        oy1 = int((y1 - dh) / r_y)
        ox0, oy0 = max(0, ox0), max(0, oy0)
        ox1, oy1 = min(w, ox1), min(h, oy1)
        if ox1 > ox0 and oy1 > oy0:
            boxes.append((ox0, oy0, ox1, oy1))
            crops.append((i, img[oy0:oy1, ox0:ox1]))
    logger.debug("Final regions: %d", len(boxes))
    return crops, boxes


# ----------------------------------------------------------------------
# Public API
# ----------------------------------------------------------------------


def segment_page(
    image_path: str,
):
    """Segment ``image_path`` using the provided ONNX models.

    Parameters
    ----------
    image_path: str
        Path to the image that should be segmented.
    layout_model_path: str | None
        Path to the layout segmentation model. If ``None`` segmentation is skipped
        and the entire image is returned as a single region.
    line_model_path: str | None
        Unused currently but kept for future parity with the reference script.
    Returns
    -------
    crops : list[tuple[int, numpy.ndarray]]
        ``(region_id, crop_img)`` tuples for each detected region.
    boxes : list[tuple[int, int, int, int]]
        Bounding boxes for each region in original image coordinates.
    """

    logger.debug("Segmenting image %s", image_path)
    img = cv2.imread(image_path)
    if img is None:
        raise FileNotFoundError(image_path)

    if layout_model_path:
        logger.debug("Using layout model %s", layout_model_path)
        layout_sess = ort.InferenceSession(layout_model_path)
        inp = get_onnx_input_name(onnx.load(layout_model_path))
        crops, boxes = get_layout_predictions(layout_sess, img, inp)
    else:  # fall back to whole image
        h, w = img.shape[:2]
        crops = [(0, img)]
        boxes = [(0, 0, w, h)]

    logger.debug("Segmented into %d regions", len(crops))
    return crops, boxes


def shift_element_coords(element: ET.Element, dx: int, dy: int) -> None:
    """Shift ``HPOS`` and ``VPOS`` attributes on ``element`` and its children."""
    for el in element.iter():
        if "HPOS" in el.attrib:
            orig_hpos = float(el.attrib["HPOS"])
            el.set("HPOS", str(int(round(orig_hpos)) + dx))
        if "VPOS" in el.attrib:
            orig_vpos = float(el.attrib["VPOS"])
            el.set("VPOS", str(int(round(orig_vpos)) + dy))

def merge_alto_region_xmls(source_image_path, region_dir, boxes_dict, output_file):
    """
    Merge per-region ALTO files by directly using boxes_dict[rid] = [x0, y0, x1, y1].
    """
    # 1) Create root <alto> and <Layout>/<Page> exactly as before, using the page size.
    #    You can compute page width/height from max(x1), max(y1) in boxes_dict if you want:
    max_x = max(v[2] for v in boxes_dict.values())
    max_y = max(v[3] for v in boxes_dict.values())

    root = ET.Element(
        f"{{{NS_ALTO}}}alto",
        {
            "xmlns": NS_ALTO,
            "xmlns:xsi": NS_XSI,
            "xsi:schemaLocation": "http://www.loc.gov/standards/alto/ns-v3# "
            "http://www.loc.gov/alto/v3/alto-3-0.xsd",
        },
    )
    desc = ET.SubElement(root, f"{{{NS_ALTO}}}Description")
    ET.SubElement(desc, f"{{{NS_ALTO}}}MeasurementUnit").text = "pixel"
    src_info = ET.SubElement(desc, f"{{{NS_ALTO}}}sourceImageInformation")
    ET.SubElement(src_info, f"{{{NS_ALTO}}}fileName").text = source_image_path
    ocr_proc = ET.SubElement(desc, f"{{{NS_ALTO}}}OCRProcessing", {"ID": "OCR_0"})
    step = ET.SubElement(ocr_proc, f"{{{NS_ALTO}}}ocrProcessingStep")
    sw = ET.SubElement(step, f"{{{NS_ALTO}}}processingSoftware")
    ET.SubElement(sw, f"{{{NS_ALTO}}}softwareName").text = "tesseract 5.5.0"

    layout = ET.SubElement(root, f"{{{NS_ALTO}}}Layout")
    page = ET.SubElement(
        layout,
        f"{{{NS_ALTO}}}Page",
        {
            "WIDTH": str(max_x),
            "HEIGHT": str(max_y),
            "PHYSICAL_IMG_NR": "0",
            "ID": "page_0",
        },
    )
    ps = ET.SubElement(
        page,
        f"{{{NS_ALTO}}}PrintSpace",
        {"HPOS": "0", "VPOS": "0", "WIDTH": str(max_x), "HEIGHT": str(max_y)},
    )

    # 2) Collect region files with their coordinates so we can
    #    order them top-to-bottom, left-to-right.
    region_entries = []
    for fn in os.listdir(region_dir):
        if not fn.startswith("region_") or not fn.endswith(".xml"):
            continue
        rid = fn.split("_")[1].split(".")[0]  # e.g. "17"
        if rid not in boxes_dict:
            continue
        x0, y0, x1, y1 = boxes_dict[rid]
        # sort primarily by VPOS (top to bottom) and then by HPOS (left to right)
        region_entries.append((y0, x0, fn, rid))

    region_entries.sort()

    for _y, _x, fn, rid in region_entries:
        x0, y0, x1, y1 = boxes_dict[rid]  # full-page offsets

        # 3) Parse the region’s ALTO and extract every <ComposedBlock> under <PrintSpace>
        tree_region = ET.parse(os.path.join(region_dir, fn))
        root_region = tree_region.getroot()
        rps = root_region.find(f".//{{{NS_ALTO}}}PrintSpace")
        if rps is None:
            continue

        # 4) For each ComposedBlock (and inside that, <TextBlock>, <TextLine>, <String>, etc.), add x0,y0:
        for cb in rps.findall(f"{{{NS_ALTO}}}ComposedBlock"):
            cb_copy = copy.deepcopy(cb)
            shift_element_coords(cb_copy, x0, y0)
            ps.append(cb_copy)

    # 6) After all regions are appended, renumber IDs exactly as before:
    id_specs = [
        (f"{{{NS_ALTO}}}String", "string"),
        (f"{{{NS_ALTO}}}TextBlock", "block"),
        (f"{{{NS_ALTO}}}TextLine", "line"),
        (f"{{{NS_ALTO}}}ComposedBlock", "cblock"),
        (f"{{{NS_ALTO}}}Illustration", "cblock"),
        (f"{{{NS_ALTO}}}GraphicalElement", "cblock"),
    ]
    for tag, prefix in id_specs:
        elems = root.findall(f".//{tag}")
        try:
            elems.sort(
                key=lambda el: (
                    int(el.attrib.get("VPOS", 0)),
                    int(el.attrib.get("HPOS", 0)),
                )
            )
        except ValueError:
            pass
        for i, el in enumerate(elems):
            el.set("ID", f"{prefix}_{i}")

    # 7) Write out the merged ALTO file:
    merged_tree = ET.ElementTree(root)
    try:
        ET.indent(merged_tree, space="  ")
    except AttributeError:
        pass
    merged_tree.write(output_file, encoding="utf-8", xml_declaration=True)
    logger.info("Composite ALTO written to: %s", output_file)
