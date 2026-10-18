#!/usr/bin/env python3
"""Flag over-commented files, narrating comments and commented-out code.

Agent-written code tends to narrate itself ("# Loop over the items" above a
for-loop). That noise costs reading time and goes stale. This script:

  1. FAILS when a file's comment-to-code ratio is above --max-ratio.
  2. FAILS on likely narrating comments (comment words mostly restate the next
     code line). --no-fail-on-narration turns this into a report only.
  3. FAILS on likely commented-out code. --no-fail-on-commented-code turns this
     into a report only.

What does NOT count as a comment here: doc comments directly above a
declaration (docstrings, JSDoc, Go doc comments, YARD, rustdoc), the license
header at the top of a file, shebangs, and tool directives (noqa, eslint-,
@ts-, go:, nolint, rubocop:, pragma, ...). Those carry information or are
required by tooling. Use the native linter rule for commented-out code where
one exists (ruff ERA001, sonarjs/no-commented-code); 2. and 3. are heuristics.

Examples:
  python comment_density.py src
  python comment_density.py . --max-ratio 0.15 --no-fail-on-narration   # legacy code: report narration only

Exit code 1 if any enabled check fails, 0 otherwise.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _files import list_files, read_text

HASH = {".py", ".pyi", ".rb", ".rake", ".rbs", ".ex", ".exs"}
SLASH = {
    ".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".mts", ".cts", ".go", ".java", ".kt", ".kts",
    ".scala", ".groovy", ".cs", ".fs", ".rs", ".swift", ".c", ".h", ".cc", ".cpp", ".cxx", ".hpp",
    ".dart", ".php", ".css", ".scss", ".less",
}
DASH = {".lua"}

# A declaration keyword is followed by whitespace and a name (`data class Foo`, `type Foo`,
# `func (r *Repo)`) or a generic list (`impl<T>`), never by `=`, `:`, `.` or `(`. That keeps
# assignments such as `data = read(path)` or `type: str = ...` from passing as declarations.
DECLARATION = re.compile(
    r"^\s*(export\s+)?(default\s+)?(pub(\([\w:]+\))?\s+)?(async\s+)?"
    r"((def|class|module|func|fn|function|interface|type|struct|enum|trait|impl|"
    r"public|private|protected|internal|static|abstract|override|sealed|data|object|package|"
    r"namespace|record)(?=\s+[\w(<\[*&$]|<)|@|\[)"
)
# Variable declarations only count as documented declarations at module level;
# indented ones are ordinary statements inside a function body.
TOP_LEVEL_BINDING = re.compile(r"^(export\s+)?(const|let|var|val)\b")
IMPORTISH = re.compile(r"^\s*(import\b|from\s+\S+\s+import\b|package\b|using\b|use\b|require\b|#include\b|module\b|<\?php)")
DIRECTIVE = re.compile(
    r"^(#!|#\s*-\*-|#\s*(type:|noqa|pragma|pylint|mypy|pyright|fmt:|isort|rubocop|frozen_string_literal|"
    r"typed:|encoding)|//\s*(eslint|@ts-|go:|nolint|NOLINT|prettier|biome|Stryker|istanbul|c8|v8|"
    r"swiftlint|deno-|#region|#endregion|region|endregion|<reference)|/\*\s*(eslint|istanbul|c8|"
    r"webpackChunkName|prettier))"
)
CODE_LIKE = re.compile(
    r"([{}]\s*$|^\s*(if|for|while|return|def|func|function|var|let|const|import|from|print|"
    r"console\.|fmt\.|puts|echo)\b.*[(=:]|^\s*\w+(\.\w+)*\s*=\s*\S|^\s*\w+(\.\w+)*\(.*\)\s*;?\s*$)"
)
# A trailing semicolon signals code only in C-family syntax; in # comments it is prose.
SEMICOLON_END = re.compile(r";\s*$")
WORD = re.compile(r"[A-Za-z]{3,}")
NARRATION_WORDS = range(2, 9)
NARRATION_OVERLAP = 0.6
STOP = {
    "the", "and", "for", "this", "that", "with", "from", "into", "then", "over", "each", "all",
    "our", "its", "are", "was", "will", "now", "new", "here", "just", "when", "via", "per",
}
SYNONYM = {
    "loop": "for", "iterate": "for", "iterating": "for", "initialize": "=", "init": "=",
    "set": "=", "assign": "=", "store": "=", "increment": "+=", "add": "+", "adding": "+",
    "check": "if", "checking": "if", "call": "(", "calling": "(", "zero": "0", "one": "1",
    "empty": "[]", "return": "return", "returns": "return", "import": "import", "print": "print",
    "log": "log",
}


@dataclass
class Report:
    path: Path
    code: int = 0
    comments: int = 0
    narration: list[tuple[int, str]] = field(default_factory=list)
    commented_code: list[tuple[int, str]] = field(default_factory=list)

    @property
    def ratio(self) -> float:
        return self.comments / self.code if self.code else 0.0


def comment_text(line: str, suffix: str) -> str | None:
    """Return the comment body if the whole line is a comment, else None."""
    stripped = line.strip()
    markers = ("#",) if suffix in HASH else ("//", "/*", "*") if suffix in SLASH else ("--",)
    if suffix == ".php":
        markers = ("//", "/*", "*", "#")
    for marker in markers:
        if stripped.startswith(marker):
            return stripped.lstrip("/#*-! ").rstrip("*/ ").strip()
    return None


def is_doc_marker(line: str) -> bool:
    stripped = line.strip()
    return stripped.startswith(("///", "//!", "/**", "#:")) or stripped.startswith(('"""', "'''"))


def code_tokens(code_line: str) -> set[str]:
    parts = re.findall(r"[A-Za-z][a-z]*|[A-Z]+(?![a-z])|\d+", code_line)
    tokens = {p.lower() for p in parts}
    tokens.update({t.rstrip("s") for t in tokens})
    tokens.update(sym for sym in ("=", "+=", "+", "(", "[]", "0", "1") if sym in code_line)
    tokens.update(kw for kw in ("for", "if", "return", "import", "print", "log") if kw in code_line)
    return tokens


def narrates(comment: str, next_code: str) -> bool:
    words = [w.lower() for w in WORD.findall(comment) if w.lower() not in STOP]
    if len(words) not in NARRATION_WORDS:
        return False
    tokens = code_tokens(next_code)
    hits = sum(1 for w in words if SYNONYM.get(w, w) in tokens or w.rstrip("s") in tokens)
    return hits / len(words) >= NARRATION_OVERLAP


def looks_like_code(text: str, suffix: str) -> bool:
    return bool(CODE_LIKE.search(text) or (suffix in SLASH and SEMICOLON_END.search(text)))


def blocks(lines: list[str], suffix: str) -> list[tuple[int, int]]:
    """(start, end) index pairs of consecutive whole-line comments."""
    spans, start = [], None
    for i, line in enumerate([*lines, ""]):
        is_comment = comment_text(line, suffix) is not None if line.strip() else False
        if is_comment and start is None:
            start = i
        elif not is_comment and start is not None:
            spans.append((start, i - 1))
            start = None
    return spans


def next_code_line(lines: list[str], index: int) -> str:
    for line in lines[index + 1 :]:
        if line.strip():
            return line
    return ""


def first_code_index(lines: list[str], suffix: str) -> int:
    for i, line in enumerate(lines):
        if line.strip() and comment_text(line, suffix) is None:
            return i
    return len(lines)


def is_file_header(lines: list[str], end: int, header_end: int) -> bool:
    """A top-of-file block is a header (license, module summary) only when a blank line,
    an import or a declaration follows it; directly above a statement it is a comment."""
    if end >= header_end:
        return False
    after = lines[end + 1] if end + 1 < len(lines) else ""
    return not after.strip() or bool(IMPORTISH.match(after) or DECLARATION.match(after))


def skip_block(lines: list[str], start: int, end: int, header_end: int) -> bool:
    if is_file_header(lines, end, header_end) or is_doc_marker(lines[start]):
        return True
    following = next_code_line(lines, end)
    return bool(DECLARATION.match(following) or TOP_LEVEL_BINDING.match(following))


def scan_block(report: Report, lines: list[str], start: int, end: int, suffix: str) -> None:
    for i in range(start, end + 1):
        raw = lines[i].strip()
        if DIRECTIVE.match(raw):
            continue
        text = comment_text(lines[i], suffix) or ""
        if not text:
            continue
        report.comments += 1
        if looks_like_code(text, suffix):
            report.commented_code.append((i + 1, raw))
        elif i == end and narrates(text, next_code_line(lines, i)):
            report.narration.append((i + 1, raw))


def analyze(path: Path) -> Report:
    report = Report(path)
    lines = read_text(path).splitlines()
    suffix = path.suffix
    report.code = sum(1 for line in lines if line.strip() and comment_text(line, suffix) is None)
    header_end = first_code_index(lines, suffix)
    for start, end in blocks(lines, suffix):
        if not skip_block(lines, start, end, header_end):
            scan_block(report, lines, start, end, suffix)
    return report


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="*", default=["."])
    ap.add_argument("--max-ratio", type=float, default=0.25, help="max comment lines per code line (default 0.25)")
    ap.add_argument("--min-code", type=int, default=20, help="ignore files with fewer code lines (default 20)")
    ap.add_argument("--fail-on-narration", action=argparse.BooleanOptionalAction, default=True,
                    help="fail on narrating comments (default: on)")
    ap.add_argument("--fail-on-commented-code", action=argparse.BooleanOptionalAction, default=True,
                    help="fail on commented-out code (default: on)")
    ap.add_argument("--exclude", nargs="*", default=[], help="fnmatch globs on the relative path to skip")
    return ap.parse_args()


def print_findings(reports: list[Report], args: argparse.Namespace) -> int:
    failures = 0
    for r in reports:
        if r.code >= args.min_code and r.ratio > args.max_ratio:
            failures += 1
            print(f"{r.path}: comment ratio {r.ratio:.2f} ({r.comments} comment / {r.code} code lines) > {args.max_ratio}")
        for line, text in r.narration:
            failures += int(args.fail_on_narration)
            print(f"{r.path}:{line}: narrating comment? {text}")
        for line, text in r.commented_code:
            failures += int(args.fail_on_commented_code)
            print(f"{r.path}:{line}: commented-out code? {text}")
    return failures


def main() -> int:
    args = parse_args()
    exts = HASH | SLASH | DASH
    reports = [analyze(p) for p in list_files(args.paths, exts, args.exclude)]
    failures = print_findings(reports, args)
    status = "FAIL" if failures else "OK"
    print(f"\ncomment_density: {status} - {len(reports)} files checked, {failures} failing findings")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
