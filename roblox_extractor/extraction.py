from __future__ import annotations

from pathlib import Path
from typing import Optional, Union

from .errors import ExtractorError
from .model import ExtractionResult, ScriptNode
from .naming import normalize_source, sanitize_filename
from .parsing import Warn, parse_rbx_xml, warn_to_stderr
from .planning import Planner

TOP_SERVICES = frozenset({
    "Workspace", "Players", "Lighting", "MaterialService", "ReplicatedFirst",
    "ReplicatedStorage", "ServerScriptService", "ServerStorage", "StarterGui",
    "StarterPack", "StarterPlayer", "SoundService", "Chat", "TextChatService",
})

PathLike = Union[str, Path]


def resolve_output_dir(
    input_file: Path,
    roots: list[ScriptNode],
    output_dir: Optional[PathLike],
) -> Path:
    if output_dir:
        return Path(output_dir).resolve()
    is_place = input_file.suffix.lower() == ".rbxlx" or any(
        r.class_name in TOP_SERVICES for r in roots
    )
    if is_place or len(roots) != 1:
        return Path(input_file.stem).resolve()
    return Path(sanitize_filename(roots[0].name, fallback=input_file.stem)).resolve()


def extract_luau_scripts(
    rbxmx_path: PathLike,
    output_dir: Optional[PathLike] = None,
    ext: str = "luau",
    rojo_format: bool = True,
    warn: Warn = warn_to_stderr,
) -> ExtractionResult:
    input_file = Path(rbxmx_path).resolve()
    roots = parse_rbx_xml(input_file, warn=warn)

    base_path = resolve_output_dir(input_file, roots, output_dir)
    planned = Planner(ext=ext, rojo_format=rojo_format).plan_roots(roots)
    if not planned:
        return ExtractionResult(base_path, 0)

    written = 0
    try:
        base_path.mkdir(parents=True, exist_ok=True)
        for node, rel_path in planned:
            dest = base_path / rel_path
            dest.parent.mkdir(parents=True, exist_ok=True)
            with open(dest, "w", encoding="utf-8", newline="\n") as f:
                f.write(normalize_source(node.source))
            written += 1
    except OSError as exc:
        raise ExtractorError(f"Could not write to '{base_path}': {exc}") from exc

    return ExtractionResult(base_path, written)
