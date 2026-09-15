from __future__ import annotations

import base64
import binascii
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Callable, Sequence

from .errors import BinaryFormatError, ExtractorError
from .model import ScriptNode, RunContext
from .naming import sanitize_filename

TEXT_PROPERTY_TAGS = frozenset({"string", "ProtectedString"})

Warn = Callable[[str], None]


def warn_to_stderr(message: str) -> None:
    print(f"warning: {message}", file=sys.stderr)


def _element_text(element: ET.Element) -> str:
    return "".join(element.itertext())


def _read_properties(
    element: ET.Element,
    node: ScriptNode,
    pending_shared: list[ScriptNode],
) -> None:
    for prop in element:
        prop_name = prop.attrib.get("name")
        if prop_name == "Name" and prop.tag in TEXT_PROPERTY_TAGS:
            text = _element_text(prop).strip()
            if text:
                node.name = text
        elif not node.is_script:
            continue
        elif prop_name == "Source" and prop.tag in TEXT_PROPERTY_TAGS:
            node.source = _element_text(prop)
        elif prop_name == "Source" and prop.tag == "SharedString":
            node.shared_source_key = _element_text(prop).strip()
            pending_shared.append(node)
        elif prop_name == "RunContext":
            node.run_context = RunContext.from_xml(_element_text(prop))


def _resolve_shared_sources(
    pending: Sequence[ScriptNode],
    shared_strings: dict[str, str],
    warn: Warn,
) -> None:
    for node in pending:
        encoded = shared_strings.get(node.shared_source_key or "")
        if encoded is None:
            warn(f"'{node.name}' references an unknown shared string; its source is empty.")
            continue
        try:
            node.source = base64.b64decode(encoded).decode("utf-8", errors="replace")
        except (binascii.Error, ValueError) as exc:
            warn(f"'{node.name}' has an undecodable shared source ({exc}); its source is empty.")


def get_item_name(item: ET.Element) -> str:
    props = item.find("Properties")
    if props is not None:
        name_tag = props.find("string[@name='Name']")
        if name_tag is not None and name_tag.text:
            cleaned = name_tag.text.strip()
            if cleaned:
                return sanitize_filename(cleaned)
    return f"Unnamed_{item.attrib.get('class', 'Item')}"


def parse_rbx_xml(file_path: Path, warn: Warn = warn_to_stderr) -> list[ScriptNode]:
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
    pending_shared: list[ScriptNode] = []
    shared_strings: dict[str, str] = {}

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
                        _read_properties(el, stack[-1], pending_shared)
                    elif el.tag == "SharedString" and "md5" in el.attrib:
                        shared_strings[el.attrib["md5"]] = _element_text(el)
    except ET.ParseError as exc:
        raise ExtractorError(f"'{file_path.name}' is not valid XML: {exc}") from exc
    except OSError as exc:
        raise ExtractorError(f"Could not read '{file_path}': {exc}") from exc

    _resolve_shared_sources(pending_shared, shared_strings, warn)
    return roots
