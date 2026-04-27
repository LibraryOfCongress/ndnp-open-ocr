"""Shared ALTO XML constants and utilities."""

from collections import defaultdict
from xml.etree import ElementTree as ET

NS_ALTO = "http://www.loc.gov/standards/alto/ns-v3#"
NS_XSI = "http://www.w3.org/2001/XMLSchema-instance"


def renumber_alto_ids(root: ET.Element, ns_uri: str) -> None:
    """Assign sequential, unique IDs to all ALTO block/line/string elements
    in column-major reading order.

    Must be called any time new elements are added to the tree
    (e.g. after region merging or gap filling).
    """
    # Column tolerance: elements within ~6% of page width are treated as the
    # same column for sort purposes. Floor at 100 px so small/missing pages
    # still sort sensibly.
    page = root.find(f".//{{{ns_uri}}}Page")
    page_w = int(float(page.get("WIDTH", 0))) if page is not None else 0
    x_tol = max(int(page_w * 0.06), 100)

    id_specs = [
        (f"{{{ns_uri}}}ComposedBlock",     "cblock"),
        (f"{{{ns_uri}}}TextBlock",         "block"),
        (f"{{{ns_uri}}}TextLine",          "line"),
        (f"{{{ns_uri}}}String",            "string"),
        (f"{{{ns_uri}}}Illustration",      "cblock"),
        (f"{{{ns_uri}}}GraphicalElement",  "cblock"),
    ]

    prefix_to_elems: dict[str, list[ET.Element]] = defaultdict(list)
    for tag, prefix in id_specs:
        prefix_to_elems[prefix].extend(root.findall(f".//{tag}"))

    for prefix, elems in prefix_to_elems.items():
        elems.sort(key=lambda el: (
            int(float(el.attrib.get("HPOS", 0))) // x_tol,
            int(float(el.attrib.get("VPOS", 0))),
            int(float(el.attrib.get("HPOS", 0))),
        ))
        for i, el in enumerate(elems):
            el.set("ID", f"{prefix}_{i}")
