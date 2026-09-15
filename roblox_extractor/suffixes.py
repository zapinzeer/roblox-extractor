from __future__ import annotations

from .model import RunContext


def script_suffix(
    class_name: str,
    run_context: RunContext,
    ext: str = "luau",
    *,
    init: bool = False,
) -> str:
    ext = ext.lstrip(".")
    if class_name == "Script":
        if run_context is RunContext.CLIENT:
            kind = "client"
        elif run_context is RunContext.PLUGIN:
            kind = "plugin"
        else:
            kind = "server"
    elif class_name == "LocalScript":
        kind = "client"
    else:
        kind = None

    suffix = "." + ".".join(part for part in (kind, ext) if part)
    return f"init{suffix}" if init else suffix
