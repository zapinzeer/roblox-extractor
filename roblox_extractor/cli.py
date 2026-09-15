from __future__ import annotations

import argparse
import sys
from typing import Optional, Sequence

from .errors import ExtractorError
from .extraction import extract_luau_scripts
from .parsing import warn_to_stderr


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("file", nargs="?", default=None)
    parser.add_argument("-i", "--input", dest="input_flag", default=None)
    parser.add_argument("-o", "--output", default=None)
    parser.add_argument("--ext", default="luau", choices=["luau", "lua"])
    parser.add_argument("--standard", action="store_true")
    parser.add_argument("-f", "--force", action="store_true")
    parser.add_argument("-q", "--quiet", action="store_true")
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
        result = extract_luau_scripts(
            target,
            args.output,
            ext=args.ext,
            rojo_format=not args.standard,
            force=args.force,
            warn=(lambda message: None) if args.quiet else warn_to_stderr,
        )
    except ExtractorError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if not args.quiet:
        if result.script_count:
            plural = "" if result.script_count == 1 else "s"
            print(f"Extracted {result.script_count} script{plural} to {result.output_dir}")
        else:
            print(f"No scripts found in {target}")
    return 0
