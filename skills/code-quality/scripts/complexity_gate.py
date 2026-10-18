#!/usr/bin/env python3
"""Per-function cyclomatic + cognitive complexity gate for any language lizard understands, plus CRAP.

lizard (`pip install lizard`) parses Python, JS/TS, Go, Java, Kotlin, Scala,
C#, Ruby, PHP, Rust, Swift, C/C++, Lua, Erlang and more. This script turns its
per-function numbers into a pass/fail gate. Cognitive complexity (SonarSource's
definition) comes from lizard's `cognitive` extension (lizard >= 1.24); with an
older lizard that gate is skipped with a warning. Given a coverage report, it also
computes CRAP for every function:

    CRAP(m) = CCN(m)^2 * (1 - coverage(m))^3 + CCN(m)

Coverage reports accepted: lcov, Cobertura XML, JaCoCo XML, Clover XML, Go
cover profiles (see coverage_formats.py). A file missing from the report counts
as 0% covered, which is deliberate: untested code is exactly what CRAP is for.

Examples:
  python complexity_gate.py src                                  # CCN < 22, cognitive < 22
  python complexity_gate.py src --coverage coverage/lcov.info    # + CRAP < 25
  python complexity_gate.py . --coverage cover.out --params-max 5 --nloc-max 60
  python complexity_gate.py src --coverage coverage.xml --top 15 # worst CRAP first, for triage

Exit code 1 if any function breaks a budget, 0 otherwise.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import coverage_formats
from _files import SOURCE_EXTS, list_files

LIZARD_EXTS = SOURCE_EXTS - {".css", ".scss", ".sass", ".less", ".erb", ".vue", ".svelte", ".rbs"}


@dataclass
class Fn:
    path: str
    name: str
    line: int
    end: int
    ccn: int
    nloc: int
    params: int
    cognitive: int | None = None
    coverage: float | None = None
    crap: float | None = None
    problems: list[str] = field(default_factory=list)


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="*", default=["."])
    ap.add_argument("--ccn-max", type=int, default=21, help="max cyclomatic complexity per function (default 21, i.e. < 22)")
    ap.add_argument("--cognitive-max", type=int, default=21, help="max cognitive complexity per function (default 21, i.e. < 22)")
    ap.add_argument("--crap-max", type=float, default=25.0, help="CRAP must be strictly below this (default 25)")
    ap.add_argument("--params-max", type=int, default=None, help="optional max parameters per function")
    ap.add_argument("--nloc-max", type=int, default=None, help="optional max non-comment lines per function")
    ap.add_argument("--coverage", default=None, help="coverage report (lcov / cobertura / jacoco / clover / go profile)")
    ap.add_argument("--exclude", action="append", default=[], metavar="GLOB",
                    help="fnmatch glob on the relative path to skip; repeat the flag for more")
    ap.add_argument("--top", type=int, default=0, help="also print the N functions with the highest CRAP (or CCN)")
    return ap.parse_args()


def make_analyzer():
    try:
        import lizard
    except ImportError:
        sys.exit("complexity_gate: lizard is not installed. Run: pip install lizard")
    try:
        return lizard.FileAnalyzer(lizard.get_extensions(["cognitive"]))
    except (ImportError, ModuleNotFoundError):
        print("complexity_gate: lizard < 1.24 has no cognitive extension; cognitive gate skipped", file=sys.stderr)
        return lizard.FileAnalyzer(lizard.get_extensions([]))


def analyze(files: list[Path]) -> list[Fn]:
    analyzer = make_analyzer()
    fns: list[Fn] = []
    for path in files:
        for f in analyzer(str(path)).function_list:
            fn = Fn(str(path), f.name, f.start_line, f.end_line, f.cyclomatic_complexity, f.nloc, f.parameter_count)
            fn.cognitive = getattr(f, "cognitive_complexity", None)
            fns.append(fn)
    return fns


def warn_unparsed(files: list[Path], fns: list[Fn]) -> None:
    """A language lizard cannot parse yields zero functions and would pass silently."""
    files_per_ext = Counter(p.suffix for p in files)
    fns_per_ext = Counter(Path(fn.path).suffix for fn in fns)
    for ext, count in sorted(files_per_ext.items()):
        if fns_per_ext[ext] == 0 and count >= 1:
            print(
                f"complexity_gate: WARNING no functions found in {count} {ext} file(s); lizard may not "
                "parse this language. Gate it with the language's native tool instead.",
                file=sys.stderr,
            )


def function_coverage(fn: Fn, lines: dict[int, bool] | None) -> float | None:
    if lines is None:
        return 0.0
    instrumented = [hit for num, hit in lines.items() if fn.line <= num <= fn.end]
    if not instrumented:
        return None
    return sum(instrumented) / len(instrumented)


def apply_coverage(fns: list[Fn], report: str) -> None:
    index = coverage_formats.CoverageIndex(coverage_formats.load(report))
    for fn in fns:
        fn.coverage = function_coverage(fn, index.lines_for(fn.path))
        if fn.coverage is not None:
            fn.crap = fn.ccn**2 * (1 - fn.coverage) ** 3 + fn.ccn


def judge(fn: Fn, args: argparse.Namespace) -> None:
    if fn.ccn > args.ccn_max:
        fn.problems.append(f"CCN {fn.ccn} > {args.ccn_max}")
    if fn.cognitive is not None and fn.cognitive > args.cognitive_max:
        fn.problems.append(f"cognitive {fn.cognitive} > {args.cognitive_max}")
    if fn.crap is not None and fn.crap >= args.crap_max:
        fn.problems.append(f"CRAP {fn.crap:.1f} >= {args.crap_max:g}")
    if args.params_max is not None and fn.params > args.params_max:
        fn.problems.append(f"params {fn.params} > {args.params_max}")
    if args.nloc_max is not None and fn.nloc > args.nloc_max:
        fn.problems.append(f"NLOC {fn.nloc} > {args.nloc_max}")


def describe(fn: Fn) -> str:
    cov = "n/a" if fn.coverage is None else f"{fn.coverage:.0%}"
    crap = "n/a" if fn.crap is None else f"{fn.crap:.1f}"
    cog = "n/a" if fn.cognitive is None else fn.cognitive
    return f"{fn.path}:{fn.line} {fn.name}  CCN={fn.ccn} CogC={cog} params={fn.params} NLOC={fn.nloc} cov={cov} CRAP={crap}"


def print_top(fns: list[Fn], n: int) -> None:
    ranked = sorted(fns, key=lambda f: (f.crap if f.crap is not None else f.ccn), reverse=True)[:n]
    print(f"\nTop {len(ranked)} by {'CRAP' if any(f.crap is not None for f in fns) else 'CCN'}:")
    for fn in ranked:
        print("  " + describe(fn))


def main() -> int:
    args = parse_args()
    files = list_files(args.paths, LIZARD_EXTS, args.exclude)
    fns = analyze(files)
    warn_unparsed(files, fns)
    if args.coverage:
        apply_coverage(fns, args.coverage)
    for fn in fns:
        judge(fn, args)
    failing = [fn for fn in fns if fn.problems]
    for fn in failing:
        print(f"{describe(fn)}  <- {'; '.join(fn.problems)}")
    if args.top:
        print_top(fns, args.top)
    status = "FAIL" if failing else "OK"
    print(f"\ncomplexity_gate: {status} - {len(fns)} functions checked, {len(failing)} over budget")
    return 1 if failing else 0


if __name__ == "__main__":
    sys.exit(main())
