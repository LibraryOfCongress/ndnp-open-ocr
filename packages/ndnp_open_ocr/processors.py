from bs4 import NavigableString, BeautifulSoup, Tag
import exiftool
import subprocess
import os
import shutil
import pikepdf
import pytesseract
from pytesseract import TesseractError
import datetime
import cv2
from enum import Enum
from xml.etree import ElementTree as ET
import logging
from datetime import datetime
import re
from tempfile import NamedTemporaryFile
import xml.sax.saxutils as saxutils
from ndnp_open_ocr.alto import renumber_alto_ids
from ndnp_open_ocr.segmenter import segment_page, merge_alto_region_xmls
from PIL import Image
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from PIL import Image, ImageDraw
from collections import defaultdict
from statistics import median
import copy

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

PASS1_PSM3_REGION_CLASSES = {"cartoon_or_advertisement", "photograph"}

# Gap filling helpers
def detect_alto_ns(tree: ET.ElementTree) -> dict:
    root = tree.getroot()
    if root.tag.startswith("{") and "}alto" in root.tag:
        ns = root.tag.split("}")[0].strip("{")
    else:
        ns = "http://www.loc.gov/standards/alto/ns-v3#"
    return {"alto": ns}

def get_page(tree: ET.ElementTree, NS: dict) -> ET.Element:
    page = tree.find(".//alto:Page", NS)
    if page is None:
        raise RuntimeError("No <alto:Page> element found.")
    return page

def boxes_intersect(a: tuple, b: tuple, eps: int = 0) -> bool:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    return not (ax2 <= bx1 + eps or bx2 <= ax1 + eps or ay2 <= by1 + eps or by2 <= ay1 + eps)

def subtract_boxes(minuend: list, subtrahend: list, eps: int = 0) -> list:
    if not subtrahend:
        return list(minuend)
    return [b for b in minuend if not any(boxes_intersect(b, s, eps) for s in subtrahend)]

def _compute_scalers(tree: ET.ElementTree, img: Image.Image, NS: dict):
    dpi = img.info.get("dpi", (300, 300))[0]
    mu_el = tree.find(".//alto:MeasurementUnit", NS)
    mu = (mu_el.text if mu_el is not None else "pixel").lower()
    k = 1.0 if mu == "pixel" else (dpi / 1200.0 if mu == "inch1200" else 1.0)
    page = get_page(tree, NS)
    alto_w = float(page.get("WIDTH", 0)) * k
    alto_h = float(page.get("HEIGHT", 0)) * k
    sx = img.width / alto_w if alto_w else 1.0
    sy = img.height / alto_h if alto_h else 1.0
    return k, sx, sy

def _to_px(v: str, k: float, s: float) -> int:
    try:
        return int(round(float(v) * k * s))
    except Exception:
        return 0

def iter_strings_with_pixel_boxes(tree: ET.ElementTree, img: Image.Image, NS: dict):
    k, sx, sy = _compute_scalers(tree, img, NS)
    for line in tree.findall(".//alto:TextLine", NS):
        for child in list(line):
            if child.tag.endswith("String"):
                x = _to_px(child.get("HPOS", "0"), k, sx)
                y = _to_px(child.get("VPOS", "0"), k, sy)
                w = _to_px(child.get("WIDTH", "0"), k, sx)
                h = _to_px(child.get("HEIGHT", "0"), k, sy)
                yield child, line, (x, y, x + w, y + h)

def load_tesseract_strings(alto_path: str, img: Image.Image) -> list:
    tree = ET.parse(alto_path)
    NS = detect_alto_ns(tree)
    out = []
    for _el, _parent, px in iter_strings_with_pixel_boxes(tree, img, NS):
        out.append(px)
    return out

def build_gap_alto_from_full(full_tess_tree: ET.ElementTree, full_NS: dict, img: Image.Image, composite_boxes_px: list, eps_touch: int) -> tuple:
    items = list(iter_strings_with_pixel_boxes(full_tess_tree, img, full_NS))
    num_full_strings = len(items)

    keep_flags = []
    for el, parent, px in items:
        intersects = any(boxes_intersect(px, b, eps_touch) for b in composite_boxes_px)
        keep_flags.append(not intersects)

    keep_set = {id(items[i][0]) for i, k in enumerate(keep_flags) if k}
    num_kept = len(keep_set)
    num_removed = num_full_strings - num_kept

    for line in full_tess_tree.findall(".//alto:TextLine", full_NS):
        for child in list(line):
            if child.tag.endswith("String"):
                if id(child) not in keep_set:
                    line.remove(child)
            elif child.tag.endswith("SP"):
                line.remove(child)

    for block in full_tess_tree.findall(".//alto:TextBlock", full_NS):
        for line in list(block):
            if len(line.findall("alto:String", full_NS)) == 0:
                block.remove(line)

    for ps in full_tess_tree.findall(".//alto:PrintSpace", full_NS):
        for block in list(ps):
            if len(block.findall("alto:TextLine", full_NS)) == 0:
                ps.remove(block)

    for cb in full_tess_tree.findall(".//alto:ComposedBlock", full_NS):
        for block in list(cb):
            if len(block.findall("alto:TextLine", full_NS)) == 0:
                cb.remove(block)

    k, sx, sy = _compute_scalers(full_tess_tree, img, full_NS)
    for string in full_tess_tree.findall(".//alto:String", full_NS):
        x = _to_px(string.get("HPOS", "0"), k, sx)
        y = _to_px(string.get("VPOS", "0"), k, sy)
        w = _to_px(string.get("WIDTH", "0"), k, sx)
        h = _to_px(string.get("HEIGHT", "0"), k, sy)
        string.set("HPOS", str(x))
        string.set("VPOS", str(y))
        string.set("WIDTH", str(w))
        string.set("HEIGHT", str(h))

    root = full_tess_tree.getroot()
    mu_el = full_tess_tree.find(".//alto:MeasurementUnit", full_NS)
    if mu_el is None:
        desc = full_tess_tree.find(".//alto:Description", full_NS)
        if desc is None:
            desc = ET.Element(f"{{{full_NS['alto']}}}Description")
            if len(root) >= 1:
                root.insert(1, desc)
            else:
                root.append(desc)
        mu_el = ET.SubElement(desc, f"{{{full_NS['alto']}}}MeasurementUnit")
    mu_el.text = "pixel"

    page = get_page(full_tess_tree, full_NS)
    page.set("WIDTH", str(img.width))
    page.set("HEIGHT", str(img.height))

    return full_tess_tree, num_full_strings, num_removed, num_kept

class AltoProcessor:
    """Class for postprocessing the ALTO files generated by Tesseract and making them
    compliant with NDNP specificiations."""

    def __init__(self, input_file):
        self.input_file = input_file
        with open(input_file, "r") as f:
            content = f.read()
        self.soup = BeautifulSoup(content, "lxml-xml")

    def fill_gaps(self, full_alto_path, image_path, eps_touch=10):
        # Simple & explicit: compute gaps = full_strings - composite_strings (pixel space),
        # then append each GAP TextLine into the nearest overlapping composite TextBlock.
        # Adds lots of prints so you can see what's happening.
        composite_path = self.input_file
        logger.info(f"[fill_gaps] composite_path={composite_path}")
        logger.info(f"[fill_gaps] full_alto_path={full_alto_path}")
        logger.info(f"[fill_gaps] image_path={image_path}")

        img = Image.open(image_path).convert("RGB")
        composite_tree = ET.parse(composite_path)
        NS = detect_alto_ns(composite_tree)
        full_tree = ET.parse(full_alto_path)
        full_NS = detect_alto_ns(full_tree)

        # Force composite page size to image size to match notebook scaling
        c_page = composite_tree.find(".//alto:Page", NS)
        if c_page is not None:
            c_page.set("WIDTH", str(img.width))
            c_page.set("HEIGHT", str(img.height))

        ps = composite_tree.find(".//alto:PrintSpace", NS)
        if ps is None and c_page is not None:
            ps = ET.SubElement(c_page, f"{{{NS['alto']}}}PrintSpace")

        # Helpers ----------------------------
        def _compute_scalers(tree, img, NS):
            dpi_x = img.info.get("dpi", (300,300))[0]
            mu_el = tree.find(".//alto:MeasurementUnit", NS)
            mu = (mu_el.text if mu_el is not None else "pixel").lower()
            k = 1.0 if mu == "pixel" else (dpi_x / 1200.0 if mu == "inch1200" else 1.0)
            page = tree.find(".//alto:Page", NS)
            alto_w = float(page.get("WIDTH", 0)) * k
            alto_h = float(page.get("HEIGHT", 0)) * k
            sx = img.width  / alto_w if alto_w else 1.0
            sy = img.height / alto_h if alto_h else 1.0
            return k, sx, sy

        def _to_px(v, k, s):
            try: return int(round(float(v) * k * s))
            except: return 0

        def _iter_line_with_boxes(tree, img, NS):
            """Yield (line_element, [(string_el, (x1,y1,x2,y2)), ...], line_bbox) in pixel coords."""
            k, sx, sy = _compute_scalers(tree, img, NS)
            for line in tree.findall(".//alto:TextLine", NS):
                line_strings = []
                for s in line.findall("alto:String", NS):
                    x = _to_px(s.get("HPOS",0), k, sx)
                    y = _to_px(s.get("VPOS",0), k, sy)
                    w = _to_px(s.get("WIDTH",0), k, sx)
                    h = _to_px(s.get("HEIGHT",0), k, sy)
                    line_strings.append((s, (x, y, x+w, y+h)))
                if not line_strings:
                    continue
                xs1 = [b[1][0] for b in line_strings]
                ys1 = [b[1][1] for b in line_strings]
                xs2 = [b[1][2] for b in line_strings]
                ys2 = [b[1][3] for b in line_strings]
                lb = (min(xs1), min(ys1), max(xs2), max(ys2))
                yield line, line_strings, lb

        def _iter_block_bboxes(tree, img, NS):
            """Return list of (block_el, bbox_px) using either its own attrs or union of child lines."""
            k, sx, sy = _compute_scalers(tree, img, NS)
            blocks = tree.findall(".//alto:TextBlock", NS)
            out = []
            for b in blocks:
                if all(b.get(a) is not None for a in ("HPOS","VPOS","WIDTH","HEIGHT")):
                    x = _to_px(b.get("HPOS",0), k, sx)
                    y = _to_px(b.get("VPOS",0), k, sy)
                    w = _to_px(b.get("WIDTH",0), k, sx)
                    h = _to_px(b.get("HEIGHT",0), k, sy)
                    out.append((b, (x,y,x+w,y+h)))
                else:
                    # derive from lines
                    xs1= []; ys1= []; xs2= []; ys2= []
                    for line, _strings, lb in _iter_line_with_boxes(composite_tree, img, NS):
                        parent = line
                        # climb until TextBlock (ElementTree has no parent; skip heavy search for simplicity)
                        # We'll approximate: collect all line bboxes and take overall union, not perfect but ok.
                        xs1.append(lb[0]); ys1.append(lb[1]); xs2.append(lb[2]); ys2.append(lb[3])
                    if xs1:
                        out.append((b, (min(xs1), min(ys1), max(xs2), max(ys2))))
            return out

        def _intersect(a,b,eps=0):
            ax1, ay1, ax2, ay2 = a; bx1, by1, bx2, by2 = b
            return not (ax2 <= bx1+eps or bx2 <= ax1+eps or ay2 <= by1+eps or by2 <= ay1+eps)

        # Composite string boxes for subtraction
        comp_string_boxes = []
        comp_line_boxes = []
        for _line, line_strings, lb in _iter_line_with_boxes(composite_tree, img, NS):
            for _s_el, box in line_strings:
                comp_string_boxes.append(box)
            comp_line_boxes.append(lb)

        # Expand composite boxes slightly to erase narrow gutters between adjacent segments
        # This prevents tiny slivers from being considered gaps and reduces column bleed.
        page = get_page(composite_tree, NS)
        page_w = int(float(page.get("WIDTH", 0))) if page is not None else img.width
        page_h = int(float(page.get("HEIGHT", 0))) if page is not None else img.height
        # margin ~0.3% of page width, at least 10px or 0.6× median text height
        comp_heights = [b[3] - b[1] for b in comp_string_boxes if b[3] > b[1]]
        typical_h = int(median(comp_heights)) if comp_heights else 0
        margin = max(10, int(page_w * 0.003), int(typical_h * 0.6))
        logger.info(f"[fill_gaps] margin_px={margin} typical_text_h={typical_h}")

        def _expand(b, m):
            x1,y1,x2,y2 = b
            return (max(0, x1-m), max(0, y1-m), min(page_w, x2+m), min(page_h, y2+m))

        comp_boxes_expanded = [_expand(b, margin) for b in comp_string_boxes]

        # Full lines & strings
        full_lines = list(_iter_line_with_boxes(full_tree, img, full_NS))
        total_full_strings = sum(len(ls) for _l, ls, _lb in full_lines)

        # Determine kept (gap) strings by line
        # With clean segmentation (IOU=0.10 + containment filter), we only need basic
        # geometric intersection check. The segmenter handles overlap/nesting upstream.
        kept_by_line = {}
        kept_count = 0
        for line, line_strings, lb in full_lines:
            kept = []
            for s, box in line_strings:
                # Keep strings that don't intersect with expanded composite boxes
                if any(_intersect(box, cb, eps_touch) for cb in comp_boxes_expanded):
                    continue
                kept.append((s, box))
            # If this looks like a narrow gutter between two composite lines, drop it entirely
            if kept:
                y1, y2 = lb[1], lb[3]
                # gather composite line boxes that vertically overlap
                overl = [b for b in comp_line_boxes if not (b[3] <= y1 or y2 <= b[1])]
                left_edges = [b[2] for b in overl if b[2] <= lb[0]]
                right_edges = [b[0] for b in overl if b[0] >= lb[2]]
                if left_edges and right_edges:
                    left_edge = max(left_edges)
                    right_edge = min(right_edges)
                    gap_span = right_edge - left_edge
                    # strict minimum gutter width to consider as real gap
                    strict_min_gap = max(18, int(page_w * 0.004))
                    if gap_span <= strict_min_gap:
                        kept = []  # suppress narrow-gutter line

            if kept:
                kept_by_line[line] = (lb, kept)
                kept_count += len(kept)

        logger.info(f"[fill_gaps] composite_strings={len(comp_string_boxes)} full_strings={total_full_strings} kept_gap_strings={kept_count}")

        if kept_count == 0:
            composite_tree.write(composite_path, encoding="utf-8", xml_declaration=True)
            with open(composite_path, "r") as f:
                self.soup = BeautifulSoup(f.read(), "lxml-xml")
            logger.info("[fill_gaps] No gaps to merge; saved unchanged.")
            return

        # Build block index for placement (more accurate per-block bbox)
        def _block_bbox(tree, block_el):
            k, sx, sy = _compute_scalers(tree, img, NS)
            if all(block_el.get(a) is not None for a in ("HPOS","VPOS","WIDTH","HEIGHT")):
                x = _to_px(block_el.get("HPOS",0), k, sx)
                y = _to_px(block_el.get("VPOS",0), k, sy)
                w = _to_px(block_el.get("WIDTH",0), k, sx)
                h = _to_px(block_el.get("HEIGHT",0), k, sy)
                return (x, y, x+w, y+h)
            xs1=[]; ys1=[]; xs2=[]; ys2=[]
            for line in block_el.findall("alto:TextLine", NS):
                line_strings = []
                for s in line.findall("alto:String", NS):
                    x = _to_px(s.get("HPOS",0), k, sx)
                    y = _to_px(s.get("VPOS",0), k, sy)
                    w = _to_px(s.get("WIDTH",0), k, sx)
                    h = _to_px(s.get("HEIGHT",0), k, sy)
                    line_strings.append((x,y,x+w,y+h))
                if not line_strings:
                    continue
                xs1.append(min(b[0] for b in line_strings))
                ys1.append(min(b[1] for b in line_strings))
                xs2.append(max(b[2] for b in line_strings))
                ys2.append(max(b[3] for b in line_strings))
            if xs1:
                return (min(xs1), min(ys1), max(xs2), max(ys2))
            return None

        block_index = []
        for b in composite_tree.findall(".//alto:TextBlock", NS):
            bb = _block_bbox(composite_tree, b)
            if bb is not None:
                block_index.append((b, bb))
        logger.info(f"[fill_gaps] composite TextBlocks={len(block_index)} (for placement)")

        # distance helper for nearest-block selection when no overlap
        def _rect_distance(a,b):
            ax1, ay1, ax2, ay2 = a; bx1, by1, bx2, by2 = b
            dx = 0 if (ax1 <= bx2 and bx1 <= ax2) else (bx1 - ax2 if bx1 > ax2 else ax1 - bx2)
            dy = 0 if (ay1 <= by2 and by1 <= ay2) else (by1 - ay2 if by1 > ay2 else ay1 - by2)
            return dx*dx + dy*dy

        # Add lines: try to append to an overlapping block; else nearest; else create positioned TextBlock
        fallback_block = None  # lazily created when needed
        appended_lines = 0
        appended_strings = 0

        for src_line, (lb, strings) in kept_by_line.items():
            target_block = None
            for b_el, bb in block_index:
                if _intersect(lb, bb, eps_touch):
                    target_block = b_el
                    break
            if target_block is None and block_index:
                target_block = min(block_index, key=lambda t: _rect_distance(lb, t[1]))[0]
            if target_block is None:
                if fallback_block is None:
                    x1,y1,x2,y2 = lb
                    fallback_block = ET.SubElement(ps, f"{{{NS['alto']}}}TextBlock", {
                        "ID":"gap_block",
                        "HPOS": str(x1),
                        "VPOS": str(y1),
                        "WIDTH": str(max(1, x2 - x1)),
                        "HEIGHT": str(max(1, y2 - y1)),
                    })
                target_block = fallback_block

            # Create a new TextLine under target_block
            x1,y1,x2,y2 = lb
            line_attrs = {"HPOS":str(x1), "VPOS":str(y1), "WIDTH":str(x2-x1), "HEIGHT":str(y2-y1)}
            new_line = ET.SubElement(target_block, f"{{{NS['alto']}}}TextLine", line_attrs)

            for s,(sx1,sy1,sx2,sy2) in strings:
                s_attrs = {"HPOS":str(sx1), "VPOS":str(sy1), "WIDTH":str(sx2-sx1), "HEIGHT":str(sy2-sy1)}
                for k in ("CONTENT","SUBS_CONTENT","SUBS_TYPE"):
                    v = s.get(k)
                    if v is not None:
                        s_attrs[k] = v
                ET.SubElement(new_line, f"{{{NS['alto']}}}String", s_attrs)
                appended_strings += 1
            appended_lines += 1

            # Ensure target_block has HPOS/VPOS/WIDTH/HEIGHT and expand to include this line
            try:
                bx = int(target_block.get("HPOS", 0)); by = int(target_block.get("VPOS", 0))
                bw = int(target_block.get("WIDTH", 0)); bh = int(target_block.get("HEIGHT", 0))
            except Exception:
                bx = by = bw = bh = 0
            if bw == 0 or bh == 0:
                target_block.set("HPOS", str(x1))
                target_block.set("VPOS", str(y1))
                target_block.set("WIDTH", str(max(1, x2 - x1)))
                target_block.set("HEIGHT", str(max(1, y2 - y1)))
            else:
                nx1, ny1 = min(bx, x1), min(by, y1)
                nx2, ny2 = max(bx + bw, x2), max(by + bh, y2)
                target_block.set("HPOS", str(nx1))
                target_block.set("VPOS", str(ny1))
                target_block.set("WIDTH", str(max(1, nx2 - nx1)))
                target_block.set("HEIGHT", str(max(1, ny2 - ny1)))

        logger.info(f"[fill_gaps] appended_lines={appended_lines} appended_strings={appended_strings}")

        renumber_alto_ids(composite_tree.getroot(), NS["alto"])

        composite_tree.write(composite_path, encoding="utf-8", xml_declaration=True)
        with open(composite_path, "r") as f:
            self.soup = BeautifulSoup(f.read(), "lxml-xml")
        logger.info("[fill_gaps] Saved updated composite ALTO.")


    def add_description_tags(self):
        """Add NDNP Open OCR description tags to the output ALTO file."""
        description = self.soup.find("Description")

        software_name = "Tesseract Open Source OCR Engine"
        software_version = str(pytesseract.get_tesseract_version())

        ocr_processing = self.soup.find("OCRProcessing")

        # Replace tesseract library/vendor info... with the tags below
        ocr_processing_step = self.soup.find("ocrProcessingStep")
        if ocr_processing_step is not None:
            processing_software = ocr_processing_step.find("processingSoftware")
            if processing_software is not None:
                software_name_tag = processing_software.find("softwareName")
                if software_name_tag is not None:
                    software_name_tag.string = software_name
                else:
                    software_name_tag = self.soup.new_tag("softwareName")
                    software_name_tag.string = software_name
                    processing_software.append(software_name_tag)

                software_version_tag = processing_software.find("softwareVersion")
                if software_version_tag is not None:
                    software_version_tag.string = software_version
                else:
                    software_version_tag = self.soup.new_tag("softwareVersion")
                    software_version_tag.string = software_version
                    processing_software.append(software_version_tag)

        # Add postProcessingStep element and its children
        post_processing_step = self.soup.new_tag("postProcessingStep")
        description.append(post_processing_step)

        processing_date_time = self.soup.new_tag("processingDateTime")
        processing_date_time.string = datetime.now().isoformat()
        post_processing_step.append(processing_date_time)

        processing_agency = self.soup.new_tag("processingAgency")
        processing_agency.string = "Library of Congress"
        post_processing_step.append(processing_agency)

        processing_software = self.soup.new_tag("processingSoftware")
        post_processing_step.append(processing_software)

        software_creator = self.soup.new_tag("softwareCreator")
        software_creator.string = "Library of Congress"
        processing_software.append(software_creator)

        software_name = self.soup.new_tag("softwareName")
        software_name.string = "ndnp-open-ocr"
        processing_software.append(software_name)

        software_version = self.soup.new_tag("softwareVersion")
        software_version.string = "1.2.0"
        processing_software.append(software_version)

        application_description = self.soup.new_tag("applicationDescription")
        application_description.string = (
            "An open-source OCR processing pipeline developed by the Library of "
            "Congress for NDNP data. The pipeline uses advanced segmentation models "
            "and custom post-processing steps to create new NDNP-compliant PDF and "
            "ALTO files."
        )
        processing_software.append(application_description)

        ocr_processing.append(post_processing_step)

    # Convert measurement units to inch1200 from pixels in the ALTO file.
    def convert_pixels_to_inches(self, dpi):
        """
        Update all HEIGHT, WIDTH, HPOS, VPOS attributes in the ALTO (via self.soup)
        by scaling from pixel units at `dpi` to inch1200 units, rounding only once.
        """
        # switch the measurement type in the header
        measurement_unit = self.soup.find("MeasurementUnit")
        measurement_unit.string = "inch1200"

        attributes_to_convert = ["HEIGHT", "WIDTH", "HPOS", "VPOS"]

        def has_required_attrs(element):
            for attr in attributes_to_convert:
                if element.has_attr(attr):
                    return True
            return False

        # walk every relevant tag…
        for element in self.soup.find_all(has_required_attrs):
            for attribute in attributes_to_convert:
                if element.has_attr(attribute):
                    pixel_value = int(element[attribute])
                    inch1200_value = round(float(pixel_value * 1200 / dpi[0]))
                    element[attribute] = str(inch1200_value)

    def add_textblock_language(self, language="eng"):
        """Add a language attribute to each TextBlock in the ALTO file."""
        for block in self.soup.find_all("TextBlock"):
            block["LANG"] = language

    def fix_alto_file_hyphenation(self):
        """Replaces HYP tag with appropriate SUBS_CONTENT tags, per NDNP specs."""
        try:
            soup = self.soup

            # Find all TextLines where the content is equal to "Content"
            text_lines = soup.find_all("TextLine")

            for index, line in enumerate(text_lines):
                hyp_tag = soup.new_tag("HYP", attrs={"CONTENT": "-"})
                strings = line.find_all("String")

                # If there are no strings in this line, then there are no hyphens to fix. Skip this line.
                if len(strings) == 0:
                    continue
                last_string = strings[-1]
                content = last_string.get("CONTENT")

                # Line-to-Line Hyphenation Check: If the last string ends with a hyphen, it means that there is a linebreak and the other portion of the hyphenation is in the next line
                if content.endswith("-") and len(content) > 1 and index + 1 < len(text_lines):
                    next_line = text_lines[index + 1]
                    next_line_string = next_line.find_all("String")[0]

                    # Insert HypTag at end of last_string line
                    line.append(hyp_tag)
                    last_string["CONTENT"] = last_string.get("CONTENT").replace("-", "")
                    combined_word = last_string.get("CONTENT") + next_line_string.get(
                        "CONTENT"
                    )
                    last_string["SUBS_CONTENT"] = combined_word
                    next_line_string["SUBS_CONTENT"] = combined_word
                    last_string["SUBS_TYPE"] = "HypPart1"
                    next_line_string["SUBS_TYPE"] = "HypPart2"
        except Exception as e:
            logger.error(f"ALTO file hyphenation fix failed: {e}")

    def save(self, output_file):
        """Write the whole ALTO XML with 2-space indentation,
        and no line-breaks inside element text values. This is essential for 2 primary reasons: 
        1. XML validation tools will fail if there are special charactersin the text values.
        2. We need the formatting to be consistent with ALTO specifications, which format the headers and body differently.
        """
        def escape_xml_attr(value):
            return saxutils.quoteattr(str(value))

        def escape_xml_text(value):
            return saxutils.escape(str(value))

        def write_tag(node, f, level=0):
            indent = "  " * level

            # build attribute string with escaped values
            attrs = "".join(f' {k}={escape_xml_attr(v)}' for k, v in node.attrs.items())

            # filter out pure-whitespace text nodes
            children = [c for c in node.contents
                        if not (isinstance(c, NavigableString) and not c.strip())]

            # no content → self-close
            if not children:
                f.write(f"{indent}<{node.name}{attrs}/>\n")
                return

            # single text node → inline
            if len(children) == 1 and isinstance(children[0], NavigableString):
                text = escape_xml_text(children[0].strip())
                f.write(f"{indent}<{node.name}{attrs}>{text}</{node.name}>\n")
                return

            # otherwise, open tag, recurse children, close tag
            f.write(f"{indent}<{node.name}{attrs}>\n")
            for c in children:
                if isinstance(c, Tag):
                    write_tag(c, f, level + 1)
                else:  # a NavigableString with real text
                    text = escape_xml_text(c.strip())
                    if text:
                        f.write(f"{indent}  {text}\n")
            f.write(f"{indent}</{node.name}>\n")

        alto = self.soup.find("alto")
        # Ensure default ALTO namespace is present so downstream XPath works
        if alto is not None:
            if 'xmlns' not in alto.attrs:
                alto.attrs['xmlns'] = 'http://www.loc.gov/standards/alto/ns-v3#'
            if 'xmlns:xsi' not in alto.attrs:
                alto.attrs['xmlns:xsi'] = 'http://www.w3.org/2001/XMLSchema-instance'
            if 'xsi:schemaLocation' not in alto.attrs:
                alto.attrs['xsi:schemaLocation'] = (
                    'http://www.loc.gov/standards/alto/ns-v3# '
                    'http://www.loc.gov/alto/v3/alto-3-0.xsd'
                )
        with open(output_file, "w", encoding="utf-8") as f:
            f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
            write_tag(alto, f)


class PDFProcessor:
    """Responsible for postprocessing the PDFs that are generated by
    Tesseract as part of the NDNP Open OCR pipeline."""

    def __init__(self, old_pdf, new_pdf, postprocessed_pdf):
        self.old_pdf = old_pdf
        self.new_pdf = new_pdf
        self.postprocessed_pdf = postprocessed_pdf

    def transfer_xmp(self):
        """Transfer necessary XMP tags (Description, Title, etc...) from the old PDF to the new PDF that's
        generated by the NDNP Open OCR pipeline."""
        try:
            with exiftool.ExifToolAlpha() as et:

                new_tags = et.get_tags(self.postprocessed_pdf, tags=None)[0]

                et.copy_tags(self.old_pdf, self.postprocessed_pdf)

                old_tags = et.get_tags(self.old_pdf, tags=None)[0]
                metadata = et.get_metadata(self.old_pdf)
                logging.info("{} metadata: {}".format(self.old_pdf, metadata))

                title_tag = None
                title_key_list = list(
                    filter(lambda x: x.startswith("XMP:Title"), old_tags)
                )
                if len(title_key_list) >= 1:
                    title_tag = old_tags[title_key_list[0]]

                if title_tag:
                    et.set_tags(
                        self.postprocessed_pdf,
                        {"Title": title_tag, "XMP:Title-en": title_tag},
                    )

                description_value = old_tags.get(
                    "XMP:Description-en", old_tags.get("XMP:Description", None)
                )

                logging.info(f"New Tags from PDF: {new_tags}")

            # Use the XMP:Identifier from old_tags if available
            identifier_to_use = old_tags.get("XMP:Identifier", "XMP-dc:Idenfitifer")
            updated_tags = {
                "XMP:CreateDate": new_tags["File:FileModifyDate"][0:14],
                "XMP:ModifyDate": new_tags["File:FileModifyDate"][0:14],
                "PDF:CreateDate": new_tags["File:FileModifyDate"][0:14],
                "PDF:ModifyDate": new_tags["File:FileModifyDate"][0:14],
                "XMP:Creator": "",
                "PDF:Producer": new_tags["PDF:Producer"],
                "XMP:Description": description_value,
                "PDF:Creator": "ndnp-open-ocr",
                "XMP:Author": "",
                "PDF:Subject": "",
                "XMP:Identifier": identifier_to_use,
            }

            et.set_tags(
                self.postprocessed_pdf,
                updated_tags,
            )
        except Exception as e:
            logging.error(
                "Failure transferring XMP data from {} to {}: {}".format(
                    self.old_pdf, self.postprocessed_pdf, e
                )
            )
            return False

    def postprocess_pdf(self):
        """Set resolution, Display type, etc... on final PDF output"""
        current_directory = os.path.dirname(os.path.abspath(__file__))
        pdf_marks_path = os.path.join(current_directory, "pdf_marks.txt")
        args = [
            "gs",
            "-q",
            "-dNOPAUSE",
            "-dBATCH",
            "-dFastWebView=true",
            f"-sOutputFile={self.postprocessed_pdf}",
            "-sDEVICE=pdfwrite",
            "-dDownsampleColorImages=true",
            "-dDownsampleGrayImages=true",
            "-dDownsampleMonoImages=true",
            "-dColorImageResolution=150",
            "-dGrayImageResolution=150",
            "-dMonoImageResolution=150",
            "-dColorImageDownsampleThreshold=1.0",
            "-dGrayImageDownsampleThreshold=1.0",
            "-dMonoImageDownsampleThreshold=1.0",
            "-dProcessDSCComments=false",
            "-dAutoFilterColorImages=false",
            "-dAutoFilterGrayImages=false",
            "-dColorImageFilter=/DCTEncode",
            "-dGrayImageFilter=/DCTEncode",
            self.new_pdf,
            pdf_marks_path,
        ]

        result = subprocess.run(args, check=True)
        logging.info("stdout: %s", result.stdout)
        logging.error("stderr: %s", result.stderr)

        if os.path.isfile(self.new_pdf):
            logging.info("Output file exists and is a regular file: {self.new_pdf}")
        else:
            logging.info("Output file does not exist or is not a regular file.")

    def linearize_pdf(self):
        """Linearize the final output PDF"""
        try:
            with pikepdf.Pdf.open(
                self.postprocessed_pdf, allow_overwriting_input=True
            ) as pdf:
                pdf.save(self.postprocessed_pdf, linearize=True)
        except Exception as e:
            logging.error(f"PDF Linearization failed: {self.postprocessed_pdf} {e}")


class PreprocessingMethod(Enum):
    """Preprocessing options for input image to Tesseract"""

    ADAPTIVE = "adaptive"
    BINARY = "binary"
    OTSU = "otsu"
    ORIGINAL = "original"


class OCRProcessor:
    """Class to run entire OCR processing job on a single file.
    It takes the input_filepath and the output_path in as input, where input_filepath is the
    location of the TIFF file for the issue on the system, and output_path is where you want
    the output directory structure written into (mirroring input structure)."""

    def __init__(
        self,
        input_file_path,
        output_path,
        preprocessing_method=PreprocessingMethod.ORIGINAL,
        use_segmenter=False,
        layout_model=None,
        line_model=None,
        use_gap_filling: bool = True,
        visualize_segmentation: bool = False, 
    ):
        self.input_file_path = input_file_path
        self.input_dir = os.path.dirname(self.input_file_path)
        self.output_path = output_path
        self.full_height = True
        self.preprocessing_method = preprocessing_method
        self.use_segmenter = use_segmenter
        self.use_gap_filling = use_gap_filling
        self.layout_model = layout_model
        self.line_model = line_model
        self.visualize_segmentation = visualize_segmentation 
        self._pixel_alto_path = None

    def _pass1_psm_config(self, region_class_name: str | None) -> str:
        return "--psm 3" if region_class_name in PASS1_PSM3_REGION_CLASSES else "--psm 6"

    def _get_file_name(self):
        return os.path.splitext(os.path.basename(self.input_file_path))[0]

    def _get_new_pdf_path(self):
        """The PDF that is outputted by Tesseract (for files that don't require further preprocessing)"""
        return os.path.join(self.output_path, f"{self._get_file_name()}_new.pdf")

    def get_postprocessed_pdf_path(self):
        """Path to final NDNP Open OCR output PDF"""
        return os.path.join(self.output_path, f"{self._get_file_name()}.pdf")

    def _get_alto_file_path(self):
        return os.path.join(self.output_path, f"{self._get_file_name()}.xml")

    def _get_old_pdf_path(self):
        old_pdf_name = f"{self._get_file_name()}.pdf"
        return os.path.join(self.input_dir, old_pdf_name)

    def _preprocess_image(self):
        """Preprocess the image before it's fed into Tesseract as an input."""

        # Check for JP2 and preprocessing method
        if (
            self.preprocessing_method == PreprocessingMethod.ORIGINAL
            and not self.input_file_path.endswith(".jp2")
        ):
            logging.info("No preprocessing required.")
            return self.input_file_path

        image = cv2.imread(self.input_file_path, cv2.IMREAD_GRAYSCALE)

        # Preprocessing methods
        if self.preprocessing_method == PreprocessingMethod.ADAPTIVE:
            logging.info("PERFORMING ADAPTIVE THRESHOLDING")
            processed_img = cv2.adaptiveThreshold(
                image, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY, 15, 5
            )
            # Denoise the image
            processed_img = cv2.fastNlMeansDenoising(processed_img, None, 40, 9, 21)
        elif self.preprocessing_method == PreprocessingMethod.BINARY:
            _, processed_img = cv2.threshold(image, 127, 255, cv2.THRESH_BINARY)
        elif self.preprocessing_method == PreprocessingMethod.OTSU:
            _, processed_img = cv2.threshold(
                image, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
            )
        else:  # original
            logging.info("USING ORIGINAL IMAGE")
            processed_img = image

        # Write the processed image to a temporary file and return the path
        temp_file_path = self._write_temp_image(processed_img)
        return temp_file_path

    def _write_temp_image(self, image):
        """Write the preprocessed image to a temporary .tif file with lossless compression."""
        temp_file = NamedTemporaryFile(delete=False, suffix=".tif")
        logger.debug("Temporary image file created at %s", temp_file.name)
        cv2.imwrite(temp_file.name, image, [cv2.IMWRITE_TIFF_COMPRESSION, 1])
        return temp_file.name

    def generate_pdf(self):
        """Generate a new OCR PDF, using a given image, with the NDNP Open OCR pipeline. This
        will create a new PDF using Tesseract, with specified preprocessing settings applied to the
        input, then will postprocess the PDF to make it compliant with NDNP specifications for content.
        """
        logging.info("Generating PDF file")

        pixel_alto_path = self._pixel_alto_path or os.path.join(
            self.output_path, f"{self._get_file_name()}_pixel.xml"
        )

        try:
            if os.path.isfile(pixel_alto_path):
                logging.info("Generating PDF from ALTO geometry (%s)", pixel_alto_path)
                self._build_pdf_from_alto(
                    self.input_file_path, pixel_alto_path, self._get_new_pdf_path()
                )
            else:
                logging.info(
                    "Pixel-unit ALTO missing for %s; using direct Tesseract PDF path",
                    self._get_file_name(),
                )
                input_file_path = self._preprocess_image()
                pdf = self._run_tesseract_pdf(input_file_path)
                with open(self._get_new_pdf_path(), "w+b") as f:
                    f.write(pdf)
                del pdf

            # PDF Post-processing
            processor = PDFProcessor(
                self._get_old_pdf_path(),  # original PDF
                self._get_new_pdf_path(),  # new PDF
                self.get_postprocessed_pdf_path(),  # where to save final PDF
            )
            processor.postprocess_pdf()
            processor.transfer_xmp()
            processor.linearize_pdf()

            os.remove(self._get_new_pdf_path())
            # Remove pikePdf .pdf_original file output
            os.remove(self.get_postprocessed_pdf_path().replace(".pdf", ".pdf_original")) 
            logging.info(f"PDF Generation successful: {self._get_file_name()}")
        except Exception as e:
            logging.error(f"PDF generation failed: {self._get_file_name()} {e}")
        finally:
            if self._pixel_alto_path and os.path.isfile(self._pixel_alto_path):
                try:
                    os.remove(self._pixel_alto_path)
                except OSError:
                    pass
                self._pixel_alto_path = None

    def _run_tesseract_pdf(self, input_file_path: str) -> bytes:
        """Run Tesseract to produce a PDF, retrying with a re-encoded image on failure."""
        try:
            return pytesseract.image_to_pdf_or_hocr(input_file_path, extension="pdf")
        except (TesseractError, FileNotFoundError) as err:
            extra = ""
            if isinstance(err, TesseractError):
                extra = f" stderr={getattr(err, 'stderr', '').strip()}"
            logging.warning(
                "Primary Tesseract pass failed for %s (%s)%s; retrying with re-encoded image",
                input_file_path,
                err,
                extra,
            )
            fallback = cv2.imread(self.input_file_path, cv2.IMREAD_GRAYSCALE)
            if fallback is None:
                logging.error(
                    "Failed to load %s for fallback preprocessing; propagating error",
                    self.input_file_path,
                )
                raise
            temp_path = self._write_temp_image(fallback)
            try:
                return pytesseract.image_to_pdf_or_hocr(temp_path, extension="pdf")
            except Exception:
                logging.error(
                    "Fallback Tesseract run also failed for %s", self._get_file_name()
                )
                raise
            finally:
                try:
                    os.remove(temp_path)
                except OSError:
                    pass

   
    
    def _build_pdf_from_alto(
        self, tif_path: str, alto_path: str, out_pdf_path: str
    ) -> None:
        """
        Paint the TIFF on a PDF page and overlay invisible text taken
        directly from the ALTO <String> elements so the file is searchable.
        Works with pixel or inch1200 ALTO coordinates.
        """
        # -- open image and derive geometry --------------------------------
        im = Image.open(tif_path)
        w_px, h_px = im.size
        dpi_x, dpi_y = im.info.get("dpi", (300, 300))
        px2pt = 72.0 / dpi_x  # points per pixel
        w_pt = w_px * px2pt
        h_pt = h_px * px2pt

        # -- prepare PDF canvas --------------------------------------------
        c = canvas.Canvas(out_pdf_path, pagesize=(w_pt, h_pt))
        c.drawInlineImage(im, 0, 0, w_pt, h_pt)

        # -- parse ALTO -----------------------------------------------------
        ns = {"a": "http://www.loc.gov/standards/alto/ns-v3#"}
        doc = ET.parse(alto_path)
        # Handle both namespaced and un-namespaced ALTO
        mu_elem = doc.find(".//a:MeasurementUnit", ns) or doc.find(".//MeasurementUnit")
        mu = mu_elem.text.lower() if mu_elem is not None else "pixel"

        # convert ALTO units to image pixels
        def alto_to_px(val: float) -> float:
            return val if mu == "pixel" else val * dpi_x / 1200.0

        # Gather strings from namespaced and (fallback) non-namespaced docs
        strings = doc.findall(".//a:String", ns)
        if not strings:
            strings = doc.findall(".//String")

        # overlay each <String> as (nearly) invisible text
        # Use a tiny nonzero alpha to avoid some PDF tools removing text rendered with mode 3.
        for s in strings:
            txt = s.get("CONTENT", "")
            if not txt:
                continue

            # get raw ALTO coords & size
            raw_hpos = float(s.get("HPOS", 0))
            raw_vpos = float(s.get("VPOS", 0))
            raw_ht_s = float(s.get("HEIGHT", 0))
            raw_w_s = float(s.get("WIDTH",0))

            # convert to pixels
            hpos_px = alto_to_px(raw_hpos)
            vpos_px = alto_to_px(raw_vpos)
            ht_px_s = alto_to_px(raw_ht_s)
            w_px_s = alto_to_px(raw_w_s)

            # convert to PDF points
            h_pt_s = ht_px_s*px2pt
            w_pt_s = w_px_s*px2pt
            x_pt = hpos_px * px2pt
            # flip Y-axis: PDF origin is bottom-left
            y_pt = (h_px - vpos_px - ht_px_s) * px2pt

            tx = c.beginText()
            # Keep text paintable but extremely faint to survive post-processing
            try:
                c.setFillAlpha(0.01)
            except Exception:
                pass  # older reportlab without transparency
            tx.setFont("Times-Roman", 1)
            tx.setLeading(0)
            tx.setCharSpace(0)
            tx.setWordSpace(0)
            tx.setHorizScale(100)

            # Align PDF text baseline so the font's em-box fits the ALTO box [x_pt,y_pt..+h_pt_s]
            # ReportLab metrics are in 1000-UPM units; descent is negative.
            ascent_u = pdfmetrics.getAscent("Times-Roman") / 1000.0
            descent_u = abs(pdfmetrics.getDescent("Times-Roman") / 1000.0)
            # Place baseline above the rectangle bottom by descent*height so the em bottom aligns to y_pt
            y_baseline = y_pt + descent_u * h_pt_s
            adj_word_width = w_pt_s / pdfmetrics.stringWidth(txt, "Times-Roman", 1.0)
            tx.setTextTransform(adj_word_width, 0, 0, h_pt_s, x_pt, y_baseline)
            tx.textOut(txt) 
            c.drawText(tx)
            try:
                c.setFillAlpha(1.0)
            except Exception:
                pass

        c.showPage()
        c.save()

    def generate_alto(self):
        """Generate a new OCR ALTO file, using a given image, with the NDNP Open OCR pipeline. This
        will create a new ALTO using Tesseract, with specified preprocessing settings applied to the
        input, then will postprocess the ALTO to fix hyphenation, units, etc...
        """
        try:
            logging.info("Generating ALTO file")
            logger.info("Input file path: %s", self.input_file_path)
            full_alto_path = None
            self._pixel_alto_path = None

            if self.use_segmenter:
                logging.info("Segmentation mode enabled")
                logger.debug("Segmenting page into regions")
                regions_dir = os.path.join(
                    self.output_path, f"{self._get_file_name()}_regions"
                )
                os.makedirs(regions_dir, exist_ok=True)
                logger.debug("Regions directory created: %s", regions_dir)

                if self.use_gap_filling:
                    full_alto_path = os.path.join(self.output_path, f"{self._get_file_name()}_full.xml")
                    xml = pytesseract.image_to_alto_xml(self.input_file_path)
                    with open(full_alto_path, "wb") as f:
                        f.write(xml)

                # segment_page returns (crops, boxes, width, height)
                # Keep names explicit to avoid confusion downstream.
                crops, boxes, page_w, page_h = segment_page(self.input_file_path)

                logging.info("Detected %d regions", len(crops))
                boxes_dict = {}

                for idx, (rid, crop, class_id, class_name) in enumerate(crops):
                    logging.debug("OCRing region %s (%s:%s)", rid, class_id, class_name)
                    # Use the AmericanStories region class directly. Text-like
                    # classes stay on PSM 6; photograph/advertisement classes
                    # switch to PSM 3 for a safer first OCR pass.
                    psm_config = self._pass1_psm_config(class_name)
                    logging.debug(
                        "Region %s (%s) selected Pass 1 config %s",
                        rid,
                        class_name,
                        psm_config,
                    )
                    xml = pytesseract.image_to_alto_xml(crop, config=psm_config)
                    xml_path = os.path.join(regions_dir, f"region_{rid}.xml")
                    with open(xml_path, "wb") as f:
                        f.write(xml)
                    logging.debug("Wrote region %s ALTO to %s", rid, xml_path)
                    boxes_dict[str(rid)] = list(boxes[idx])

                merge_alto_region_xmls(
                    source_image_path=self.input_file_path,
                    region_dir=regions_dir,
                    boxes_dict=boxes_dict,
                    output_file=self._get_alto_file_path(),
                    image_width=page_w,
                    image_height=page_h,
                )
                logging.info("Composite ALTO written to %s", self._get_alto_file_path())

                # Clean up regions directory once composite ALTO is created
                if os.path.isdir(regions_dir):
                    shutil.rmtree(regions_dir)
            else:
                logging.debug(
                    "Segmentation disabled or utilities missing; using whole image"
                )
                input_file_path = self._preprocess_image()
                xml = pytesseract.image_to_alto_xml(input_file_path)
                pixel_alto_path = os.path.join(
                    self.output_path, f"{self._get_file_name()}_pixel.xml"
                )
                with open(pixel_alto_path, "w+b") as f:
                    f.write(xml)
                shutil.copy(pixel_alto_path, self._get_alto_file_path())
                self._pixel_alto_path = pixel_alto_path

            dpi = (300, 300)

            alto_processor = AltoProcessor(self._get_alto_file_path())
            if self.use_gap_filling and full_alto_path:
                alto_processor.fill_gaps(full_alto_path, self.input_file_path)
            elif self.use_gap_filling:
                logging.warning(
                    "Gap filling requested but no full ALTO available; skipping."
                )

            if full_alto_path and os.path.isfile(full_alto_path):
                os.remove(full_alto_path)

            alto_processor.add_description_tags()
            alto_processor.fix_alto_file_hyphenation()
            alto_processor.add_textblock_language()

            # If using segmenter, save a pixel-unit version of the ALTO *before* unit conversion (for PDF generation in generate_pdf)
            pixel_alto_path = None
            if self.use_segmenter:
                pixel_alto_path = os.path.join(
                    self.output_path, f"{self._get_file_name()}_pixel.xml"
                )
                alto_processor.save(pixel_alto_path)
                self._pixel_alto_path = pixel_alto_path

            # Now convert to inch1200 units
            alto_processor.convert_pixels_to_inches(dpi)
            alto_processor.save(self._get_alto_file_path())

            if self.visualize_segmentation and self.use_segmenter and pixel_alto_path:
                self._visualize_alto_boxes(pixel_alto_path)


            logging.info(f"ALTO Generation successful: {self._get_file_name()}")
        except Exception as e:
            logging.error(f"ALTO generation failed: {self._get_file_name()} {e}")

    def _visualize_alto_boxes(self, pixel_alto_path: str) -> None:
        """Overlay ALTO bounding boxes on the original TIFF and save as PNG for segmentation visualization."""
        try:
            # Load original image
            img = cv2.imread(self.input_file_path)
            if img is None:
                raise FileNotFoundError(f"Cannot load image: {self.input_file_path}")

            # Parse pixel-unit ALTO
            ns = {"a": "http://www.loc.gov/standards/alto/ns-v3#"}
            doc = ET.parse(pixel_alto_path)

            # Draw boxes for TextBlocks (or adjust to other elements like ComposedBlock/TextLine if needed)
            for block in doc.findall(".//a:TextBlock", ns):
                hpos = int(float(block.get("HPOS", 0)))
                vpos = int(float(block.get("VPOS", 0)))
                width = int(float(block.get("WIDTH", 0)))
                height = int(float(block.get("HEIGHT", 0)))
                cv2.rectangle(img, (hpos, vpos), (hpos + width, vpos + height), (0, 255, 0), 2)  # Green boxes

            # Save visualization
            vis_path = os.path.join(self.output_path, f"{self._get_file_name()}_segmentation_vis.png")
            cv2.imwrite(vis_path, img)
            logging.info(f"Segmentation visualization saved to: {vis_path}")

        except Exception as e:
            logging.error(f"Segmentation visualization failed: {e}")





    def process(self):
        """OCR an issue in an NDNP batch, generates a new PDF and ALTO file to replace the originals."""
        self.generate_alto()
        self.generate_pdf()
