from __future__ import annotations

import re

WINDOWS_RESERVED = frozenset({
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
})
ILLEGAL_CHARS = re.compile(r'[\x00-\x1f\\/*?:"<>|]')


def sanitize_filename(name: str, fallback: str = "Unnamed") -> str:
    if not name or not any(c not in '\\/*?:"<>| . ' and ord(c) >= 32 for c in name):
        return fallback
    sanitized = ILLEGAL_CHARS.sub("_", name.strip()).strip(". ")[:255].rstrip(". ")
    if not sanitized:
        return fallback
    if sanitized.split(".")[0].upper() in WINDOWS_RESERVED:
        sanitized = f"_{sanitized}"
    return sanitized


def normalize_source(source: str) -> str:
    if not source:
        return ""
    normalized = source.replace("\r\n", "\n").replace("\r", "\n")
    return normalized if normalized.endswith("\n") else normalized + "\n"
