"""Shared file discovery for the gate scripts.

Uses `git ls-files` when run inside a git repo (so .gitignore is respected and
untracked-but-not-ignored files are included), and falls back to walking the
tree otherwise. Generated/vendored directories are always skipped.
"""

from __future__ import annotations

import fnmatch
import subprocess
from pathlib import Path

SOURCE_EXTS = frozenset(
    {
        ".py", ".pyi",
        ".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".mts", ".cts", ".vue", ".svelte",
        ".go",
        ".java", ".kt", ".kts", ".scala", ".groovy",
        ".cs", ".fs", ".vb",
        ".rb", ".erb", ".rake", ".rbs",
        ".php",
        ".rs",
        ".swift", ".m", ".mm",
        ".ex", ".exs",
        ".c", ".h", ".cc", ".cpp", ".cxx", ".hpp",
        ".lua", ".dart",
        ".css", ".scss", ".sass", ".less",
    }
)

SKIP_DIRS = frozenset(
    {
        ".git", "node_modules", "vendor", ".venv", "venv", "env", "dist", "build",
        "target", "out", "obj", "bin", "coverage", "mutants", "htmlcov", ".next",
        ".nuxt", ".svelte-kit", "__pycache__", ".mypy_cache", ".ruff_cache",
        ".pytest_cache", ".tox", ".nox", ".gradle", ".idea", ".vscode",
        ".stryker-tmp", "reports",
    }
)


def _git_files(roots: list[str]) -> list[Path] | None:
    cmd = ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard", "--", *roots]
    try:
        out = subprocess.run(cmd, capture_output=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return None
    return [Path(p) for p in out.decode().split("\0") if p]


def _walk(roots: list[str]) -> list[Path]:
    found: list[Path] = []
    for root in map(Path, roots):
        if root.is_file():
            found.append(root)
            continue
        found.extend(p for p in root.rglob("*") if p.is_file())
    return found


def _skipped(path: Path, exclude: list[str]) -> bool:
    if any(part in SKIP_DIRS for part in path.parts[:-1]):
        return True
    posix = path.as_posix()
    return any(fnmatch.fnmatch(posix, pat) for pat in exclude)


def list_files(
    roots: list[str],
    exts: frozenset[str] | set[str] = SOURCE_EXTS,
    exclude: list[str] | None = None,
) -> list[Path]:
    """Return source files under `roots`, filtered by extension and exclude globs."""
    roots = roots or ["."]
    candidates = _git_files(roots)
    if candidates is None:
        candidates = _walk(roots)
    patterns = exclude or []
    return sorted(
        p for p in candidates if p.suffix in exts and p.is_file() and not _skipped(p, patterns)
    )


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")
