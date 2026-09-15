from __future__ import annotations

from pathlib import Path
from typing import Optional

from .model import ScriptNode
from .naming import sanitize_filename
from .suffixes import script_suffix


class Planner:
    def __init__(self, ext: str = "luau", rojo_format: bool = True):
        self.ext = ext
        self.rojo_format = rojo_format
        self.planned: list[tuple[ScriptNode, Path]] = []
        self.claimed: set[str] = set()

    def plan_roots(self, roots: list[ScriptNode]) -> list[tuple[ScriptNode, Path]]:
        single_unwrap = len(roots) == 1 and (
            not roots[0].is_script or bool(roots[0].children)
        )
        if single_unwrap:
            self._plan_single_root(roots[0])
        else:
            container = ScriptNode("Folder")
            container.children = list(roots)
            self.plan_tree(container, Path("."))
        return self.planned

    def plan_tree(self, node: ScriptNode, current_dir: Path) -> None:
        for child in node.children:
            child_dir = self._place(child, current_dir)
            if child_dir is not None:
                self.plan_tree(child, child_dir)

    def _plan_single_root(self, root: ScriptNode) -> None:
        base = Path(".")
        if not root.is_script:
            self.plan_tree(root, base)
            return
        if self.rojo_format:
            target = base / script_suffix(root.class_name, root.run_context, self.ext, init=True)
            self.claimed.add(_claim_key(target))
            self.planned.append((root, target))
            self.plan_tree(root, base)
        else:
            suffix = script_suffix(root.class_name, root.run_context, self.ext)
            stem = self._claim(base, sanitize_filename(root.name), suffix=suffix)
            self.planned.append((root, base / f"{stem}{suffix}"))
            self.plan_tree(root, Path(stem))

    def _place(self, node: ScriptNode, directory: Path) -> Optional[Path]:
        has_children = bool(node.children)
        base_name = sanitize_filename(node.name)

        if not node.is_script:
            if not has_children:
                return None
            return directory / self._claim(directory, base_name, needs_dir=True)

        if self.rojo_format and has_children:
            stem = self._claim(directory, base_name, needs_dir=True)
            child_dir = directory / stem
            init_path = child_dir / script_suffix(
                node.class_name, node.run_context, self.ext, init=True
            )
            self.claimed.add(_claim_key(init_path))
            self.planned.append((node, init_path))
            return child_dir

        suffix = script_suffix(node.class_name, node.run_context, self.ext)
        stem = self._claim(directory, base_name, suffix=suffix, needs_dir=has_children)
        self.planned.append((node, directory / f"{stem}{suffix}"))
        return directory / stem if has_children else None

    def _claim(
        self,
        directory: Path,
        base_name: str,
        *,
        suffix: Optional[str] = None,
        needs_dir: bool = False,
    ) -> str:
        index = 1
        while True:
            stem = base_name if index == 1 else f"{base_name}_{index}"
            keys = []
            if suffix is not None:
                keys.append(_claim_key(directory / f"{stem}{suffix}"))
            if needs_dir:
                keys.append(_claim_key(directory / stem))
            if not any(key in self.claimed for key in keys):
                self.claimed.update(keys)
                return stem
            index += 1


def _claim_key(path: Path) -> str:
    return str(path).lower()
