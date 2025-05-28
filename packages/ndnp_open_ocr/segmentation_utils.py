import os
import pytesseract
import json
import cv2
import numpy as np
import torch
import onnx
import onnxruntime as ort
from torchvision.ops import nms

try:
    from effocr.engines.yolov8_ops import non_max_suppression as nms_yolov8
except Exception:  # pragma: no cover - optional dependency
    nms_yolov8 = None


# ---------------------------
# Helper functions
# ---------------------------

def letterbox(im, new_shape=(640, 640), color=(114, 114, 114), auto=False):
    """Resize with unchanged aspect ratio using padding."""
    shape = im.shape[:2]  # current shape [height, width]
    r = min(new_shape[0] / shape[0], new_shape[1] / shape[1])
    new_unpad = (int(round(shape[1] * r)), int(round(shape[0] * r)))
    dw, dh = new_shape[1] - new_unpad[0], new_shape[0] - new_unpad[1]
    dw /= 2
    dh /= 2
    im = cv2.resize(im, new_unpad, interpolation=cv2.INTER_LINEAR)
    top, bottom = int(round(dh - 0.1)), int(round(dh + 0.1))
    left, right = int(round(dw - 0.1)), int(round(dw + 0.1))
    im = cv2.copyMakeBorder(im, top, bottom, left, right, cv2.BORDER_CONSTANT, value=color)
    return im, (r, r), (dw, dh)


def get_onnx_input_name(model):
    """Return the first non-initializer input name from an ONNX model."""
    inputs = [n.name for n in model.graph.input]
    inits = [n.name for n in model.graph.initializer]
    feed = list(set(inputs) - set(inits))
    if not feed:
        raise ValueError("Model does not have a non-initializer input")
    return feed[0]


def non_max_suppression(pred, conf_thres=0.25, iou_thres=0.45):
    pred = pred[pred[:, 4] > conf_thres]
    if not pred.shape[0]:
        return []
    boxes = pred[:, :4]
    scores = pred[:, 4]
    keep = nms(boxes, scores, iou_thres)
    return pred[keep]


def get_layout_predictions(session, img, input_name, backend="yolov8"):
    """Return cropped regions and bounding boxes using a layout model."""
    im, (r_x, r_y), (dw, dh) = letterbox(img, (1280, 1280), auto=False)
    im_model = im[:, :, ::-1].transpose(2, 0, 1)[None].astype(np.float32) / 255.0
    raw = session.run(None, {input_name: im_model})[0]
    preds = torch.from_numpy(raw)[0]

    if backend == "yolo":
        det = non_max_suppression(preds, conf_thres=0.05, iou_thres=0.01)
    elif backend == "yolov8" and nms_yolov8 is not None:
        out = nms_yolov8(preds.unsqueeze(0), conf_thres=0.05, iou_thres=0.01, max_det=1000, agnostic=True)
        det = out[0]
    else:
        raise ValueError(f"Unknown backend: {backend}")

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
    return crops, boxes


# ---------------------------
# ALTO stitching
# ---------------------------

NS_ALTO = "http://www.loc.gov/standards/alto/ns-v3#"
NS_XSI = "http://www.w3.org/2001/XMLSchema-instance"


def merge_alto_region_xmls(source_image_path, region_dir, offsets_file, boxes_file, output_file):
    """Combine regional ALTO XMLs into a single document."""
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
        {"WIDTH": str(max_x), "HEIGHT": str(max_y), "PHYSICAL_IMG_NR": "0", "ID": "page_0"},
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

    blocks.sort(key=lambda b: (int(b.attrib.get("VPOS", 0)), int(b.attrib.get("HPOS", 0))))
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
            elems.sort(key=lambda el: (int(el.attrib.get("VPOS", 0)), int(el.attrib.get("HPOS", 0))))
        except ValueError:
            pass
        for i, el in enumerate(elems):
            el.set("ID", f"{prefix}_{i}")

    tree = ET.ElementTree(root)
    tree.write(output_file, encoding="utf-8", xml_declaration=True)




def run_segmented_ocr(image_path, output_dir, layout_model, line_model=None):
    """Segment ``image_path`` using ``layout_model`` and run Tesseract on each
    detected region. Each region ALTO file is written into ``output_dir``.

    Parameters
    ----------
    image_path : str
        Path to the source image.
    output_dir : str
        Directory to save region XML files and helper JSON files.
    layout_model : str or onnxruntime.InferenceSession
        Path to the ONNX layout model or a pre-loaded session.
    line_model : unused
        Kept for future expansion.
    Returns
    -------
    str
        Path to the composite ALTO XML generated from all regions.
    """
    os.makedirs(output_dir, exist_ok=True)

    # initialise sessions
    if isinstance(layout_model, str):
        layout_sess = ort.InferenceSession(layout_model)
        layout_input = get_onnx_input_name(onnx.load(layout_model))
    else:
        layout_sess = layout_model
        layout_input = get_onnx_input_name(layout_sess._model)

    img = cv2.imread(image_path)
    crops, boxes = get_layout_predictions(layout_sess, img, layout_input)

    offsets = {}
    boxes_json = {}
    for idx, crop in crops:
        # run tesseract on each crop
        xml = pytesseract.image_to_alto_xml(crop)
        xml_path = os.path.join(output_dir, f"region_{idx}.xml")
        with open(xml_path, "wb") as f:
            f.write(xml)
        x0, y0, x1, y1 = boxes[idx]
        offsets[str(idx)] = [x0, y0]
        boxes_json[str(idx)] = [x0, y0, x1, y1]

    offsets_path = os.path.join(output_dir, "region_offsets.json")
    boxes_path = os.path.join(output_dir, "region_boxes.json")
    with open(offsets_path, "w") as f:
        json.dump(offsets, f)
    with open(boxes_path, "w") as f:
        json.dump(boxes_json, f)

    composite_path = os.path.join(output_dir, "composite.xml")
    merge_alto_region_xmls(
        source_image_path=image_path,
        region_dir=output_dir,
        offsets_file=offsets_path,
        boxes_file=boxes_path,
        output_file=composite_path,
    )
    return composite_path