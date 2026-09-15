from __future__ import annotations

from .model import RunContext


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
