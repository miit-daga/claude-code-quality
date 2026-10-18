#!/usr/bin/env python3
"""Fail when any source file exceeds a line budget (and optionally a byte budget).

Language-agnostic. Counts physical lines, because that is what a reader (human
or agent) has to load into context. Run the project's formatter first so the
budget cannot be gamed by cramming several statements onto one line.

Examples:
  python loc_budget.py src                       # files must be < 500 lines
  python loc_budget.py . --max-lines 399
  python loc_budget.py web --max-bytes 51200 --bytes-ext .css .js   # 50 KB per CSS/JS file
  python loc_budget.py . --exclude '*/migrations/*' --exclude '*.generated.*'

Exit code 1 if any file is over budget, 0 otherwise.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _files import SOURCE_EXTS, list_files, read_text


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="*", default=["."])
    ap.add_argument("--max-lines", type=int, default=499, help="max physical lines per file (default 499, i.e. < 500)")
    ap.add_argument("--max-bytes", type=int, default=None, help="max bytes per file for --bytes-ext files")
    ap.add_argument(
        "--bytes-ext", nargs="*", default=[".css", ".scss", ".js", ".mjs"], help="extensions the byte budget applies to"
    )
    ap.add_argument("--ext", nargs="*", default=None, help="only check these extensions (default: all known source extensions)")
    ap.add_argument("--exclude", action="append", default=[], metavar="GLOB",
                    help="fnmatch glob on the relative path to skip; repeat the flag for more")
    return ap.parse_args()


def check(path: Path, args: argparse.Namespace) -> list[str]:
    problems = []
    lines = len(read_text(path).splitlines())
    if lines > args.max_lines:
        problems.append(f"{path}: {lines} lines (budget {args.max_lines}, over by {lines - args.max_lines})")
    if args.max_bytes is not None and path.suffix in args.bytes_ext:
        size = path.stat().st_size
        if size > args.max_bytes:
            problems.append(f"{path}: {size} bytes (budget {args.max_bytes})")
    return problems


def main() -> int:
    args = parse_args()
    exts = set(args.ext) if args.ext else SOURCE_EXTS
    files = list_files(args.paths, exts, args.exclude)
    problems = [msg for f in files for msg in check(f, args)]
    for msg in problems:
        print(msg)
    status = "FAIL" if problems else "OK"
    print(f"loc_budget: {status} - {len(files)} files checked, {len(problems)} over budget")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
