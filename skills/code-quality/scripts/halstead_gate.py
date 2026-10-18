#!/usr/bin/env python3
"""Halstead difficulty gate: D = (distinct operators / 2) * (total operands / distinct operands).

Difficulty climbs when code juggles many operators and reuses the same operands
over and over, which is a good proxy for "hard to read in one pass".

  * Python files: per function, via radon (`pip install radon`).
  * Every other language: per file, via multimetric (`pip install multimetric`),
    which tokenises 50+ languages with Pygments.

Different tools count operators and operands differently, so the same code can
score very differently across tools (and per-file scores run higher than
per-function ones). Pick one tool per language, measure the current
distribution, and keep the threshold fixed for that tool; do not compare
numbers across tools.

Examples:
  python halstead_gate.py src                 # D < 80
  python halstead_gate.py src --max 40 --top 10

Exit code 1 if anything is at or above the threshold, 0 otherwise.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _files import SOURCE_EXTS, list_files, read_text

CHUNK = 200
NON_CODE = {".css", ".scss", ".sass", ".less", ".rbs", ".erb"}


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="*", default=["."])
    ap.add_argument("--max", type=float, default=80.0, help="difficulty must be strictly below this (default 80)")
    ap.add_argument("--exclude", nargs="*", default=[], help="fnmatch globs on the relative path to skip")
    ap.add_argument("--top", type=int, default=0, help="also print the N highest scores")
    return ap.parse_args()


def python_scores(files: list[Path]) -> list[tuple[str, float]]:
    try:
        from radon.metrics import h_visit
    except ImportError:
        sys.exit("halstead_gate: radon is not installed. Run: pip install radon")
    scores = []
    for path in files:
        try:
            report = h_visit(read_text(path))
        except SyntaxError as err:
            print(f"halstead_gate: skipping {path} ({err.msg})", file=sys.stderr)
            continue
        scores.extend((f"{path} {name}()", h.difficulty) for name, h in report.functions)
    return scores


def multimetric_command() -> str:
    # Use the console script: `python -m multimetric` deadlocks in its worker pool on macOS.
    beside_python = Path(sys.executable).with_name("multimetric")
    found = str(beside_python) if beside_python.exists() else shutil.which("multimetric")
    if not found:
        sys.exit("halstead_gate: multimetric is not installed. Run: pip install multimetric")
    return found


def multimetric_scores(files: list[Path]) -> list[tuple[str, float]]:
    command = multimetric_command()
    scores = []
    for start in range(0, len(files), CHUNK):
        batch = [str(p) for p in files[start : start + CHUNK]]
        proc = subprocess.run(
            [command, *batch], capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=600, check=False
        )
        if proc.returncode != 0:
            sys.exit(f"halstead_gate: multimetric failed\n{proc.stderr.strip()}")
        per_file = json.loads(proc.stdout)["files"]
        scores.extend((f"{os.path.relpath(name)} (file)", data["halstead_difficulty"]) for name, data in per_file.items())
    return scores


def main() -> int:
    args = parse_args()
    files = list_files(args.paths, SOURCE_EXTS - NON_CODE, args.exclude)
    py = [f for f in files if f.suffix in {".py", ".pyi"}]
    other = [f for f in files if f not in py]
    scores = (python_scores(py) if py else []) + (multimetric_scores(other) if other else [])
    failing = [(where, d) for where, d in scores if d >= args.max]
    for where, d in sorted(failing, key=lambda s: -s[1]):
        print(f"{where}: Halstead difficulty {d:.1f} >= {args.max:g}")
    if args.top:
        print(f"\nTop {args.top}:")
        for where, d in sorted(scores, key=lambda s: -s[1])[: args.top]:
            print(f"  {d:6.1f}  {where}")
    status = "FAIL" if failing else "OK"
    print(f"\nhalstead_gate: {status} - {len(scores)} units checked, {len(failing)} at/over {args.max:g}")
    return 1 if failing else 0


if __name__ == "__main__":
    sys.exit(main())
