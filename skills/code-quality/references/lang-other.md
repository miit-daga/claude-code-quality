# Other languages: Elixir, Scala, Swift, C/C++, and the universal kit

Each section maps the gates to native tools, then gives install, config and the one command. The
bundled scripts live in `S=<skill-dir>/scripts`. Two traps apply everywhere:

- **lizard parses about 27 languages** (cpp, java, csharp, javascript, python, objectivec,
  ruby, php, swift, scala, go, lua, rust, typescript, kotlin, erlang, zig, …) **but not Elixir**.
  `complexity_gate.py` silently finds no functions in a language lizard can't parse, so always
  check the "N functions checked" count.
- **semgrep's default ignore list skips `test/` and `tests/`** when no `.semgrepignore` exists.
  Create one (e.g. containing `vendor/`) before writing rules for test code. semgrep Community
  Edition does not support Elixir (it is a Pro language); use ast-grep there.

Unless noted, every tool below fails when the value is **strictly greater** than the limit, so
set the limit to the largest allowed value (21 for "< 22").

## Elixir

| Gate | Tool | Setting |
|------|------|---------|
| Cyclomatic < 22 | Credo `Refactor.CyclomaticComplexity` | `max_complexity: 21` (default 9) |
| Cognitive < 22 | none native; Credo `Refactor.PerceivedComplexity` is a cyclomatic variant | `max_complexity: 21`. Not in the default config, so add it |
| Halstead < 80 | `halstead_gate.py` (multimetric handles `.ex`) | per file, advisory unless `--file-max` is set |
| File < 500 / comments / suppressions | `loc_budget.py`, `comment_density.py`, `suppression_audit.py` | the audit counts `credo:disable` |
| 100% coverage | excoveralls `minimum_coverage: 100` via `mix coveralls`, or built-in `test_coverage: [summary: [threshold: 100]]` | **line coverage only**: BEAM `cover` has no branch coverage. Say so in the report |
| CRAP < 25 | no lizard support, so no script | follows from CCN ≤ 21 plus 100% coverage (CRAP = CCN at full coverage) |
| 0 mutants | `muex` (maintained) | `mix muex --fail-at 100 --no-filter` (verify for your version). muzak and exavier are unmaintained |
| Dead code | compiler warnings (unused private functions and variables) + `--warnings-as-errors`; `mix_unused` for public functions; `mix deps.unlock --check-unused` | `mix xref unreachable` no longer does anything (moved into the compiler) |
| Duplication | Credo `Design.DuplicatedCode` (disabled by default) + jscpd `format: ["elixir"]` | `mass_threshold: 40` default |
| No `any()`/`term()` | no Credo check exists | `grep` gate below, or a custom check (`mix credo.gen.check`) |
| ABC ≤ 17 / params ≤ 5 / nesting ≤ 3 | Credo `ABCSize` (disabled by default), `FunctionArity`, `Nesting` | `max_size: 17`, `max_arity: 5`, `max_nesting: 3` (Credo's default 2 is stricter; keep it if you like) |
| Function length, boolean ops | no Credo check | ABC size and complexity act as the proxy |
| TODO, debug leftovers | Credo `Design.TagTODO`, `TagFIXME`, `Warning.IoInspect`, `Warning.Dbg`, `Warning.IExPry` | on by default |
| Types | Dialyzer via dialyxir; Elixir 1.20's inferred gradual types | there are no user-written set-theoretic signatures yet |
| Boundaries | `boundary` (`use Boundary, deps: [...], exports: [...]`, `compilers: [:boundary] ++ Mix.compilers()`) | |
| Properties | StreamData: `use ExUnitProperties`; `check all x <- integer(), max_runs: 500 do ... end` | |

```elixir
# mix.exs (project/0)
test_coverage: [tool: ExCoveralls],
dialyzer: [flags: [:unmatched_returns, :error_handling, :underspecs, :extra_return, :missing_return],
           plt_file: {:no_warn, "priv/plts/project.plt"}],
# and: def cli, do: [preferred_envs: [coveralls: :test, "coveralls.lcov": :test]]   # Elixir 1.15+
# deps: {:credo, "~> 1.7", only: [:dev, :test], runtime: false}, {:dialyxir, "~> 1.4", only: [:dev, :test], runtime: false},
#       {:excoveralls, "~> 0.18", only: :test}, {:stream_data, "~> 1.0", only: :test}, {:muex, ...}, {:boundary, ...}
```

```elixir
# .credo.exs: `extra` merges into Credo's default check list (checks: %{enabled: ...} would replace it)
%{configs: [%{name: "default", strict: true,
  files: %{included: ["lib/", "test/"], excluded: [~r"/_build/", ~r"/deps/"]},
  checks: %{extra: [
    {Credo.Check.Refactor.CyclomaticComplexity, [max_complexity: 21]},
    {Credo.Check.Refactor.PerceivedComplexity, [max_complexity: 21]},
    {Credo.Check.Refactor.ABCSize, [max_size: 17]},
    {Credo.Check.Refactor.FunctionArity, [max_arity: 5]},
    {Credo.Check.Refactor.Nesting, [max_nesting: 3]},
    {Credo.Check.Design.DuplicatedCode, []},
    {Credo.Check.Readability.Specs, []}
  ]}}]}
```

`coveralls.json`: `{"coverage_options": {"minimum_coverage": 100}}`. Only `mix coveralls`,
`coveralls.detail`, `.html` and `.cobertura` enforce the minimum. `coveralls.lcov`
("experimental"), `.json` and `.xml` do not, so run `mix coveralls` as the gate and the lcov
task for reports. Ignore markers `# coveralls-ignore-start/-stop/-next-line` are escape
hatches: grep for them. Built-in `mix test --cover` exits with status **3** below the
threshold (the docs say 1).

```bash
mix format --check-formatted && mix compile --warnings-as-errors && mix credo --strict
mix dialyzer && mix deps.unlock --check-unused && mix hex.audit
if grep -rnE '@(spec|type|typep|callback|opaque).*\b(any|term)\(\)' lib; then exit 1; fi   # single-line specs only
if grep -rn 'coveralls-ignore' lib; then exit 1; fi
npx --yes jscpd lib && python3 $S/loc_budget.py lib test && python3 $S/halstead_gate.py lib
python3 $S/comment_density.py lib --fail-on-commented-code && python3 $S/suppression_audit.py lib test --zero todo
MIX_ENV=test mix coveralls && mix muex --since origin/main --fail-at 100 --no-filter   # muex flags: verify
```

Legacy ratchet: `mix credo diff --from-git-ref origin/main` (only new issues), a dialyzer
`ignore_warnings` file that may only shrink, `muex --since`. Pre-commit: lefthook running
`mix format --check-formatted`, `mix compile --warnings-as-errors` and `mix credo --strict`.

## Scala

| Gate | Tool | Setting |
|------|------|---------|
| Cyclomatic, cognitive, params, NLOC, nesting | lizard via `complexity_gate.py` and `lizard -Ecognitive -ENS` | **caveat**: lizard truncates brace-less bodies (`def f = x match {...}`, Scala 3 indentation syntax). Check it on your code. scalastyle is unmaintained, and scapegoat is maintained (its complexity inspections: verify) |
| Halstead / file length / comments / suppressions | `halstead_gate.py`, `loc_budget.py`, `comment_density.py`, `suppression_audit.py` | the audit counts `@SuppressWarnings` |
| 100% statement + branch | sbt-scoverage | `coverageMinimumStmtTotal := 100`, `coverageMinimumBranchTotal := 100`, `coverageFailOnMinimum := true` (passes when actual >= min). Scala 3 needs 3.2+ |
| CRAP < 25 | `complexity_gate.py --coverage target/scala-*/coverage-report/cobertura.xml` | |
| 0 mutants | stryker4s (`sbt stryker`) | `break` can be at most 99, because `low` must be > `break`. Gate on the JSON report (below) |
| Dead code | `-Wunused:all` (3.3.4+; 2.13: `-Wunused`) + `-Werror`; scalafix `RemoveUnused` fixes it | scalafix docs suggest `-Wconf:cat=unused:info` while auto-fixing |
| Duplication | jscpd `format: ["scala"]` | |
| No `Any` | WartRemover `Warts.unsafe` (includes `Wart.Any`, `AsInstanceOf`, `IsInstanceOf`, `Null`, `Var`, `Return`, `Throw`, `OptionPartial`, `TryPartial`, `StringPlusAny`) | suppression: `@SuppressWarnings(Array("org.wartremover.warts.Any"))` |
| Style / syntax bans | scalafix `DisableSyntax` (`noVars`, `noNulls`, `noReturns`, `noThrows`, `noAsInstanceOf`, `noIsInstanceOf`, `noWhileLoops`, `noFinalize`, `noUniversalEquality`, …) | `sbt "scalafixAll --check"` (needs `semanticdbEnabled := true`) |
| Properties | ScalaCheck: munit-scalacheck (`ScalaCheckSuite`, `property("...") { forAll { (n: Int) => ... } }`) or scalatestplus `scalacheck-1-20` | |

```scala
// project/plugins.sbt: sbt-scoverage, sbt-scalafix, sbt-wartremover ("org.wartremover" % "sbt-wartremover"), sbt-stryker4s
// build.sbt
ThisBuild / semanticdbEnabled := true
scalacOptions ++= Seq("-Wunused:all", "-Werror")        // 2.13: Seq("-Wunused", "-Xfatal-warnings")
wartremoverErrors ++= Warts.unsafe
coverageMinimumStmtTotal := 100
coverageMinimumBranchTotal := 100
coverageFailOnMinimum := true
```

```hocon
# .scalafix.conf
rules = [RemoveUnused, DisableSyntax, LeakingImplicitClassVal, NoValInForComprehension, ProcedureSyntax, RedundantSyntax, OrganizeImports]
DisableSyntax { noVars = true, noNulls = true, noReturns = true, noThrows = true, noAsInstanceOf = true, noIsInstanceOf = true }
# stryker4s.conf
stryker4s { mutate: ["src/main/scala/**/*.scala"], reporters: ["console", "html", "json"], thresholds { high = 100, low = 99, break = 98 } }
```

```bash
sbt "scalafixAll --check" clean coverage test coverageReport    # fails below 100% stmt/branch
python3 $S/complexity_gate.py src/main --coverage target/scala-*/coverage-report/cobertura.xml
sbt stryker && python3 - <<'EOF'
import glob, json, sys
report = max(glob.glob("target/stryker4s-report/*/report.json"))   # mutation-testing-elements schema
alive = [(f, m["mutatorName"], m["location"]["start"]["line"]) for f, d in json.load(open(report))["files"].items()
         for m in d["mutants"] if m["status"] in ("Survived", "NoCoverage")]
print(*alive, sep="\n"); sys.exit(1 if alive else 0)
EOF
```

The equivalent-mutant skip is `@SuppressWarnings(Array("stryker4s.mutation.EqualityOperator"))`
(mutator names: EqualityOperator, BooleanLiteral, ConditionalExpression, LogicalOperator,
StringLiteral, MethodExpression). There is no comment form and no documented incremental mode,
so run stryker4s nightly or on a module subset via `mutate`. Coverage exclusions:
`// $COVERAGE-OFF$` works **on Scala 2 only**. `coverageExcludedPackages`/`coverageExcludedFiles`
work on Scala 2 and 3.3.4+. Every exclusion needs a reason.

## Swift

| Gate | Tool | Setting |
|------|------|---------|
| Cyclomatic < 22 | SwiftLint `cyclomatic_complexity` | `{warning: 21, error: 21}`. The shorthand `cyclomatic_complexity: 21` sets the warning only and **clears the error level** |
| Cognitive, nesting | no SwiftLint rule | `lizard -l swift -Ecognitive -Tcognitive_complexity=21 -ENS -Tmax_nested_structures=3`. SwiftLint `nesting` counts nested *types and functions*, not control flow |
| Function ≤ 50, params ≤ 5, file < 500 | `function_body_length`, `function_parameter_count` (`ignores_default_parameters: false`), `file_length` | plus `loc_budget.py`, which counts physical lines |
| Halstead / comments / suppressions | `halstead_gate.py`, `comment_density.py`, `suppression_audit.py` | the audit counts `swiftlint:disable` |
| 100% coverage | `swift test --enable-code-coverage` → `llvm-cov export -format=lcov` → `lcov_gate.py` (universal section) | llvm-cov has no fail-under. For Xcode projects, xcov `--minimum_coverage_percentage` |
| CRAP < 25 | `complexity_gate.py --coverage lcov.info` | |
| 0 mutants | Muter (macOS) | no score gate: `coverageThreshold` only skips low-coverage files. Parse `--format json` yourself |
| Dead code | SwiftLint analyzer rules `unused_declaration`, `unused_import` (`swiftlint analyze --compiler-log-path build.log`); Periphery `scan --strict` | Periphery's open-source repo is archived (now commercial); 3.8.0 is the last free release |
| Duplication | jscpd `format: ["swift"]` | |
| No `Any` / `AnyObject` | ast-grep rule below | also opt-in `force_unwrapping`, `implicitly_unwrapped_optional`; `force_cast`/`force_try` are on by default |
| TODO | `todo` rule (on by default) | |

```yaml
# .swiftlint.yml
strict: true                       # warnings fail too (same as `swiftlint lint --strict`)
excluded: [.build, Pods, DerivedData]
opt_in_rules: [force_unwrapping, implicitly_unwrapped_optional, discouraged_optional_boolean, closure_body_length]
analyzer_rules: [unused_declaration, unused_import]
cyclomatic_complexity: { warning: 21, error: 21 }
function_body_length: { warning: 50, error: 50 }
function_parameter_count: { warning: 5, error: 5, ignores_default_parameters: false }
file_length: { warning: 499, error: 499, ignore_comment_only_lines: false }
```

```bash
swiftlint lint --strict
lizard -l swift -C 21 -a 5 -Tnloc=50 -Ecognitive -Tcognitive_complexity=21 -ENS -Tmax_nested_structures=3 -w Sources
swift test --enable-code-coverage
BIN=$(find .build/debug -name '*PackageTests' -path '*MacOS*' | head -1)   # macOS layout (verify); Linux: .build/debug/<Pkg>PackageTests.xctest
xcrun llvm-cov export -format=lcov "$BIN" -instr-profile .build/debug/codecov/default.profdata \
  -ignore-filename-regex='(\.build|Tests)/' > lcov.info
python3 lcov_gate.py lcov.info && python3 $S/complexity_gate.py Sources --coverage lcov.info
muter --format json --output muter.json   # then fail on any survivor (field names: verify for your version)
```

Muter config `muter.conf.yml` (from `muter init`) has `executable`, `arguments`, `exclude`
(substring match) and `excludeCalls`. Its skip annotations are `// muter:disable` …
`// muter:enable`. `suppression_audit.py` counts `muter:disable` under `mutation`.

## C and C++

| Gate | Tool | Setting |
|------|------|---------|
| Cyclomatic < 22 | lizard / `complexity_gate.py` (clang-tidy has no cyclomatic check) | `--ccn-max 21` |
| Cognitive < 22 | clang-tidy `readability-function-cognitive-complexity` | `Threshold: 21` (default 25; flags Total > Threshold) |
| Function size, params, nesting | clang-tidy `readability-function-size` | `LineThreshold: 50` (physical lines, not NLOC), `ParameterThreshold: 5`, `NestingThreshold: 4` (the function body itself is level 1, so 4 allows three nested control blocks). All default to none except `StatementThreshold` 800 |
| Halstead / file / comments / suppressions | `halstead_gate.py`, `loc_budget.py`, `comment_density.py`, `suppression_audit.py` | the audit counts `NOLINT`, and a bare `NOLINT` without `(check)` counts as blanket |
| 100% line + branch | gcovr | `--fail-under-line 100 --fail-under-branch 100` (exit 2 / 4) |
| CRAP < 25 | `complexity_gate.py --coverage build/coverage.xml` (gcovr `--cobertura`) | |
| 0 mutants | Mull (`mull-runner` fails on any survivor by default; `--mutation-score-threshold` defaults to 100) | `--allow-surviving` turns that off, so never pass it |
| Dead code | cppcheck `--enable=unusedFunction`; `-Wall -Wextra -Werror` (unused variables, parameters, static functions); GNU ld `-ffunction-sections -Wl,--gc-sections -Wl,--print-gc-sections` | unusedFunction is silently disabled with `-j` > 1 unless `--cppcheck-build-dir` is set |
| Duplication | jscpd `format: ["c", "cpp"]` | |
| No `void*` / `std::any` | no clang-tidy check; ast-grep rule below; `cppcoreguidelines-pro-type-reinterpret-cast`, `cppcoreguidelines-pro-type-vararg` | |
| Memory and UB invariants | sanitizers: `-fsanitize=address,undefined -fno-sanitize-recover=undefined`; TSan as a separate build (it can't combine with ASan); MSan is clang-only | |
| Properties / fuzzing | RapidCheck (`rc::check`); libFuzzer `clang -g -O1 -fsanitize=fuzzer,address` | |

```yaml
# .clang-tidy
Checks: >
  -*, bugprone-*, readability-function-cognitive-complexity, readability-function-size,
  misc-unused-parameters, misc-unused-using-decls, misc-include-cleaner,
  cppcoreguidelines-avoid-goto, cppcoreguidelines-pro-type-vararg, cppcoreguidelines-pro-type-reinterpret-cast
WarningsAsErrors: '*'
HeaderFilterRegex: '.*/(src|include)/.*'
CheckOptions:
  readability-function-cognitive-complexity.Threshold: 21
  readability-function-size.LineThreshold: 50
  readability-function-size.ParameterThreshold: 5
  readability-function-size.NestingThreshold: 4   # body = level 1, so this is nesting <= 3
```

```bash
cmake -S . -B build -DCMAKE_EXPORT_COMPILE_COMMANDS=ON -DCMAKE_C_FLAGS="--coverage -O0" -DCMAKE_CXX_FLAGS="--coverage -O0"
cmake --build build && ctest --test-dir build
run-clang-tidy -p build                        # changed lines only: git diff -U0 origin/main | clang-tidy-diff.py -p1
cppcheck --project=build/compile_commands.json --enable=warning,style,unusedFunction --error-exitcode=1 --inline-suppr
gcovr --root . --filter src/ --fail-under-line 100 --fail-under-branch 100 \
  --exclude-throw-branches --exclude-unreachable-branches --cobertura build/coverage.xml --lcov build/lcov.info
python3 $S/complexity_gate.py src --coverage build/coverage.xml
```

`--exclude-throw-branches` and `--exclude-unreachable-branches` drop compiler-generated
exception branches that no test can reach. They are standard for C++, but list them as
exclusions in the report. Coverage escape hatches are `GCOVR_EXCL_LINE`, `GCOVR_EXCL_START/STOP`
and `GCOVR_EXCL_BR_*` (the `LCOV_` prefix also works). The audit counts both `LCOV_EXCL` and
`GCOVR_EXCL` under `coverage`. With clang, `-fprofile-instr-generate -fcoverage-mapping` (+ `-fcoverage-mcdc`)
and `llvm-cov export -format=lcov` replace gcov.

Mull: compile tests with `clang-18 -fpass-plugin=/usr/lib/mull-ir-frontend-18 -g -grecord-command-line`,
run `mull-runner-18 ./tests`. In `mull.yml`, `gitDiffRef: origin/main` + `gitProjectRoot: .`
restrict mutation to changed code, and `excludePaths` takes regexes. Equivalent-mutant
annotations: `// mull-off` … `// mull-on`, `// mull-ignore`, `// mull-ignore-next` (count by grep).

## Any other language

The universal kit, for anything without a better native tool:

| Gate | Tool | Command |
|------|------|---------|
| Cyclomatic, params, NLOC, CRAP | lizard via `complexity_gate.py` | `python3 $S/complexity_gate.py src --coverage <lcov or cobertura> --params-max 5 --nloc-max 50` |
| Cognitive, nesting | lizard 1.24+ extensions | `lizard -Ecognitive -Tcognitive_complexity=21 -ENS -Tmax_nested_structures=3 -w src` (exit 1 on any warning; `-i N` tolerates N). `-ENS` is accurate for brace languages but over-counts indentation-based ones (Python, Elixir-style `do` blocks): use their native nesting rule there |
| Halstead < 80 | multimetric via `halstead_gate.py` | per file for non-Python, using Pygments lexers (most languages); advisory unless you calibrate a per-file budget with `--file-max` |
| File < 500 | `loc_budget.py` | `--ext` to restrict extensions |
| Duplication | jscpd 5 (Rust rewrite, 200+ formats) | `npx --yes jscpd --threshold 0 --min-tokens 50 --format <fmt> src`. `threshold` fails when duplication % > value; markers `jscpd:ignore-start` / `jscpd:ignore-end` |
| Any-type and invariant rules | semgrep (`semgrep scan --config .semgrep.yml --error`) or ast-grep (`ast-grep scan`, exit 1 on `severity: error`) | ast-grep supports Elixir, Swift and C++. Suppression comment: `// ast-grep-ignore: rule-id` |
| Comments, escape hatches, TODO | `comment_density.py --fail-on-commented-code`, `suppression_audit.py --zero todo` | the audit knows the markers listed in its header; grep for others |

```yaml
# rules/no-any.yml, with sgconfig.yml containing `ruleDirs: [rules]` (tested with ast-grep 0.51)
id: no-any-swift
language: swift
severity: error
message: Any/AnyObject erases the type. Use a concrete type, a protocol or a generic.
rule: { kind: user_type, regex: "^(Any|AnyObject)$" }
---
id: no-void-pointer
language: cpp
severity: error
message: void* / std::any erase the type. Use a concrete type, a template or std::variant.
rule:
  any:
    - pattern: std::any
    - kind: primitive_type
      regex: "^void$"
      precedes: { any: [{ kind: pointer_declarator }, { kind: abstract_pointer_declarator }] }
```

**Getting a coverage file for CRAP.** `complexity_gate.py` reads lcov, Cobertura, JaCoCo, Clover
and Go profiles. Sources: `llvm-cov export -format=lcov` (clang, Swift, Rust), `gcovr --lcov` /
`--cobertura` (gcc), grcov `-t lcov` (or `-t cobertura`), kcov (writes
`<out>/<binary>/cobertura.xml`, `--cobertura-only` to skip HTML; works for compiled binaries
and scripts), Dart `dart pub global run coverage:format_coverage --lcov -i coverage.json -o lcov.info`,
Lua `luacov -r lcov` (needs `luacov-reporter-lcov`), Haskell `hpc-lcov` (stack only). Where no
tool enforces 100%, gate the lcov file with this:

```python
#!/usr/bin/env python3
"""lcov_gate.py: fail unless an lcov file shows 100% line and branch coverage (LF/LH, BRF/BRH totals)."""
import sys
totals = {"LF": 0, "LH": 0, "BRF": 0, "BRH": 0}
for raw in open(sys.argv[1], encoding="utf-8"):
    key, _, value = raw.strip().partition(":")
    if key in totals:
        totals[key] += int(value)
print(f"lines {totals['LH']}/{totals['LF']}, branches {totals['BRH']}/{totals['BRF']}")
missing = totals["LH"] < totals["LF"] or totals["BRH"] < totals["BRF"]
sys.exit(1 if missing or totals["LF"] == 0 else 0)
```

If the report has no `BRF` records, the toolchain is not measuring branches, and the report has
to say so. Mutation testing has no universal tool. If the language has none, report gate 7 as
not enforced rather than dropping it silently.
