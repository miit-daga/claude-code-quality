"""Is this change only formatting? (code-quality skill: references/agent-loop.md, "Adopting a formatter")

Running the formatter over old code changes thousands of lines the PR did not really write, and the
changed-line checks (quality rules, size limits, coverage) would judge all of them. CI skips those checks
only when this script proves that every changed file under the current directory is a Python file whose new content is
exactly `ruff format` applied to its own version at the merge base. Anything else (an added, deleted or
renamed file of any type, a change to the formatter settings, any other changed file) means "false", so a
real code change cannot pass as formatting.

Usage (from the Python project root, where pyproject.toml is): python format_only_ruff.py [--base origin/main]
In CI, run the BASE branch's copy (git show origin/$BASE:path/to/format_only_ruff.py > $RUNNER_TEMP/...) with
`python -I`, so a PR cannot change the check it is judged by.
Prints "true" or "false" on stdout and the reason on stderr. Any git or ruff error prints "false", so
the checks run as usual.
"""

import argparse
import subprocess
import sys
from pathlib import Path

# Files whose change could alter what `ruff format` produces; a PR that touches them is never "formatting only".
FORMATTER_SETTINGS = {"pyproject.toml", "ruff.toml", ".ruff.toml", "requirements-dev.txt"}


def _run(cmd: list[str], stdin: bytes | None = None) -> bytes:
    return subprocess.run(cmd, input=stdin, check=True, capture_output=True).stdout


def changed_files(base: str) -> list[tuple[str, str]]:
    """(status, path) of every file that differs between the merge base with `base` and the working tree,
    paths relative to the current directory. Renames count as a delete plus an add."""
    out = _run(["git", "diff", "--merge-base", base, "--name-status", "--no-renames", "--relative", "-z"])
    parts = out.decode("utf-8").split("\0")
    return [(parts[i], parts[i + 1]) for i in range(0, len(parts) - 1, 2)]


def formatted(source: bytes, path: str) -> bytes:
    """`source` after `ruff format`, with the settings that apply to `path` (pyproject.toml / ruff.toml). `-I` keeps
    Python from importing anything from the working directory, so a file in the PR cannot stand in for ruff."""
    return _run([sys.executable, "-I", "-m", "ruff", "format", "--stdin-filename", path, "-"], stdin=source)


def _not_formatting(status: str, path: str) -> str | None:
    """Why this changed file alone rules out "formatting only", or None when it may be a formatting change."""
    if status != "M":
        return f"{path}: added, deleted or renamed ({status})"
    if Path(path).name in FORMATTER_SETTINGS:
        return f"{path}: formatter settings changed"
    if not path.endswith(".py"):
        return f"{path}: not a Python file"
    return None


def check(base: str) -> tuple[bool, str]:
    files = changed_files(base)
    if not files:
        return True, "no file changed"
    for status, path in files:
        if reason := _not_formatting(status, path):
            return False, reason
    merge_base = _run(["git", "merge-base", base, "HEAD"]).decode().strip()
    for _, path in files:
        old = _run(["git", "show", f"{merge_base}:./{path}"])
        if formatted(old, path) != Path(path).read_bytes():
            return False, f"{path}: differs from its formatted base version"
    return True, f"{len(files)} Python files changed, all only by ruff format"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base", default="origin/main")
    args = parser.parse_args(argv)
    try:
        only, reason = check(args.base)
    except (subprocess.CalledProcessError, OSError, UnicodeDecodeError) as e:
        only, reason = False, f"could not check ({e}); running the changed-line checks"
    print("true" if only else "false")
    print(f"formatting only: {reason}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
