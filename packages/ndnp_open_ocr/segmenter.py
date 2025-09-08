from collections import defaultdict
import os
import sys
import logging
import cv2
import numpy as np
 
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
    return im, (r, r), (left, top)


def get_onnx_input_name(model):
    """Return the name of the first input tensor for the ONNX model."""
    inputs = [n.name for n in model.graph.input]
    inits = [n.name for n in model.graph.initializer]
    feed = list(set(inputs) - set(inits))
    return feed[0]


def non_max_suppression(pred, conf_thres=0.02, iou_thres=0.45):
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
    im, (r_x, r_y), (left, top) = letterbox(img, (1280, 1280), auto=False)

    # 2) prep for model: BGR→RGB, HWC→CHW, 0–1
    im_model = im[:, :, ::-1].transpose(2, 0, 1)[None].astype(np.float32) / 255.0

    # 3) ONNX inference
    raw = session.run(None, {input_name: im_model})[0]
    preds = torch.from_numpy(raw)[0]
    logger.debug("Raw ONNX out shape: %s", raw.shape)

    # 4) NMS
    if backend == "yolo":
        det = non_max_suppression(preds, conf_thres=0.01, iou_thres=0.40)
    elif backend == "yolov8":
        # v8 NMS expects (bs, boxes, 6) → list of 1 tensor
        out = nms_yolov8(
            preds.unsqueeze(0),
            conf_thres=0.01,
            iou_thres=0.40,
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
        ox0 = int((x0 - left) / r_x)
        oy0 = int((y0 - top) / r_y)
        ox1 = int((x1 - left) / r_x)
        oy1 = int((y1 - top) / r_y)
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

    h, w = img.shape[:2]

    if layout_model_path:
        logger.debug("Using layout model %s", layout_model_path)
        layout_sess = ort.InferenceSession(layout_model_path)
        inp = get_onnx_input_name(onnx.load(layout_model_path))
        crops, boxes = get_layout_predictions(layout_sess, img, inp)

    else:  # fall back to whole image
        crops = [(0, img)]
        boxes = [(0, 0, w, h)]

    logger.debug("Segmented into %d regions", len(crops))
    return crops, boxes, w, h
def shift_element_coords(element: ET.Element, dx: int, dy: int) -> None:
    """
    Shift the ALTO HPOS/VPOS attributes on `element` and all its children by (dx, dy),
    """
    for el in element.iter():
        if "HPOS" in el.attrib:
            orig_hpos = float(el.attrib["HPOS"])
            # keep fractional sub-pixel precision
            el.set("HPOS", str(int(orig_hpos + dx)))
        if "VPOS" in el.attrib:
            orig_vpos = float(el.attrib["VPOS"])
            el.set("VPOS", str(int(orig_vpos + dy)))

# Note: helper utilities for block bbox and intersections are no longer needed
# in this build since we only merge segmented region ALTO without gap filling.

def merge_alto_region_xmls(source_image_path: str,
                           region_dir: str,
                           boxes_dict: dict[str, tuple[int, int, int, int]],
                           output_file: str,
                           image_width: int,
                           image_height: int) -> None:
    """
    Merge per-region ALTO files back into one page-level ALTO, using a
    simple column-major sort with an X-tolerance so that a block that is
    far *below* another one never jumps ahead just because its HPOS is a
    few pixels smaller.
    """
    # ------------------------------------------------------------
    # 1)  <alto> skeleton
    # ------------------------------------------------------------
    max_x = image_width
    max_y = image_height

    root = ET.Element(
        f"{{{NS_ALTO}}}alto",
        {
            "xmlns": NS_ALTO,
            "xmlns:xsi": NS_XSI,
            "xsi:schemaLocation": (
                "http://www.loc.gov/standards/alto/ns-v3# "
                "http://www.loc.gov/alto/v3/alto-3-0.xsd"
            ),
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
        {"WIDTH": str(max_x), "HEIGHT": str(max_y),
         "PHYSICAL_IMG_NR": "0", "ID": "page_0"},
    )
    ps = ET.SubElement(
        page,
        f"{{{NS_ALTO}}}PrintSpace",
        {"HPOS": "0", "VPOS": "0", "WIDTH": str(max_x), "HEIGHT": str(max_y)},
    )

    # ------------------------------------------------------------
    # 2) No gap collection in this build; proceed to regions only


    # ------------------------------------------------------------
    # 3)  Gather regions
    # ------------------------------------------------------------
    region_entries = []                            # [(x0, y0, fn, rid), …]
    for fn in os.listdir(region_dir):
        if not (fn.startswith("region_") and fn.endswith(".xml")):
            continue
        rid = fn.split("_")[1].split(".")[0]       # "17" from "region_17.xml"
        if rid not in boxes_dict:
            continue
        x0, y0, *_ = boxes_dict[rid]
        region_entries.append((x0, y0, fn, rid))

    # ------------------------------------------------------------
    # 4)  Sort regions with X-tolerance
    # ------------------------------------------------------------
    X_TOL = max(int(max_x * 0.06), 100)            # 6 % of page or ≥100 px

    def sort_key(x0: int, y0: int) -> tuple[int, int]:
        col_bucket = x0 // X_TOL                   # “coarse” column number
        return (col_bucket, y0)

    region_entries.sort(key=lambda t: sort_key(t[0], t[1]))

    # ------------------------------------------------------------
    # 5)  Append in reading order
    # ------------------------------------------------------------
    supported_tags = {f"{{{NS_ALTO}}}{t}" for t in ["ComposedBlock", "TextBlock", "Illustration", "GraphicalElement"]}
    for x0, y0, fn, rid in region_entries:
        tree_r = ET.parse(os.path.join(region_dir, fn))
        rps = tree_r.find(f".//{{{NS_ALTO}}}PrintSpace")
        if rps is None:
            continue
        for child in list(rps):
            if child.tag not in supported_tags:
                continue
            child_copy = copy.deepcopy(child)
            shift_element_coords(child_copy, x0, y0)
            ps.append(child_copy)

    # ------------------------------------------------------------
    # 6)  Renumber IDs using *the same* sort rule
    # ------------------------------------------------------------
    id_specs = [
        (f"{{{NS_ALTO}}}ComposedBlock", "cblock"),
        (f"{{{NS_ALTO}}}TextBlock",    "block"),
        (f"{{{NS_ALTO}}}TextLine",     "line"),
        (f"{{{NS_ALTO}}}String",       "string"),
        (f"{{{NS_ALTO}}}Illustration","cblock"),
        (f"{{{NS_ALTO}}}GraphicalElement","cblock"),
    ]

    prefix_to_elems = defaultdict(list)
    for tag, prefix in id_specs:
        elems = root.findall(f".//{tag}")
        prefix_to_elems[prefix].extend(elems)

    for prefix, all_elems in prefix_to_elems.items():
        all_elems.sort(
            key=lambda el: (
                int(el.attrib.get("HPOS", 0)) // X_TOL,
                int(el.attrib.get("VPOS", 0)),
                int(el.attrib.get("HPOS", 0)),
            )
        )
        for i, el in enumerate(all_elems):
            el.set("ID", f"{prefix}_{i}")

    # ------------------------------------------------------------
    # 7)  Write merged ALTO
    # ------------------------------------------------------------
    ET.ElementTree(root).write(output_file, encoding="utf-8",
                               xml_declaration=True)
    logger.info("Composite ALTO written to: %s", output_file)
