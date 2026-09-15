from __future__ import annotations

from pathlib import Path
from typing import Optional, Union

from .errors import ExtractorError, OutputConflictError
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


def _looks_like_place(input_file: Path, roots: list[ScriptNode]) -> bool:
    return input_file.suffix.lower() == ".rbxlx" or any(
        r.class_name in TOP_SERVICES for r in roots
    )


def resolve_output_dir(
    input_file: Path,
    roots: list[ScriptNode],
    output_dir: Optional[PathLike],
) -> tuple[Path, bool]:
    if output_dir:
        return Path(output_dir).resolve(), False

    fallback = sanitize_filename(input_file.stem, fallback="extracted")
    if _looks_like_place(input_file, roots) or len(roots) != 1:
        return Path(fallback).resolve(), False

    return Path(sanitize_filename(roots[0].name, fallback=fallback)).resolve(), True


def _exists(path: Path) -> bool:
    try:
        return path.exists()
    except OSError:
        return False


def find_conflicts(base_path: Path, planned: list[tuple[ScriptNode, Path]]) -> list[Path]:
    conflicts: list[Path] = []
    seen: set[Path] = set()

    for _, rel_path in planned:
        destination = base_path / rel_path
        if destination not in seen:
            seen.add(destination)
            if _exists(destination):
                conflicts.append(destination)

        for parent in destination.parents:
            if parent == base_path or parent in seen:
                break
            seen.add(parent)
            if _exists(parent) and not parent.is_dir():
                conflicts.append(parent)

    return conflicts


def _describe_conflicts(base_path: Path, conflicts: list[Path], limit: int = 5) -> str:
    shown = "\n".join(f"  {path}" for path in conflicts[:limit])
    if len(conflicts) > limit:
        shown += f"\n  ... and {len(conflicts) - limit} more"
    return (
        f"{len(conflicts)} file(s) in '{base_path}' would be overwritten:\n"
        f"{shown}\n"
        "Pass --force to overwrite them, or -o DIR to write somewhere else."
    )


def extract_luau_scripts(
    rbxmx_path: PathLike,
    output_dir: Optional[PathLike] = None,
    ext: str = "luau",
    rojo_format: bool = True,
    force: bool = False,
    warn: Warn = warn_to_stderr,
) -> ExtractionResult:
    input_file = Path(rbxmx_path).resolve()
    roots = parse_rbx_xml(input_file, warn=warn)

    base_path, unwrap = resolve_output_dir(input_file, roots, output_dir)
    planned = Planner(ext=ext, rojo_format=rojo_format).plan_roots(roots, unwrap=unwrap)
    if not planned:
        return ExtractionResult(base_path, 0)

    if not force:
        conflicts = find_conflicts(base_path, planned)
        if conflicts:
            raise OutputConflictError(_describe_conflicts(base_path, conflicts))

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
