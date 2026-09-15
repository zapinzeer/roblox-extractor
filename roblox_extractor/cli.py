from __future__ import annotations

import argparse
import sys
from typing import Optional, Sequence

from . import __version__
from .errors import ExtractorError, OutputConflictError
from .extraction import extract_luau_scripts
from .parsing import warn_to_stderr

FORCE_HINT = "Pass --force to overwrite them, or -o DIR to write somewhere else."


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="extractor",
        description=(
            "Extract Luau scripts from a Roblox XML model (.rbxmx) or place "
            "(.rbxlx) file into a Rojo-compatible source tree. Run with no "
            "arguments to be asked for the paths instead."
        ),
    )
    parser.add_argument(
        "file", nargs="?", default=None,
        help="the .rbxmx / .rbxlx file to read",
    )
    parser.add_argument(
        "-i", "--input", dest="input_flag", default=None, metavar="FILE",
        help="another way to give the input file",
    )
    parser.add_argument(
        "-o", "--output", default=None, metavar="DIR",
        help="where to write (default: a folder named after the model or place)",
    )
    parser.add_argument(
        "--ext", default="luau", choices=["luau", "lua"],
        help="extension for extracted scripts (default: %(default)s)",
    )
    parser.add_argument(
        "--standard", action="store_true",
        help="write a flat layout instead of Rojo init files",
    )
    parser.add_argument(
        "-f", "--force", action="store_true",
        help="overwrite files that already exist in the output directory",
    )
    parser.add_argument("-q", "--quiet", action="store_true", help="only report errors")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def use_replacement_on_unencodable_output() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(errors="backslashreplace")
        except (ValueError, OSError):
            pass


def _read_path(prompt: str) -> Optional[str]:
    try:
        raw = input(prompt)
    except (EOFError, KeyboardInterrupt):
        print()
        return None
    return raw.strip().strip('"').strip("'").strip()


def _confirm(prompt: str) -> bool:
    try:
        return input(prompt).strip().lower() in ("y", "yes")
    except (EOFError, KeyboardInterrupt):
        print()
        return False


def _pause() -> None:
    try:
        input("\nPress Enter to close...")
    except (EOFError, KeyboardInterrupt):
        pass


def extract(
    args: argparse.Namespace,
    source: str,
    destination: Optional[str],
    interactive: bool,
) -> int:
    force = args.force
    while True:
        try:
            result = extract_luau_scripts(
                source,
                destination,
                ext=args.ext,
                rojo_format=not args.standard,
                force=force,
                warn=(lambda message: None) if args.quiet else warn_to_stderr,
            )
        except OutputConflictError as exc:
            if interactive:
                print(f"\n{exc}\n", file=sys.stderr)
                if _confirm("Overwrite them? [y/N]: "):
                    force = True
                    continue
                print("Nothing was written.", file=sys.stderr)
            else:
                print(f"error: {exc}\n{FORCE_HINT}", file=sys.stderr)
            return 1
        except ExtractorError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        break

    if not args.quiet:
        if result.script_count:
            plural = "" if result.script_count == 1 else "s"
            print(f"Extracted {result.script_count} script{plural} to {result.output_dir}")
        else:
            print(f"No scripts found in {source}")
    return 0


def run_interactive(args: argparse.Namespace) -> int:
    print(f"Roblox script extractor {__version__}")
    print("Paste the file to read, then where the scripts should go.\n")

    source = _read_path("Roblox file (.rbxmx / .rbxlx): ")
    if not source:
        return 1

    destination = args.output
    if destination is None:
        destination = _read_path("Output folder (blank to name one automatically): ")
        if destination is None:
            return 1
    print()

    return extract(args, source, destination or None, interactive=True)


def main(argv: Optional[Sequence[str]] = None) -> int:
    use_replacement_on_unencodable_output()
    args = build_parser().parse_args(argv)

    target = args.file or args.input_flag
    if target:
        return extract(args, target, args.output, interactive=False)

    code = run_interactive(args)
    _pause()
    return code
