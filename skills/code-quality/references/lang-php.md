# PHP gates

PHPStan at `level: max` with strict-rules, a cognitive-complexity extension and
shipmonk's dead-code detector does most of the work. PHP_CodeSniffer and PHPMD add cyclomatic,
nesting, length and parameter budgets. PHPUnit (under Xdebug) and a small Clover check cover
100% line and branch coverage plus CRAP, Infection kills mutants, and jscpd, deptrac, Rector,
PHP-CS-Fixer and the bundled scripts handle the rest. Versions checked: PHPStan 2.3, PHPMD 3.0,
PHPUnit 12–13, Infection 0.35, Psalm 6.20, PHPCS 4.0, Slevomat 8.31.

## Tool map

| Gate | Tool | Setting / rule |
|------|------|----------------|
| Cyclomatic < 22 | PHPCS `Generic.Metrics.CyclomaticComplexity` | `absoluteComplexity` 21 (error when > value). PHPMD 3 alternative: `CyclomaticComplexity` `maximum` 21 (PHPMD 2.x: `reportLevel` 22, which fires at >=) |
| Cognitive < 22 | `tomasvotruba/cognitive-complexity` (PHPStan) | `cognitive_complexity.function: 21` (reported when > limit, despite the "keep it under" message) |
| Halstead < 80 | `scripts/halstead_gate.py` (multimetric, per file) | fails at >= 80 |
| File < 500 lines | `scripts/loc_budget.py` | default 499 physical lines |
| 100% line + branch | PHPUnit + Xdebug path coverage → Clover → `tools/check_clover.py` | PHPUnit has no built-in fail-under. PCOV is line-only |
| CRAP < 25 | the same Clover check (PHPUnit writes `crap` per method) and `scripts/complexity_gate.py --coverage build/clover.xml` | |
| 0 surviving mutants | Infection | `--min-msi=100 --min-covered-msi=100` |
| 0 dead code | `shipmonk/dead-code-detector` (methods, constants, enum cases, properties; not whole classes) + PHPMD `unusedcode` | or Psalm `findUnusedCode` |
| 0 duplication | jscpd (`phpcpd` is abandoned) | `threshold: 0`, `format: ["php"]` |
| 0 `mixed` | PHPStan level 10 (`max`): errors on operations on explicit **and** implicit (missing-type) mixed | ban written `mixed`: `suppression_audit.py --zero any-type` |
| ABC ≤ 17 | no PHP tool | rely on cognitive + Halstead; or lizard token count as proxy |
| Function ≤ 50 NLOC | `SlevomatCodingStandard.Functions.FunctionLength` | `maxLinesLength` 50 (error when > max; `includeComments` / `includeWhitespace` decide what counts) |
| Params ≤ 5 | PHPMD `ExcessiveParameterList` | 3.x `maximum` 5 (2.x: `minimum` 6) |
| Nesting ≤ 3 | PHPCS `Generic.Metrics.NestingLevel` | `absoluteNestingLevel` 3 (error when >) |
| Boolean ops ≤ 3 | semgrep rule below | pure `&&` / `\|\|` chains; mixed chains raise cognitive complexity anyway |
| Comment density, no commented-out code | `scripts/comment_density.py --fail-on-commented-code` | |
| Suppression ratchet, no blanket | PHPStan `reportIgnoresWithoutComments: true` (2.1.41+) + `reportUnmatchedIgnoredErrors` (default true); Psalm `findUnusedPsalmSuppress`; `scripts/suppression_audit.py` | bare `@phpstan-ignore-line` / `-next-line` are rejected |
| Architecture boundaries | deptrac (`deptrac/deptrac`; `qossmic/deptrac` is abandoned) or Pest `arch()` tests | |
| No unused deps | `shipmonk/composer-dependency-analyser` | unused, shadow and dev-in-prod dependencies |
| Every test asserts | PHPUnit `beStrictAboutTestsThatDoNotTestAnything` (default true) + `failOnRisky="true"` | |
| No logic in tests | semgrep rule `phpunit-no-logic-in-tests` | use `#[DataProvider]` instead |
| TODO ban | `suppression_audit.py --zero todo` | |
| Debug leftovers; automated cleanup | PHPMD `DevelopmentCodeFragment`, Pest `arch()->preset()->php()`; Rector prepared sets | `rector --dry-run` exits non-zero when it would change code |

## Configuration

### Install (new project)

```bash
composer config allow-plugins.phpstan/extension-installer true
composer config allow-plugins.dealerdirect/phpcodesniffer-composer-installer true
composer require --dev phpunit/phpunit phpstan/phpstan phpstan/extension-installer \
  phpstan/phpstan-strict-rules tomasvotruba/cognitive-complexity shipmonk/dead-code-detector \
  squizlabs/php_codesniffer slevomat/coding-standard dealerdirect/phpcodesniffer-composer-installer \
  phpmd/phpmd infection/infection rector/rector friendsofphp/php-cs-fixer deptrac/deptrac \
  shipmonk/composer-dependency-analyser captainhook/captainhook
# Laravel: + larastan/larastan. Symfony/Doctrine: + phpstan/phpstan-symfony phpstan/phpstan-doctrine
pip install lizard multimetric semgrep && npm add -D jscpd
```

Branch coverage needs **Xdebug** (`XDEBUG_MODE=coverage`). PCOV is line-only. The files below
plus `.semgrepignore`, `captainhook.json` and `bin/quality` are all new.

### phpstan.neon

```neon
# With phpstan/extension-installer, strict-rules, cognitive-complexity and dead-code-detector load automatically.
parameters:
    level: max                          # = 10 in PHPStan 2.x: also flags implicit mixed (missing types)
    paths: [src, tests]
    checkMissingCallableSignature: true # callable/Closure must spell out parameter and return types
    checkUninitializedProperties: true
    checkBenevolentUnionTypes: true
    reportIgnoresWithoutComments: true  # every @phpstan-ignore needs "(reason)"
    cognitive_complexity:
        function: 21
        class: 40                       # extension default; class totals are not a skill gate, agree a value
    shipmonkDeadCode:
        reportTransitivelyDeadMethodAsSeparateError: true
        usageExcluders:
            tests:
                enabled: true           # code only called from tests counts as dead
```

### phpcs.xml (metrics only; PHP-CS-Fixer owns style)

```xml
<?xml version="1.0"?>
<ruleset name="gates">
  <file>src</file> <file>tests</file> <arg name="extensions" value="php"/>
  <rule ref="Generic.Metrics.CyclomaticComplexity"><properties><property name="complexity" value="21"/><property name="absoluteComplexity" value="21"/></properties></rule>
  <rule ref="Generic.Metrics.NestingLevel"><properties><property name="nestingLevel" value="3"/><property name="absoluteNestingLevel" value="3"/></properties></rule>
  <rule ref="SlevomatCodingStandard.Functions.FunctionLength"><properties><property name="maxLinesLength" value="50"/></properties></rule>
</ruleset>
```

### phpmd.xml (PHPMD 3.x property names)

```xml
<?xml version="1.0"?>
<ruleset name="gates" xmlns="https://phpmd.org/xml/ruleset/1.0.0">
  <rule ref="rulesets/unusedcode.xml"/>
  <!-- PHPMD 2.x: name="minimum" value="6" (2.x fires at >=) -->
  <rule ref="rulesets/codesize.xml/ExcessiveParameterList"><properties><property name="maximum" value="5"/></properties></rule>
  <rule ref="rulesets/design.xml/DevelopmentCodeFragment"/>
  <rule ref="rulesets/design.xml/EmptyCatchBlock"/>
  <rule ref="rulesets/design.xml/EvalExpression"/>
  <rule ref="rulesets/design.xml/GotoStatement"/>
</ruleset>
```

### phpunit.xml

```xml
<!-- requireCoverageMetadata: every test declares what it covers, so there is no incidental coverage -->
<phpunit xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="vendor/phpunit/phpunit/phpunit.xsd"
         bootstrap="vendor/autoload.php" failOnRisky="true" failOnWarning="true" requireCoverageMetadata="true">
  <testsuites><testsuite name="all"><directory>tests</directory></testsuite></testsuites>
  <source><include><directory suffix=".php">src</directory></include></source>
  <coverage pathCoverage="true"/>  <!-- branch data in Clover; needs Xdebug -->
</phpunit>
```

`beStrictAboutTestsThatDoNotTestAnything` (default true) plus `failOnRisky` fails assertion-free tests.

### tools/check_clover.py (PHPUnit has no coverage threshold)

```python
#!/usr/bin/env python3
"""Fail unless PHPUnit's Clover report shows 100% line and branch coverage and CRAP < 25 everywhere."""
import sys
import xml.etree.ElementTree as ET

root = ET.parse(sys.argv[1] if len(sys.argv) > 1 else "build/clover.xml").getroot()
m = root.find("project/metrics").attrib
problems = [f"{k}: {m['covered' + k]}/{m[k]} covered" for k in ("statements", "conditionals") if m["covered" + k] != m[k]]
if m["conditionals"] == "0":
    problems.append("no branch data: run PHPUnit under Xdebug (XDEBUG_MODE=coverage) with --path-coverage")
for file in root.iter("file"):
    for line in file.iter("line"):
        if line.get("type") == "method" and float(line.get("crap", "0")) >= 25:
            problems.append(f"{file.get('name')}:{line.get('num')} {line.get('name')} CRAP {line.get('crap')}")
print("\n".join(problems) or "clover: 100% lines and branches, CRAP < 25")
sys.exit(1 if problems else 0)
```

Pest projects can use `vendor/bin/pest --coverage --min=100` instead, but that threshold is a
single line-coverage percentage. Keep the Clover check for branches and CRAP.

### rector.php and .php-cs-fixer.dist.php

```php
<?php // rector.php
declare(strict_types=1);
return Rector\Config\RectorConfig::configure()
    ->withPaths([__DIR__ . '/src', __DIR__ . '/tests'])
    ->withPhpSets()      // PHP version read from composer.json
    ->withPreparedSets(deadCode: true, codeQuality: true, typeDeclarations: true, earlyReturn: true, privatization: true);
```

```php
<?php // .php-cs-fixer.dist.php
return (new PhpCsFixer\Config())
    ->setRiskyAllowed(true)  // declare_strict_types and strict_comparison are risky rules
    ->setRules(['@PER-CS' => true, 'declare_strict_types' => true, 'strict_comparison' => true, 'no_unused_imports' => true])
    ->setFinder(PhpCsFixer\Finder::create()->in([__DIR__ . '/src', __DIR__ . '/tests']));
```

### deptrac.yaml

```yaml
deptrac:
  paths: [./src]
  layers:
    - { name: Domain,         collectors: [{ type: directory, value: src/Domain/.* }] }
    - { name: Application,    collectors: [{ type: directory, value: src/Application/.* }] }
    - { name: Infrastructure, collectors: [{ type: directory, value: src/Infrastructure/.* }] }
  ruleset:
    Domain: ~
    Application: [Domain]
    Infrastructure: [Domain, Application]
```

### .jscpd.json, .semgrep.yml, .semgrepignore

```json
{ "threshold": 0, "minTokens": 50, "minLines": 5, "format": ["php"], "gitignore": true,
  "reporters": ["console"], "ignore": ["**/vendor/**", "**/var/**", "**/storage/**"] }
```

```yaml
rules:
  - id: phpunit-no-logic-in-tests
    languages: [php]
    severity: ERROR
    message: Branching or looping inside a test hides which case failed. Use a data provider.
    paths: { include: ["/tests/**/*Test.php"] }
    patterns:
      - pattern-inside: |
          function $M(...) { ... }
      - metavariable-regex: { metavariable: $M, regex: "^test" }   # #[Test]-named methods are not caught
      - pattern-either:
          - pattern: if ($X) { ... }
          - pattern: foreach ($XS as $V) { ... }
          - pattern: for ($I; $C; $S) { ... }
          - pattern: while ($X) { ... }
          - pattern: "$X ? $A : $B"
  - id: too-many-boolean-operators
    languages: [php]
    severity: ERROR
    message: More than 3 boolean operators in one condition. Extract a named predicate method.
    pattern-either:
      - pattern: $A && $B && $C && $D && $E
      - pattern: $A || $B || $C || $D || $E
```

`.semgrepignore` must exist (for example containing `vendor/`). Without it, semgrep falls back
to a built-in ignore list that skips `tests/`, and the test rule silently finds nothing.

## One command for every gate

```bash
#!/usr/bin/env bash
# bin/quality: every gate, fast ones first. Also wire "quality": "bin/quality" into composer scripts
# with "config": {"process-timeout": 0}, because Composer kills scripts after 300 s by default.
set -euo pipefail
S="${SLOP_SCRIPTS:-<skill-dir>/scripts}"
BASE="${BASE_REF:-origin/main}"
B=vendor/bin

$B/php-cs-fixer check --diff                  # exit 8 when files need fixing
$B/rector --dry-run
$B/phpcs                                      # CCN, nesting, function length
$B/phpstan analyse --no-progress              # types/mixed, strict rules, cognitive, dead code
$B/phpmd analyze --ruleset phpmd.xml --format text src   # PHPMD 2.x: $B/phpmd src text phpmd.xml
$B/deptrac analyse
$B/composer-dependency-analyser
npx --yes jscpd src tests
semgrep scan --config .semgrep.yml --error --metrics=off --quiet
python3 "$S/loc_budget.py" src tests
python3 "$S/halstead_gate.py" src
python3 "$S/comment_density.py" src --fail-on-commented-code
python3 "$S/suppression_audit.py" src tests --zero coverage skipped any-type todo
XDEBUG_MODE=coverage $B/phpunit --coverage-clover build/clover.xml \
  --coverage-xml build/coverage/coverage-xml --log-junit build/coverage/junit.xml
python3 tools/check_clover.py build/clover.xml   # 100% lines + branches, PHPUnit CRAP < 25
python3 "$S/complexity_gate.py" src --coverage build/clover.xml   # lizard CCN + CRAP cross-check
XDEBUG_MODE=coverage $B/infection --threads=max --min-msi=100 --min-covered-msi=100 --with-uncovered \
  --coverage=build/coverage --skip-initial-tests --git-diff-lines --git-diff-base="$BASE"
```

Every line exits non-zero on failure. `--zero any-type` fails on every written `mixed`,
docblocks included. That is intended: write the real type.

## Coverage report for CRAP

`XDEBUG_MODE=coverage vendor/bin/phpunit --coverage-clover build/clover.xml`, then
`python <skill-dir>/scripts/complexity_gate.py src --coverage build/clover.xml --top 20`.
Clover paths are absolute, and the script matches them by suffix (`--coverage-cobertura` works
too). PHPUnit's Clover also carries a `crap` attribute on every `<line type="method">`, computed
from PHPUnit's own CCN. `tools/check_clover.py` gates on that number, and lizard's is a second opinion.

## Mutation testing

```json5
// infection.json5
{
    "$schema": "vendor/infection/infection/resources/schema.json",
    "source": { "directories": ["src"] },
    "logs": { "text": "build/infection.log", "html": "build/infection.html", "github": true },
    "mutators": { "@default": true },
    "minMsi": 100,
    "minCoveredMsi": 100,
    "timeout": 10,
}
```

- **Driver**: Xdebug, PCOV or phpdbg. `--coverage=build/coverage --skip-initial-tests` reuses
  the PHPUnit run (the directory needs both `coverage-xml/` and `junit.xml`).
- **Changed code**: `--git-diff-lines --git-diff-base=origin/main` mutates changed lines only
  (`--git-diff-filter=AM` mutates whole files). Run the full set nightly.
- **Uncovered code**: since 0.31 it isn't mutated without `--with-uncovered` (which replaced
  `--only-covered`). Pass the flag so `--min-msi=100` also catches untested code.
- **Survivors**: `build/infection.log` holds a diff per escaped mutant. `--show-mutations=max`
  prints them, and `logs.github` annotates the PR. Infection exits non-zero below either MSI.
- **Equivalent mutants**: `/** @infection-ignore-all */` on a class or method, or above a
  statement. Narrower: per-mutator `"ignore": ["App\\Money::round"]` or `"ignoreSourceCodeByRegex"`.
  State a reason. The audit counts `@infection-ignore`.
- **Runtime**: only the covering tests run per mutant. Minutes for a library, much longer for a
  framework app, so use `--threads=max` and `--git-diff-lines` in CI.
- **Pest**: Infection's schema no longer lists Pest. Use `pest --mutate --parallel --min=100`;
  the audit does not count its `@pest-mutate-ignore` marker.

## Killing untyped escape hatches

- `level: max` (10) treats a missing type like explicit `mixed`, so every parameter, return and
  property needs a real type. Give arrays shapes or generics (`list<Order>`,
  `array{id: int, name: string}`), or better, use readonly DTOs.
- Ban written `mixed` with `suppression_audit.py --zero any-type`. Slevomat's
  `DisallowMixedTypeHint` only checks phpDoc.
- Other holes: inline `/** @var Foo $x */` casts, `@phpstan-ignore` (needs a reason under
  `reportIgnoresWithoutComments`), `@psalm-suppress`, and `object`/`array` with no shape.
- Decode request and JSON data once at the boundary into typed objects (`cuyz/valinor`, Symfony
  Serializer, or named constructors).
- **Psalm instead**: `<psalm errorLevel="1" findUnusedCode="true" findUnusedPsalmSuppress="true"
  findUnusedBaselineEntry="true">`. `Mixed*` issues are reported only at level 1, and `totallyTyped`
  is deprecated. `--find-dead-code` is an alias for `--find-unused-code`.

## Language-specific slop to hunt

- `@` error suppression; `empty()`/`isset()` on values that are always set; loose `==`.
- `catch (\Exception $e) {}` or catch-log-continue. Returning `null`/`false` as an error code.
- Associative arrays passed through layers instead of a DTO. `array<string, mixed>` config bags.
- Docblocks that repeat native types (Rector and PHP-CS-Fixer `no_superfluous_phpdoc_tags` remove them).
- Facades and static helpers deep in domain code. `new` on services inside methods.
- Leftover `dd()`, `dump()`, `var_dump()`, `ray()`. Pest's `php` preset bans most of them; `dd`
  is only in the `laravel` preset.
- Tests that mock the class under test, assert `assertTrue(true)`, or `sleep()`.

## Invariants

Laravel: model events and Form Request validation don't run for `DB::table()->insert()`,
mass `update()`/`delete()`, or `saveQuietly()`. Symfony validators don't run for raw DBAL
writes. Put invariants in the schema. Laravel's Blueprint has `unique()` and
`foreignId()->constrained()` but no check-constraint method, so use a statement:

```php
Schema::create('orders', function (Blueprint $table) {
    $table->id();
    $table->foreignId('user_id')->constrained();
    $table->bigInteger('total_cents');
    $table->string('external_id');
    $table->unique(['user_id', 'external_id']);
});
DB::statement('ALTER TABLE orders ADD CONSTRAINT orders_total_cents_non_negative CHECK (total_cents >= 0)');
```

```php
// test: the constraint holds even without Eloquent. Run it on the production DB engine;
// SQLite cannot add constraints with ALTER TABLE.
$this->expectException(\Illuminate\Database\QueryException::class);
DB::table('orders')->insert(['user_id' => User::factory()->create()->id, 'external_id' => 'x', 'total_cents' => -1]);
```

 For "only the Auth module creates users", use a deptrac layer or a Pest arch test:
`arch()->expect('App\Models\User')->toOnlyBeUsedIn('App\Auth')`.

## Ratchets for legacy code

Path B only.

- PHPStan: `phpstan analyse --generate-baseline` writes `phpstan-baseline.neon`, which you add
  under `includes:`. Fixed errors become "unmatched" and fail (`reportUnmatchedIgnoredErrors`
  defaults to true), so the file can only shrink. Never regenerate it to absorb new errors.
- Psalm: `--set-baseline=psalm-baseline.xml`, then `--update-baseline` (it only removes
  entries). PHPMD: `--generate-baseline` (3.x writes `phpmd.baseline.xml`), then `--update-baseline`.
- Changed-code coverage: `pip install diff-cover`, then `diff-cover build/cobertura.xml
  --compare-branch=origin/main --fail-under=100` (PHPUnit `--coverage-cobertura`). Mutation:
  `--git-diff-lines`. Suppressions: `suppression_audit.py --write-baseline`, then `--baseline`.

## Pre-commit wiring

```json
{
  "pre-commit": { "enabled": true, "actions": [
    { "action": "vendor/bin/php-cs-fixer check --diff" },
    { "action": "vendor/bin/phpcs" },
    { "action": "vendor/bin/phpstan analyse --no-progress" },
    { "action": "python3 tools/quality/suppression_audit.py src tests" } ] },
  "pre-push": { "enabled": true, "actions": [ { "action": "bin/quality" } ] }
}
```

Save it as `captainhook.json` and run `vendor/bin/captainhook install`. PHPStan's result cache
keeps the hook fast. The alternative is GrumPHP (`phpro/grumphp`; `grumphp.yml` under
`grumphp: tasks:` with `phpstan`, `phpcs`, `phpunit`, and `infection: { min_msi: 100, min_covered_msi: 100 }`).
