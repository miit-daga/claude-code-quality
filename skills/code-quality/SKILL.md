---
name: code-quality
description: >-
  Set up strict, machine-checked quality gates for a project from day one, so that AI agents
  cannot write slop into it: cyclomatic and cognitive complexity < 22, Halstead difficulty
  < 80, files < 500 lines, 100% line and branch coverage, CRAP < 25, zero surviving mutants,
  zero dead or duplicated code, zero any/unknown types, plus ABC size, CSS/JS size budgets,
  comment-density limits, suppression ratchets, explicit invariants and (where warranted)
  formal methods. Wires the gates into agent hooks, pre-commit and CI and writes the budgets
  into the project's CLAUDE.md/AGENTS.md. Can also bring an existing codebase up to the same
  gates. Covers Python, Node/TypeScript, Go, Java/Kotlin, C#/.NET, Ruby/Rails, PHP, Rust,
  and other languages. Manual only: run when the user types /code-quality.
disable-model-invocation: true
---

# Code quality gates

**Run this skill only when the user invokes it explicitly** by typing `/code-quality`.
Do not start it on your own initiative, even if a task looks related.

Agents optimise against whatever feedback loop they are given. A linter rule that
would feel draconian to a human ("no function above complexity 21", "no file over
500 lines", "every mutant must die") costs an agent nothing to obey and reliably
steers it toward simpler, smaller, better-tested code. Telling an agent "this must pass
the cyclomatic complexity lint" changes what it writes in the first place, not just
what it fixes afterwards.

The intended use is **at the start of a project**: install the gates before the first
feature, so every line is written under them and there is never any slop to clean up.
After that, the project carries the gates itself. Its CLAUDE.md/AGENTS.md lists the
budgets, and hooks, pre-commit and CI enforce them, so later sessions keep complying
without this skill being loaded again.

There are two paths:

- **Path A, new project (the default).** Bootstrap the gates on an empty or near-empty
  repo, prove they work, and hand over a project that enforces them on its own.
- **Path B, existing codebase.** Install the same gates, then clean up until the code
  passes them, using ratchets so nothing gets worse along the way.

Either way, the gates matter more than any cleanup. A cleanup without gates rots back
within weeks.

## The gates

Defaults the user asked for. Tighten freely; never loosen without the user's say-so.

| # | Gate | Budget | Why it helps with agent code |
|---|------|--------|------------------------------|
| 1 | Cyclomatic complexity (per function) | < 22 | Caps the number of paths; forces decomposition instead of `if` pile-ups |
| 2 | Cognitive complexity (per function) | < 22 | Penalises nesting and broken flow, which cyclomatic misses |
| 3 | Halstead difficulty (per function) | < 80 | Catches dense, operator-heavy code that is short but hard to read. Gated per function where the tool supports it (Python); per-file scores (other languages) are advisory unless the project calibrates a per-file budget |
| 4 | Lines per file | < 500 | Keeps every file loadable in one read, for humans and agents |
| 5 | Test coverage (line **and** branch) | 100% | No unexecuted code. Exclusions only for provably unreachable lines, each listed with a reason |
| 6 | CRAP per function | < 25 | Complexity × lack of coverage. Ranks what to test or simplify first |
| 7 | Surviving mutants | 0 | Proves tests check behaviour, not just execute lines |
| 8 | Dead code | 0 | Unused functions, exports, files, params, deps |
| 9 | Redundant code | 0 | Copy-paste duplication, no-op wrappers, re-implemented stdlib |
| 10 | `any` / `unknown` (and equivalents) | 0 | Untyped holes are where agents hide confusion. Two uses are allowed: catch variables, and the raw input of a schema parse in a designated boundary file |

**Extended gates ("what else").** Recommend these too, as suggested starting points
rather than hard requirements:

| Gate | Suggested budget | Notes |
|------|------------------|-------|
| ABC size (Assignments, Branches, Conditions) | ≤ 17 per method | Native in RuboCop and Credo. Elsewhere use lizard token count as a proxy |
| Function length | ≤ 50 NLOC | Long functions are where agents append "one more case" |
| Parameters | ≤ 5 | Pushes toward parameter objects and fewer boolean flags |
| Nesting depth | ≤ 3 | The main driver of cognitive complexity |
| Boolean expression operators | ≤ 3 per condition | Name the condition instead |
| CSS/JS byte budgets | per file and per bundle | When the budget is hit, have the agent prune before adding |
| Comment density | ≤ 0.25 comment lines per code line, no commented-out code; narrating comments are reported for review, not failed (the heuristic also flags some good "why" comments) | Agents narrate. Comments should explain *why* |
| Suppression ratchet | counts may only go down; no blanket suppressions | Stops gates being met by silencing them |
| Type coverage | 100% | `type-coverage`, mypy any-exprs report, etc. |
| Architecture boundaries | declared layers, no forbidden imports | import-linter, dependency-cruiser, ArchUnit, depguard, deptrac |
| Dependency budget | no unused deps; new runtime deps need approval | knip, deptry, cargo-machete, `go mod tidy` diff |
| No logic in tests | no `if`/loops in test bodies | Branching tests hide which case failed |
| Diff size per change | e.g. ≤ 400 changed lines per PR | Keeps agent changes reviewable |
| TODO/FIXME | 0 in main, or must reference an issue | Agents leave placeholders and move on |

Tools disagree on `>` vs `>=` and on how they count (Halstead especially). After
configuring any threshold, **verify the boundary**: write a throwaway function that
sits exactly at the limit and one just over, and confirm only the second fails.

## Which gates for which project

The full set is the default, and for a new project it costs least to adopt on day one.
Ask the user only if the project is clearly one of the exceptions:

- **Production service or library, new or existing**: the full set.
- **Prototype, research code, or notebooks**: a light subset only. Use complexity,
  file size, dead code, duplication and types. Skip 100% coverage and mutation
  testing. For notebooks, apply the gates to the `.py` modules the notebook imports,
  not to the notebook itself.
- **Generated code, vendored code, migrations, fixtures**: exclude them by path in
  every tool, and list the exclusions in one place.

## Path A: new project (gates before the first feature)

### A1. Pin down the stack

Read whatever already exists (scaffold, `package.json`, `pyproject.toml`, `go.mod`,
CI config). For anything not yet decided, ask the user: languages and frameworks,
package manager, test runner, CI provider, and whether there is a frontend (for the
CSS/JS budgets). Open the matching language reference(s) from the table at the end.

### A2. Agree the plan

Propose the gates (the full table above, plus any extended gates that fit), the dev
dependencies to add, and the three enforcement layers. Get a yes before installing,
because this adds dependencies, hooks and CI jobs. Mention the costs: mutation testing
takes real CI time even when it runs only on changed code.

### A3. Install the tools and one `quality` command

Add the config files from the language reference with the budgets filled in. Copy
the bundled scripts the project will use into the repo (for example `tools/quality/`,
including `_files.py` and `coverage_formats.py`) and add `lizard`, `radon` and
`multimetric` to its dev dependencies. CI and teammates don't have `~/.claude/skills/`.
Then
create **one command** that runs every gate, fast checks first: format check → lint
(complexity, cognitive, params, nesting, file length) → types → dead code and
duplication → tests with coverage → CRAP / Halstead / comment / suppression scripts →
mutation on changed code. Use whatever the stack already has: `make quality`,
`npm run quality`, `just quality`, a nox session, or a Gradle/Maven task. Everything
else (hooks, CI, CLAUDE.md) calls this command so there is a single source of truth.

### A4. Wire the three layers

Details and snippets are in `references/agent-loop.md`.

1. **Agent hook**: a Claude Code PostToolUse hook that lints each edited file, and a
   Stop hook that runs the fast gates before the agent says "done". Use the
   `update-config` skill (or show the user the JSON) to add these, since they change
   Claude Code settings.
2. **Pre-commit**: pre-commit / lefthook / husky+lint-staged on staged files.
3. **CI**: the full `quality` command on every push or PR, including coverage, mutation
   on changed code, and dead code. CI is the layer that can't be bypassed locally.

### A5. Write the budgets where agents will read them

Add this section (adapted to the stack) to the project's `CLAUDE.md` and/or
`AGENTS.md`. This is what keeps future sessions compliant without loading this skill:

```markdown
## Quality budgets (enforced by `make quality`, pre-commit and CI)

Every change must pass `make quality` before you say it is done.

- Functions: cyclomatic < 22, cognitive < 22, Halstead difficulty < 80, ≤ 5 params, nesting ≤ 3
- Files: < 500 lines. Split by responsibility, never by line count
- Tests: 100% line and branch coverage, CRAP < 25, zero surviving mutants on changed code.
  Every test asserts observable behaviour
- Zero dead code, zero duplication, zero `any`/`unknown`. Exceptions: catch variables, and the raw
  input of a schema parse in a boundary file
- Comments explain why, never what. No commented-out code, no TODOs without an issue link
- Never loosen a threshold, add a blanket suppression, skip a test, or grow a baseline to get
  green. If a budget looks wrong, stop and ask. A genuine exception (an equivalent mutant, a
  named suppression with a reason) grows the suppression baseline only with the user's approval
- Invariants are listed in INVARIANTS.md. Each one is enforced by a type, a constraint, a lint
  rule or a test. Do not remove an enforcement.
```

Also create `INVARIANTS.md` with the invariants the user already knows (see
"Invariants" below). It will grow as the project does.

### A6. Prove the gates bite

An empty repo passes every gate trivially, so green proves nothing yet. Add throwaway
fixtures that should each fail exactly one gate, and confirm each gate fails:

- a function with cyclomatic complexity 22, and one at 21 that must pass (this checks
  the `>` vs `>=` boundary)
- a deeply nested function (cognitive), a 500-line file, a 6-parameter function
- an uncovered branch, and a test that runs the code without asserting (mutation)
- an unused export or function, a copy-pasted block, an `any`
- commented-out code and a blanket suppression (both must fail), and a narrating comment
  (must appear in the comment report; narration is reported, not failed)

Then delete the fixtures and confirm everything is green again. Run this through every
layer you wired (hook, pre-commit, CI) at least once. Report which gates you proved
and any you could not trigger.

### A7. Hand over

Report what was installed, the `quality` command and its runtime, the files touched,
and the proven gates. From here on, normal feature work runs under the gates. This
skill does not need to be invoked again unless the user wants to change the gates or
audit the project.

## Path B: existing codebase (install gates, then clean up)

### B1. Survey (read-only)

Identify languages, package managers, test runners, existing lint/format/type
config, CI provider, pre-commit setup, and whether this is a git repo. Read the
config before proposing anything, because existing settings may already encode the
team's decisions. Open the matching language reference(s).

### B2. Baseline scoreboard (read-only)

Measure every gate before changing anything. The bundled scripts work across
languages. Run them with a Python that has `lizard`, `radon` and `multimetric`
installed (`pip install lizard radon multimetric`):

```bash
S=<skill-dir>/scripts                  # <skill-dir>: this skill's base directory
python $S/loc_budget.py src                               # gate 4 (+ --max-bytes for CSS/JS budgets)
python $S/complexity_gate.py src --coverage <report>      # gates 1, 2 and 6, plus --params-max / --nloc-max
python $S/halstead_gate.py src                            # gate 3
python $S/comment_density.py src                          # comment density, narration, commented-out code
python $S/suppression_audit.py src                        # escape hatches: lint, coverage, mutation, skips, any-types, TODOs
```

Then run the language-native tools for cognitive complexity, coverage, mutation,
dead code, duplication and types, as listed in the language reference. Present a
scoreboard:

```markdown
| Gate | Budget | Now | Worst offender | Violations |
|------|--------|-----|----------------|-----------:|
| Cyclomatic | < 22 | max 47 | billing/invoice.ts:88 `applyRules` | 12 |
| ...  |        |     |                |            |
```

### B3. Agree the plan

Show the scoreboard and propose full enforcement or **ratchet mode**. In ratchet
mode, all new and changed code is gated fully (diff coverage, `new-from-rev` linting,
`--since` mutation runs), and existing violations are baselined so their count can
only fall. A baseline grows only with the user's approval for a documented exception. List the dev dependencies and layers, and get
a yes before installing.

### B4. Install the gates before cleaning

Do A3–A5 (tools, `quality` command, three layers, budgets in CLAUDE.md/AGENTS.md).
In ratchet mode, also generate the baselines now (`suppression_audit.py
--write-baseline`, PHPStan/detekt/basedpyright baselines, complexipy snapshot, etc.).
Installing the gates first means their failures drive the cleanup and nothing
regresses along the way.

### B5. Clean up, in this order

The order matters: don't write tests for code you are about to delete, and don't
refactor code that has no tests pinning its behaviour.

1. **Delete dead code.** Use vulture / knip / deadcode / debride / IDE inspections.
   Before deleting, grep for dynamic use: reflection, string-based dispatch,
   framework entry points (routes, DI, serializers, CLI commands, Celery tasks,
   Rails callbacks), public API consumed elsewhere. Deleting is the cheapest fix
   there is, and it shrinks every other metric.
2. **Remove slop patterns.** Work through `references/slop-catalog.md`: narrating
   comments, swallowed exceptions, pointless wrappers, defensive checks for states
   that cannot happen, re-implemented stdlib, fake fallbacks, leftover debug output.
3. **Pin behaviour.** Add characterisation tests around anything you are about to
   restructure, asserting what it does today.
4. **Remove `any` / `unknown`.** Replace each one with a real type. Parse external
   data once at the boundary with a schema (zod, pydantic, serde, encoding/json into
   structs, …) and pass typed values inward.
5. **Deduplicate.** Use jscpd or the language tool. Merge true duplicates. Leave
   coincidental similarity alone: two things that merely look alike today will
   change for different reasons.
6. **Cut complexity and size.** Use the refactoring playbook below. Split files by
   responsibility, not alphabetically or by line count.
7. **Reach 100% coverage with meaningful tests.** Every test asserts an observable
   outcome. No assertion-free tests, no testing mocks, no snapshot dumps of huge
   objects as a coverage shortcut.
8. **Kill every mutant.** Treat each survivor as one of three cases, checked in this
   order:
   - **Redundant code.** The mutation changed nothing because the code does nothing,
     so delete it.
   - **Missing assertion.** Add or strengthen a test.
   - **Equivalent mutant.** The change genuinely can't alter behaviour. Mark it with
     the tool's skip annotation and give a reason. The suppression audit counts these.
9. **CRAP follows.** With CCN < 22 and 100% coverage, CRAP equals CCN, so it is
   automatically below 25. Use `complexity_gate.py --top 20` with a coverage report
   to decide what to fix first in a legacy codebase.

Commit after each step with all gates green, so any step can be reverted alone.

## Invariants (both paths)

On a new project, ask the user for the rules the system must never break before any
code exists. Each one is cheapest to enforce before the first line that could violate it.
On an existing codebase, also dig them out of the code, the schema and the tests.
Write them down in an `INVARIANTS.md` (or a section
of CLAUDE.md/AGENTS.md), each with how it is enforced. For agents, explicit
invariants matter even more than they do for humans. An agent has no memory of why a
rule exists and will happily "simplify" it away unless the rule is written down and
checked mechanically.

Enforce each invariant as low on this ladder as possible. Types and constraints beat
tests, and tests beat prose:

1. Types that make the illegal state unrepresentable.
2. Database constraints (NOT NULL, CHECK, FK, UNIQUE, exclusion constraints).
3. Module boundaries: only one module can perform the action.
4. Custom lint rules (semgrep / ast-grep / ArchUnit / banned-API lists).
5. Runtime assertions and contracts at the boundary.
6. Property-based tests.
7. Model checking or formal proof, for concurrency, protocols and state machines
   where tests cannot explore every interleaving.

Worked examples (including "never store a row in the user table unless the user
has authenticated") and a formal-methods guide are in `references/invariants.md`.

## Report (both paths)

For Path A, report what A7 lists. For Path B, show the scoreboard again (before → after),
plus:

- the list of remaining baselined violations (ratchet mode)
- every suppression that was added, each with its reason
- what each layer of gates runs and how long it takes
- anything you deliberately did not do, and why

## Rules of engagement (anti-gaming)

A gate is only worth something if passing it means the code got better. Do not:

- **Loosen a threshold, add a path exclusion, or edit a baseline upward** to get
  green. If a budget seems wrong, stop and ask the user. A genuine exception that needs
  a baseline increase (see the next point) also needs the user's approval first.
- **Add suppressions** (`noqa`, `eslint-disable`, `@ts-expect-error`, `nolint`,
  `pragma: no cover`, `Stryker disable`, …) unless the case is genuinely an exception.
  When it is, name the specific rule, write the reason inline, and report it. Blanket
  suppressions are never acceptable.
- **Skip, delete, or weaken tests** to make anything pass, or add tests without
  assertions to inflate coverage.
- **Split code to satisfy a metric rather than for meaning.** Examples: `helpers2.ts`,
  `_part2` functions that are only ever called in sequence, files split
  alphabetically, a function chopped in half at line 25. Each new unit needs a name
  that says what it is for.
- **Squash lines to dodge the LOC budget.** The formatter is part of the gate.
- **Replace `any` with an equally empty type**: `object` without narrowing,
  `Record<string, unknown>` passed around, `interface{}` renamed, `dynamic`,
  `serde_json::Value` everywhere.
- **Hide complexity in data** (giant config maps of lambdas) or in metaprogramming
  that the tools cannot see.

Mechanical backstops cover part of this list. `suppression_audit.py --baseline` fails when
suppression counts grow, and blanket suppressions always fail. The CI config guard and
CODEOWNERS (see `references/agent-loop.md`) catch loosened thresholds, new path
exclusions and baseline edits, but only as a human review step, so a baseline file that
was edited upward will pass the audit itself. The rest needs judgement, so review your own
diff against this list before finishing.

## Refactoring playbook for complexity and size

| Smell | Move |
|-------|------|
| Deep nesting | Guard clauses and early returns; invert conditions; extract the loop body |
| Long `if/elif` or `switch` on a type or kind | Lookup table / map of handlers, or polymorphism |
| Flag arguments (`express=True, gift=False`) | Separate functions, or an options/strategy object |
| Repeated computation with small variations | Extract one function with a parameter for the difference |
| Function doing parse → validate → compute → persist | One function per stage, composed by a short coordinator |
| Complex boolean condition | Name it: `is_eligible_for_refund(order)` |
| Many parameters travelling together | Introduce a parameter object / value type |
| `try/except` around big blocks | Narrow the `try` to the call that can fail; let unexpected errors propagate |
| File > 500 lines | Split by responsibility (one reason to change per module); move types next to their owners |
| Class with many unrelated methods | Split by which fields each method uses |

After each move, re-run the gates and tests. If a metric improved but the code reads
worse, undo it.

## Bundled scripts

`<skill-dir>` below and in the references means this skill's base directory, which
Claude Code shows when the skill loads (for example `~/.claude/skills/code-quality` for a
personal install, or a folder in the plugin cache for a plugin install).

All are language-agnostic, use only the Python stdlib apart from the noted
packages, exit 1 on failure, and take `--exclude` globs. Run with `--help` for the options.

| Script | Checks | Needs |
|--------|--------|-------|
| `scripts/loc_budget.py` | lines per file; optional byte budget for CSS/JS | – |
| `scripts/complexity_gate.py` | cyclomatic **and cognitive** per function, params, NLOC, **CRAP** from lcov / Cobertura / JaCoCo / Clover / Go cover profiles | `lizard` ≥ 1.24 |
| `scripts/halstead_gate.py` | Halstead difficulty: gated per function for Python; per file elsewhere, advisory unless `--file-max` is set | `radon`, `multimetric` |
| `scripts/comment_density.py` | comment ratio, narrating comments, commented-out code | – |
| `scripts/suppression_audit.py` | lint/coverage/mutation suppressions, skipped tests, any-types (catch variables and `--any-type-allow` boundary files exempt), TODOs; blanket check; ratchet baseline | – |

Prefer a native tool when the language has a good one (for example ESLint `complexity`
over lizard for TS) because it runs in the editor too. The scripts cover languages and
gates that lack one, and give a single cross-language scoreboard.

## References

Read the language file(s) for the stack in front of you, plus the others as needed.

| File | Read when |
|------|-----------|
| `references/metrics.md` | You need definitions, formulas, threshold rationale, or how each metric gets gamed |
| `references/slop-catalog.md` | During cleanup step 2, or reviewing agent-written code |
| `references/agent-loop.md` | Wiring hooks, pre-commit, CI, baselines and ratchets |
| `references/invariants.md` | Defining or enforcing invariants; considering formal methods |
| `references/lang-python.md` | Python |
| `references/lang-typescript.md` | Node.js / TypeScript / JavaScript, plus CSS and bundle budgets |
| `references/lang-go.md` | Go |
| `references/lang-jvm.md` | Java / Kotlin |
| `references/lang-dotnet.md` | C# / .NET |
| `references/lang-ruby.md` | Ruby / Rails (including ERB via Herb) |
| `references/lang-php.md` | PHP / Laravel / Symfony |
| `references/lang-rust.md` | Rust |
| `references/lang-other.md` | Elixir, Scala, Swift, C/C++, and any language without its own file |
