# Python gates

Ruff formats and lints, complexipy checks cognitive complexity, basedpyright type-checks with `Any` banned, pytest with coverage.py enforces the coverage floor (70% line and branch; Strict 100%), and mutmut plus `mutation_score.py` gate the mutation score on covered, changed code (≥ 80%; Strict: zero survivors). vulture, deptry, pylint (file length and duplication only), import-linter and semgrep cover dead code, dependencies, layers and test hygiene, and the bundled scripts cover Halstead, CRAP, comment density and suppressions. Everything here was run end to end on Python 3.13 with uv 0.10, ruff 0.17, complexipy 8.0, basedpyright 1.40, mutmut 3.8, vulture 2.16, pylint 4.1, import-linter 2.15, deptry 0.25 and semgrep 1.181. The Standard-profile changes (coverage 70, function length 60, covered-code mutation score, cross-cutting bans) were rechecked on ruff 0.17.3, coverage.py 7.17, mutmut 3.8, import-linter 2.15 and semgrep 1.182.

**Tool choices are the org's or the user's.** The formatter (ruff format, or black plus isort) and the type checker (basedpyright, pyright or mypy; a mypy setup is under "Killing `any`") are interchangeable here. The configs below use ruff and basedpyright; for a researched comparison use the `quality-tool-picker` skill.

## Tool map

| Gate | Tool | Setting / rule |
|------|------|----------------|
| Cyclomatic < 22 | ruff `C901` | `[tool.ruff.lint.mccabe] max-complexity = 21`; fires when complexity > 21 |
| Cognitive < 22 | complexipy | `max-complexity-allowed = 21`; fails when > 21 (21 passes, 22 fails) |
| Halstead difficulty < 80 | `scripts/halstead_gate.py` (radon, per function) | default `--max 80`, fails at ≥ 80. Raw numbers: `radon hal -f -j src` |
| File < 500 lines | pylint `C0302` too-many-lines | `max-module-lines = 499` (500 fails). Ruff has no file-length rule. `scripts/loc_budget.py` covers all file types |
| Coverage ≥ 70% line + branch | pytest-cov + coverage.py | `branch = true`, `fail_under = 70` gates the combined line+branch figure; the `quality` target also checks each one from `coverage.json`. Strict: `fail_under = 100` |
| CRAP < 25 | `scripts/complexity_gate.py --coverage coverage.lcov` | `--crap-max 25` default, fails at ≥ 25 |
| Mutation score ≥ 80% on covered, changed code | mutmut 3.8 + `scripts/mutation_score.py` | mutmut has no score threshold and `mutmut run` exits 0 with survivors, so gate `mutants/mutmut-cicd-stats.json` with `mutation_score.py --min-covered 80`. Strict: `--max-survived 0` |
| 0 dead code | vulture; ruff `F401` `F841` `ARG001`-`ARG005` | `min_confidence = 60`; vulture exits 3 when it finds anything |
| 0 duplication | pylint `R0801` duplicate-code | `min-similarity-lines = 6`; for mixed-language repos also `npx jscpd --threshold 0` |
| 0 `Any` | basedpyright `recommended` (`reportAny`, `reportExplicitAny`, `reportUnknown*`); ruff `ANN401`, `TID251` | `banned-api` bans `typing.Any` and `typing.cast` |
| ABC size ≤ 17 | no Python tool | proxies: ruff `PLR0912 max-branches`, `PLR0915 max-statements`, `complexity_gate.py --nloc-max` |
| Function ≤ 60 NLOC | `complexity_gate.py --nloc-max 60` (lizard; 60 passes, 61 fails) | ruff `PLR0915 max-statements = 60` is a backstop: it counts statements, not lines, and stayed quiet on a 61-NLOC function of 60 statements. Strict: 50 for both |
| Params ≤ 5 | ruff `PLR0913`, `PLR0917` | `max-args = 5`, `max-positional-args = 5` (6 fails) |
| Nesting ≤ 3 | ruff `PLR1702` (preview) | `max-nested-blocks = 3`; needs `preview = true` plus explicit selection |
| Boolean operators ≤ 3 | ruff `PLR0916` (preview) | `max-bool-expr = 4`. It counts operands in an `if` condition (4 operands = 3 operators) and ignores `return`/assignment expressions |
| CSS/JS byte budgets | n/a | `loc_budget.py --max-bytes` for any static assets the package ships |
| Comment density, no commented-out code | `scripts/comment_density.py --fail-on-commented-code`; ruff `ERA001` | ratio ≤ 0.25 by default |
| Suppression ratchet, no blanket | ruff `PGH004` blanket-noqa, `PGH003` blanket-type-ignore, `RUF100` unused-noqa; `scripts/suppression_audit.py` | `--zero coverage skipped any-type todo --baseline .quality/suppressions.json`. The audit also counts `# complexipy: ignore`, ignores `from typing import Any` lines, and skips boundary parsers passed to `--any-type-allow` |
| Type coverage 100% | basedpyright `recommended` fails on any warning | numeric report: `mypy --any-exprs-report out src`, then `out/any-exprs.txt` Total must read 100.00% |
| Architecture boundaries | import-linter (`lint-imports`) | `layers` and `forbidden` contracts; third-party modules in a contract need `include_external_packages = true` |
| No unused dependencies | deptry | DEP001 missing, DEP002 unused, DEP003 transitive, DEP004 dev dep used in code |
| Tests assert, no logic in tests | semgrep rules below; ruff `PT011`, `PT012`, `PT017`, `PT018` | semgrep skips `tests/` unless the repo has a `.semgrepignore`, and it scans only git-tracked files |
| TODO ban | ruff `FIX001`-`FIX004`, `TD003` (all in `ALL`) | plus `suppression_audit.py --zero todo` |

## Configuration

### Scaffold and install (empty repo)

```bash
git init && uv init --lib --name shop .      # src/shop/__init__.py, py.typed; delete the generated hello()
uv add pydantic                               # runtime: boundary parsing
uv add --dev ruff complexipy basedpyright mypy pylint vulture deptry import-linter \
  pytest pytest-cov hypothesis mutmut diff-cover pre-commit semgrep crosshair-tool \
  lizard radon multimetric
mkdir -p tests tools/quality .semgrep src/shop/domain src/shop/adapters
touch src/shop/domain/__init__.py src/shop/adapters/__init__.py
cp <skill-dir>/scripts/*.py tools/quality/   # CI has no ~/.claude
printf '.venv/\nmutants/\n.coverage\ncoverage.lcov\ncoverage.json\ncoverage.xml\n' >> .gitignore
printf '.venv/\nnode_modules/\n' > .semgrepignore                    # replaces the default that skips tests/
```

Layout: `src/shop/domain/` (pure logic, no I/O imports), `src/shop/adapters/` (HTTP, DB, parsing), `tests/`, `tools/quality/` (vendored scripts), `.semgrep/`.

### pyproject.toml (append under the `[project]` table uv created)

```toml
[tool.ruff]
line-length = 100
src = ["src", "tests"]
extend-exclude = ["tools/quality"]

[tool.ruff.lint]
select = ["ALL"]
ignore = [
  "D1",      # missing docstrings: names carry meaning; required docstrings breed narration
  "D203",    # conflicts with D211
  "D213",    # conflicts with D212
  "COM812",  # conflicts with the formatter
  "CPY001",  # copyright headers: enable only if the project wants them
]
preview = true
explicit-preview-rules = true            # preview only for the codes listed below
extend-select = ["PLR1702", "PLR0916", "PLR0904"]

[tool.ruff.lint.per-file-ignores]
"tests/**" = ["S101", "PLR2004"]         # asserts and literal expectations are the point of tests
# The sanctioned modules (see "Cross-cutting conventions") may import what TID251 bans elsewhere
"src/shop/adapters/http.py" = ["TID251"]
"src/shop/adapters/retry.py" = ["TID251"]
"src/shop/log.py" = ["TID251"]

[tool.ruff.lint.mccabe]
max-complexity = 21

[tool.ruff.lint.pylint]
max-args = 5
max-positional-args = 5
max-branches = 21
max-statements = 60                      # Strict: 50
max-nested-blocks = 3
max-bool-expr = 4                        # counts operands: 4 operands = 3 and/or operators
max-public-methods = 20

[tool.ruff.lint.flake8-tidy-imports]
ban-relative-imports = "all"

[tool.ruff.lint.flake8-tidy-imports.banned-api]
"typing.Any".msg = "No Any. Parse at the boundary into a real type."
"typing.cast".msg = "cast() is an unchecked claim. Narrow with isinstance or a schema."
# Cross-cutting conventions: one module each for service calls, retries and logging
"requests".msg = "Call services through shop.adapters.http."
"httpx".msg = "Call services through shop.adapters.http."
"urllib3".msg = "Call services through shop.adapters.http."
"urllib.request".msg = "Call services through shop.adapters.http."
"tenacity".msg = "Retry through shop.adapters.retry."
"stamina".msg = "Retry through shop.adapters.retry."
"logging.getLogger".msg = "Get a logger from shop.log.get_logger()."
"structlog".msg = "Get a logger from shop.log.get_logger()."

[tool.complexipy]
paths = ["src"]
max-complexity-allowed = 21

[tool.basedpyright]
include = ["src", "tests"]
pythonVersion = "3.13"
typeCheckingMode = "recommended"         # every rule on, warnings fail the run; "all" adds noisier rules

[tool.pylint.main]
jobs = 0

[tool.pylint."messages control"]
disable = ["all"]
enable = ["too-many-lines", "duplicate-code"]   # the two gates ruff cannot check

[tool.pylint.format]
max-module-lines = 499

[tool.pylint.similarities]
min-similarity-lines = 6
ignore-imports = true
ignore-signatures = true

[tool.vulture]
paths = ["src", "tests"]
min_confidence = 60
ignore_names = ["model_config"]          # read by pydantic, never by our code

[tool.importlinter]
root_package = "shop"
include_external_packages = true

[[tool.importlinter.contracts]]
name = "Layers"
type = "layers"
layers = ["shop.adapters", "shop.domain"]   # higher layers may import lower ones, never the reverse

[[tool.importlinter.contracts]]
name = "Domain has no I/O dependencies"
type = "forbidden"
source_modules = ["shop.domain"]
forbidden_modules = ["pydantic", "httpx", "sqlalchemy"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = ["--strict-markers", "--strict-config", "-ra"]
xfail_strict = true
filterwarnings = ["error"]

[tool.coverage.run]
branch = true
source = ["src"]

[tool.coverage.report]
fail_under = 70                          # Strict: 100
show_missing = true
skip_covered = true
# Not `raise NotImplementedError`: a subclass calling super() reaches it, so it stays measured.
# Give abstract methods and Protocol members a `...` body instead; there is nothing to cover.
exclude_also = ["if TYPE_CHECKING:", "@overload"]

[tool.mutmut]
source_paths = ["src/shop"]
pytest_add_cli_args_test_selection = ["tests/"]   # replaces the deprecated tests_dir
mutate_only_covered_lines = true
```

coverage.py's branch measurement counts `if a and b:` as one two-way branch. It does not see short-circuit operands, so mutation testing catches what branch coverage misses there.

### .semgrep/tests.yml

```yaml
rules:
  - id: no-logic-in-tests
    languages: [python]
    severity: ERROR
    message: No if/for/while in a test body. Use pytest.mark.parametrize or a second test.
    paths: { include: ["/tests"] }
    patterns:
      - pattern-inside: |
          def $TEST(...):
            ...
      - metavariable-regex: { metavariable: $TEST, regex: ^test_ }
      - pattern-either:
          - pattern: "if $COND:\n  ..."
          - pattern: "for $X in $ITER:\n  ..."
          - pattern: "while $COND:\n  ..."
  - id: test-must-assert
    languages: [python]
    severity: ERROR
    message: Test has no assert and no pytest.raises, so it checks nothing.
    paths: { include: ["/tests"] }
    patterns:
      - pattern: |
          def $TEST(...):
            ...
      - metavariable-regex: { metavariable: $TEST, regex: ^test_ }
      - pattern-not: |
          def $TEST(...):
            ...
            assert $X
            ...
      - pattern-not: |
          def $TEST(...):
            ...
            with pytest.raises(...):
              ...
            ...
```

## One command for every gate

`Makefile` (recipe lines start with a tab). `quality-fast` runs in seconds on every agent stop and commit; `quality` is the CI gate.

```make
S    := tools/quality
SRC  := src
RUN  := uv run --frozen
BASE ?= origin/main

quality-fast:
	$(RUN) ruff format --check .
	$(RUN) ruff check .
	$(RUN) complexipy
	$(RUN) basedpyright
	$(RUN) lint-imports
	$(RUN) python $(S)/loc_budget.py $(SRC) tests
	$(RUN) python $(S)/complexity_gate.py $(SRC) --params-max 5 --nloc-max 60
	$(RUN) python $(S)/halstead_gate.py $(SRC)
	$(RUN) python $(S)/comment_density.py $(SRC) tests --fail-on-commented-code
	$(RUN) python $(S)/suppression_audit.py $(SRC) tests --zero coverage skipped any-type todo --baseline .quality/suppressions.json
	! grep -rn "complexipy: ignore" $(SRC)
	$(RUN) pytest -q -x

quality: quality-fast
	$(RUN) vulture
	$(RUN) deptry $(SRC)
	$(RUN) pylint $(SRC) tests
	$(RUN) semgrep scan --config .semgrep --error --metrics=off --quiet
	$(RUN) pytest -q --cov --cov-report=term-missing:skip-covered --cov-report=lcov:coverage.lcov --cov-report=json:coverage.json
	$(RUN) python -c "import json,sys; t=json.load(open('coverage.json'))['totals']; \
	  sys.exit(min(t['percent_statements_covered'], t['percent_branches_covered']) < 70)"
	$(RUN) python $(S)/complexity_gate.py $(SRC) --coverage coverage.lcov
	$(MAKE) mutation

mutation:
	$(RUN) mutmut run $$(git diff --name-only $(BASE)...HEAD -- '$(SRC)/*.py' \
	  | sed -e 's|^$(SRC)/||' -e 's|\.py$$|.*|' -e 's|/|.|g')
	$(RUN) mutmut export-cicd-stats
	$(RUN) python $(S)/mutation_score.py mutants/mutmut-cicd-stats.json --min-covered 80

.PHONY: quality quality-fast mutation
```

On the sample project (two modules, six tests including a Hypothesis property) `make quality` takes about 6 s. The `mutation` target turns changed files into mutant-name globs (`src/shop/domain/money.py` becomes `shop.domain.money.*`). An empty diff passes no globs, so mutmut mutates everything. That is right for a fresh repo or a nightly run (`make mutation BASE=HEAD`). The coverage one-liner holds line and branch coverage at 70% each, since `fail_under` only sees their combined figure (field names verified on coverage.py 7.17). For Strict, change its `70` to `100` and add `--max-survived 0` to the `mutation_score.py` line.

## Coverage report for CRAP

```bash
uv run pytest --cov --cov-report=lcov:coverage.lcov           # branch=true comes from pyproject
uv run python tools/quality/complexity_gate.py src --coverage coverage.lcov --top 15
# Cobertura works too: --cov-report=xml:coverage.xml, or `uv run coverage xml` after a run
```

The lcov `SF:` paths (`src/shop/...`) match the paths lizard sees, so no path mapping is needed.

## Mutation testing

- **Install/config:** `mutmut` is in the dev group. `[tool.mutmut]` is above. Other keys read by 3.8: `do_not_mutate` (globs ending in `.py` or `*`), `also_copy`, `timeout_multiplier` (default 15.0), `process_isolation` (`fork` or `forkserver`; use `forkserver` if the code under test is not fork-safe), and `type_check_command`. That last one filters mutants that fail type checking, but only for mypy or pyrefly with JSON output, e.g. `["mypy", "src", "--output", "json", "--disable-error-code", "unused-ignore"]`.
- **Run:** `mutmut run` runs everything. `mutmut run "shop.domain.money.*"` uses fnmatch on mutant names. Results are cached in `mutants/`, and a rerun on unchanged code reuses them (measured: 0 mutants re-executed). `use_git_change_detection` (default true) only decides whether changed non-.py files invalidate that cache. It does not limit mutation to your diff, so use the name globs for that.
- **Read survivors:** `mutmut results` lists survivors (`--all true` lists every status). `mutmut show shop.price.x_discount__mutmut_1` prints the diff. `mutmut browse` is a TUI. `mutmut apply <name>` writes the mutant into your source, so only use it on a clean tree.
- **Equivalent mutant:** put `# pragma: no mutate` on the line, with the reason after it: `# pragma: no mutate -- equivalent: max() already clamps at 0` (verified to work). Block forms are `# pragma: no mutate block` and `# pragma: no mutate start` / `# pragma: no mutate end`. Lines excluded from coverage (`pragma: no cover`, `exclude_also`) are never mutated either. That is one more reason the audit holds `coverage` at zero.
- **Fail CI:** `mutmut run` exits 0 when mutants survive and has no score-threshold option (3.8 `run` takes only `--max-children`), so the chain always reaches the gate. `mutmut export-cicd-stats` writes `mutants/mutmut-cicd-stats.json` with `killed, survived, total, no_tests, skipped, suspicious, timeout, check_was_interrupted_by_user, segfault`. `mutation_score.py` gates killed / (killed + survived) at 80% (timeouts count as killed; `no_tests` is left to the coverage gate, and `mutate_only_covered_lines` keeps it near zero anyway). Verified: a suite with 2 of 8 covered mutants killed exits 1 with "covered score 25.0% < 80%". Strict: add `--max-survived 0`.
- **What the score covers:** the stats count every mutant in the `mutants/` cache. With a fresh `mutants/` they cover only the globbed modules; with a cached one they also include earlier results for unchanged modules (both verified). On a project gated from day one that is fine; in ratchet mode, use a fresh `mutants/` for PR runs.
- **Runtime:** mutmut forks a worker per mutant and runs only the tests that cover the mutated function. It ran about 100 to 180 mutants/s on the sample. Real suites are dominated by per-test time, and Hypothesis tests multiply it, so lower `max_examples` in a settings profile for mutation runs. It needs POSIX `fork` (use WSL on Windows). In CI, cache `mutants/` keyed on the lockfile so reruns only re-test changed functions.

## Killing `any` / `unknown`

- **Checker:** basedpyright `typeCheckingMode = "recommended"` reports `reportAny` (any expression typed `Any`, including what leaks out of `json.loads`), `reportExplicitAny`, and `reportUnknown*` (Python's "unknown" is an inferred type the checker cannot resolve). Warnings fail the run. With mypy instead, use `strict = true`, `disallow_any_explicit`, `disallow_any_expr`, `disallow_any_unimported`, `disallow_any_decorated`, `warn_unreachable`, and `enable_error_code = ignore-without-code,redundant-expr,truthy-bool,possibly-undefined`.
- **Linter:** ruff `ANN` (in `ALL`) requires annotations, `ANN401` rejects `Any` annotations, and `TID251` bans importing `typing.Any` and `typing.cast`.
- **Boundary pattern:** raw bytes go straight into one schema, and typed values flow inward. Never let `json.loads(...)` output escape a function.

  ```python
  from typing import ClassVar
  from pydantic import BaseModel, ConfigDict, Field
  from shop.domain.money import Cents

  class OrderIn(BaseModel):
      model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid", strict=True)
      total_cents: int = Field(ge=0)
      parts: int = Field(gt=0)

  def parse_order(raw: bytes) -> tuple[Cents, int]:
      order = OrderIn.model_validate_json(raw)
      return Cents(order.total_cents), order.parts
  ```

  The `ClassVar` annotation is what basedpyright needs (`reportUnannotatedClassAttribute`). Decorating the model `@final` instead triggers a different error.
- **Not acceptable as replacements:** `object` or `dict[str, object]` passed around without narrowing, `Mapping[str, Any]`, `cast()`, `# type: ignore` / `# pyright: ignore` (blanket forms fail `PGH003`), `getattr(x, "field")` to dodge attribute types, or `TypedDict(total=False)` used as a bag of optionals. Narrow with `isinstance`, `TypeIs`, `match` on a union, or a schema.

## Language-specific slop to hunt

- `except Exception:` that logs and returns `None` or `{}`: `BLE001`, `S110`, `TRY400`. Catch the specific error at the call that raises it, or let it propagate.
- `try` wrapping a whole function body: `TRY300`, `TRY203` (useless try/except). Narrow it to one call.
- `raise ValueError(f"...")` built inline (`EM101`, `TRY003`), and re-raises without `from` (`B904`).
- `isinstance` checks or `if x is None` guards on parameters whose type already rules it out. basedpyright reports them (`reportUnnecessaryIsInstance`, `reportUnnecessaryComparison`, `reportUnreachable`). Delete them.
- Manual loops that re-implement `sum`/`any`/`all`, comprehensions or `dict.get`: `SIM110`, `PERF401`, `C419`, `RET504`, `SIM108`, `FURB110`.
- Boolean flag parameters (`def ship(order, express=True)`): `FBT001`, `FBT003`. Split into two functions.
- One-method classes, `Manager`/`Helper`/`utils.py` grab bags, and pass-through wrappers: vulture finds the unused ones. Fold the rest into plain functions.
- Old typing (`List`, `Optional`, `Dict`): `UP006`. `os.path` and `open()`: `PTH*`. Naive `datetime.now()`: `DTZ005`. f-strings in logging calls: `G004`. Mutable defaults: `B006`, `RUF012`. Leftover `print`/`breakpoint`: `T201`, `T100`. Docstrings that restate the signature, and narrating comments: `comment_density.py`.
- Tests that mock the unit under test, assert `mock.called` and nothing else, use `pytest.raises(Exception)` (`PT011`), loop over cases instead of `parametrize`, or `time.sleep`. The semgrep rules and mutation testing catch most of these.

## Cross-cutting conventions

One sanctioned module per concern: `shop/adapters/http.py` for service calls and their timeouts, `shop/adapters/retry.py` for retries, `shop/log.py` for the structured logger. The libraries are the org's choice, for example httpx or requests; tenacity or stamina; structlog, or stdlib `logging` with a JSON formatter. The `quality-tool-picker` skill compares them. Everything below was verified on ruff 0.17.3, import-linter 2.15 and semgrep 1.182.

- **Banned elsewhere:** the `banned-api` entries and per-file ignores in the pyproject above. `TID251` flags `import httpx`, `from stamina import retry` and every `logging.getLogger(...)` call outside the three modules. A per-file ignore lifts *every* banned API in that file, `typing.Any` included (basedpyright still reports `Any` there).
- **Exact per-import exemptions:** an import-linter `forbidden` contract with `ignore_imports`. Code that calls `shop.adapters.http` stays legal, because the ignored edge breaks the indirect chain. Every `ignore_imports` line must match a real import, or import-linter reports it.

  ```toml
  [[tool.importlinter.contracts]]
  name = "Only shop.adapters.http imports HTTP libraries"
  type = "forbidden"
  source_modules = ["shop"]
  forbidden_modules = ["httpx", "requests", "urllib3"]
  ignore_imports = ["shop.adapters.http -> httpx"]
  ```

- **Timeouts:** ruff `S113` (in `ALL`) flags `requests.get(...)` without `timeout` and any `httpx` call with `timeout=None` (httpx has a default timeout). It does not see methods on a `requests.Session` or `httpx.Client` object, so construct the one client in `http.py` with an explicit timeout and pin it with a test.
- **Logging:** `T201`/`T203` (`print`, `pprint`) and `LOG015` (calls on the root logger such as `logging.info(...)`) are in `ALL`, so only the `getLogger` and `structlog` bans above are extra.
- **Hand-rolled retry loops:** a sleep inside a loop is a retry or a poll. This semgrep rule (`.semgrep/conventions.yml`, run by `make quality`) also catches `from time import sleep`:

  ```yaml
  rules:
    - id: no-hand-rolled-retry
      languages: [python]
      severity: ERROR
      message: Retry or poll through shop.adapters.retry, not a sleep inside a loop.
      paths: { exclude: ["/src/shop/adapters/retry.py"] }
      patterns:
        - pattern-either:
            - pattern-inside: "for $X in $ITER:\n  ..."
            - pattern-inside: "while $COND:\n  ..."
        - pattern-either:
            - pattern: time.sleep(...)
            - pattern: asyncio.sleep(...)
  ```

## Invariants

- **Types:** use `NewType("Cents", int)` for units and IDs, and `Literal`/`Enum` for closed sets. Use frozen dataclasses or pydantic models with `extra="forbid"` whose constructors validate (`__post_init__` raising `ValueError`). Make "unchecked" and "checked" values different types (`RawEmail` → `VerifiedEmail`), so only the verifier can produce the second.
- **Boundaries:** import-linter `forbidden`/`layers` contracts (config above). Ruff `TID251` can confine a library to one module. Ban it in `banned-api` (`"sqlalchemy".msg = "Only shop.adapters.db talks to the database."` also bans `sqlalchemy.orm`), then exempt that one file with `[tool.ruff.lint.per-file-ignores] "src/shop/adapters/db.py" = ["TID251"]`.
- **Custom rules:** put semgrep rules in `.semgrep/` and run them with `semgrep scan --config .semgrep --error`.
- **Property tests (Hypothesis):** state the invariant, not an example.

  ```python
  @given(st.integers(min_value=0, max_value=10**9), st.integers(min_value=1, max_value=50))
  def test_split_preserves_total_and_count(total: int, parts: int) -> None:
      shares = split(Cents(total), parts)
      assert sum(shares) == total
      assert len(shares) == parts
      assert max(shares) - min(shares) <= 1
  ```

- **Contracts plus symbolic search (CrossHair):** write PEP 316 docstring contracts (`pre:` / `post:`, `__return__`) or icontract decorators, then run `uv run crosshair check src/shop/domain/money.py --per_condition_timeout=5`. It exits 1 with a concrete counterexample. On a buggy `split` it reported `false when calling bad_split(-1, 2) (which returns [-1, -1])`. Use it on pure domain functions, not on I/O.

## Ratchets for legacy code

Path B only. Gate new code fully and let old violations only shrink.

- `uv run complexipy --snapshot-create` writes `complexipy-snapshot.json`. Later runs fail on new functions over 21 and on tracked functions that got worse, and improved functions drop out automatically. `complexipy --diff origin/main` or `--staged` checks only changes.
- `uv run basedpyright --writebaseline` writes `.basedpyright/baseline.json`. Later runs report only new errors.
- `uv run diff-cover coverage.xml --compare-branch=origin/main --fail-under=70` holds changed lines to the 70% floor (Strict: `--fail-under=100`). `diff-quality --violations=ruff.check --compare-branch=origin/main --fail-under=100` does the same for lint, and it also supports `mypy` and `pylint`.
- `ruff check --add-noqa="legacy, see #123"` adds a specific per-line `noqa` to every existing violation once. Then `RUF100` and `suppression_audit.py --write-baseline .quality/suppressions.json` / `--baseline` keep the count falling.
- Run mutation only on changed modules (the `mutation` target), and run `mutmut run` on everything nightly.

## Pre-commit wiring

`.pre-commit-config.yaml` (verified with `pre-commit run --all-files`, then proven to fail on a cognitive-22 function, commented-out code, a TODO and a bare `noqa`):

```yaml
exclude: ^tools/quality/
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.17.1
    hooks:
      - id: ruff-check
      - id: ruff-format
  - repo: https://github.com/rohaquinlop/complexipy-pre-commit
    rev: v8.0.1
    hooks:
      - id: complexipy            # reads [tool.complexipy] from pyproject.toml
  - repo: local
    hooks:
      - id: basedpyright
        name: basedpyright
        entry: uv run --frozen basedpyright
        language: system
        types: [python]
        pass_filenames: false
      - id: budgets
        name: file budget
        entry: uv run --frozen python tools/quality/loc_budget.py
        language: system
        types: [python]
      - id: suppressions
        name: suppression audit
        # trailing "--" stops --zero from swallowing the filenames pre-commit appends
        entry: uv run --frozen python tools/quality/suppression_audit.py --zero coverage skipped any-type todo --baseline .quality/suppressions.json --
        language: system
        types: [python]
      - id: quality-fast
        name: make quality-fast
        entry: make quality-fast
        language: system
        pass_filenames: false
        stages: [pre-push]
```

Run `uv run pre-commit install --hook-type pre-commit --hook-type pre-push` once per clone. Keep the ruff and complexipy `rev` values in step with the versions in `uv.lock`.
