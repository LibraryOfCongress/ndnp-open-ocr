import ast
import os
import sys
import logging
import cv2
import numpy as np

import xml.etree.ElementTree as ET
import copy

from ndnp_open_ocr.alto import NS_ALTO, NS_XSI, renumber_alto_ids
 


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


def filter_contained_boxes(boxes, crops, threshold=0.85):
    """Drop the smaller box when two boxes overlap by >= *threshold* of the smaller's area."""
    n = len(boxes)
    if n <= 1:
        return boxes, crops

    areas = [(b[2] - b[0]) * (b[3] - b[1]) for b in boxes]
    contained = set()

    for i in range(n):
        if i in contained:
            continue
        for j in range(i + 1, n):
            if j in contained:
                continue

            # intersection rectangle
            ix0, iy0 = max(boxes[i][0], boxes[j][0]), max(boxes[i][1], boxes[j][1])
            ix1, iy1 = min(boxes[i][2], boxes[j][2]), min(boxes[i][3], boxes[j][3])
            if ix1 <= ix0 or iy1 <= iy0:
                continue

            inter_area = (ix1 - ix0) * (iy1 - iy0)
            smaller_area = min(areas[i], areas[j])
            if smaller_area <= 0:
                continue

            # discard the smaller box if it's mostly covered
            if inter_area / smaller_area >= threshold:
                if areas[i] <= areas[j]:
                    contained.add(i)
                    break
                else:
                    contained.add(j)

    if contained:
        logger.debug("Containment filter removed %d of %d boxes", len(contained), n)

    kept = [idx for idx in range(n) if idx not in contained]
    return [boxes[i] for i in kept], [crops[i] for i in kept]


def get_layout_predictions(session, img, input_name, class_names, backend="yolov8"):
    """
    Returns:
      crops: [(region_id, crop_np, class_id, class_name), ...]
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

    # 4) NMS - Use iou_thres=0.10 to match AmericanStories recommended settings.
    # Gap filling recovers any content missed due to suppressed regions.
    if backend == "yolo":
        det = non_max_suppression(preds, conf_thres=0.01, iou_thres=0.10)
    elif backend == "yolov8":
        # v8 NMS expects (bs, boxes, 6) → list of 1 tensor
        out = nms_yolov8(
            preds.unsqueeze(0),
            conf_thres=0.01,
            iou_thres=0.10,
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
        # yolov8 detection row is [x0, y0, x1, y1, conf, class_id]; pull the
        # class so downstream OCR can pick the right Tesseract PSM per region.
        class_id = int(d[5].item())
        class_name = class_names[class_id]
        ox0 = int((x0 - left) / r_x)
        oy0 = int((y0 - top) / r_y)
        ox1 = int((x1 - left) / r_x)
        oy1 = int((y1 - top) / r_y)
        ox0, oy0 = max(0, ox0), max(0, oy0)
        ox1, oy1 = min(w, ox1), min(h, oy1)
        if ox1 > ox0 and oy1 > oy0:
            boxes.append((ox0, oy0, ox1, oy1))
            crops.append((i, img[oy0:oy1, ox0:ox1], class_id, class_name))

    # 6) Remove boxes significantly overlapping with a larger box
    boxes, crops = filter_contained_boxes(boxes, crops)

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
    crops : list[tuple[int, numpy.ndarray, int, str]]
        ``(region_id, crop_img, class_id, class_name)`` tuples for each detected region.
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
        layout_model = onnx.load(layout_model_path)
        inp = get_onnx_input_name(layout_model)
        # yolov8 stores class names in the ONNX metadata as a dict literal.
        metadata = {p.key: p.value for p in layout_model.metadata_props}
        class_names = ast.literal_eval(metadata["names"])
        crops, boxes = get_layout_predictions(layout_sess, img, inp, class_names)

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
    # 2) Region merge only (gap filling occurs later in processors)


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
    # 6)  Renumber IDs
    # ------------------------------------------------------------
    renumber_alto_ids(root, NS_ALTO)

    # ------------------------------------------------------------
    # 7)  Write merged ALTO
    # ------------------------------------------------------------
    ET.ElementTree(root).write(output_file, encoding="utf-8",
                               xml_declaration=True)
    logger.info("Composite ALTO written to: %s", output_file)
