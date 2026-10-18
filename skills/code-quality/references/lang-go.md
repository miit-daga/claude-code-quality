# Go gates

golangci-lint v2 is the single entry point for formatting and most per-function gates
(gocyclo, gocognit, funlen, revive, dupl, depguard, unused, unparam). `go test` covers
coverage, fuzzing and `-race`. deadcode, go-test-coverage, gremlins, ast-grep and the
bundled scripts fill the gaps: Halstead, CRAP, mutation testing, the `any` ban,
boolean-operator counts and file budgets. Facts below were checked against golangci-lint
v2.15 (`.golangci.reference.yml`), gremlins v0.6.0 and the Go 1.25+ `go` command docs.

## Tool map

| Gate | Tool | Setting / rule |
|------|------|----------------|
| Cyclomatic < 22 | golangci `gocyclo`; `complexity_gate.py` (lizard) for CRAP | `min-complexity: 21`. Reports `> 21` (message reads "is high (> 21)") |
| Cognitive < 22 | golangci `gocognit` | `min-complexity: 21`. Reports `> 21` |
| Halstead difficulty < 80 | no Go linter. `scripts/halstead_gate.py` (per file, via multimetric) | default `--max 80`. `maintidx` (`under: 20`) uses Halstead volume but is a different metric |
| File < 500 lines | revive `file-length-limit`; `scripts/loc_budget.py` | `max: 499`. Passes while `lines <= max` |
| 100% coverage | `go test -coverprofile` + go-test-coverage | Statement coverage only: Go has **no branch coverage**. Gate file/package/total at 100. Optional condition coverage: `gobco` (third party; it prints `Condition coverage: X/Y`, so parse that and require X = Y; its exit status is unverified) |
| CRAP < 25 | `scripts/complexity_gate.py --coverage cover.out` | reads Go cover profiles directly |
| 0 surviving mutants | gremlins (`--diff`) + JSON gate; go-mutesting as fallback | see Mutation testing |
| 0 dead code | `unused` (standard set), `unparam`, revive `unused-parameter`/`unused-receiver`, `deadcode -test` | `unparam.check-exported: true` for applications, `false` for libraries with external importers |
| 0 duplication | golangci `dupl`; `jscpd --format go` across the repo | `dupl.threshold: 100` (tokens; default 150) |
| 0 `any` / `interface{}` | ast-grep rule `go-no-any` (below); revive `use-any` | No golangci linter bans the empty interface. forbidigo `^any$` matches the identifier but also flags `[T any]` constraints, and it never sees `interface{}` |
| ABC ≤ 17 | none for Go | `complexity_gate.py` lizard token count is the only proxy |
| Function ≤ 50 NLOC | `funlen`; `complexity_gate.py --nloc-max 50` | `lines: 50` (reports `> 50`, counts blank lines, skips comments by default) |
| Params ≤ 5 | revive `argument-limit`; `complexity_gate.py --params-max 5` | `arguments: [5]`, reports `> 5` |
| Nesting ≤ 3 | revive `max-control-nesting`; `nestif` as a second signal | `arguments: [3]` (fires when nesting exceeds 3); `nestif.min-complexity: 5` reports `>= 5` |
| Bool operators ≤ 3 | ast-grep rule `go-max-bool-ops` | no linter counts `&&`/`\|\|` |
| Comment density, commented-out code | `scripts/comment_density.py`; gocritic `commentedOutCode` | enable the check explicitly (it is not in the default stable set) |
| Suppression ratchet | `nolintlint`; `scripts/suppression_audit.py` | `require-specific: true`, `require-explanation: true`. The script also counts go-test-coverage `// coverage-ignore` and go-mutesting `// mutator-disable-*` |
| Architecture | `internal/` + `depguard` rules | see Invariants |
| Unused deps | `go mod tidy -diff` | prints a diff and exits non-zero when go.mod/go.sum are not tidy |
| No logic in tests / every test asserts | no linter | Table-driven `for _, tc := range` with `t.Run` and `if got != want { t.Errorf }` is idiomatic Go. Ban branching on `tc` fields in review. Mutation testing catches tests that assert nothing |
| TODO ban | `godox` | `keywords: [TODO, FIXME, HACK, XXX, BUG]` |

## Configuration

Project layout for a new service (Go ≥ 1.24, needed for `tool` directives):

```text
go.mod                     # module example.com/app; tool lines added by `go get -tool`
cmd/app/main.go            # one line: os.Exit(run(os.Args[1:], os.Stdout, os.Stderr))
internal/domain/           # types and invariants; no I/O imports (depguard)
internal/app/              # use cases
internal/adapters/         # http, db, JSON decode at the boundary
.golangci.yml  .testcoverage.yml  sgconfig.yml  .ast-grep/rules/  lefthook.yml  Makefile
tools/quality/             # vendored copies of the skill's scripts (see agent-loop.md)
.quality/                  # baselines, equivalent-mutant list
```

Install (pin versions; `go get -tool` records them in go.mod so CI gets the same ones):

```bash
go mod init example.com/app
curl -sSfL https://golangci-lint.run/install.sh | sh -s -- -b "$(go env GOPATH)/bin" v2.15.0
go get -tool golang.org/x/tools/cmd/deadcode@latest
go get -tool github.com/vladopajic/go-test-coverage/v2@latest
go get -tool github.com/go-gremlins/gremlins/cmd/gremlins@v0.6.0
go get -tool github.com/boumenot/gocover-cobertura@latest      # only if CI wants Cobertura XML
python3 -m venv .venv && .venv/bin/pip install lizard radon multimetric ast-grep-cli
brew install lefthook jq      # or: pipx install lefthook
mkdir -p tools/quality .quality && cp <skill-dir>/scripts/*.py tools/quality/
```

golangci-lint's docs recommend the binary install over `go install`/`go tool`. Run
`golangci-lint config verify` after editing the config.

### .golangci.yml

```yaml
version: "2"
linters:
  default: standard            # errcheck, govet, ineffassign, staticcheck, unused
  enable: [gocyclo, gocognit, funlen, nestif, dupl, maintidx, unparam, depguard, forbidigo,
           revive, godox, nolintlint, gocritic, exhaustive, gochecksumtype, errorlint,
           forcetypeassert, nilerr, musttag]
  settings:
    gocyclo: { min-complexity: 21 }     # reports > 21
    gocognit: { min-complexity: 21 }    # reports > 21
    funlen: { lines: 50, statements: -1, ignore-comments: true }   # -1 disables the statement count
    nestif: { min-complexity: 5 }       # reports >= 5
    dupl: { threshold: 100 }            # tokens
    maintidx: { under: 20 }             # reports MI < 20
    unparam: { check-exported: true }   # false for libraries imported by other modules
    errcheck: { check-type-assertions: true, check-blank: true }   # `_ = f()` is a swallowed error
    exhaustive: { default-signifies-exhaustive: false }
    gochecksumtype: { default-signifies-exhaustive: false }
    godox: { keywords: [TODO, FIXME, HACK, XXX, BUG] }
    nolintlint: { require-specific: true, require-explanation: true, allow-unused: false }
    gocritic: { enabled-checks: [commentedOutCode] }   # added to the default stable checks
    forbidigo:
      forbid:
        - pattern: ^(fmt\.Print.*|print|println)$
          msg: use the logger
    depguard:
      rules:
        domain-is-pure:                 # the domain never does I/O or decoding
          files: ["**/internal/domain/**"]
          deny:
            - { pkg: net/http, desc: "HTTP lives in internal/adapters" }
            - { pkg: database/sql, desc: "persistence lives in internal/adapters" }
            - { pkg: encoding/json, desc: "decode at the boundary, pass domain types inward" }
            - { pkg: example.com/app/internal/adapters, desc: "domain must not depend on adapters" }
        no-legacy:
          deny:
            - { pkg: github.com/pkg/errors, desc: "use errors / fmt.Errorf with %w" }
            - { pkg: io/ioutil, desc: "deprecated; use io and os" }
    revive:
      enable-default-rules: true        # otherwise listing any rule disables the defaults
      rules:
        - { name: argument-limit, arguments: [5] }
        - { name: max-control-nesting, arguments: [3] }
        - name: file-length-limit
          arguments: [{ max: 499, skip-comments: false, skip-blank-lines: false }]
        - { name: flag-parameter }      # bool params that switch behaviour
        - { name: unused-parameter }
        - { name: unused-receiver }
        - { name: early-return }
        - { name: superfluous-else }
        - { name: deep-exit }           # os.Exit / log.Fatal outside main and init
        - { name: use-any }             # normalises interface{} to any so one ban covers both
  exclusions:
    generated: strict                   # only files with the standard "Code generated ... DO NOT EDIT." header
    rules:
      - path: _test\.go                 # table-driven tests are long tables by design
        linters: [funlen, dupl]
    paths: []                           # vendored / generated dirs only, listed here and nowhere else
formatters:
  enable: [gofumpt, goimports]
issues:
  max-issues-per-linter: 0              # show everything, not the first 50
  max-same-issues: 0
```

### .testcoverage.yml (go-test-coverage)

```yaml
profile: cover.out
threshold: { file: 100, package: 100, total: 100 }
force-annotation-comment: true   # any `// coverage-ignore` must carry a reason
exclude:
  paths: []                      # e.g. \.pb\.go$ for generated code; nothing hand-written
```

Keep `main()` to one statement and test `run(...)`. If that single line is the only
uncovered statement, either list `^cmd/app/main\.go$` under `exclude.paths` with a
comment, or cover it with a `go build -cover` binary run under `GOCOVERDIR` in an
integration test.

### sgconfig.yml and .ast-grep/rules/go.yml

```yaml
# sgconfig.yml
ruleDirs: [.ast-grep/rules]
```

```yaml
id: go-no-any
language: go
severity: error
message: "any / interface{} is banned. Decode into a concrete type at the boundary."
rule:
  any:
    - { kind: type_identifier, regex: ^any$ }
    - { kind: interface_type, regex: '^interface\s*\{\s*\}$' }
  not:
    inside: { kind: type_parameter_list, stopBy: end }   # `[T any]` constraints are typed
---
id: go-max-bool-ops
language: go
severity: error
message: "More than 3 boolean operators in one expression. Name the condition."
rule:
  kind: binary_expression
  regex: '(&&|\|\|)(?s:.*)(&&|\|\|)(?s:.*)(&&|\|\|)(?s:.*)(&&|\|\|)'
  not:
    inside: { kind: binary_expression, stopBy: end }     # outermost expression only
```

Both rules were tested with ast-grep 0.51: `[T any]` passes; `map[string]any`,
`v interface{}`, `Box[any]` and `a && (b || c) && d && e` fail; `ast-grep scan` exits 1.

## One command for every gate

```make
SHELL  := bash
S      := tools/quality
PY     := .venv/bin/python
SRC    := cmd internal
BASE   ?= origin/main

quality-fast:
	golangci-lint fmt --diff                          # exits 1 if anything would be reformatted
	golangci-lint run ./...
	.venv/bin/ast-grep scan
	$(PY) $(S)/loc_budget.py $(SRC)
	$(PY) $(S)/complexity_gate.py $(SRC) --params-max 5 --nloc-max 50
	$(PY) $(S)/halstead_gate.py $(SRC)
	$(PY) $(S)/comment_density.py $(SRC) --fail-on-commented-code
	$(PY) $(S)/suppression_audit.py $(SRC) --zero coverage mutation skipped any-type todo
	go test -race -count=1 ./...

quality: quality-fast
	go test -covermode=atomic -coverpkg=./... -coverprofile=cover.out ./...
	go tool go-test-coverage --config=.testcoverage.yml
	$(PY) $(S)/complexity_gate.py $(SRC) --coverage cover.out
	out="$$(go tool deadcode -test ./...)"; [ -z "$$out" ] || { echo "$$out"; exit 1; }
	go mod tidy -diff
	bash $(S)/gremlins_gate.sh $(BASE)

.PHONY: quality quality-fast
```

- `suppression_audit.py --zero any-type` flags `any` / `interface{}` in parameters, slices and
  maps, and skips generic constraints such as `[T any]`. The ast-grep rule is the stricter,
  syntax-aware gate; the script is the cross-language backstop.
- `deadcode` exits 0 even when it finds dead functions, hence the empty-output check.
  It reports functions unreachable from `main` (and, with `-test`, from tests) via RTA.
- `-race` needs cgo (`CGO_ENABLED=1`) and a supported platform (linux/darwin amd64/arm64
  and a few others).

## Coverage report for CRAP

```bash
go test -covermode=atomic -coverpkg=./... -coverprofile=cover.out ./...
python3 <skill-dir>/scripts/complexity_gate.py cmd internal --coverage cover.out
go tool cover -func=cover.out | tail -1        # "total: (statements) 100.0%"
go tool gocover-cobertura < cover.out > coverage.xml   # Cobertura for CI UIs, run from the go.mod dir
```

The script matches the profile's import-path file names (`example.com/app/internal/x.go`)
to `internal/x.go` by suffix. Run it from the module root.

## Mutation testing

gremlins mutates arithmetic, comparison boundaries, negated conditionals,
increment/decrement and negatives by default. Run it from the module root:
`go tool gremlins unleash` (aliases `run`, `r`). Incremental run on changed code:
`--diff origin/main` (CI needs `fetch-depth: 0`). Config lives in `.gremlins.yaml`:

```yaml
unleash:
  timeout-coefficient: 10      # default 5; raise if mutants show TIMED OUT on a busy CI box
  exclude-files: ['\.pb\.go$']  # regexps; generated code only
mutants:
  invert-logical: { enabled: true }      # off by default; && <-> || catches agent boolean slop
  invert-loopctrl: { enabled: true }
```

**Do not use `--threshold-efficacy 100` as the gate.** In v0.6.0 the check is
`efficacy <= threshold`, so a perfect 100% still exits 10. Gate on the JSON instead.
gremlins writes no file when the diff produced no mutants. `tools/quality/gremlins_gate.sh`:

```bash
#!/usr/bin/env bash
# Fail if any mutant LIVED or was NOT COVERED, minus documented equivalent mutants.
set -euo pipefail
rm -f gremlins.json
go tool gremlins unleash --diff "${1:-origin/main}" --output gremlins.json
[ -f gremlins.json ] || { echo "no mutants in diff"; exit 0; }
allow=.quality/equivalent-mutants.txt   # lines: <file_name>:<line>:<col> <TYPE>  # reason
survivors=$(jq -r '.files[] | .file_name as $f | .mutations[]
    | select(.status == "LIVED" or .status == "NOT COVERED")
    | "\($f):\(.line):\(.column) \(.type)"' gremlins.json \
  | grep -vxF -f <(sed -e 's/[[:space:]]*#.*//' -e '/^$/d' "$allow" 2>/dev/null) || true)
[ -z "$survivors" ] || { printf 'Surviving mutants:\n%s\n' "$survivors"; exit 1; }
```

Reading survivors: run with `--output-statuses lc --output-diff-statuses l` to print
each LIVED mutant with its `-x > y / +x >= y` diff. `LIVED` means a test ran the line and
nothing failed: add the assertion, or delete the code if the mutation changed nothing.
`NOT COVERED` means no test of that package executes it. gremlins runs only the mutated
package's own tests (unless `--integration`), so cross-package coverage does not kill mutants.

**Equivalent mutants.** gremlins has no inline skip comment. Record the mutant in
`.quality/equivalent-mutants.txt` exactly as the gate prints it, followed by `# reason`.
Line and column move when the file changes, so the entry fails loudly instead of rotting.
go-mutesting (avito-tech fork, `go install -v github.com/avito-tech/go-mutesting/...`) does
support inline `// mutator-disable-next-line <mutator>` and `// mutator-disable-func`.
`suppression_audit.py` counts both (category `mutation`). ooze runs as a
`//go:build mutation` test with `ooze.Release(t)` and fails below
`WithMinimumThreshold` (default 1.0), but it has no per-line skip.

Runtime: each mutant is a `go test` of one package, parallel across cores. Expect
minutes per changed package. Whole-module runs on a mature service can take hours, so
keep `--diff` in CI and run the full module nightly.

## Killing `any` / untyped escape hatches

Settings: the `go-no-any` ast-grep rule plus revive `use-any`. Allowed pattern: decode
once, at the edge, into a struct with tags (musttag enforces the tags), then convert to a
domain type through its constructor:

```go
type createOrderReq struct {
	SKU string `json:"sku"`
	Qty int    `json:"qty"`
}

func decodeCreateOrder(r io.Reader) (order.Line, error) {
	dec := json.NewDecoder(r)
	dec.DisallowUnknownFields()
	var req createOrderReq
	if err := dec.Decode(&req); err != nil {
		return order.Line{}, fmt.Errorf("decode create order: %w", err)
	}
	return order.NewLine(req.SKU, req.Qty) // validates; domain never sees raw JSON
}
```

Calling stdlib functions whose parameters are `any` (`json.Unmarshal`, `fmt.Errorf`) is
fine. Your own signatures and fields may not contain `any`. Do not replace it with
`type Payload = interface{}`, `map[string]any` renamed, `json.RawMessage` or `[]byte`
passed inward, `reflect.Value`, a marker interface with one dummy method, or a generic
`[T any]` that only shuttles the value through. Use a concrete struct, a small interface
with real methods, or a sealed sum type (`//sumtype:decl` + gochecksumtype).

## Language-specific slop to hunt

- `if err != nil { return err }` with no context, or `log.Println(err); return nil`. Fix:
  `return fmt.Errorf("load user %d: %w", id, err)`, and let errorlint enforce `errors.Is/As`.
- `_ = f()` and ignored `Close()` errors. Fix: handle them (`check-blank: true` flags them).
- `v.(T)` without `ok`. Fix: `t, ok := v.(T)`, or better, remove the `any` (forcetypeassert).
- Interfaces declared next to their only implementation "for mocking". Fix: delete the
  interface. Define small interfaces at the consumer, only when there are two implementations or a test needs one.
- `utils`/`helpers`/`common` packages. Fix: move each function next to its caller or
  into a package named for what it does.
- Getters/setters on plain data. Fix: exported fields, or unexported fields with a constructor when an invariant exists.
- `context.Background()` deep in call stacks, goroutines without cancellation or `WaitGroup`.
  Fix: thread `ctx` from the entry point and own each goroutine's lifetime.
- `panic` for expected errors, `os.Exit`/`log.Fatal` outside `main` (revive `deep-exit`).
- `init()` doing I/O or global mutable state. Fix: explicit construction in `run`.
- Re-implemented stdlib: hand-rolled `contains`, `min`/`max`, `sort` loops. Fix: `slices`,
  `maps`, `cmp`, `strings.Cut` (staticcheck and gocritic point at many).
- Tests with `time.Sleep` for synchronisation. Fix: channels, `testing/synctest` (Go 1.25+), or injected clocks.

## Invariants

Ladder for Go, cheapest first:

1. **Types and constructors.** Unexported fields plus `NewX(...) (X, error)` in
   `internal/domain`. The zero value `X{}` can still be built from other packages, so
   make it detectably invalid (`IsZero`) or valid by design.
2. **Package boundaries.** `internal/` stops other modules importing the code at all.
   depguard enforces "only this package may do that", e.g. only the store touches SQL:
   ```yaml
   only-store-uses-sql:
     files: ["$all", "!**/internal/adapters/store/**"]
     deny: [{ pkg: database/sql, desc: "only internal/adapters/store talks to the DB" }]
   ```
3. **Exhaustiveness.** `exhaustive` for enum switches, `gochecksumtype` for sealed
   interfaces marked `//sumtype:decl`.
4. **Banned APIs.** forbidigo patterns, ast-grep rules in `.ast-grep/rules/`.
5. **Property tests and fuzzing.** `pgregory.net/rapid` for properties; native fuzzing for parsers:
   ```go
   func FuzzNewLine(f *testing.F) {
   	f.Add("SKU-1", 3)
   	f.Fuzz(func(t *testing.T, sku string, qty int) {
   		line, err := order.NewLine(sku, qty)
   		if err == nil && line.Qty() <= 0 {
   			t.Fatalf("NewLine(%q, %d) accepted non-positive qty", sku, qty)
   		}
   	})
   }
   ```
   Run `go test -run='^$' -fuzz='^FuzzNewLine$' -fuzztime=60s ./internal/domain/order`.
   `-fuzz` takes exactly one package and must match exactly one fuzz target. Failing
   inputs land in `testdata/fuzz/FuzzNewLine/`. Commit them; plain `go test` replays them.
6. **Concurrency.** `go test -race` in every run, `testing/synctest` for time-dependent
   code. For protocols, model in TLA+ or P. Gobra (ETH Zürich) verifies Go code but is
   research-grade.

## Ratchets for legacy code

- Lint only new issues: `golangci-lint run --new-from-merge-base=origin/main` (or
  `issues.new-from-merge-base` / `new-from-rev` in config; `--whole-files` widens to whole changed files).
- Mutation on the diff: `gremlins unleash --diff origin/main` (the gate script above).
- Coverage on the diff: `gocover-cobertura < cover.out > coverage.xml && diff-cover coverage.xml --compare-branch=origin/main --fail-under=100`.
- Suppressions: `suppression_audit.py . --write-baseline .quality/suppressions.json`, then `--baseline` in CI.

## Pre-commit wiring

```yaml
# lefthook.yml  (lefthook v2; `lefthook install` once per clone)
pre-commit:
  parallel: true
  jobs:
    - name: format
      glob: "*.go"
      run: golangci-lint fmt --diff
    - name: lint                       # golangci-lint needs whole packages, not single files
      glob: "*.go"
      run: golangci-lint run ./...
    - name: ast-grep
      glob: "*.go"
      run: .venv/bin/ast-grep scan {staged_files}
    - name: budgets
      glob: "*.go"
      run: >-
        .venv/bin/python tools/quality/loc_budget.py {staged_files} &&
        .venv/bin/python tools/quality/complexity_gate.py {staged_files} --params-max 5 --nloc-max 50
pre-push:
  jobs:
    - name: quality-fast
      run: make quality-fast
```
