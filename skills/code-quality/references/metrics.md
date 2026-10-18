# Metrics: definitions, budgets, and how each gets gamed

Read this when you need to explain a metric to the user, pick or calibrate a threshold,
or judge whether a fix improved the code or just moved the number.

## Contents

1. Cyclomatic complexity
2. Cognitive complexity
3. Halstead difficulty
4. Lines per file (and function length)
5. Coverage
6. CRAP
7. Mutation score / surviving mutants
8. Dead code
9. Redundant code
10. `any` / `unknown`
11. ABC size
12. Nesting, parameters, boolean complexity
13. Size budgets (CSS/JS/bundles)
14. Comment density
15. Calibrating a threshold

---

## 1. Cyclomatic complexity (McCabe, 1976)

**What:** the number of linearly independent paths through a function. In practice:
1 + the number of decision points (`if`, `elif`, `case`, loop, `catch`, `&&`, `||`,
`?:`, and in some tools `?.`/`??`). Tools differ on which operators count, so the same
function can score 18 in one tool and 21 in another.

**Budget:** < 22 (max 21) per function. Common tool defaults are lower (ESLint 20,
lizard warns at 15, Sonar 10, RuboCop 7), so 21 is a ceiling, not a target. Most
functions in a healthy codebase sit under 10.

**Why for agents:** cyclomatic complexity grows when an agent handles each new case
by appending another branch to the function it already has. A hard cap forces it to
extract and name the cases.

**Gaming and counters:**
- *Split a function into `part1()`/`part2()` that only ever run in sequence.* Counter:
  each extracted unit must have a meaningful name and be independently testable.
- *Replace `if` chains with a dictionary of lambdas with the same logic inside.*
  This is fine when it really is a dispatch table. It's gaming when the lambdas are
  long and branchy themselves, which cognitive complexity and Halstead will flag.
- *Turn conditions into exceptions or early `return`s inside helper calls.* Watch for
  control flow that becomes harder to follow even though the score dropped.

## 2. Cognitive complexity (G. Ann Campbell, SonarSource, 2017)

**What:** a score of how hard a function is to *understand*:
- +1 for each break in linear flow (`if`, `else if`, `else`, `switch`, loops, `catch`,
  `goto`, break/continue to label, each sequence of mixed boolean operators, recursion)
- +1 *extra per nesting level* for structures nested inside other structures
- no increment for shorthand that aids reading (e.g. `?.`, null-coalescing)

The nesting penalty is the key difference from cyclomatic. A flat `switch` with ten
cases scores low on cognitive but high on cyclomatic. Four nested `if`s score low on
cyclomatic but high on cognitive. Gate both.

**Budget:** < 22 (max 21) per function. Sonar's default is 15.

**Tools:** eslint-plugin-sonarjs `cognitive-complexity`, Biome
`noExcessiveCognitiveComplexity`, complexipy (Python), gocognit (Go), PMD
`CognitiveComplexity` (Java), detekt `CognitiveComplexMethod` (Kotlin), Sonar S3776
(C#), clippy `cognitive_complexity` (Rust, a different formula), RuboCop
Ruby has no true cognitive-complexity cop (`Metrics/PerceivedComplexity` is a weighted
cyclomatic score with no nesting penalty, so pair it with `Metrics/BlockNesting`), clang-tidy
`readability-function-cognitive-complexity`, and for any language lizard parses, lizard's
`cognitive` extension (`lizard -Ecognitive`, used by `scripts/complexity_gate.py`).

**Gaming:** the same as cyclomatic, plus flattening nesting with `continue` soup. Guard
clauses at the top of a function are good. Ten `continue` statements scattered through a
loop body are not.

## 3. Halstead difficulty (Halstead, 1977)

**What:** with n1 = distinct operators, n2 = distinct operands, N2 = total operand
occurrences:

```
D = (n1 / 2) × (N2 / n2)
```

Difficulty rises with operator variety and with heavy reuse of the same operands. It
captures "dense" code (long arithmetic expressions, many operators per line, the same
variables juggled over and over) that branch-based metrics miss.

**Budget:** < 80 per function. **Calibrate per tool**:
radon (Python, per function) gives small numbers; multimetric (per file, any language)
gives larger ones because a whole file has more operators and operand reuse. In this
environment the same pricing logic scored 6.6 in radon (per function) and 27.9 in
multimetric (per file, TypeScript). Pick one tool per language, measure the existing
distribution, and keep the threshold fixed for that tool.

**Per function vs per file.** The budget of 80 is a per-function budget, and only Python
(radon) is gated per function. Per-file scores are a different measurement: on a
well-written TypeScript library, about half the files score over 80, including one of 57
lines. So `scripts/halstead_gate.py` reports per-file scores as advisory and fails on them
only when the project sets its own calibrated per-file budget (`--file-max`). Never split
a file just to lower its per-file score.

**Gaming:** introducing throwaway variable names to inflate n2 (distinct operands).
Counter: review. Meaningless intermediate names (`tmp1`, `val2`) are slop in their own
right.

## 4. Lines per file (and function length)

**What:** physical lines in a file. Budget < 500. Function length: ≤ 50 NLOC suggested.

**Why for agents:** an agent reads files whole. Past a few hundred lines, files stop
fitting comfortably in context alongside everything else. Agents also tend to append
to whatever file is open, so files grow without limit. The cap forces a decision
about where code belongs.

**Gaming:** cramming statements onto one line, removing blank lines, or minifying.
Counter: the formatter runs in the same gate (`--check`), and a line-length limit
exists. Splitting `big.ts` into `big1.ts`/`big2.ts` is the other form, and the
counter is that each module needs a responsibility you can state in one sentence.

## 5. Coverage

**What:** line (statement) coverage = executed lines / executable lines. Branch coverage =
taken branch outcomes / possible outcomes (both sides of every `if`, every `case`).
Gate both at 100%. Line coverage alone misses the untaken `else`.

Not every toolchain measures branches. Go's built-in coverage is statement-only, and
Rust branch coverage via cargo-llvm-cov needs nightly. Where branches can't be
measured, mutation testing covers the gap.

**Legitimate exclusions** (each listed in config with a reason, never inline by
default): `if TYPE_CHECKING:` blocks, `@overload` stubs, abstract methods and protocol
members written with a `...` body (not `raise NotImplementedError`, which a `super()` call
can reach), `__repr__` of debug-only classes, platform-specific branches tested
in a different CI job, and `main()` entry points that only wire things up (test the
wiring separately or keep it trivial).

**Gaming:**
- *Assertion-free tests* that execute code without checking anything. Counter:
  mutation testing exposes them at once.
- *Snapshot everything*: one giant snapshot covers lines but asserts nothing specific.
  Counter: review, and keep snapshots small and targeted.
- *`pragma: no cover` / `istanbul ignore`* sprinkled around. Counter: the
  `suppression_audit.py --zero coverage` gate, or ratchet.
- *Testing private helpers through mocks of everything around them.* Counter: assert
  on observable outputs, and mock only true boundaries (network, clock, randomness, filesystem).

## 6. CRAP (Change Risk Anti-Patterns; Savoia & Evans, 2007)

```
CRAP(m) = CC(m)² × (1 − cov(m))³ + CC(m)
```

CC is cyclomatic complexity and cov is that method's coverage as a fraction.

| CC \ coverage | 0% | 50% | 80% | 100% |
|---|---|---|---|---|
| 4  | 20.0 | 6.0 | 4.1 | 4 |
| 5  | **30.0** | 8.1 | 5.2 | 5 |
| 10 | **110** | 22.5 | 10.8 | 10 |
| 11 | **132** | **26.1** | 12.0 | 11 |
| 21 | **462** | **76.1** | 24.5 | 21 |

Bold = fails CRAP < 25. Two consequences:

- With 100% coverage, CRAP = CC, so CC < 22 already implies CRAP < 25. CRAP adds
  information only while coverage is below 100%: on a legacy codebase, or as a
  ratchet during cleanup.
- Untested code may only be trivial: at 0% coverage, CC ≤ 4.

Use `scripts/complexity_gate.py --coverage <report> --top 20` to rank functions by
CRAP. That list is the order in which to add tests or simplify.

## 7. Mutation testing (surviving mutants = 0)

**What:** the tool makes small changes (mutants) to the code, such as `<` → `<=`,
`+` → `-`, `True` → `False`, deleting a call, or returning a default value. It then
re-runs the tests. If the tests still pass, the mutant *survived*: no test notices
that behaviour.

**Budget:** 0 surviving mutants on code under the gate (a mutation score of 100% of
killable mutants). In practice, run on changed files per PR and on everything nightly.

**Triage each survivor in this order:**
1. **Redundant code?** If the mutation changed nothing observable because the code does
   nothing (a re-check of a condition already guaranteed, a default that is always
   overwritten), delete the code. This is the most common case in agent-written code.
2. **Missing or weak assertion?** Add or sharpen a test that would fail under the mutant.
3. **Equivalent mutant?** If the mutant is semantically identical (e.g. `i < len` vs
   `i != len` in a loop that only increments by 1), mark it with the tool's skip
   annotation plus a reason. The suppression audit counts these.

**Cost:** mutation runs are roughly (number of mutants) × (time of the relevant tests).
Keep unit tests fast, use incremental or diff-only modes, and give the tool test
selection where it supports it.

## 8. Dead code

Unused functions, methods, classes, exports, files, parameters, variables, imports,
feature flags that are always on or always off, config keys nobody reads, and
dependencies nobody imports. Budget: 0. Static tools give false positives for
dynamic use (reflection, DI containers, framework conventions, string dispatch, public
APIs used by other repos). Handle those with a whitelist file that names each entry
and the reason, not with inline suppressions scattered through the code.

## 9. Redundant code

- **Duplication:** token-level clones (jscpd, PMD CPD, flay, dupl, Sonar). Budget: 0
  clones above the tool's minimum size (e.g. jscpd `--min-tokens 50`). Merge real
  duplicates. If two pieces of code look alike but change for different reasons, they
  are coincidental twins: leave them and raise the minimum size or exclude that pair
  with a reason.
- **No-op code:** wrappers that only forward their arguments, conditions that are always
  true, re-validation of already-validated data, `try/except` that re-raises unchanged,
  re-implementations of a standard-library function. Mutation testing and linters
  (`no-unnecessary-condition`, ruff `SIM`/`RET`/`PIE`, clippy `needless_*`) find most of these.

## 10. `any` / `unknown` and equivalents

**Budget:** 0 explicit escape hatches in application code. Equivalents: TS `any` /
`unknown`, Python `Any`, Go `any`/`interface{}`, C# `dynamic` (and `object`
parameters), Java raw types and `Object` parameters, Kotlin `Any`, Ruby `T.untyped`, PHP
`mixed`, Scala `Any`, Rust `Box<dyn Any>` / passing `serde_json::Value` around.

**The boundary exception:** data entering the system (JSON bodies, env vars, files,
third-party SDK results) is genuinely untyped at the moment it arrives. Parse it once at
the edge with a schema (zod / valibot, pydantic / msgspec, serde, `encoding/json` into
structs, records with validation) and give the rest of the code the typed result. The
`unknown` (or equivalent) appears only inside that parser function. Allow it in that
file with a path-scoped rule override (and `suppression_audit.py --any-type-allow
'<glob>'`), not with inline suppressions. The other allowed use is a caught error:
`catch (e: unknown)` and promise `.catch((e: unknown) => ...)` callbacks, which the audit
script does not count.

**Gaming:** swapping `any` for an equally empty type (`object` without narrowing,
`Record<string, unknown>`, `Map<String, Object>`, `dict[str, object]`), or casting
(`as Foo`) without validation. A cast is an `any` with a nicer name.

## 11. ABC size (Fitzpatrick, 1997)

```
ABC = √(A² + B² + C²)
```

A = assignments, B = branches (in RuboCop's definition, *calls*: method/function
invocations), C = conditions (comparisons, `else`, `rescue`, etc.). It measures how much
*stuff* a method does, which complements cyclomatic (paths) and cognitive (nesting).
Native in RuboCop (`Metrics/AbcSize`, default max 17), flog (a weighted ABC variant), and
Credo (`Credo.Check.Refactor.ABCSize`). Elsewhere, lizard's token count per function
is a reasonable proxy. Suggested budget: ≤ 17.

## 12. Nesting, parameters, boolean complexity

- **Nesting depth ≤ 3:** the main driver of cognitive complexity. Fix with guard clauses
  and extraction.
- **Parameters ≤ 5:** more usually means a missing type (parameter object) or a function
  doing two jobs. Boolean flag parameters are the worst case: split the function.
- **Boolean operators per condition ≤ 3:** give the condition a name with a predicate
  function or a well-named local.

## 13. Size budgets (CSS/JS/bundles)

Per-file byte limits (`scripts/loc_budget.py --max-bytes`) and per-bundle / per-route
limits (size-limit, Lighthouse CI budgets, bundler `performance` hints). When a budget
is hit, the agent's next task is to **prune before adding**: delete unused CSS,
unused dependencies, duplicate utilities and dead routes. Budgets turn "slowly rotting
frontend" into a visible failure.

## 14. Comment density

Comments should say *why* (constraints, trade-offs, links to incidents), never *what*
the next line does. Agents over-comment. `scripts/comment_density.py` fails files
above 0.25 comment lines per code line, and reports narrating comments and
commented-out code. Doc comments on declarations, license headers and tool directives
are not counted. Native commented-out-code rules: ruff `ERA001`, sonarjs
`no-commented-code`, Sonar S125 (most languages via SonarQube/SonarLint).

## 15. Calibrating a threshold

1. Measure the current distribution (`--top 50`) before setting anything.
2. For a new project, start at the user's budget. Do not raise it because the first
   feature is hard. Restructure the feature.
3. For a legacy project, set the gate at the budget for **new and changed** code, and
   baseline the rest (ratchet).
4. Verify the `>` vs `>=` boundary with a fixture at the limit and one just over.
5. Write the threshold in one place (the tool config) and reference it from
   CLAUDE.md/AGENTS.md. Two copies drift apart.
