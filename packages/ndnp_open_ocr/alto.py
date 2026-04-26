"""Shared ALTO XML constants and utilities."""

from collections import defaultdict
from xml.etree import ElementTree as ET

NS_ALTO = "http://www.loc.gov/standards/alto/ns-v3#"
NS_XSI = "http://www.w3.org/2001/XMLSchema-instance"


def renumber_alto_ids(root: ET.Element, ns_uri: str) -> None:
    """Assign sequential, unique IDs to all ALTO block/line/string elements.

    Must be called any time new elements are added to the tree
    (e.g. after region merging or gap filling).
    """
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
        for i, el in enumerate(elems):
            el.set("ID", f"{prefix}_{i}")
