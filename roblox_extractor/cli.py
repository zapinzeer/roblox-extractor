from __future__ import annotations

import argparse
import sys
from typing import Optional, Sequence

from .extraction import extract_luau_scripts


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("file", nargs="?", default=None)
    parser.add_argument("-i", "--input", dest="input_flag", default=None)
    parser.add_argument("-o", "--output", default=None)
    parser.add_argument("--ext", default="luau", choices=["luau", "lua"])
    parser.add_argument("--standard", action="store_true")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = build_parser().parse_args(argv)

    target = args.file or args.input_flag
    if not target:
        try:
            target = input().strip().strip('"').strip("'")
            if not target:
                sys.exit(0)
        except (KeyboardInterrupt, EOFError):
            sys.exit(0)

    try:
        extract_luau_scripts(target, args.output, ext=args.ext, rojo_format=not args.standard)
    except Exception:
        sys.exit(1)
