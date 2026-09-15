from __future__ import annotations

import argparse
import sys
from typing import Optional, Sequence

from .errors import ExtractorError
from .extraction import extract_luau_scripts


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("file", nargs="?", default=None)
    parser.add_argument("-i", "--input", dest="input_flag", default=None)
    parser.add_argument("-o", "--output", default=None)
    parser.add_argument("--ext", default="luau", choices=["luau", "lua"])
    parser.add_argument("--standard", action="store_true")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)

    target = args.file or args.input_flag
    if not target:
        try:
            target = input().strip().strip('"').strip("'")
        except (KeyboardInterrupt, EOFError):
            return 1
        if not target:
            return 1

    try:
        extract_luau_scripts(target, args.output, ext=args.ext, rojo_format=not args.standard)
    except ExtractorError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    return 0
