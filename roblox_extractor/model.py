from __future__ import annotations

import enum
from typing import Optional

SCRIPT_CLASSES = frozenset({"Script", "LocalScript", "ModuleScript"})


class RunContext(enum.Enum):
    LEGACY = "Legacy"
    SERVER = "Server"
    CLIENT = "Client"
    PLUGIN = "Plugin"

    @classmethod
    def from_xml(cls, val: Optional[str]) -> "RunContext":
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
