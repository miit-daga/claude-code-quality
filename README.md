# code-quality: quality gates for agent-written code

A [Claude Code](https://code.claude.com) plugin with two skills:

- **`code-quality`** sets up machine-checked quality gates on a project from day one,
  before the first feature is written. After that, every change Claude (or anyone else)
  makes has to pass them.
- **`quality-tool-picker`** researches the current options for one tooling slot (a Java
  formatter, a Python type checker, a retry library) on the web, compares them with
  sources, and records the choice you make.

It's most useful for personal projects and teams without an org-wide toolkit. If your
org already ships shared lint configs, templates or standard libraries, the skill adopts
those as the baseline and only adds what's missing.

Coding agents optimise for whatever feedback loop they're given. A rule like "no
function above cyclomatic complexity 21" or "tests must kill 80% of mutants" would be tiresome
for a person, but it costs an agent nothing and steers it toward smaller, simpler,
better-tested code. This skill turns those rules into automated checks and wires them
in where an agent can't skip them.

## What it enforces

There are two profiles. **Standard** is the default. **Strict** is opt-in, for libraries,
safety-critical code or a critical core module.

| Gate | Standard | Strict |
|---|---|---|
| Cyclomatic complexity per function | < 22 | < 22 |
| Cognitive complexity per function | < 22 | < 22 |
| Halstead difficulty per function | < 80 | < 80 |
| Lines per file | < 500 | < 500 |
| Test coverage (line **and** branch), project-wide and on changed lines | ≥ 70% | 100% |
| CRAP per function | < 25 | < 25 |
| Mutation score on covered, changed code | ≥ 80% | 0 surviving mutants |
| Dead code | 0 | 0 |
| Duplicated / redundant code | 0 | 0 |
| `any` / `unknown` and equivalents | 0 (except catch variables and the raw input of a boundary schema parser) | same |

Coverage is a floor, not a quality measure: it shows code ran, not that a test checked
the result. Test quality is gated by the mutation score instead, measured on covered code
so it doesn't repeat coverage. Per-file Halstead scores outside Python are advisory
unless you set a per-file budget.

**Cross-cutting conventions.** One sanctioned way each to call other services, retry,
time out, log and report errors, enforced by lint and architecture rules, instead of a
different pattern in every module.

It also offers optional gates: ABC size, function length (≤ 60 lines, or ≤ 100 in
Java, Kotlin, C# and PHP, where logging makes methods long without making them
complex), parameter count, nesting depth, CSS/JS size budgets, comment density (no narrating or commented-out code), and a
suppression ratchet that fails the build when `noqa` / `eslint-disable` /
`pragma: no cover` / skipped tests increase. It writes the project's invariants to
`INVARIANTS.md` and enforces each one with a type, a database constraint, a lint rule
or a test, and gives guidance on when formal methods are worth using.

## What it does when you run it

**New project (the main use).** It confirms the stack with you, then:
1. adds the tool configs and one `quality` command that runs every gate, fastest first
2. wires that command into three layers:
   - a Claude Code PostToolUse hook that lints each edited file
   - a Stop hook that runs the fast gates before Claude says it's done
   - pre-commit, plus CI
3. writes the budgets into the project's `CLAUDE.md` / `AGENTS.md`, so later sessions
   follow them without loading the skill
4. plants deliberate violations to prove each gate actually fails, then removes them

**Existing codebase.** It measures every gate first, installs the gates in *ratchet
mode* (new code is gated fully, and old violations can only go down), then cleans up
in order: delete dead code, remove slop, pin behaviour with tests, fix types,
deduplicate, converge the ways it calls services, retries and logs, cut complexity,
reach the coverage floor, raise the mutation score.

It also blocks the common ways an agent games a gate: loosening thresholds, blanket
suppressions, skipped tests, splitting a function just to pass a metric, and editing
the gate config itself. The last is enforced with Claude Code permission deny rules
and a CI guard.

## What this plugin does on your machine

**Installing it does nothing on its own.** The plugin contains two skills and a few
Python scripts. It has no hooks, no MCP servers and no background processes, and it
never changes your user-level `~/.claude/settings.json`. `code-quality` is manual-only,
so it runs only when you invoke it. `quality-tool-picker` uses the web (see below).

**When you run it on a project,** Claude first proposes a plan (the tools, the gates
and the files involved) and asks for your approval. After you approve, it changes only
that project:

- **`.claude/settings.json` in the project** gets:
  - two hooks: PostToolUse runs `.claude/hooks/lint-file.sh` on each file Claude edits,
    and Stop runs `.claude/hooks/quality-gate.sh` before Claude finishes, so failing
    gates are reported back to Claude
  - permission **deny** rules that stop Claude from editing the gate configuration, for
    example `Edit(/eslint.config.js)`, `Edit(/.claude/hooks/**)`,
    `Edit(/tools/quality/**)`, and optionally running `git commit --no-verify`

  These rules only restrict Claude in that project. They never grant extra permissions.
- **Tooling:** linter, test and mutation-testing configs, a `quality` command, and dev
  dependencies installed with the project's own package manager (from npm, PyPI, etc.)
- **Scripts:** the bundled scripts are copied into the project's `tools/quality/`, so
  CI and teammates can run them
- **Git hooks:** set up through the project's pre-commit tool (lefthook, husky or
  pre-commit). This can set `core.hooksPath` in the project's `.git/config`
- **Other files:** a CI workflow file, plus `CLAUDE.md` / `AGENTS.md`, `INVARIANTS.md`
  and `CONVENTIONS.md`, and baselines under `.quality/`
- **Test fixtures:** temporary files used to prove each gate fails, deleted afterwards

**`quality-tool-picker`** uses Claude Code's web search and fetch tools to research tool
options, so the search queries (the tooling slot and your stack, such as "Java formatter
Gradle 9") go to the web. It writes one decision record (`docs/adr/…`) after you choose.

The bundled scripts read the files you point them at, list files with `git ls-files`,
and the Halstead script runs the locally installed `multimetric`. They make no network
calls, send no data anywhere, and store nothing outside the project. Every change is an
ordinary file in your project, so you can review it in the diff and revert it with git.

## Languages

Python, Node.js / TypeScript, Go, Java / Kotlin, C# / .NET, Ruby / Rails (including
ERB via Herb), PHP, Rust, plus Elixir, Scala, Swift and C/C++. Each language has a
reference file with complete from-scratch configs. The bundled scripts cover any
language [lizard](https://github.com/terryyin/lizard) can parse.

## Install

As a plugin (recommended):

```
/plugin marketplace add miit-daga/claude-code-quality
/plugin install code-quality@miit-daga
```

Or as personal skills: copy `skills/code-quality/` and `skills/quality-tool-picker/` into
`~/.claude/skills/`.

## Use

The skill is **manual-only** (`disable-model-invocation: true`). Claude never starts it
on its own. Run it explicitly:

- plugin install: `/code-quality:code-quality`
- personal install: `/code-quality`

For example:

```
/code-quality:code-quality I'm starting a new TypeScript REST API (Fastify, Postgres later).
Set up the quality gates before we write any features.
```

`quality-tool-picker` is not manual-only. Claude uses it when you ask to choose between
tools, and `code-quality` hands tool choices to it instead of picking silently. It
searches the web, so it needs Claude Code's web tools.

## Bundled scripts

The scripts live in `skills/code-quality/scripts/`. They need Python 3.10+, plus
`pip install lizard radon multimetric` for the complexity and Halstead scripts. Each
exits 1 on failure:

| Script | Checks |
|---|---|
| `loc_budget.py` | lines per file, and optional byte budgets for CSS/JS |
| `complexity_gate.py` | cyclomatic and cognitive complexity per function, params, length, and **CRAP**. CRAP is computed from lcov, Cobertura, JaCoCo, Clover or Go coverage reports |
| `halstead_gate.py` | Halstead difficulty |
| `mutation_score.py` | mutation score from Stryker, PIT, mutmut, gremlins or cargo-mutants reports, on covered code or total; fails when changed code has no tested mutants |
| `convention_census.py` | counts each way the code calls services, retries and logs, per module, with a baseline that may only shrink |
| `comment_density.py` | comment ratio, narrating comments, commented-out code |
| `suppression_audit.py` | lint, coverage and mutation suppressions, skipped tests, `any`-style types and TODOs across languages, with a baseline that may only shrink |

The skill copies the scripts into each project (`tools/quality/`) so CI and teammates
have them.

## Evaluation

Version 1.0 of the skill (whose defaults match today's Strict profile) was compared with
a baseline run without it on one task: "bootstrap a new
TypeScript API". A grader planted 10 violations in each resulting project and checked
whether the project's own gates caught them:

| | With skill | Without |
|---|---|---|
| Planted violations caught | 10 / 10 | 6 / 10 |
| All checks (incl. hooks, CI, agent docs, invariants) | 18 / 18 | 11 / 18 |

The baseline missed a test that ran code without checking the result (only mutation
testing catches that), copy-paste duplication, `unknown`, a bare `eslint-disable`, and
commented-out code. This is a single scenario with one run per side, so treat it as a
sanity check, not a benchmark.

The Python and TypeScript configs were run end to end. The Go, Rust, JVM, .NET, Ruby
and PHP configs were checked against official documentation but not run; details that
couldn't be verified are marked "verify for your version" in the reference files.

## License

MIT
