# Wiring the gates into the agent's loop

A gate only shapes agent behaviour if the agent hits it *while working*, not after a
human reviews the PR. Wire the same `quality` command into three layers, from fastest
feedback to hardest enforcement, and protect the gate configuration itself.

## Contents

1. One command, split fast and full
2. Vendor the scripts into the repo
3. Layer 1: Claude Code hooks
4. Layer 2: pre-commit
5. Layer 3: CI
6. Protecting the gates from the agent
7. Ratchets and baselines (existing codebases)
8. Telling every agent the budgets
9. Speed budgets for the gates themselves

---

## 1. One command, split fast and full

Define two entry points in whatever task runner the stack uses (Makefile, npm
scripts, justfile, nox, Gradle/Maven task, `mix` alias):

- **`quality-fast`**: format check, lint (complexity, cognitive, params, nesting, file
  length), type check, the bundled scripts without coverage, and the unit tests. Target
  under about 60 seconds, because it runs on every agent stop and every commit.
- **`quality`**: everything in `quality-fast`, plus full coverage at 100%, CRAP from the
  coverage report, dead code, duplication, dependency checks, and mutation testing on
  changed code. Runs in CI.

Example Makefile skeleton (adapt the tool lines from the language reference):

```make
S := tools/quality            # vendored copies of the skill's scripts
SRC := src

quality-fast:
	<formatter> --check .
	<linter> .                                    # complexity, cognitive, params, nesting
	<type checker>
	python $(S)/loc_budget.py $(SRC) tests
	python $(S)/complexity_gate.py $(SRC) --params-max 5 --nloc-max 50
	python $(S)/halstead_gate.py $(SRC)
	python $(S)/comment_density.py $(SRC)
	python $(S)/suppression_audit.py . --zero skipped coverage --baseline .quality/suppressions.json
	<unit tests>

quality: quality-fast
	<tests with coverage, fail under 100 line+branch, write lcov/cobertura>
	python $(S)/complexity_gate.py $(SRC) --coverage <report>      # CRAP < 25
	<dead code tool>
	<duplication tool, e.g. npx jscpd --threshold 0 $(SRC)>
	<unused dependency tool>
	<mutation tool, changed files only>

.PHONY: quality quality-fast
```

On a new project, drop the `--baseline` flag and use `--zero` for every category
you want held at zero from day one (typically `coverage mutation skipped any-type todo`).

## 2. Vendor the scripts into the repo

CI machines and teammates don't have `~/.claude/skills/`. Copy the scripts the
project uses into the repo (for example `tools/quality/`), keep `_files.py` and
`coverage_formats.py` alongside them, and add their pip dependencies (`lizard`,
`radon`, `multimetric`) to the project's dev dependencies. Commit them. They are
then part of the project's own quality tooling.

## 3. Layer 1: Claude Code hooks

Two hooks in the project's `.claude/settings.json` (committed, so every Claude
session on the repo gets them). They change Claude Code settings, so add them with
the `update-config` skill or show the user the JSON first.

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          { "type": "command", "command": "${CLAUDE_PROJECT_DIR}/.claude/hooks/lint-file.sh", "timeout": 60 }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          { "type": "command", "command": "${CLAUDE_PROJECT_DIR}/.claude/hooks/quality-gate.sh", "timeout": 600 }
        ]
      }
    ]
  }
}
```

How these behave (per the Claude Code hooks docs):
- Hook input arrives as JSON on stdin. For `Edit` and `Write`, `tool_input.file_path` is
  the edited file.
- **Exit code 2** sends the hook's stderr back to Claude. For PostToolUse the edit has
  already happened, so Claude sees the lint errors and fixes them right away. For Stop,
  Claude is prevented from finishing and continues working.
- Stop input includes `stop_hook_active: true` when Claude is already continuing
  because of a Stop hook. Claude Code ends the turn anyway after 8 consecutive
  Stop-hook continuations (configurable with `CLAUDE_CODE_STOP_HOOK_BLOCK_CAP`), so a
  gate that can't be met won't loop forever.

`.claude/hooks/lint-file.sh`: fast, per-file feedback on every edit.

```bash
#!/usr/bin/env bash
# PostToolUse: lint the file Claude just edited. Exit 2 = errors go back to Claude.
set -uo pipefail
file=$(python3 -c 'import json,sys; print(json.load(sys.stdin).get("tool_input", {}).get("file_path", ""))')
if [ -z "$file" ] || [ ! -f "$file" ]; then exit 0; fi
cd "${CLAUDE_PROJECT_DIR}" || exit 0

case "$file" in
  *.py)                     out=$(ruff check --quiet "$file" 2>&1 && ruff format --check --quiet "$file" 2>&1) ;;
  *.ts|*.tsx|*.js|*.jsx|*.mjs|*.cjs)
                            out=$(npx --no-install eslint --max-warnings 0 "$file" 2>&1) ;;
  *.go)                     out=$(golangci-lint run "./$(dirname "${file#"${CLAUDE_PROJECT_DIR}"/}")/..." 2>&1) ;;
  *.rb)                     out=$(bundle exec rubocop --format simple "$file" 2>&1) ;;
  *.php)                    out=$(vendor/bin/phpstan analyse --no-progress --error-format=raw "$file" 2>&1) ;;
  *)                        exit 0 ;;
esac
status=$?
loc=$(python3 tools/quality/loc_budget.py "$file" 2>&1) || { out="$out"$'\n'"$loc"; status=1; }

if [ "$status" -ne 0 ]; then
  { echo "Quality gate failed for $file. Fix the code; do not add suppressions or loosen config."; echo "$out" | tail -n 40; } >&2
  exit 2
fi
exit 0
```

Languages whose linters work per project rather than per file (JVM, .NET, Rust) are
too slow for a per-edit hook. Leave them to the Stop hook.

`.claude/hooks/quality-gate.sh`: run the fast gates before Claude says it's done.

```bash
#!/usr/bin/env bash
# Stop: run quality-fast before Claude finishes, but only if the working tree changed.
set -uo pipefail
cd "${CLAUDE_PROJECT_DIR}" || exit 0
if [ -z "$(git status --porcelain 2>/dev/null)" ]; then exit 0; fi

if out=$(make quality-fast 2>&1); then exit 0; fi
{
  echo "quality-fast failed. Fix the code so the gates pass."
  echo "Do not loosen thresholds, add suppressions, skip tests or edit baselines."
  echo "If a gate genuinely cannot be met, stop and explain the conflict to the user."
  echo "$out" | tail -n 60
} >&2
exit 2
```

Make both scripts executable (`chmod +x .claude/hooks/*.sh`).

## 4. Layer 2: pre-commit

Run `quality-fast` (or its staged-files equivalent) on every commit, for humans and
for agents that commit. Pick the framework the stack already uses.

**pre-commit** (Python-centric, works for any language with local hooks):

```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: quality-fast
        name: quality gates (fast)
        entry: make quality-fast
        language: system
        pass_filenames: false
        stages: [pre-commit]
```

`pre-commit install` once per clone.

**lefthook** (single binary, polyglot, parallel):

```yaml
# lefthook.yml
pre-commit:
  parallel: true
  commands:
    lint-ts:
      glob: "*.{ts,tsx,js,jsx}"
      run: npx eslint --max-warnings 0 {staged_files}
    lint-py:
      glob: "*.py"
      run: ruff check {staged_files} && ruff format --check {staged_files}
    budgets:
      run: python tools/quality/loc_budget.py {staged_files}
pre-push:
  commands:
    quality-fast:
      run: make quality-fast
```

`lefthook install` once per clone.

**husky + lint-staged** (Node projects):

```json
// package.json (excerpt)
{
  "scripts": { "prepare": "husky", "quality:fast": "make quality-fast" },
  "lint-staged": {
    "*.{ts,tsx,js,jsx}": ["eslint --max-warnings 0", "prettier --check"],
    "*.{css,scss}": ["stylelint"]
  }
}
```

`.husky/pre-commit` contains `npx lint-staged` and then `npm run quality:fast`.

`git commit --no-verify` skips every pre-commit framework. That is why CI (layer 3)
is the real gate, and why the agent rules say never to use `--no-verify`.

## 5. Layer 3: CI

CI runs the full `quality` on every PR and push to the main branch, and is a
**required status check** in branch protection. Generic GitHub Actions shape:

```yaml
# .github/workflows/quality.yml
name: quality
on:
  pull_request:
  push:
    branches: [main]
jobs:
  quality:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0            # diff-based gates (changed-file mutation, diff coverage) need history
      # - language setup + dependency cache steps from the language reference
      - run: make quality
        env:
          BASE_REF: origin/${{ github.base_ref || 'main' }}
      - name: Guard gate configuration
        if: github.event_name == 'pull_request'
        run: |
          changed=$(git diff --name-only "origin/${{ github.base_ref }}...HEAD" -- \
            .quality/ tools/quality/ .claude/settings.json .claude/hooks/ \
            eslint.config.* biome.json* pyproject.toml ruff.toml .golangci.yml .rubocop.yml \
            phpstan.neon* detekt.yml .editorconfig Directory.Build.props stryker* clippy.toml)
          if [ -n "$changed" ]; then
            echo "Gate configuration changed:"; echo "$changed"
            echo "A human must review these diffs for loosened thresholds or new exclusions."
            exit 1
          fi
  mutation-nightly:
    if: github.event_name == 'schedule'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      # full (non-incremental) mutation run over the whole codebase
```

Add `schedule: - cron: "0 3 * * *"` under `on:` for the nightly job. The config
guard fails on *any* change to gate files, including legitimate dependency bumps in
`pyproject.toml`. Narrow it to the threshold sections the project actually uses, or
replace the hard fail with a required label (for example `quality-config-approved`).

## 6. Protecting the gates from the agent

Agents under pressure edit whatever stands between them and green. Close the easy
paths:

1. **Claude Code deny rules** in the project's `.claude/settings.json`. A leading `/`
   anchors the path at the project root, and `Edit` rules cover every built-in
   file-editing tool:

   ```json
   {
     "permissions": {
       "deny": [
         "Edit(/.quality/**)",
         "Edit(/tools/quality/**)",
         "Edit(/.claude/hooks/**)",
         "Edit(/.claude/settings.json)",
         "Edit(/eslint.config.js)",
         "Edit(/.golangci.yml)"
       ]
     }
   }
   ```

   List the project's actual gate files. Deny rules don't stop shell commands (`sed`,
   `cat >`), so they are a guard rail, not a lock. The CI config guard and CODEOWNERS
   are the lock.
2. **CODEOWNERS** on the gate files so a human must approve changes:
   ```
   /.quality/                @team-leads
   /tools/quality/           @team-leads
   /.claude/                 @team-leads
   /eslint.config.js         @team-leads
   ```
3. **The suppression ratchet** (`suppression_audit.py --baseline` in CI) so new
   `noqa` / `eslint-disable` / `pragma: no cover` / skipped tests fail the build.
4. **Branch protection**: CI `quality` required, no force-push, no admin bypass for agents'
   tokens.
5. **The rules in CLAUDE.md/AGENTS.md** (section 8). They prevent most attempts before
   they happen.

## 7. Ratchets and baselines (existing codebases)

A ratchet lets a legacy codebase adopt the full budgets immediately for new code while
the old violations are paid down. The pattern:

1. Record today's violations in a committed baseline file.
2. CI fails on any violation **not** in the baseline, and on any baseline that grew.
3. When a violation is fixed, regenerate the baseline (it only ever shrinks), and the
   fix can't silently regress.

Built-in support by tool (details in the language references): `suppression_audit.py
--write-baseline/--baseline` (all languages), complexipy `--snapshot-create`,
basedpyright baseline, ESLint bulk suppressions / betterer, golangci-lint
`new-from-rev` / `new-from-merge-base`, detekt `--create-baseline`, RuboCop
`--auto-gen-config`, PHPStan `--generate-baseline`, Psalm `--set-baseline`, Sonar
"new code" period, diff-cover / diff-only coverage, and mutation tools' `--since` /
incremental / `--in-diff` modes.

Rules: a baseline may only shrink, every baseline file is CODEOWNED, and the cleanup
plan says when each baseline reaches zero.

## 8. Telling every agent the budgets

Write the "Quality budgets" block from SKILL.md (Path A, step A5) into:
- `CLAUDE.md`, which Claude Code reads at the start of every session
- `AGENTS.md`, read by Codex, Cursor, Copilot agents, Jules, Amp and others (link one
  file from the other to keep a single copy)
- the PR template, as a checklist for humans

Keep it to about 15 lines: the budgets, the one command, and the never-do list.
Agents read the whole thing, and long policy documents get skimmed.

## 9. Speed budgets for the gates themselves

Slow gates get bypassed. Rough targets:

| Layer | Target | Keep it fast by |
|---|---|---|
| PostToolUse hook | < 5 s per edit | linting only the edited file or package |
| Stop hook / pre-commit | < 60 s | `quality-fast` only; parallel jobs; caches |
| CI `quality` | < 15 min | dependency caches, test sharding, mutation on changed files only |
| Nightly | whatever it takes | full mutation run, full dead-code and dependency scans |

If a layer exceeds its target, move checks to a later layer. Never delete them.
