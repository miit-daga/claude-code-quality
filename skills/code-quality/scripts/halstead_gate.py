#!/usr/bin/env python3
"""Halstead difficulty gate: D = (distinct operators / 2) * (total operands / distinct operands).

Difficulty climbs when code juggles many operators and reuses the same operands
over and over, which is a good proxy for "hard to read in one pass".

  * Python files: per function, via radon (`pip install radon`). This is the
    gate: a function at or above --max fails.
  * Every other language: per file, via multimetric (`pip install multimetric`),
    which tokenises 50+ languages with Pygments. A per-file score is a different
    measurement on a different scale (well-written files of a few dozen lines can
    exceed 80), so these scores are ADVISORY by default: reported, never failing.
    To gate them, set a per-file budget calibrated on the project with --file-max.
    Never split a file only to lower its per-file score.

Different tools count operators and operands differently, so the same code can
score very differently across tools (and per-file scores run higher than
per-function ones). Pick one tool per language, measure the current
distribution, and keep the threshold fixed for that tool; do not compare
numbers across tools.

Examples:
  python halstead_gate.py src                        # Python functions D < 80; other files advisory
  python halstead_gate.py src --max 40 --top 10
  python halstead_gate.py web --file-max 150         # gate per-file scores at a calibrated budget

Exit code 1 if a Python function is at/over --max, or a file is at/over --file-max.
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
    ap.add_argument("--exclude", action="append", default=[], metavar="GLOB",
                    help="fnmatch glob on the relative path to skip; repeat the flag for more")
    ap.add_argument("--file-max", type=float, default=None,
                    help="per-file budget for non-Python files; without it per-file scores are advisory")
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
    fn_scores = python_scores(py) if py else []
    file_scores = multimetric_scores(other) if other else []
    scores = fn_scores + file_scores
    failing = [(where, d, args.max) for where, d in fn_scores if d >= args.max]
    if args.file_max is not None:
        failing += [(where, d, args.file_max) for where, d in file_scores if d >= args.file_max]
    else:
        advisory = sorted(((w, d) for w, d in file_scores if d >= args.max), key=lambda s: -s[1])
        for where, d in advisory:
            print(f"advisory: {where}: per-file Halstead difficulty {d:.1f} (not gated; see --file-max)")
    for where, d, limit in sorted(failing, key=lambda s: -s[1]):
        print(f"{where}: Halstead difficulty {d:.1f} >= {limit:g}")
    if args.top:
        print(f"\nTop {args.top}:")
        for where, d in sorted(scores, key=lambda s: -s[1])[: args.top]:
            print(f"  {d:6.1f}  {where}")
    status = "FAIL" if failing else "OK"
    print(f"\nhalstead_gate: {status} - {len(scores)} units checked, {len(failing)} over budget")
    return 1 if failing else 0


if __name__ == "__main__":
    sys.exit(main())
