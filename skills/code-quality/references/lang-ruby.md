# Ruby and Rails gates

RuboCop (with rubocop-rspec, rubocop-rails and rubocop-sorbet) carries cyclomatic, perceived
complexity, ABC size, length, parameter and nesting budgets; SimpleCov enforces 100% line and
branch coverage; mutant kills mutants; Sorbet (or RBS + Steep) removes untyped holes; reek, spoom,
flay, jscpd, Herb and the bundled scripts cover smells, dead code, duplication, ERB and the rest.
Versions checked: RuboCop 1.92, SimpleCov 1.3, mutant 0.17, rubocop-sorbet 0.17, Herb 0.11.

## Tool map

| Gate | Tool | Setting / rule |
|------|------|----------------|
| Cyclomatic < 22 | RuboCop `Metrics/CyclomaticComplexity` | `Max: 21` (offense when score > Max) |
| Cognitive < 22 | RuboCop `Metrics/PerceivedComplexity` (closest analogue: counts `else`, weights `when`) | `Max: 21`. No native cognitive-complexity cop exists for Ruby |
| Halstead < 80 | `scripts/halstead_gate.py` (multimetric, per file) | default `--max 80`, fails at >= 80 |
| File < 500 lines | `scripts/loc_budget.py` | default 499. `Metrics/ClassLength`/`ModuleLength` count only code lines inside one class, so they are an early warning, not the gate |
| 100% line + branch | SimpleCov | `enable_coverage :branch`, `minimum_coverage line: 100, branch: 100` |
| CRAP < 25 | `scripts/complexity_gate.py --coverage coverage/coverage.xml` | lizard's Ruby parser cuts some methods short (`case ... end`), so treat CRAP as triage and RuboCop as the CCN gate |
| 0 surviving mutants | mutant (`mutant-rspec` / `mutant-minitest`) | `mutant run` exits non-zero on any alive mutation |
| 0 dead code | `spoom deadcode` (exits 1 on candidates); `debride` for a second opinion; RuboCop `Lint/UnusedMethodArgument`, `Lint/UselessAssignment`, `Lint/UselessMethodDefinition` | see Configuration |
| 0 duplication | jscpd (`threshold: 0`) + flay (fail on `IDENTICAL`); RuboCop `Lint/DuplicateBranch`, `Lint/DuplicateMethods` | flay `--mass` default 16 |
| 0 `T.untyped` | Sorbet `# typed: strict` + rubocop-sorbet `Sorbet/StrictSigil`, `Sorbet/ForbidTUntyped`, `Sorbet/ForbidTUnsafe`; or Steep with `D::Ruby.strict` | see "Killing untyped escape hatches" |
| ABC ≤ 17 | `Metrics/AbcSize` | `Max: 17` (the RuboCop default) |
| Function ≤ 50 NLOC | `Metrics/MethodLength` | `Max: 50`, `CountComments: false` |
| Params ≤ 5 | `Metrics/ParameterLists` | `Max: 5`, `CountKeywordArgs: true`, `MaxOptionalParameters: 3` |
| Nesting ≤ 3 | `Metrics/BlockNesting` | `Max: 3` (counts `if`/`case`/loops/`rescue`; `CountBlocks: false` by default) |
| Boolean ops ≤ 3 | semgrep rule `too-many-boolean-operators` below | catches pure `&&` or pure `\|\|` chains only; mixed chains still raise PerceivedComplexity |
| Comment density, no commented-out code | `scripts/comment_density.py --fail-on-commented-code` | RuboCop has no commented-out-code cop |
| Suppression ratchet, no blanket | `Style/DisableCopsWithinSourceCodeDirective` with `AllowWithReason: true`; `Lint/RedundantCopDisableDirective`; `scripts/suppression_audit.py` | blanket `rubocop:disable all` always fails the audit |
| Architecture boundaries | packwerk (`enforce_dependencies: true`) | `bin/packwerk check` |
| No unused deps | no reliable Ruby tool | review every Gemfile change; CODEOWNERS on `Gemfile`/`Gemfile.lock` |
| Every test asserts, no logic in tests | `RSpec/NoExpectationExample` (enabled by default); semgrep rule `rspec-no-logic-in-examples` | |
| TODO ban | `suppression_audit.py --zero todo` | |
| ERB templates | Herb linter (`@herb-tools/linter`, binary `herb-lint`) or `erb_lint` | `--fail-level warning` |
| Smells | reek (exit code 2 on smells) | `.reek.yml` below |
| DB invariants (Rails) | `database_consistency`, `strong_migrations`, `Rails/SkipsModelValidations` | see Invariants |

## Configuration

### Install (new project)

New files: `.rubocop.yml`, `.reek.yml`, `.jscpd.json`, `.semgrep.yml`, `lefthook.yml`,
`config/mutant.yml`, `bin/quality`, `sorbet/` (Rails also `.herb.yml`, `packs/*/package.yml`).

```ruby
# Gemfile additions
gem "sorbet-runtime"                     # or skip Sorbet: rbs + steep in :development
gem "strong_migrations"                  # Rails only
group :development, :test do
  %w[rubocop rubocop-rspec rubocop-sorbet sorbet tapioca spoom reek flay debride lefthook].each { |g| gem g, require: false }
  %w[rubocop-rails database_consistency packwerk].each { |g| gem g, require: false }   # Rails only
end
group :test do
  gem "rspec"                            # Rails: rspec-rails
  gem "simplecov", require: false
  gem "simplecov-cobertura", require: false  # 4.x needs simplecov ~> 1.0; 3.x for simplecov 0.22
  gem "mutant-rspec", require: false
  gem "prop_check"
end
```

```bash
bundle install && bundle exec tapioca init && bundle exec lefthook install   # tapioca: sorbet/config + gem RBIs
pip install lizard multimetric semgrep && npm add -D jscpd @herb-tools/linter
```

### .rubocop.yml

```yaml
plugins:                      # RuboCop 1.72+; older versions use `require:`
  - rubocop-rspec
  - rubocop-rails             # Rails only
  - rubocop-sorbet
AllCops:
  NewCops: enable
  Exclude: ["bin/**/*", "db/schema.rb", "db/migrate/**/*", "vendor/**/*", "node_modules/**/*", "sorbet/rbi/**/*", "tmp/**/*"]
# Metrics cops are marked "expected to be disabled by default in the next major release": enable explicitly.
Metrics/CyclomaticComplexity: { Enabled: true, Max: 21 }
Metrics/PerceivedComplexity:  { Enabled: true, Max: 21 }
Metrics/AbcSize:              { Enabled: true, Max: 17 }
Metrics/MethodLength:         { Enabled: true, Max: 50, CountComments: false }
Metrics/ClassLength:          { Enabled: true, Max: 499 }   # early warning; loc_budget.py is the file gate
Metrics/ModuleLength:         { Enabled: true, Max: 499 }
Metrics/BlockNesting:         { Enabled: true, Max: 3 }
Metrics/ParameterLists:       { Enabled: true, Max: 5, CountKeywordArgs: true, MaxOptionalParameters: 3 }
Metrics/BlockLength:          { Enabled: true, Max: 50, AllowedMethods: [describe, context, shared_examples, refine] }
Lint/DuplicateBranch:         { Enabled: true }
Lint/MissingCopEnableDirective: { Enabled: true, MaxRangeSize: 0 }   # disables may cover one line only
Style/DisableCopsWithinSourceCodeDirective:
  Enabled: true
  AllowWithReason: true       # only `# rubocop:disable Dept/Cop -- reason` is accepted
Sorbet/StrictSigil:     { Enabled: true, Exclude: ["spec/**/*", "db/**/*", "bin/**/*", "config/**/*"] }
Sorbet/ForbidTUntyped:  { Enabled: true }
Sorbet/ForbidTUnsafe:   { Enabled: true }
```

**Standard (standardrb) projects.** Standard's `config/base.yml` sets every `Metrics/*` cop to
`Enabled: false`, and neither `plugins` nor `extend_config` in `.standard.yml` can change a rule
Standard has already configured. Keep Standard for style and run the metrics as a second RuboCop
pass with its own config file, which contains only the `Metrics/*` block above (plus `AllCops`):

```bash
bundle exec standardrb
bundle exec rubocop --config .rubocop-metrics.yml --only Metrics
```

### spec/spec_helper.rb (first lines, before any app code is required)

```ruby
require "simplecov"
require "simplecov-cobertura"
SimpleCov.start do                          # Rails: SimpleCov.start "rails" do
  enable_coverage :branch                   # must come before minimum_coverage names :branch
  cover "{app,lib}/**/*.rb"                 # 1.x: also counts files no test ever loads
  minimum_coverage line: 100, branch: 100   # suite exits non-zero (status 2) below either
  formats :html, SimpleCov::Formatter::CoberturaFormatter   # writes coverage/coverage.xml
  deprecations :raise                       # 1.x: fail on legacy spellings
end
```

SimpleCov 0.22 has no `cover`, `formats` or `deprecations`: use `track_files "{app,lib}/**/*.rb"`
and `SimpleCov.formatters = [SimpleCov::Formatter::HTMLFormatter, SimpleCov::Formatter::CoberturaFormatter]`.
`SimpleCov.start "strict"` (1.x) is equivalent to 100% line, branch **and method** coverage.

### .reek.yml

```yaml
detectors:
  TooManyStatements: { max_statements: 15 }   # default 5 fights the 50-line method budget
  LongParameterList: { max_params: 5 }
  TooManyMethods:    { max_methods: 25 }
exclude_paths: [vendor, db/migrate, spec]
```

### .semgrep.yml

```yaml
rules:
  - id: rspec-no-logic-in-examples
    languages: [ruby]
    severity: ERROR
    message: Branching or looping inside an example hides which case failed. Write one example per case.
    paths: { include: ["/spec/**/*_spec.rb"] }
    patterns:
      - pattern-inside: "it $NAME do\n  ...\nend"
      - pattern-either:
          - pattern: "if $C\n  ...\nend"
          - pattern: "unless $C\n  ...\nend"
          - pattern: "case ...\nend"
          - pattern: "$C ? $A : $B"
          - pattern: "$XS.each { |$V| ... }"
          - pattern: "$XS.each do |$V|\n  ...\nend"
  - id: too-many-boolean-operators
    languages: [ruby]
    severity: ERROR
    message: More than 3 boolean operators in one condition. Extract a named predicate method.
    pattern-either:
      - pattern: $A && $B && $C && $D && $E
      - pattern: $A || $B || $C || $D || $E
```

Also create `.semgrepignore` (e.g. `vendor/`). Without one, semgrep's built-in ignore list
applies, and it skips `test/` and `tests/` (Minitest projects).

### .jscpd.json

```json
{ "threshold": 0, "minTokens": 50, "minLines": 5, "format": ["ruby"], "gitignore": true,
  "reporters": ["console"], "ignore": ["**/vendor/**", "**/node_modules/**", "**/db/schema.rb"] }
```

### ERB (Rails): .herb.yml or .erb_lint.yml

Run `npx herb-lint --init` to create `.herb.yml` (it records the Herb version so new rules don't
switch on silently), then add:

```yaml
linter:
  failLevel: warning            # default fails only on errors
  rules:
    erb-no-commented-out-output-tags: { severity: error }   # reported as info by default
    erb-strict-locals-required:  { enabled: true }          # opt-in: partials declare their locals
    erb-no-silent-statement:     { enabled: true }          # opt-in: no logic in <% %> tags
```

`erb-no-debug-output`, `erb-no-instance-variables-in-partials`, `erb-no-unsafe-raw` and
`herb-disable-comment-unnecessary` are on by default. Inline suppression is
`<%# herb:disable rule-name %>`. Alternative: `bundle exec erb_lint --lint-all` with
`.erb_lint.yml` containing `EnableDefaultLinters: true` and the `Rubocop` linter inheriting `.rubocop.yml`.

### Rails structure: packwerk and strong_migrations

Run `bin/packwerk init` and `bin/rails generate strong_migrations:install`. Each pack's
`package.yml` declares `enforce_dependencies: true` and `dependencies: [packs/accounts]`
(`strict` also refuses new entries in `package_todo.yml`).

## One command for every gate

```bash
#!/usr/bin/env bash
# bin/quality: every gate, fast ones first. CI runs it; pre-commit and the agent Stop hook call it too.
set -euo pipefail
S="${SLOP_SCRIPTS:-<skill-dir>/scripts}"
SRC=(app lib)                    # a gem: SRC=(lib)
BASE="${BASE_REF:-origin/main}"
fail() { echo "quality: $1" >&2; exit 1; }

bundle exec rubocop                            # style + every Metrics budget + Sorbet/RSpec/Rails cops
bundle exec srb tc                             # or: bundle exec steep check
bundle exec reek "${SRC[@]}"
bundle exec spoom deadcode "${SRC[@]}"
out=$(bundle exec flay "${SRC[@]}"); grep -q "IDENTICAL code found" <<<"$out" && fail "flay: $out"
npx --yes jscpd "${SRC[@]}"
semgrep scan --config .semgrep.yml --error --metrics=off --quiet
npx --yes @herb-tools/linter app/views         # Rails only
bundle exec database_consistency               # Rails only
bin/packwerk check                             # Rails only
python3 "$S/loc_budget.py" "${SRC[@]}" spec
python3 "$S/halstead_gate.py" "${SRC[@]}"
python3 "$S/comment_density.py" "${SRC[@]}" --fail-on-commented-code
python3 "$S/suppression_audit.py" "${SRC[@]}" spec --zero coverage skipped any-type todo
# suppression_audit.py knows `:nocov:` but not SimpleCov 1.x's `simplecov:disable`, Herb or strong_migrations escapes
if grep -rnE "simplecov:disable|herb:disable|safety_assured" "${SRC[@]}"; then fail "unreviewed escape hatch"; fi
bundle exec rspec                              # 100% line + branch, writes coverage/coverage.xml
python3 "$S/complexity_gate.py" "${SRC[@]}" --coverage coverage/coverage.xml   # CRAP < 25
bundle exec mutant run --since "$BASE"         # 0 alive mutations in changed subjects
```

`chmod +x bin/quality`. Each line exits non-zero on failure: RuboCop 1, reek 2, spoom 1,
jscpd 1 (`threshold: 0`), semgrep 1 (`--error`), SimpleCov 2, mutant 1. flay always exits 0,
hence the `grep` wrapper. Use `make quality` or a Rake task instead if the project has one.

## Coverage report for CRAP

The SimpleCov block above writes Cobertura XML (paths relative to the project root):
`bundle exec rspec && python <skill-dir>/scripts/complexity_gate.py app lib --coverage coverage/coverage.xml --top 20`.
For lcov, add `gem "simplecov-lcov"`, configure it with
`SimpleCov::Formatter::LcovFormatter.config { |c| c.report_with_single_file = true; c.single_report_path = "coverage/lcov.info" }`,
and add `SimpleCov::Formatter::LcovFormatter` to `formats`.

## Mutation testing

```yaml
# config/mutant.yml (also accepted: .mutant.yml, mutant.yml)
usage: opensource            # required. `commercial` needs a paid per-developer subscription
integration:
  name: rspec                # or minitest
includes: [lib]
requires: [my_gem]           # Rails: [./config/environment] plus environment_variables: { RAILS_ENV: test }
matcher:
  subjects: ["MyGem*"]       # Rails: descendants:ApplicationRecord, or your namespaces
mutation:
  operators: full            # light (default) skips the #== -> #eql? mutation
  timeout: 5.0               # seconds per mutation
coverage_criteria:
  timeout: false             # a timeout does not count as a kill
```

- **Licensing**: free for open source (`usage: opensource`, public repos only). Commercial code
  needs a per-developer subscription ($30/month or $250/year per mutant's `docs/commercial.md`,
  October 2026; CI needs no extra seats). No maintained free alternative exists (`mutest`: last
  release 2019). Without a licence, report gate 7 as not enforced. Never drop it silently.
- **Changed code**: `mutant run --since origin/main` picks subjects with lines in `git diff
  origin/main`. It misses indirect changes, so run a full `mutant run` nightly.
- **Rails**: add the eager-load hook `hooks.register(:env_infection_post) { Rails.application.eager_load! }`
  and per-worker DB isolation. The recipe is in mutant's `docs/rails.md`.
- **Survivors**: each `evil:Subject#method:path:line:id` block diffs one unkilled mutation.
  `mutant session subject 'Foo#bar'` replays the last run's survivors without re-running.
- **Equivalent mutants**: the only inline directive is `# mutant:disable` above a `def`, and it
  skips the *whole method*. Write the reason in the same comment. `mutation.ignore_patterns`
  (AST patterns, e.g. `send{selector=log}`) stops log calls being mutated. The audit counts `mutant:disable`.
- **Runtime and CI**: one fork per mutation, `jobs` defaults to the CPU count. Expect minutes
  for a gem and much longer for a Rails app. mutant exits non-zero ("Uncovered mutations
  detected") on any alive mutation, so no extra flag is needed.

## Killing untyped escape hatches

- **Sorbet**: `# typed: strict` in every `app/` and `lib/` file (enforced by `Sorbet/StrictSigil`)
  requires a `sig` on every method and typed constants and ivars. `Sorbet/ForbidTUntyped` and
  `Sorbet/ForbidTUnsafe` ban the explicit holes. Consider `Sorbet/ForbidTCast` and `ForbidTBind`
  as well. `# typed: strong` forbids even *using* untyped values, which is practical only in leaf modules.
- Generate RBIs instead of writing `T.untyped`: `bin/tapioca gems` covers dependencies and
  `bin/tapioca dsl` covers Rails DSLs. `bundle exec spoom srb coverage` tracks what is left.
- **RBS + Steep** instead: the `Steepfile` holds `D = Steep::Diagnostic` and `target :app do signature "sig";
  check "app", "lib"; configure_code_diagnostics(D::Ruby.strict); end`. Strict reports `FallbackAny` ("Cannot detect
  the type of the expression") as a warning, and `steep check` fails on warnings by default
  (`--severity-level=warning`). Steep has no diagnostic for an explicit `untyped` in `.rbs`
  files, so add `if grep -rnw untyped sig; then fail "untyped in sig/"; fi` to `bin/quality`.
- **At the boundary**: parse params and JSON once into `T::Struct` / `Data.define` values.
  Never pass `params` or `T::Hash[String, T.untyped]` inward, and never swap `T.untyped` for
  an equally empty `T.anything` or `Object`.

## Language-specific slop to hunt

- `rescue => e` that logs and carries on; `rescue nil` modifiers (`Style/RescueModifier`,
  `Lint/SuppressedException`, ideally with `AllowComments: false`).
- `&.` chains and `|| {}` / `|| []` defaults on values that can't be nil.
- `respond_to?` / `is_a?` ladders instead of polymorphism. `send` with built-up method names,
  `method_missing` and `define_method` loops, all of which hide code from every metric and from mutant.
- Service objects that wrap a single ActiveRecord call. Concerns used as junk drawers. Business
  rules in callbacks, which `update_column` and `insert_all` silently skip.
- Leftover `puts`, `pp`, `binding.irb` and `debugger` (`Lint/Debugger`, `Rails/Output`,
  Herb's `erb-no-debug-output`). Logic in ERB. N+1 queries.
- Tests that use `allow_any_instance_of`, stub the subject (`RSpec/SubjectStub`), assert
  `be_truthy` when the exact value is known, stack `let!` towers, or `sleep`.
- YARD blocks that restate the signature.

## Invariants

Model validations are not invariants. `update_column(s)`, `update_all`, `insert_all`,
`upsert_all`, `toggle!`, `touch` and raw SQL skip them (`Rails/SkipsModelValidations` flags
these), and `validates uniqueness:` is check-then-insert, so concurrent requests both pass. Put
the rule in the database. Keep the validation only for the error message:

```ruby
create_table :orders do |t|
  t.references :user, null: false, foreign_key: true
  t.string :external_id, null: false
  t.bigint :total_cents, null: false
  t.check_constraint "total_cents >= 0", name: "orders_total_cents_non_negative"
  t.index [:user_id, :external_id], unique: true
end
# spec: the constraint holds even when validations are bypassed
expect { create(:order).update_column(:total_cents, -1) }.to raise_error(ActiveRecord::StatementInvalid)
```

`database_consistency` fails when validations and constraints disagree (presence without
`NOT NULL`, uniqueness without a unique index). strong_migrations blocks unsafe migrations, and
each `safety_assured { }` is a suppression that needs a reason. packwerk makes "only
`packs/auth` creates users" checkable. Property tests use prop_check:
`PropCheck.forall(G.array(G.integer)) { |xs| expect(sort(xs)).to eq(xs.sort) }` with
`G = PropCheck::Generators` (rantly is the older option).

## Ratchets for legacy code

Path B only: gate new code fully and let old counts only fall.

- RuboCop: `rubocop --auto-gen-config --auto-gen-only-exclude --no-exclude-limit` writes
  `.rubocop_todo.yml` (`inherit_from` it). Offending files are listed rather than `Max` raised
  or the cop disabled. Delete entries as files get fixed and reject any diff that adds to the file.
- `standardrb --generate-todo`, `reek --todo`, `database_consistency -g`, packwerk
  `enforce_dependencies: strict` + `package_todo.yml`: same rule, they only shrink.
- SimpleCov 1.x: `simplecov ratchet` (per-file floors in `.simplecov_baseline.yml`) and
  `simplecov patch --base origin/main --minimum 100` (changed lines). mutant: `--since origin/main`.
- `suppression_audit.py . --write-baseline .quality/suppressions.json`, then `--baseline` in CI.

## Pre-commit wiring

```yaml
# lefthook.yml  (gem "lefthook", then: bundle exec lefthook install)
pre-commit:
  parallel: true
  jobs:
    - { name: rubocop, glob: "*.{rb,rake}", run: "bundle exec rubocop --force-exclusion {staged_files}" }
    - { name: sorbet,  glob: "*.rb",        run: "bundle exec srb tc" }
    - { name: herb,    glob: "*.erb",       run: "npx --yes @herb-tools/linter {staged_files}" }
    - { name: budgets, glob: "*.{rb,rake}", run: "python3 tools/quality/loc_budget.py {staged_files}" }
    - { name: escapes, glob: "*.{rb,rake,erb}", run: "python3 tools/quality/suppression_audit.py {staged_files}" }
pre-push:
  jobs:
    - { name: quality, run: bin/quality }
```

overcommit is the alternative: `.overcommit.yml` with `PreCommit: { RuboCop: { enabled: true } }`,
then `overcommit --install`. Coverage, mutation and dead code need the whole suite, so they run
in `pre-push` and CI rather than `pre-commit`.
