#!/usr/bin/env python3
"""Count the ways code can dodge its quality gates, and stop the count from growing.

An agent under pressure from a strict gate has a cheaper option than fixing
the code: silence the gate. This script counts every such escape hatch across
languages, so the gates cannot be satisfied by suppression:

  lint      noqa, type: ignore, eslint-disable, @ts-ignore, rubocop:disable, nolint,
            #[allow(...)], @SuppressWarnings, NOSONAR, @phpstan-ignore, ...
  coverage  pragma: no cover, istanbul/c8/v8 ignore, :nocov:, ExcludeFromCodeCoverage, ...
  mutation  pragma: no mutate, Stryker disable, mutants::skip, @infection-ignore-all, ...
  skipped   pytest skip/xfail, it.skip/xit/.only, t.Skip, @Disabled, [Ignore], #[ignore], ...
  any-type  TS any/unknown, Python Any, Go any/interface{}, C# dynamic, Sorbet T.untyped,
            PHP mixed, Kotlin Any, Rust unsafe / dyn Any
  todo      TODO / FIXME / HACK / XXX

"Blanket" suppressions (no rule named: a bare noqa, a bare eslint-disable,
ts-ignore, a bare nolint) always fail unless --allow-blanket is given.

Allowed by design (not counted): TS catch variables typed `unknown`, Python
`import ... Any` lines, Go generic constraints, `equals(Object)` overrides, and
the untyped input *parameter* of functions in boundary files passed to
--any-type-allow (the schema parsers that receive raw input, e.g.
--any-type-allow 'src/boundary/*'); casts and other uses there still count.

Modes:
  python suppression_audit.py src                          # report; fail on blanket only
  python suppression_audit.py src --zero coverage skipped  # these categories must be 0
  python suppression_audit.py . --write-baseline .quality/suppressions.json
  python suppression_audit.py . --baseline .quality/suppressions.json   # ratchet: no count may grow

Exit code 1 on any failure, 0 otherwise.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _files import SOURCE_EXTS, list_files, read_text

PY = {".py", ".pyi"}
JS = {".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".mts", ".cts", ".vue", ".svelte"}
TS = {".ts", ".tsx", ".mts", ".cts", ".vue", ".svelte"}
RB = {".rb", ".rake", ".erb"}
EX = {".ex", ".exs"}
CPP = {".c", ".h", ".cc", ".cpp", ".cxx", ".hpp"}
# equals(Object o) / equals(other: Any?) are required signatures, not escape hatches.
EQUALS = r"\bequals\s*\("
# `[T any]` is a generic constraint (anything is allowed by design), not an untyped value.
# `unknown` is the correct type for a caught error: `catch (e: unknown)`, `.catch((e: unknown) => ...)`.
TS_CATCH = r"catch\s*\(\s*\(?\s*\w+\s*:\s*unknown\b|\.then\([^,]*,\s*\(\s*\w+\s*:\s*unknown\b"
# `from typing import Any` imports the name; only annotations that use it are escape hatches.
PY_IMPORT = r"^\s*(from\s+\S+\s+)?import\b"
GO_CONSTRAINT = r"\[[^\]()]*\s+any\b[^\]()]*\]"


@dataclass
class Marker:
    """One escape hatch. Patterns are plain strings; `re` caches their compiled form."""

    category: str
    name: str
    pattern: str
    exts: set[str] | None = None
    blanket: str | None = None
    code_only: bool = False
    unless: str | None = None  # skip lines matching this (legitimate uses of the pattern)
    strip: str | None = None  # blank out spans matching this before searching (exempt spans only)


MARKERS = [
    # lint / type-checker suppressions
    Marker("lint", "noqa", r"#\s*noqa\b", PY, blanket=r"#\s*noqa(?!\s*:)"),
    Marker("lint", "type: ignore", r"#\s*type:\s*ignore", PY, blanket=r"type:\s*ignore(?!\[)"),
    Marker("lint", "pyright: ignore", r"#\s*pyright:\s*ignore", PY, blanket=r"pyright:\s*ignore(?!\[)"),
    Marker("lint", "complexipy: ignore", r"#\s*complexipy:\s*ignore", PY),
    Marker("lint", "pylint: disable", r"#\s*pylint:\s*disable", PY, blanket=r"pylint:\s*disable\s*=\s*all"),
    Marker("lint", "eslint-disable", r"eslint-disable", JS, blanket=r"eslint-disable(-next-line|-line)?\s*(\*/)?\s*$"),
    Marker("lint", "@ts-ignore", r"@ts-ignore", TS, blanket=r"@ts-ignore"),
    Marker("lint", "@ts-nocheck", r"@ts-nocheck", TS, blanket=r"@ts-nocheck"),
    Marker("lint", "@ts-expect-error", r"@ts-expect-error", TS, blanket=r"@ts-expect-error\s*(\*/)?\s*$"),
    Marker("lint", "biome-ignore", r"biome-ignore", JS),
    Marker("lint", "rubocop:disable", r"rubocop:disable", RB, blanket=r"rubocop:disable\s+all"),
    Marker("lint", "nolint", r"//\s*nolint\b", {".go"}, blanket=r"//\s*nolint(?!:)"),
    Marker("lint", "lint:ignore", r"//\s*lint:(file-)?ignore", {".go"}),
    Marker("lint", "#[allow/expect(...)]", r"#!?\[(allow|expect)\(", {".rs"}),
    Marker("lint", "@SuppressWarnings", r"@SuppressWarnings\(", {".java", ".scala", ".groovy"}),
    Marker("lint", "@Suppress", r"@(file:)?Suppress\(", {".kt", ".kts"}),
    Marker("lint", "#pragma warning disable", r"#pragma\s+warning\s+disable", {".cs"}, blanket=r"disable\s*$"),
    Marker("lint", "SuppressMessage", r"SuppressMessage\(", {".cs"}),
    Marker("lint", "NOSONAR", r"NOSONAR"),
    Marker("lint", "NOLINT", r"NOLINT", {".c", ".h", ".cc", ".cpp", ".cxx", ".hpp"}, blanket=r"NOLINT(NEXTLINE)?(?!\()"),
    Marker("lint", "phpcs:ignore", r"phpcs:(ignore|disable)", {".php"}),
    Marker("lint", "@phpstan-ignore", r"@phpstan-ignore", {".php"}, blanket=r"@phpstan-ignore(-line|-next-line)?\s*(\*/)?\s*$"),
    Marker("lint", "@psalm-suppress", r"@psalm-suppress", {".php"}),
    Marker("lint", "swiftlint:disable", r"swiftlint:disable", {".swift"}),
    Marker("lint", "credo:disable", r"credo:disable", EX),
    Marker("lint", "herb:disable", r"herb:disable", {".erb"}),
    Marker("lint", "strong_migrations safety_assured", r"\bsafety_assured\b", {".rb"}),
    Marker("lint", "nosec / nosemgrep", r"\b(nosec|nosemgrep)\b"),
    # coverage exclusions
    Marker("coverage", "pragma: no cover", r"pragma:\s*no\s*cover", PY),
    Marker("coverage", "istanbul/c8/v8 ignore", r"(istanbul|c8|v8)\s+ignore", JS),
    Marker("coverage", ":nocov: / simplecov:disable", r":nocov:|simplecov:disable", RB),
    Marker("coverage", "coveralls-ignore", r"coveralls-ignore", EX),
    Marker("coverage", "GCOVR_EXCL", r"GCOVR_EXCL", CPP),
    Marker("coverage", "@codeCoverageIgnore", r"@codeCoverageIgnore", {".php"}),
    Marker("coverage", "ExcludeFromCodeCoverage", r"ExcludeFromCodeCoverage", {".cs"}),
    Marker("coverage", "#[coverage(off)]", r"coverage\(off\)", {".rs"}),
    Marker("coverage", "LCOV_EXCL", r"LCOV_EXCL"),
    Marker("coverage", "go coverage-ignore", r"//\s*coverage-ignore", {".go"}),
    Marker("coverage", "tarpaulin skip", r"tarpaulin_include|tarpaulin::skip", {".rs"}),
    Marker("coverage", "@Generated (JaCoCo skips it)", r"@(\w+\.)*Generated\b", {".java", ".kt", ".kts"}),
    # mutation-testing exclusions
    Marker("mutation", "pragma: no mutate", r"pragma:\s*no\s*mutate", PY),
    Marker("mutation", "Stryker disable", r"Stryker\s+disable", JS | {".cs", ".scala"}),
    Marker("mutation", "mutant:disable", r"mutant:disable", RB),
    Marker("mutation", "@infection-ignore / @pest-mutate-ignore", r"@(infection|pest-mutate)-ignore", {".php"}),
    Marker("mutation", "muter:disable", r"muter:disable", {".swift"}),
    Marker("mutation", "mull-off / mull-ignore", r"mull-(off|ignore)", CPP),
    Marker("mutation", "mutants::skip/exclude_re", r"mutants::(skip|exclude_re)", {".rs"}),
    Marker("mutation", "go-mutesting disable", r"mutator-disable", {".go"}),
    Marker("mutation", "PIT @DoNotMutate/@CoverageIgnore", r"@(DoNotMutate|CoverageIgnore)\b", {".java", ".kt", ".kts"}),
    # skipped or focused tests
    Marker("skipped", "pytest skip/xfail", r"(@pytest\.mark\.(skip|skipif|xfail)|pytest\.skip\(|@unittest\.skip)", PY),
    Marker(
        "skipped", "js skip/only/todo", r"\b(it|test|describe|context|suite)\.(skip|only|todo)\(|\b[xf](it|describe|test)\(", JS
    ),
    Marker("skipped", "go t.Skip", r"\bt\.Skip(f|Now)?\(", {".go"}),
    Marker("skipped", "@Disabled/@Ignore", r"@(Disabled|Ignore)\b", {".java", ".kt", ".kts", ".scala"}),
    Marker("skipped", "[Ignore]/Skip=", r"\[Ignore\]|Skip\s*=\s*\"", {".cs"}),
    Marker("skipped", "rspec x/f/pending/skip", r"^\s*(xit|xdescribe|xcontext|fit|fdescribe|pending|skip)\b", RB),
    Marker("skipped", "#[ignore]", r"#\[ignore\]", {".rs"}),
    Marker("skipped", "phpunit skip", r"markTestSkipped\(|markTestIncomplete\(|->skip\(", {".php"}),
    # escape hatches from the type system
    Marker("any-type", "TS any", r"(:\s*|\bas\s+|<\s*|,\s*|\|\s*|=\s*)any\b(?!\s*[:(])", TS, code_only=True),
    Marker("any-type", "TS unknown", r"(:\s*|\bas\s+|<\s*|,\s*|\|\s*)unknown\b", TS, code_only=True, strip=TS_CATCH),
    Marker("any-type", "Python Any", r"(:\s*|->\s*|\[\s*|,\s*|\|\s*|typing\.)Any\b", PY, code_only=True, unless=PY_IMPORT),
    Marker("any-type", "Go any/interface{}", r"\binterface\{\}|[\s\[\](*,]any\b", {".go"}, code_only=True, strip=GO_CONSTRAINT),
    Marker("any-type", "C# dynamic", r"\bdynamic\b", {".cs"}, code_only=True),
    Marker("any-type", "Sorbet T.untyped/T.unsafe", r"T\.(untyped|unsafe)\b", RB, code_only=True),
    Marker("any-type", "RBS untyped", r"\buntyped\b", {".rbs"}, code_only=True),
    Marker("any-type", "Elixir any()/term()", r"\b(any|term)\(\)", EX, code_only=True),
    Marker("any-type", "PHP mixed", r"\bmixed\b", {".php"}),
    Marker("any-type", "Kotlin Any", r":\s*Any\??(?![\w])", {".kt", ".kts"}, code_only=True, unless=EQUALS),
    Marker("any-type", "Java Object param", r"[(,]\s*Object\s+\w+\s*[,)]", {".java"}, code_only=True, unless=EQUALS),
    Marker("any-type", "Rust unsafe / dyn Any", r"\bunsafe\b|dyn\s+Any\b", {".rs"}, code_only=True),
    # placeholders
    Marker("todo", "TODO/FIXME/HACK/XXX", r"\b(TODO|FIXME|HACK|XXX)\b"),
]
CATEGORIES = sorted({mk.category for mk in MARKERS})
COMMENT_START = ("#", "//", "/*", "*", "--")


@dataclass
class Hit:
    marker: Marker
    path: Path
    line: int
    text: str
    blanket: bool


def applies(marker: Marker, path: Path, line: str) -> bool:
    if marker.exts is not None and path.suffix not in marker.exts:
        return False
    if marker.code_only and line.lstrip().startswith(COMMENT_START):
        return False
    if marker.unless and re.search(marker.unless, line):
        return False
    if marker.strip:
        line = re.sub(marker.strip, " ", line)
    return re.search(marker.pattern, line) is not None


def scan(path: Path) -> list[Hit]:
    hits = []
    for number, line in enumerate(read_text(path).splitlines(), start=1):
        for marker in MARKERS:
            if applies(marker, path, line):
                blanket = bool(marker.blanket and re.search(marker.blanket, line))
                hits.append(Hit(marker, path, number, line.strip()[:120], blanket))
    return hits


# A function parameter typed as untyped input: `(raw: unknown)`, `(raw: Any)`, `func Parse(raw any)`.
UNTYPED_PARAM = r"[(,]\s*\*?\w+\??\s*(:\s*|\s+)(unknown|any|Any|interface\{\}|mixed|dynamic|T\.untyped)\b"
SIGNATURE = r"\b(def|function|func|fn)\b|=>"
CAST = r"\bas\s+(any|unknown)\b|\bcast\(|<(any|unknown)>"


def boundary_any(hit: Hit, globs: list[str]) -> bool:
    """In a boundary parser named by --any-type-allow, the raw input parameter may be untyped.
    Only that is exempt: casts, return types and variables in the same file still count."""
    if hit.marker.category != "any-type" or not any(fnmatch.fnmatch(hit.path.as_posix(), g) for g in globs):
        return False
    line = hit.text
    return bool(re.search(SIGNATURE, line) and re.search(UNTYPED_PARAM, line) and not re.search(CAST, line))


def counts(hits: list[Hit]) -> dict[str, int]:
    counter = Counter(f"{h.marker.category}/{h.marker.name}" for h in hits)
    counter.update(f"blanket/{h.marker.name}" for h in hits if h.blanket)
    return dict(sorted(counter.items()))


def ratchet_failures(current: dict[str, int], baseline_path: str) -> list[str]:
    baseline = json.loads(Path(baseline_path).read_text())
    return [
        f"{key}: {current[key]} (baseline {baseline.get(key, 0)})"
        for key in current
        if current[key] > baseline.get(key, 0)
    ]


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="*", default=["."])
    ap.add_argument("--zero", nargs="*", default=[], help=f"categories that must have no hits at all: {CATEGORIES}")
    ap.add_argument("--baseline", help="JSON from --write-baseline; fail if any count grew")
    ap.add_argument("--write-baseline", help="write current counts to this JSON file and exit 0")
    ap.add_argument("--any-type-allow", action="append", default=[], metavar="GLOB",
                    help="boundary files (schema parsers) whose function parameters may take untyped input; "
                         "repeat the flag for more")
    ap.add_argument("--allow-blanket", action="store_true", help="do not fail on blanket suppressions")
    ap.add_argument("--list", nargs="*", default=[], help="print every hit in these categories")
    ap.add_argument("--exclude", action="append", default=[], metavar="GLOB",
                    help="fnmatch glob on the relative path to skip; repeat the flag for more")
    return ap.parse_args()


def print_hits(hits: list[Hit], title: str) -> None:
    if hits:
        print(f"\n{title}:")
    for h in hits:
        print(f"  {h.path}:{h.line}: [{h.marker.name}] {h.text}")


def evaluate(hits: list[Hit], current: dict[str, int], args: argparse.Namespace) -> list[str]:
    failures = []
    if not args.allow_blanket:
        blanket = [h for h in hits if h.blanket]
        print_hits(blanket, "Blanket suppressions (name the rule and give a reason, or fix the code)")
        failures += [f"{len(blanket)} blanket suppressions"] if blanket else []
    for category in args.zero:
        found = [h for h in hits if h.marker.category == category]
        print_hits(found, f"'{category}' must be zero")
        failures += [f"{len(found)} '{category}' hits"] if found else []
    if args.baseline:
        grown = ratchet_failures(current, args.baseline)
        failures += [f"grew vs baseline: {g}" for g in grown]
    return failures


def split_categories(args: argparse.Namespace) -> None:
    """--zero/--list take a variable number of values, so file names that a pre-commit
    hook appends after them land there too. Treat non-category values as paths."""
    strays = [v for v in args.zero + args.list if v not in CATEGORIES]
    args.zero = [v for v in args.zero if v in CATEGORIES]
    args.list = [v for v in args.list if v in CATEGORIES]
    if strays:
        args.paths = [p for p in args.paths if p != "."] + strays


def main() -> int:
    args = parse_args()
    split_categories(args)
    this_file = Path(__file__).resolve()
    files = [f for f in list_files(args.paths, SOURCE_EXTS, args.exclude) if f.resolve() != this_file]
    hits = [h for f in files for h in scan(f) if not boundary_any(h, args.any_type_allow)]
    current = counts(hits)
    if args.write_baseline:
        Path(args.write_baseline).parent.mkdir(parents=True, exist_ok=True)
        Path(args.write_baseline).write_text(json.dumps(current, indent=2) + "\n")
        print(f"suppression_audit: baseline with {sum(current.values())} hits written to {args.write_baseline}")
        return 0
    print("Counts:" if current else "Counts: none")
    for key, value in current.items():
        print(f"  {value:5d}  {key}")
    print_hits([h for h in hits if h.marker.category in args.list], "Listed hits")
    failures = evaluate(hits, current, args)
    for failure in failures:
        print(f"FAIL: {failure}")
    print(f"\nsuppression_audit: {'FAIL' if failures else 'OK'} - {len(files)} files, {len(hits)} hits")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
