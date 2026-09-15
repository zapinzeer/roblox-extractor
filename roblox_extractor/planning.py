from __future__ import annotations

from pathlib import Path

from .model import ScriptNode
from .naming import sanitize_filename
from .suffixes import script_suffix


class Planner:
    def __init__(self, ext: str = "luau", rojo_format: bool = True):
        self.ext = ext
        self.rojo_format = rojo_format
        self.planned: list[tuple[ScriptNode, Path]] = []
        self.registered_paths: set[Path] = set()

    def plan_tree(self, node: ScriptNode, current_dir: Path) -> None:
        used_names: set[str] = set()
        for child in node.children:
            raw_name = sanitize_filename(child.name)
            candidate = raw_name
            idx = 2
            while candidate.lower() in used_names:
                candidate = f"{raw_name}_{idx}"
                idx += 1
            used_names.add(candidate.lower())

            has_children = bool(child.children)

            if child.is_script:
                if self.rojo_format and has_children:
                    target = current_dir / candidate / script_suffix(child.class_name, child.run_context, self.ext, init=True)
                    while target in self.registered_paths:
                        candidate = f"{candidate}_{idx}"
                        target = current_dir / candidate / script_suffix(child.class_name, child.run_context, self.ext, init=True)
                    self.registered_paths.add(target)
                    self.planned.append((child, target))
                    self.plan_tree(child, target.parent)
                else:
                    file_ext = script_suffix(child.class_name, child.run_context, self.ext)
                    target = current_dir / f"{candidate}{file_ext}"
                    while target in self.registered_paths:
                        candidate = f"{candidate}_{idx}"
                        target = current_dir / f"{candidate}{file_ext}"
                    self.registered_paths.add(target)
                    self.planned.append((child, target))
                    if has_children:
                        self.plan_tree(child, current_dir / candidate)
            else:
                self.plan_tree(child, current_dir / candidate)

    def plan_roots(self, roots: list[ScriptNode]) -> list[tuple[ScriptNode, Path]]:
        single_unwrap = len(roots) == 1 and (
            not roots[0].is_script or bool(roots[0].children)
        )
        if single_unwrap:
            self._plan_single_root(roots[0])
        else:
            for r in roots:
                self._plan_root(r)
        return self.planned

    def _plan_single_root(self, root: ScriptNode) -> None:
        if not root.is_script:
            self.plan_tree(root, Path("."))
            return
        if self.rojo_format:
            target = Path(script_suffix(root.class_name, root.run_context, self.ext, init=True))
            self.planned.append((root, target))
            self.registered_paths.add(target)
            self.plan_tree(root, Path("."))
        else:
            name = sanitize_filename(root.name)
            target = Path(f"{name}{script_suffix(root.class_name, root.run_context, self.ext)}")
            self.planned.append((root, target))
            self.registered_paths.add(target)
            self.plan_tree(root, Path(name))

    def _plan_root(self, root: ScriptNode) -> None:
        r_name = sanitize_filename(root.name)
        has_children = bool(root.children)
        if not root.is_script:
            self.plan_tree(root, Path(r_name))
            return
        if self.rojo_format and has_children:
            target = Path(r_name) / script_suffix(root.class_name, root.run_context, self.ext, init=True)
            self.planned.append((root, target))
            self.registered_paths.add(target)
            self.plan_tree(root, target.parent)
        else:
            target = Path(f"{r_name}{script_suffix(root.class_name, root.run_context, self.ext)}")
            self.planned.append((root, target))
            self.registered_paths.add(target)
            if has_children:
                self.plan_tree(root, Path(r_name))
