from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from .errors import BinaryFormatError, ExtractorError
from .model import ScriptNode, RunContext
from .naming import sanitize_filename


def get_item_name(item: ET.Element) -> str:
    props = item.find("Properties")
    if props is not None:
        name_tag = props.find("string[@name='Name']")
        if name_tag is not None and name_tag.text:
            cleaned = name_tag.text.strip()
            if cleaned:
                return sanitize_filename(cleaned)
    return f"Unnamed_{item.attrib.get('class', 'Item')}"


def parse_rbx_xml(file_path: Path) -> list[ScriptNode]:
    if not file_path.is_file():
        raise ExtractorError(f"File not found: {file_path}")

    try:
        with open(file_path, "rb") as f:
            if f.read(16).startswith(b"<roblox!"):
                raise BinaryFormatError(
                    f"'{file_path.name}' is a binary Roblox file (.rbxm/.rbxl). "
                    "Re-save it from Studio as .rbxmx or .rbxlx (XML)."
                )
    except OSError as exc:
        raise ExtractorError(f"Could not read '{file_path}': {exc}") from exc

    stack: list[ScriptNode] = []
    roots: list[ScriptNode] = []

    try:
        with open(file_path, "rb") as f:
            ctx = ET.iterparse(f, events=("start", "end"))
            _, root_elem = next(ctx)
            for ev, el in ctx:
                if ev == "start" and el.tag == "Item":
                    node = ScriptNode(el.attrib.get("class", "Item"))
                    if stack:
                        stack[-1].children.append(node)
                    else:
                        roots.append(node)
                    stack.append(node)
                elif ev == "end":
                    if el.tag == "Item":
                        if stack:
                            curr = stack.pop()
                            if not curr.is_script and not curr.children:
                                if stack:
                                    stack[-1].children.pop()
                                elif roots and roots[-1] is curr:
                                    roots.pop()
                            el.clear()
                            if not stack:
                                root_elem.clear()
                    elif el.tag == "Properties" and stack:
                        curr = stack[-1]
                        for p in el:
                            pname = p.attrib.get("name")
                            if pname == "Name" and p.text:
                                curr.name = p.text.strip() or curr.name
                            elif pname == "Source" and curr.is_script:
                                curr.source = p.text or ""
                            elif pname == "RunContext" and curr.is_script:
                                curr.run_context = RunContext.from_xml(p.text)
    except ET.ParseError as exc:
        raise ExtractorError(f"'{file_path.name}' is not valid XML: {exc}") from exc
    except OSError as exc:
        raise ExtractorError(f"Could not read '{file_path}': {exc}") from exc

    return roots
