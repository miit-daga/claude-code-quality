# code-quality: strict quality gates for agent-written code

A [Claude Code](https://code.claude.com) skill that sets up strict quality gates on a
project from day one, before the first feature is written. After that, every change
Claude (or anyone else) makes has to pass them.

Coding agents optimise for whatever feedback loop they're given. A rule like "no
function above cyclomatic complexity 21" or "every mutant must die" would be tiresome
for a person, but it costs an agent nothing and steers it toward smaller, simpler,
better-tested code. This skill turns those rules into automated checks and wires them
in where an agent can't skip them.

## What it enforces

| Gate | Budget |
|---|---|
| Cyclomatic complexity per function | < 22 |
| Cognitive complexity per function | < 22 |
| Halstead difficulty | < 80 |
| Lines per file | < 500 |
| Test coverage (line **and** branch) | 100% |
| CRAP per function | < 25 |
| Surviving mutants | 0 |
| Dead code | 0 |
| Duplicated / redundant code | 0 |
| `any` / `unknown` and equivalents | 0 |

It also offers optional gates: ABC size, function length, parameter count, nesting
depth, CSS/JS size budgets, comment density (no narrating or commented-out code), and a
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
deduplicate, cut complexity, reach full coverage, kill mutants.

It also blocks the common ways an agent games a gate: loosening thresholds, blanket
suppressions, skipped tests, splitting a function just to pass a metric, and editing
the gate config itself. The last is enforced with Claude Code permission deny rules
and a CI guard.

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

Or as a personal skill: copy `skills/code-quality/` to `~/.claude/skills/code-quality/`.

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

## Bundled scripts

The scripts live in `skills/code-quality/scripts/`. They need Python 3.10+, plus
`pip install lizard radon multimetric` for the complexity and Halstead scripts. Each
exits 1 on failure:

| Script | Checks |
|---|---|
| `loc_budget.py` | lines per file, and optional byte budgets for CSS/JS |
| `complexity_gate.py` | cyclomatic and cognitive complexity per function, params, length, and **CRAP**. CRAP is computed from lcov, Cobertura, JaCoCo, Clover or Go coverage reports |
| `halstead_gate.py` | Halstead difficulty |
| `comment_density.py` | comment ratio, narrating comments, commented-out code |
| `suppression_audit.py` | lint, coverage and mutation suppressions, skipped tests, `any`-style types and TODOs across languages, with a baseline that may only shrink |

The skill copies the scripts into each project (`tools/quality/`) so CI and teammates
have them.

## Evaluation

The skill was compared with a baseline run without it on one task: "bootstrap a new
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
