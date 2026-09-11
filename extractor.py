from __future__ import annotations

import argparse
import enum
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional, Union

WINDOWS_RESERVED = frozenset({
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
})
ILLEGAL_CHARS = re.compile(r'[\x00-\x1f\\/*?:"<>|]')
SCRIPT_CLASSES = frozenset({"Script", "LocalScript", "ModuleScript"})
TOP_SERVICES = frozenset({
    "Workspace", "Players", "Lighting", "MaterialService", "ReplicatedFirst",
    "ReplicatedStorage", "ServerScriptService", "ServerStorage", "StarterGui",
    "StarterPack", "StarterPlayer", "SoundService", "Chat", "TextChatService"
})

class RunContext(enum.Enum):
    LEGACY = "Legacy"
    SERVER = "Server"
    CLIENT = "Client"
    PLUGIN = "Plugin"

    @classmethod
    def from_xml(cls, val: Optional[str]) -> RunContext:
        token_map = {"0": cls.LEGACY, "1": cls.SERVER, "2": cls.CLIENT, "3": cls.PLUGIN}
        return token_map.get(str(val).strip(), cls.LEGACY)

class ScriptNode:
    __slots__ = ("class_name", "name", "source", "run_context", "children", "is_script")

    def __init__(self, class_name: str):
        self.class_name = class_name
        self.name = class_name
        self.source = ""
        self.run_context = RunContext.LEGACY
        self.children: list[ScriptNode] = []
        self.is_script = class_name in SCRIPT_CLASSES

    def has_script_descendant(self) -> bool:
        for c in self.children:
            if c.is_script or c.has_script_descendant():
                return True
        return False

def sanitize_filename(name: str, fallback: str = "Unnamed") -> str:
    if not name or not any(c not in '\\/*?:"<>| . ' and ord(c) >= 32 for c in name):
        return fallback
    sanitized = ILLEGAL_CHARS.sub("_", name.strip()).strip(". ")[:255].rstrip(". ")
    if not sanitized:
        return fallback
    if sanitized.split(".")[0].upper() in WINDOWS_RESERVED:
        sanitized = f"_{sanitized}"
    return sanitized

def get_item_name(item: ET.Element) -> str:
    props = item.find("Properties")
    if props is not None:
        name_tag = props.find("string[@name='Name']")
        if name_tag is not None and name_tag.text:
            cleaned = name_tag.text.strip()
            if cleaned:
                return sanitize_filename(cleaned)
    return f"Unnamed_{item.attrib.get('class', 'Item')}"

def normalize_source(source: str) -> str:
    if not source:
        return ""
    normalized = source.replace("\r\n", "\n").replace("\r", "\n")
    return normalized if normalized.endswith("\n") else normalized + "\n"

def get_script_ext(class_name: str, run_context: RunContext, ext: str = "luau") -> str:
    ext = ext.lstrip(".")
    if class_name == "Script":
        if run_context == RunContext.CLIENT:
            return f".client.{ext}"
        if run_context == RunContext.PLUGIN:
            return f".plugin.{ext}"
        return f".server.{ext}"
    if class_name == "LocalScript":
        return f".client.{ext}"
    return f".{ext}"

def get_init_filename(class_name: str, run_context: RunContext, ext: str = "luau") -> str:
    ext = ext.lstrip(".")
    if class_name == "Script":
        if run_context == RunContext.CLIENT:
            return f"init.client.{ext}"
        if run_context == RunContext.PLUGIN:
            return f"init.plugin.{ext}"
        return f"init.server.{ext}"
    if class_name == "LocalScript":
        return f"init.client.{ext}"
    return f"init.{ext}"

def parse_rbx_xml(file_path: Path) -> list[ScriptNode]:
    if not file_path.is_file():
        raise FileNotFoundError(f"File not found: {file_path}")

    with open(file_path, "rb") as f:
        if f.read(16).startswith(b"<roblox!"):
            raise ValueError(f"'{file_path.name}' is binary Roblox format (.rbxm/.rbxl), XML expected.")

    stack: list[ScriptNode] = []
    roots: list[ScriptNode] = []

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
    return roots

def extract_luau_scripts(
    rbxmx_path: Union[str, Path],
    output_dir: Optional[Union[str, Path]] = None,
    ext: str = "luau",
    rojo_format: bool = True,
) -> int:
    input_file = Path(rbxmx_path).resolve()
    roots = parse_rbx_xml(input_file)

    if not output_dir:
        is_place = input_file.suffix.lower() == ".rbxlx" or any(r.class_name in TOP_SERVICES for r in roots)
        if is_place or len(roots) != 1:
            base_path = Path(input_file.stem).resolve()
        else:
            base_path = Path(sanitize_filename(roots[0].name, fallback=input_file.stem)).resolve()
    else:
        base_path = Path(output_dir).resolve()

    base_path.mkdir(parents=True, exist_ok=True)
    planned: list[tuple[ScriptNode, Path]] = []
    registered_paths: set[Path] = set()

    def plan_tree(node: ScriptNode, current_dir: Path) -> None:
        used_names: set[str] = set()
        for child in node.children:
            if not (child.is_script or child.has_script_descendant()):
                continue

            raw_name = sanitize_filename(child.name)
            candidate = raw_name
            idx = 2
            while candidate.lower() in used_names:
                candidate = f"{raw_name}_{idx}"
                idx += 1
            used_names.add(candidate.lower())

            has_children = any(c.is_script or c.has_script_descendant() for c in child.children)

            if child.is_script:
                if rojo_format and has_children:
                    target = current_dir / candidate / get_init_filename(child.class_name, child.run_context, ext)
                    while target in registered_paths:
                        candidate = f"{candidate}_{idx}"
                        target = current_dir / candidate / get_init_filename(child.class_name, child.run_context, ext)
                    registered_paths.add(target)
                    planned.append((child, target))
                    plan_tree(child, target.parent)
                else:
                    file_ext = get_script_ext(child.class_name, child.run_context, ext)
                    target = current_dir / f"{candidate}{file_ext}"
                    while target in registered_paths:
                        candidate = f"{candidate}_{idx}"
                        target = current_dir / f"{candidate}{file_ext}"
                    registered_paths.add(target)
                    planned.append((child, target))
                    if has_children:
                        plan_tree(child, current_dir / candidate)
            else:
                plan_tree(child, current_dir / candidate)

    single_unwrap = len(roots) == 1 and (not roots[0].is_script or any(c.is_script or c.has_script_descendant() for c in roots[0].children))
    if single_unwrap:
        root = roots[0]
        if root.is_script:
            if rojo_format:
                target = Path(get_init_filename(root.class_name, root.run_context, ext))
                planned.append((root, target))
                registered_paths.add(target)
                plan_tree(root, Path("."))
            else:
                target = Path(f"{sanitize_filename(root.name)}{get_script_ext(root.class_name, root.run_context, ext)}")
                planned.append((root, target))
                registered_paths.add(target)
                plan_tree(root, Path(sanitize_filename(root.name)))
        else:
            plan_tree(root, Path("."))
    else:
        for r in roots:
            if not (r.is_script or r.has_script_descendant()):
                continue
            r_name = sanitize_filename(r.name)
            has_children = any(c.is_script or c.has_script_descendant() for c in r.children)
            if r.is_script:
                if rojo_format and has_children:
                    target = Path(r_name) / get_init_filename(r.class_name, r.run_context, ext)
                    planned.append((r, target))
                    registered_paths.add(target)
                    plan_tree(r, target.parent)
                else:
                    target = Path(f"{r_name}{get_script_ext(r.class_name, r.run_context, ext)}")
                    planned.append((r, target))
                    registered_paths.add(target)
                    if has_children:
                        plan_tree(r, Path(r_name))
            else:
                plan_tree(r, Path(r_name))

    for node, rel_path in planned:
        dest = base_path / rel_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        with open(dest, "w", encoding="utf-8", newline="\n") as f:
            f.write(normalize_source(node.source))

    return len(planned)

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("file", nargs="?", default=None)
    parser.add_argument("-i", "--input", dest="input_flag", default=None)
    parser.add_argument("-o", "--output", default=None)
    parser.add_argument("--ext", default="luau", choices=["luau", "lua"])
    parser.add_argument("--standard", action="store_true")
    args = parser.parse_args()

    target = args.file or args.input_flag
    if not target:
        try:
            target = input().strip().strip('"').strip("'")
            if not target:
                sys.exit(0)
        except (KeyboardInterrupt, EOFError):
            sys.exit(0)

    try:
        extract_luau_scripts(target, args.output, ext=args.ext, rojo_format=not args.standard)
    except Exception:
        sys.exit(1)

if __name__ == "__main__":
    main()
