import os
import sys
import json
import logging
import cv2
import numpy as np
from typing import List, Tuple


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

REPO_ROOT = "./vendor/AmericanStories"  # adjust if cloned elsewhere
SRC_DIR = os.path.join(REPO_ROOT, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

import onnx
import onnxruntime as ort
import torch
from torchvision.ops import nms
from effocr.engines.yolov8_ops import non_max_suppression as nms_yolov8

layout_model_path = "vendor/american_stories_models/layout_model_new.onnx"
line__model_path = "vendor/american_stories_models/line_model_new.onnx"

# ----------------------------------------------------------------------
# Utilities from the sample segmentation script
# ----------------------------------------------------------------------


def letterbox(im, new_shape=(640, 640), color=(114, 114, 114), auto=False):
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
    inputs = [n.name for n in model.graph.input]
    inits = [n.name for n in model.graph.initializer]
    feed = list(set(inputs) - set(inits))
    return feed[0]

def non_max_suppression(pred, conf_thres=0.25, iou_thres=0.45):
    # very minimal wrapper around torchvision nms
    pred = pred[pred[:,4] > conf_thres]
    if not pred.shape[0]:
        return []
    boxes = pred[:, :4]
    scores= pred[:, 4]
    keep  = nms(boxes, scores, iou_thres)
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
    print(f"▶ raw ONNX out: {raw.shape}")

    # 4) NMS
    if backend == "yolo":
        det = non_max_suppression(preds, conf_thres=0.15, iou_thres=0.45)
    elif backend == "yolov8":
        # v8 NMS expects (bs, boxes, 6) → list of 1 tensor
        out = nms_yolov8(
            preds.unsqueeze(0),
            conf_thres=0.05,
            iou_thres=0.01,
            max_det=1000,
            agnostic=True,
        )
        det = out[0]
    else:
        raise ValueError(f"Unknown backend: {backend}")

    print(
        f"▶ post‐NMS detections: {det.shape if isinstance(det, torch.Tensor) else len(det)}"
    )

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
    print(f"▶ final regions: {len(boxes)}\n")
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
    print(f"Segmenting image {image_path}", file=sys.stderr)
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


# Stitching logic from the reference script ------------------------------------

NS_ALTO = "http://www.loc.gov/standards/alto/ns-v3#"
NS_XSI = "http://www.w3.org/2001/XMLSchema-instance"
cv2.setNumThreads(0)


def merge_alto_region_xmls(
    source_image_path: str,
    region_dir: str,
    offsets_file: str,
    boxes_file: str,
    output_file: str,
):
    logger.debug("Merging regions from %s", region_dir)
    import xml.etree.ElementTree as ET
    import copy

    ET.register_namespace("", NS_ALTO)
    ET.register_namespace("xsi", NS_XSI)

    root = ET.Element(
        f"{{{NS_ALTO}}}alto",
        {
            "xmlns": NS_ALTO,
            "xmlns:xsi": NS_XSI,
            "xsi:schemaLocation": "http://www.loc.gov/standards/alto/ns-v3# http://www.loc.gov/alto/v3/alto-3-0.xsd",
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

    with open(offsets_file) as f:
        region_offsets = json.load(f)
    with open(boxes_file) as f:
        region_boxes = json.load(f)

    max_x = max(v[2] for v in region_boxes.values())
    max_y = max(v[3] for v in region_boxes.values())

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

    blocks = []
    for fn in sorted(os.listdir(region_dir)):
        if not fn.startswith("region_") or not fn.endswith(".xml"):
            continue
        rid = fn.split("_")[1].split(".")[0]
        dx, dy = region_offsets.get(rid, (0, 0))
        tree = ET.parse(os.path.join(region_dir, fn))
        rps = tree.getroot().find(f".//{{{NS_ALTO}}}PrintSpace")
        if rps is None:
            continue
        for cb in rps.findall(f"{{{NS_ALTO}}}ComposedBlock"):
            cb_copy = copy.deepcopy(cb)
            for el in cb_copy.iter():
                if "HPOS" in el.attrib:
                    el.attrib["HPOS"] = str(int(el.attrib["HPOS"]) + dx)
                if "VPOS" in el.attrib:
                    el.attrib["VPOS"] = str(int(el.attrib["VPOS"]) + dy)
            blocks.append(cb_copy)

    blocks.sort(
        key=lambda b: (int(b.attrib.get("VPOS", 0)), int(b.attrib.get("HPOS", 0)))
    )
    for b in blocks:
        ps.append(b)

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

    tree = ET.ElementTree(root)
    tree.write(output_file, encoding="utf-8", xml_declaration=True)
    logger.debug("Composite ALTO written to %s", output_file)
