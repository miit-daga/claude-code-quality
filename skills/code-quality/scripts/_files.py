"""Shared file discovery for the gate scripts.

Uses `git ls-files` when run inside a git repo (so .gitignore is respected and
untracked-but-not-ignored files are included), and falls back to walking the
tree otherwise. Generated/vendored directories are always skipped.
"""

from __future__ import annotations

import fnmatch
import subprocess
import sys
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

# Never source code: dependencies, virtualenvs, VCS metadata and tool caches.
ALWAYS_SKIP = frozenset(
    {
        ".git", "node_modules", "vendor", ".venv", "venv", "__pycache__", ".mypy_cache",
        ".ruff_cache", ".pytest_cache", ".tox", ".nox", ".gradle", ".idea", ".vscode",
        ".stryker-tmp", ".next", ".nuxt", ".svelte-kit", "htmlcov",
    }
)
# Usually build output, but also legitimate source names (a Django `reports` app, a
# `bin/` of scripts). Inside a git repo .gitignore decides; these apply only when
# walking a directory that is not under git, and a warning names what was skipped.
WALK_ONLY_SKIP = frozenset({"env", "dist", "build", "target", "out", "obj", "bin", "coverage", "mutants", "reports"})


Candidate = tuple[Path, tuple[str, ...]]  # (path, directory parts below the root it was found under)


def _git_files(roots: list[str]) -> list[Candidate] | None:
    cmd = ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard", "--", *roots]
    try:
        out = subprocess.run(cmd, capture_output=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return None
    paths = [Path(p) for p in out.decode().split("\0") if p]
    return [(p, p.parts[:-1]) for p in paths]


def _walk(roots: list[str]) -> list[Candidate]:
    found: list[Candidate] = []
    for root in map(Path, roots):
        if root.is_file():
            found.append((root, ()))
            continue
        found.extend((p, p.relative_to(root).parts[:-1]) for p in root.rglob("*") if p.is_file())
    return found


def _skip_reason(path: Path, dirs: tuple[str, ...], skip_dirs: frozenset[str], exclude: list[str]) -> str | None:
    hit = next((part for part in dirs if part in skip_dirs), None)
    if hit:
        return hit
    posix = path.as_posix()
    return "--exclude" if any(fnmatch.fnmatch(posix, pat) for pat in exclude) else None


def list_files(
    roots: list[str],
    exts: frozenset[str] | set[str] = SOURCE_EXTS,
    exclude: list[str] | None = None,
) -> list[Path]:
    """Return source files under `roots`, filtered by extension and exclude globs."""
    roots = roots or ["."]
    candidates = _git_files(roots)
    skip_dirs = ALWAYS_SKIP
    if candidates is None:
        candidates = _walk(roots)
        skip_dirs = ALWAYS_SKIP | WALK_ONLY_SKIP
    patterns = exclude or []
    kept, walk_skipped = [], set()
    for p, dirs in candidates:
        if p.suffix not in exts or not p.is_file():
            continue
        reason = _skip_reason(p, dirs, skip_dirs, patterns)
        if reason is None:
            kept.append(p)
        elif reason in WALK_ONLY_SKIP:
            walk_skipped.add(reason)
    if walk_skipped:
        print(
            f"note: not a git repo, so directories named {sorted(walk_skipped)} were skipped as likely "
            "build output. Run inside the git repo, or pass those directories explicitly, to check them.",
            file=sys.stderr,
        )
    return sorted(kept)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")
