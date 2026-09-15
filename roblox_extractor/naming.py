from __future__ import annotations

import re

WINDOWS_RESERVED = frozenset({
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
})
ILLEGAL_CHARS = re.compile(r'[\x00-\x1f\\/*?:"<>|]')

MAX_FILENAME_BYTES = 255


def sanitize_filename(name: str, fallback: str = "Unnamed") -> str:
    sanitized = ILLEGAL_CHARS.sub("_", name or "").strip(". ")
    if not sanitized:
        return fallback
    if sanitized.split(".")[0].upper() in WINDOWS_RESERVED:
        sanitized = f"_{sanitized}"
    return sanitized


def fit_to_byte_limit(
    text: str,
    reserved: int = 0,
    limit: int = MAX_FILENAME_BYTES,
) -> str:
    budget = max(limit - reserved, 1)
    encoded = text.encode("utf-8")
    if len(encoded) <= budget:
        return text
    trimmed = encoded[:budget].decode("utf-8", errors="ignore").rstrip(" .")
    return trimmed or "_"


def normalize_source(source: str) -> str:
    if not source:
        return ""
    normalized = source.replace("\r\n", "\n").replace("\r", "\n")
    return normalized if normalized.endswith("\n") else normalized + "\n"
