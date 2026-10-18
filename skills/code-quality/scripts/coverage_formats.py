"""Parse line coverage from the report formats that mainstream toolchains emit.

Returns {path: {line_number: covered}} for:
  * lcov            (Jest/Vitest/c8, coverage.py `coverage lcov`, cargo-llvm-cov, simplecov-lcov)
  * Cobertura XML   (coverage.py `coverage xml`, coverlet, gocover-cobertura, simplecov-cobertura, PHPUnit)
  * JaCoCo XML      (JaCoCo, Kover)
  * Clover XML      (PHPUnit --coverage-clover)
  * Go cover profile (`go test -coverprofile=cover.out`)
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

Coverage = dict[str, dict[int, bool]]


def _mark(cov: Coverage, path: str, line: int, hit: bool) -> None:
    lines = cov.setdefault(path, {})
    lines[line] = lines.get(line, False) or hit


def parse_lcov(text: str) -> Coverage:
    cov: Coverage = {}
    current = ""
    for raw in text.splitlines():
        if raw.startswith("SF:"):
            current = raw[3:].strip()
        elif raw.startswith("DA:") and current:
            num, hits = raw[3:].split(",")[:2]
            _mark(cov, current, int(num), int(float(hits)) > 0)
    return cov


def parse_go_profile(text: str) -> Coverage:
    cov: Coverage = {}
    for raw in text.splitlines()[1:]:
        if not raw.strip():
            continue
        location, _stmts, count = raw.rsplit(" ", 2)
        path, span = location.rsplit(":", 1)
        start, end = span.split(",")
        for line in range(int(start.split(".")[0]), int(end.split(".")[0]) + 1):
            _mark(cov, path, line, int(count) > 0)
    return cov


def _cobertura(root: ET.Element) -> Coverage:
    cov: Coverage = {}
    sources = [s.text.strip() for s in root.iter("source") if s.text]
    for cls in root.iter("class"):
        name = cls.get("filename", "")
        paths = [name] + [f"{src.rstrip('/')}/{name}" for src in sources]
        for line in cls.iter("line"):
            hit = int(line.get("hits", "0")) > 0
            for path in paths:
                _mark(cov, path, int(line.get("number", "0")), hit)
    return cov


def _jacoco(root: ET.Element) -> Coverage:
    cov: Coverage = {}
    for package in root.iter("package"):
        for sourcefile in package.iter("sourcefile"):
            package_dir, name = package.get("name", ""), sourcefile.get("name", "")
            path = f"{package_dir}/{name}" if package_dir else name
            for line in sourcefile.iter("line"):
                _mark(cov, path, int(line.get("nr", "0")), int(line.get("ci", "0")) > 0)
    return cov


def _clover(root: ET.Element) -> Coverage:
    cov: Coverage = {}
    for file in root.iter("file"):
        path = file.get("path") or file.get("name", "")
        for line in file.iter("line"):
            if line.get("type") == "method":
                continue
            _mark(cov, path, int(line.get("num", "0")), int(line.get("count", "0")) > 0)
    return cov


def parse_xml(text: str) -> Coverage:
    root = ET.fromstring(text)
    if root.tag == "report":
        return _jacoco(root)
    if root.find("project") is not None:
        return _clover(root)
    return _cobertura(root)


def load(path: str | Path) -> Coverage:
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    stripped = text.lstrip()
    if stripped.startswith("<"):
        return parse_xml(stripped)
    if stripped.startswith("mode:"):
        return parse_go_profile(stripped)
    return parse_lcov(text)


def _same_file(a: str, b: str) -> bool:
    return a == b or a.endswith("/" + b) or b.endswith("/" + a)


class CoverageIndex:
    """Look up coverage for a source file even when the report uses a different path prefix."""

    def __init__(self, cov: Coverage) -> None:
        self._by_path = {Path(k).as_posix(): v for k, v in cov.items()}

    def lines_for(self, source: str | Path) -> dict[int, bool] | None:
        candidates = (Path(source).as_posix(), Path(source).resolve().as_posix())
        best: tuple[int, dict[int, bool]] | None = None
        for key, lines in self._by_path.items():
            if any(_same_file(key, c) for c in candidates) and (best is None or len(key) > best[0]):
                best = (len(key), lines)
        return best[1] if best else None
