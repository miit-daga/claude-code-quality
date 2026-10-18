# TypeScript / JavaScript gates

`tsc` in strict mode and ESLint 10 (typescript-eslint v8 typed rules, eslint-plugin-sonarjs) carry the gates, Biome formats, Vitest with V8 coverage enforces 100%, and Stryker runs mutation testing. knip, jscpd, type-coverage and dependency-cruiser cover dead code, duplication, leftover `any` and layers, stylelint plus size-limit cover frontend budgets, and the bundled scripts cover Halstead, CRAP, comment density and suppressions. Everything here was run end to end on Node 25 with TypeScript 6.0, ESLint 10.13, typescript-eslint 8.71, sonarjs 4.2, Biome 2.5, Ultracite 8.0, Vitest 4.1, Stryker 10.0, knip 6.41, jscpd 5.4, dependency-cruiser 17.4, type-coverage 2.30, size-limit 14, stylelint 17 and lefthook 2.2.

## Tool map

| Gate | Tool | Setting / rule |
|------|------|----------------|
| Cyclomatic < 22 | ESLint `complexity` | `{ max: 21 }`; fires when > 21 (21 passes, 22 fails). Biome has no cyclomatic rule |
| Cognitive < 22 | `sonarjs/cognitive-complexity` | `["error", 21]`; fires when > 21. Biome: `noExcessiveCognitiveComplexity` `maxAllowedComplexity: 21`, same semantics |
| Halstead difficulty < 80 | `scripts/halstead_gate.py` (multimetric, per file) | no maintained ESLint rule; fails at ≥ 80 |
| File < 500 lines | ESLint `max-lines` | `{ max: 499, skipBlankLines: false, skipComments: false }`. Biome: `style/noExcessiveLinesPerFile` `maxLines: 499` |
| 100% line + branch coverage | Vitest + `@vitest/coverage-v8` | `thresholds: { 100: true, perFile: true }`, `coverage.include` so untested files count |
| CRAP < 25 | `scripts/complexity_gate.py --coverage coverage/lcov.info` | fails at ≥ 25 |
| 0 surviving mutants | Stryker + vitest-runner + typescript-checker | `thresholds.break: 100`; exits 1 when the score < 100 (NoCoverage counts against it) |
| 0 dead code | knip; `noUnusedLocals`/`noUnusedParameters` | run `knip` and then `knip --production --strict` (catches code used only by tests) |
| 0 duplication | jscpd 5; `sonarjs/no-identical-functions` | `.jscpd.json` `threshold: 0` exits 1 on any clone |
| 0 `any` / `unknown` | `@typescript-eslint/no-explicit-any`, `no-unsafe-*` (strictTypeChecked); `no-restricted-syntax` `TSUnknownKeyword`; `consistent-type-assertions: never` | plus type-coverage 100 |
| ABC size ≤ 17 | none for TS | proxies: `complexity`, `max-statements`, `complexity_gate.py` |
| Function ≤ 50 NLOC | ESLint `max-lines-per-function` | `{ max: 50, skipBlankLines: true, skipComments: true }`. Biome's `noExcessiveLinesPerFunction` counted 62 lines for a 94-line body, so don't use it as the gate |
| Params ≤ 5 | ESLint `max-params` | `{ max: 5 }`. Biome: `useMaxParams` `max: 5` |
| Nesting ≤ 3 | ESLint `max-depth`, `max-nested-callbacks` | `{ max: 3 }` (4 in tests for describe > it > property > callback) |
| Boolean operators ≤ 3 | `sonarjs/expression-complexity` | `{ max: 3 }` counts `&&`, `\|\|` and `?:` operators; 4 fails |
| CSS/JS byte budgets | size-limit (`@size-limit/file`); `loc_budget.py --max-bytes` | per-bundle `limit` with `gzip` or `brotli`; per-file bytes via the script |
| CSS complexity | stylelint 17 | `max-nesting-depth: 3`, `selector-max-compound-selectors: 3`, `selector-max-specificity`, `selector-max-id: 0`, `declaration-no-important`. stylelint has no file-length rule, so use `loc_budget.py` |
| Comment density, no commented-out code | `scripts/comment_density.py`; `sonarjs/no-commented-code` | the sonarjs rule judges a whole comment block, so code inside a block that also has prose is missed |
| Suppression ratchet, no blanket | `linterOptions.reportUnusedDisableDirectives: "error"`; `@eslint-community/eslint-comments` (`no-unlimited-disable`, `require-description`, `no-use`); `ban-ts-comment`; `suppression_audit.py` | stylelint `reportNeedlessDisables` / `reportDescriptionlessDisables` / `reportInvalidScopeDisables` |
| Type coverage 100% | type-coverage | `"typeCoverage": { "atLeast": 100, "strict": true }` in package.json |
| Architecture boundaries | dependency-cruiser | `forbidden` rules; exit code = number of errors. eslint-plugin-boundaries v7 renamed its rule to `boundaries/dependencies` with `policies`. It flagged nothing in my test even with eslint-import-resolver-typescript, so verify it for your version |
| No unused dependencies | knip | unused, unlisted and dev-in-prod deps; dependency-cruiser `not-to-dev-dep` too |
| Tests assert, no logic in tests | `sonarjs/assertions-in-tests` (on in recommended); `no-restricted-syntax` selector on `it`/`test` bodies | verified on Vitest test files |
| TODO ban | `no-warning-comments`, `sonarjs/todo-tag`, `sonarjs/fixme-tag` | plus `suppression_audit.py --zero todo` |

## Configuration

### Scaffold and install (empty repo)

Two version traps, both verified:
- typescript-eslint 8.71 declares `typescript >=4.8.4 <6.1.0`, but `npm i typescript` now installs 7.x. Pin `typescript@~6.0`.
- With Vitest 5.0.5, `@stryker-mutator/vitest-runner` 10.0.0 reported every mutant as survived (a 4% score on a suite that scores 100% under Vitest 4.1). Pin `vitest` and `@vitest/coverage-v8` to the same exact 4.x version (each peer-depends on the other's exact version) until the runner supports 5.

```bash
git init && npm init -y && npm pkg set type=module
npm i zod
npm i -D --save-exact vitest@4.1.12 @vitest/coverage-v8@4.1.12   # same 4.x version for both
npm i -D typescript@~6.0 @types/node eslint @eslint/js typescript-eslint eslint-plugin-sonarjs \
  @eslint-community/eslint-plugin-eslint-comments @biomejs/biome fast-check \
  @stryker-mutator/core @stryker-mutator/vitest-runner @stryker-mutator/typescript-checker \
  knip jscpd dependency-cruiser type-coverage lefthook
npm i -D stylelint stylelint-config-standard size-limit @size-limit/file   # frontends only
mkdir -p src/domain src/boundary tools/quality
cp <skill-dir>/scripts/*.py tools/quality/            # CI has no ~/.claude
printf 'node_modules/\ncoverage/\nreports/\n.stryker-tmp/\n.eslintcache\ndist/\n' > .gitignore
```

Layout: `src/domain/` (pure logic, no I/O, no npm imports), `src/boundary/` (HTTP, DB, env, parsing with zod), `src/index.ts` (public entry, the knip entry), tests next to code as `*.test.ts`. `uv` (for the Python gate scripts) must be on PATH.

### tsconfig.json

```json
{
  "compilerOptions": {
    "target": "es2023", "module": "nodenext", "moduleResolution": "nodenext",
    "lib": ["es2023"], "types": ["node"],
    "strict": true,
    "noUncheckedIndexedAccess": true, "exactOptionalPropertyTypes": true,
    "noImplicitOverride": true, "noImplicitReturns": true, "noFallthroughCasesInSwitch": true,
    "noPropertyAccessFromIndexSignature": true,
    "noUnusedLocals": true, "noUnusedParameters": true,
    "allowUnreachableCode": false, "allowUnusedLabels": false,
    "verbatimModuleSyntax": true, "isolatedModules": true,
    "erasableSyntaxOnly": true,
    "skipLibCheck": true, "noEmit": true
  },
  "include": ["src", "*.config.ts"]
}
```

`erasableSyntaxOnly` rejects `enum`, `namespace` and parameter properties (use unions and plain fields). For a frontend, use `"lib": ["es2023", "dom", "dom.iterable"]`, `"types": []`, `"jsx": "react-jsx"` (or your framework's setting), and `"module": "esnext"`, `"moduleResolution": "bundler"`.

### eslint.config.mjs

```js
// @ts-check
import js from "@eslint/js";
import comments from "@eslint-community/eslint-plugin-eslint-comments/configs";
import { defineConfig } from "eslint/config";
import sonarjs from "eslint-plugin-sonarjs";
import tseslint from "typescript-eslint";

const noUnknown = { selector: "TSUnknownKeyword", message: "No `unknown`. Pass raw input straight into a schema parse." };

export default defineConfig(
  { ignores: ["dist/**", "coverage/**", "reports/**", ".stryker-tmp/**", "tools/**"] },
  { linterOptions: { reportUnusedDisableDirectives: "error", reportUnusedInlineConfigs: "error" } },
  js.configs.recommended,
  tseslint.configs.strictTypeChecked,
  tseslint.configs.stylisticTypeChecked,
  sonarjs.configs.recommended,
  comments.recommended,
  {
    languageOptions: { parserOptions: { projectService: true, tsconfigRootDir: import.meta.dirname } },
    rules: {
      complexity: ["error", { max: 21 }],
      "sonarjs/cognitive-complexity": ["error", 21],
      "max-lines": ["error", { max: 499, skipBlankLines: false, skipComments: false }],
      "max-lines-per-function": ["error", { max: 50, skipBlankLines: true, skipComments: true }],
      "max-params": ["error", { max: 5 }],
      "max-depth": ["error", { max: 3 }],
      "max-nested-callbacks": ["error", { max: 3 }],
      "sonarjs/expression-complexity": ["error", { max: 3 }],
      "@typescript-eslint/no-explicit-any": ["error", { fixToUnknown: false, ignoreRestArgs: false }],
      "no-restricted-syntax": ["error", noUnknown],
      "@typescript-eslint/consistent-type-assertions": ["error", { assertionStyle: "never" }],
      "@typescript-eslint/ban-ts-comment": ["error", { "ts-expect-error": "allow-with-description", minimumDescriptionLength: 10 }],
      "@typescript-eslint/switch-exhaustiveness-check": "error",
      "@typescript-eslint/strict-boolean-expressions": "error",
      "sonarjs/no-commented-code": "error",
      "no-warning-comments": ["error", { terms: ["todo", "fixme", "hack", "xxx"], location: "anywhere" }],
      "no-console": "error",
      "@eslint-community/eslint-comments/no-unlimited-disable": "error",
      "@eslint-community/eslint-comments/require-description": ["error", { ignore: [] }],
      "@eslint-community/eslint-comments/no-use": ["error", { allow: ["eslint-disable-next-line"] }],
    },
  },
  {
    files: ["**/*.test.ts"],
    rules: {
      "max-lines-per-function": "off", // a describe() callback is one function; cap each test with max-statements
      "max-statements": ["error", { max: 15 }],
      "max-nested-callbacks": ["error", { max: 4 }], // describe > it > fc.property > callback
      "no-restricted-syntax": ["error", noUnknown, {
        selector: "CallExpression[callee.name=/^(it|test)$/] :matches(IfStatement, SwitchStatement, ForStatement, ForOfStatement, ForInStatement, WhileStatement, ConditionalExpression)",
        message: "No branching or loops in a test. Use it.each or a second test.",
      }],
    },
  },
  { files: ["**/*.mjs", "**/*.cjs"], extends: [tseslint.configs.disableTypeChecked] },
  { files: ["**/*.cjs"], languageOptions: { sourceType: "commonjs", globals: { module: "writable", require: "readonly" } } },
);
```

### biome.jsonc (formatter and import sorting; ESLint is the linter)

```jsonc
{
  "$schema": "./node_modules/@biomejs/biome/configuration_schema.json",
  "vcs": { "enabled": true, "clientKind": "git", "useIgnoreFile": true },
  "files": { "includes": ["**", "!coverage", "!reports", "!.stryker-tmp", "!tools"] },
  "formatter": { "enabled": true, "indentStyle": "space", "lineWidth": 100 },
  "assist": { "actions": { "source": { "organizeImports": "on" } } },
  "linter": { "enabled": false }
}
```

**Ultracite variant** (Biome lints as well): `npx ultracite init --linter biome --pm npm` writes `biome.jsonc` with `"extends": ["ultracite/biome/core"]` and `check`/`fix` scripts. The core preset sets cognitive complexity to 20 (stricter than the budget, which is fine) and leaves `noExcessiveLinesPerFile` and `useMaxParams` off. It also turns off `noExcessiveCognitiveComplexity` and `noExplicitAny` for test files, so re-enable them. Add to its `biome.jsonc`:

```jsonc
"linter": { "rules": {
  "complexity": { "useMaxParams": { "level": "error", "options": { "max": 5 } } },
  "style": { "noExcessiveLinesPerFile": { "level": "error", "options": { "maxLines": 499 } } }
} },
"overrides": [{ "includes": ["**/*.test.ts"], "linter": { "rules": {
  "complexity": { "noExcessiveCognitiveComplexity": "error" }, "suspicious": { "noExplicitAny": "error" }
} } }]
```

Biome has no cyclomatic, nesting-depth, boolean-operator or `unknown` rule, and no typed `no-unsafe-*` rules. So keep the ESLint config above, and turn off Biome's duplicates of its rules if both run.

### vitest.config.ts

```ts
import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    include: ["src/**/*.test.ts"],
    coverage: {
      provider: "v8",
      include: ["src/**/*.ts"], // files no test imports still count, at 0%
      exclude: ["src/**/*.test.ts"],
      reporter: ["text", "lcov", "json-summary"],
      thresholds: { 100: true, perFile: true },
    },
  },
});
```

For Jest, the equivalent is `coverageThreshold: { global: { branches: 100, functions: 100, lines: 100, statements: 100 } }`, `collectCoverageFrom: ["src/**/*.ts"]` and `coverageReporters: ["lcov", "text"]`, with `@stryker-mutator/jest-runner` (verify for your version).

### stryker.config.json

```json
{
  "$schema": "./node_modules/@stryker-mutator/core/schema/stryker-schema.json",
  "testRunner": "vitest",
  "checkers": ["typescript"],
  "tsconfigFile": "tsconfig.json",
  "mutate": ["src/**/*.ts", "!src/**/*.test.ts", "!src/index.ts"],
  "coverageAnalysis": "perTest",
  "incremental": true,
  "incrementalFile": "reports/stryker-incremental.json",
  "reporters": ["clear-text", "progress", "html", "json"],
  "thresholds": { "high": 100, "low": 100, "break": 100 }
}
```

Use JSON rather than `stryker.config.mjs`. knip reports the JSDoc type import in the `.mjs` form as an unlisted dependency.

### knip.json, .jscpd.json

```json
{
  "$schema": "https://unpkg.com/knip@6/schema.json",
  "entry": ["src/index.ts!"],
  "project": ["src/**/*.ts!"],
  "ignoreBinaries": ["uv"]
}
```

The `!` suffix marks production files. Without it, `knip --production` has no entries and reports every runtime dependency as unused.

```json
{
  "path": ["src"],
  "format": ["typescript", "tsx", "javascript", "css", "scss"],
  "minTokens": 50, "minLines": 5,
  "threshold": 0, "exitCode": 1,
  "reporters": ["console"],
  "ignore": ["**/*.test.ts", "**/coverage/**", "**/dist/**"]
}
```

### .dependency-cruiser.cjs

```js
/** @type {import('dependency-cruiser').IConfiguration} */
module.exports = {
  forbidden: [
    { name: "no-circular", severity: "error", from: {}, to: { circular: true } },
    { name: "no-orphans", severity: "error", to: {},
      from: { orphan: true, pathNot: ["\\.d\\.ts$", "\\.test\\.ts$", "(^|/)[^/]+\\.config\\.(js|cjs|mjs|ts)$"] } },
    { name: "domain-is-pure", comment: "src/domain imports only src/domain", severity: "error",
      from: { path: "^src/domain", pathNot: "\\.test\\.ts$" },
      to: { pathNot: "^src/domain", dependencyTypesNot: ["type-only"] } },
    { name: "not-to-unresolvable", severity: "error", from: {}, to: { couldNotResolve: true } },
    { name: "not-to-dev-dep", severity: "error", from: { path: "^src", pathNot: "\\.test\\.ts$" },
      to: { dependencyTypes: ["npm-dev"], dependencyTypesNot: ["type-only"] } },
    { name: "no-non-package-json", severity: "error", from: {}, to: { dependencyTypes: ["npm-no-pkg", "npm-unknown"] } },
  ],
  options: {
    doNotFollow: { path: "node_modules" },
    tsPreCompilationDeps: true,
    tsConfig: { fileName: "tsconfig.json" },
    enhancedResolveOptions: { exportsFields: ["exports"], conditionNames: ["import", "require", "node", "default", "types"] },
  },
};
```

### Frontend budgets: .size-limit.json and stylelint.config.mjs

```json
[
  { "name": "JS bundle", "path": "dist/assets/*.js", "limit": "100 kB", "gzip": true },
  { "name": "CSS", "path": "dist/assets/*.css", "limit": "20 kB", "brotli": true }
]
```

```js
/** @type {import('stylelint').Config} */
export default {
  extends: ["stylelint-config-standard"],
  reportNeedlessDisables: true,
  reportInvalidScopeDisables: true,
  reportDescriptionlessDisables: true,
  rules: {
    "max-nesting-depth": 3,
    "selector-max-compound-selectors": 3,
    "selector-max-specificity": "0,3,0",
    "selector-max-id": 0,
    "selector-max-universal": 1,
    "declaration-no-important": true,
    "color-named": "never",
    "no-duplicate-selectors": true,
    "declaration-block-no-duplicate-properties": true,
  },
};
```

Per-file CSS byte budget: `python3 tools/quality/loc_budget.py src --max-bytes 20480 --bytes-ext .css .scss`. When a budget is hit, have the agent delete unused rules before adding new ones.

## One command for every gate

`package.json` (the `typeCoverage` block is read by `type-coverage`):

```json
"scripts": {
  "format": "biome check --write .",
  "format:check": "biome check .",
  "lint": "eslint . --max-warnings 0 --cache",
  "typecheck": "tsc -p .",
  "typecov": "type-coverage",
  "test": "vitest run",
  "coverage": "vitest run --coverage",
  "budgets": "python3 tools/quality/loc_budget.py src && python3 tools/quality/comment_density.py src --fail-on-commented-code && python3 tools/quality/suppression_audit.py src --zero coverage mutation skipped any-type todo",
  "metrics": "uv run --no-project --with lizard --with multimetric python tools/quality/complexity_gate.py src --exclude '*.test.ts' --params-max 5 --nloc-max 50 && uv run --no-project --with radon --with multimetric python tools/quality/halstead_gate.py src --exclude '*.test.ts'",
  "crap": "uv run --no-project --with lizard python tools/quality/complexity_gate.py src --exclude '*.test.ts' --coverage coverage/lcov.info",
  "deadcode": "knip && knip --production --strict",
  "dupes": "jscpd",
  "arch": "depcruise src --config .dependency-cruiser.cjs",
  "mutation": "stryker run",
  "quality:fast": "npm run format:check && npm run lint && npm run typecheck && npm run budgets && npm test",
  "quality": "npm run quality:fast && npm run typecov && npm run deadcode && npm run dupes && npm run arch && npm run coverage && npm run metrics && npm run crap && npm run mutation",
  "prepare": "lefthook install"
},
"typeCoverage": { "atLeast": 100, "strict": true, "detail": true, "reportUnusedIgnore": true }
```

Frontends add `"lint:css": "stylelint \"src/**/*.{css,scss}\""` and `"size": "size-limit"` (after the build) to `quality`. On the sample project (three modules, 15 tests including a fast-check property), `npm run quality` takes about 16 s, of which Stryker takes about 6.

## Coverage report for CRAP

```bash
npx vitest run --coverage            # writes coverage/lcov.info (reporter "lcov")
uv run --no-project --with lizard python tools/quality/complexity_gate.py src \
  --exclude '*.test.ts' --coverage coverage/lcov.info --top 15
```

Jest writes the same `coverage/lcov.info` with `coverageReporters: ["lcov"]`. The lcov `SF:` paths are relative to the repo root and match what lizard sees.

## Mutation testing

- **Install/config:** see above. `checkers: ["typescript"]` discards mutants that don't compile (they show as CompileError and don't count). Drop it if the per-mutant type check makes runs too slow.
- **Incremental:** `incremental: true` reuses results for unchanged code and tests (measured: 21 of 28 results reused after a one-line change). Use `--force` to rebuild. Run on changed files only in CI:

  ```bash
  CHANGED=$(git diff --name-only origin/main...HEAD -- 'src/**/*.ts' ':!src/**/*.test.ts' | paste -sd, -)
  [ -z "$CHANGED" ] || npx stryker run --mutate "$CHANGED"
  ```

- **Read survivors:** the clear-text reporter prints each `[Survived]` mutant with its diff and the tests that covered it. `reports/mutation/mutation.html` is browsable. `reports/mutation/mutation.json` (mutation-testing-report-schema) has `files[path].mutants[]` with `status` (`Killed`, `Survived`, `NoCoverage`, `Timeout`, `CompileError`, `Ignored`).
- **Equivalent mutant:** `// Stryker disable next-line all: <reason>` on the line above, or name the mutator: `// Stryker disable next-line ConditionalExpression: <reason>`. Ignored mutants are excluded from the score, and `suppression_audit.py` counts them.
- **Fail CI:** `thresholds.break: 100` makes Stryker log "Final mutation score … under breaking threshold 100" and exit 1. NoCoverage mutants lower the score, so they fail too.
- **Runtime:** `perTest` coverage runs only the covering tests per mutant. The sample's 28 mutants took about 6 s. Expect minutes for thousands of mutants, so run full runs nightly and changed files on PRs, and cache `reports/stryker-incremental.json` between CI runs.

## Killing `any` / `unknown`

- **Compiler:** `strict` (includes `noImplicitAny` and `useUnknownInCatchVariables`), plus `noUncheckedIndexedAccess` and `exactOptionalPropertyTypes`.
- **Linter:** `strictTypeChecked` turns on `no-explicit-any`, `no-unsafe-argument`/`-assignment`/`-call`/`-member-access`/`-return`, `no-non-null-assertion`, `no-unnecessary-type-parameters` and `no-unnecessary-condition`. On top of that, `no-restricted-syntax` bans the `unknown` keyword and `consistent-type-assertions: never` bans `as`. type-coverage `--strict` at 100% catches implicit `any` the linter misses.
- **Boundary pattern:** don't write a function that takes `unknown`. Hand the raw value (`any` from `JSON.parse`, `await res.json()` or `req.body`) straight to the schema. `no-unsafe-argument` allows `any` into zod's `unknown` parameter, so nothing untyped survives the call.

  ```ts
  import { z } from "zod";

  const OrderInput = z.strictObject({ totalCents: z.number().int().nonnegative(), parts: z.number().int().positive() });
  export type OrderInput = z.infer<typeof OrderInput>;

  export function parseOrder(json: string): OrderInput {
    return OrderInput.parse(JSON.parse(json));
  }
  ```

- **Catch clauses** are implicitly `unknown` (no keyword written). Narrow with `instanceof` or a schema, never with `as Error`.
- **Not acceptable as replacements:** `object`, `{}` (`no-empty-object-type`), `Record<string, unknown>` (also hits the `unknown` ban), `Function`, `as` / `as unknown as T`, `!`, a type parameter used once to launder a value, or `// @ts-expect-error` (it needs a 10-character description, and the audit counts it).

## Language-specific slop to hunt

- `try { … } catch (e) { console.error(e); return null; }`: `no-console`, `sonarjs/no-useless-catch`, `only-throw-error`. Let it throw, or return a typed `Result` union.
- Floating promises and `async` callbacks in `forEach`: `no-floating-promises`, `no-misused-promises`.
- Optional chaining and `?? defaultValue` on values that can't be nullish: `no-unnecessary-condition`. Truthiness checks on numbers and strings: `strict-boolean-expressions`.
- An interface duplicating a zod schema: derive it with `z.infer`. `enum`: string-literal unions (`erasableSyntaxOnly`). Hand-rolled deep clone through `JSON.parse(JSON.stringify(x))`: use `structuredClone`.
- Barrel files that re-export everything, and exports nobody imports: knip. Pass-through wrapper functions and one-method classes: inline them.
- `switch` on a union without exhaustiveness: `switch-exhaustiveness-check`. Boolean flag params: split the function (and `max-params`).
- Tests that snapshot whole objects to buy coverage, assert only `toBeDefined()`, mock the unit under test, or loop over cases: `sonarjs/assertions-in-tests`, the `it`/`test` branching ban, mutation testing.
- Frontend: inline styles and one-off CSS classes per component, `!important`, ID selectors, deeply nested SCSS: stylelint rules above, plus `size-limit` so bundle growth is visible in every PR.

## Invariants

- **Branded types:** make a validated value unforgeable. With zod: `const UserId = z.uuid().brand<"UserId">(); type UserId = z.infer<typeof UserId>;` makes `greet("plain-string")` fail to compile (`TS2345 ... not assignable to ... $brand<"UserId">`). Without zod, use a `unique symbol` brand plus a type-guard constructor (no `as` needed):

  ```ts
  declare const centsBrand: unique symbol;
  export type Cents = number & { readonly [centsBrand]: true };
  export function isCents(value: number): value is Cents {
    return Number.isSafeInteger(value) && value >= 0;
  }
  ```

- **Private constructors:** the only way to get a `Session` is through verification. (`erasableSyntaxOnly` forbids parameter properties, so assign the field explicitly.)

  ```ts
  export class Session {
    readonly userId: UserId;
    private constructor(userId: UserId) { this.userId = userId; }
    static fromVerifiedToken(token: VerifiedToken): Session { return new Session(token.userId); }
  }
  ```
- **Module boundaries:** dependency-cruiser `forbidden` rules (config above). For example, add a rule that only `src/boundary/db/` may import the database client.
- **Custom rules:** ESLint `no-restricted-syntax` / `no-restricted-imports` for single-file bans, and semgrep (`languages: [typescript]`) for cross-file patterns.
- **Property tests (fast-check):**

  ```ts
  it("preserves the total and differs by at most one", () => {
    fc.assert(fc.property(fc.nat(1_000_000), fc.integer({ min: 1, max: 50 }), (total, parts) => {
      const shares = splitEvenly(total, parts);
      expect(shares.reduce((a, b) => a + b, 0)).toBe(total);
      expect(Math.max(...shares) - Math.min(...shares)).toBeLessThanOrEqual(1);
    }));
  });
  ```

## Ratchets for legacy code

Path B only. Gate new code fully and let old violations only shrink.

- **ESLint bulk suppressions:** `eslint . --suppress-all` (or `--suppress-rule <rule>`) writes `eslint-suppressions.json` with per-file, per-rule counts. A file that goes over its count reports all its errors for that rule. A count that is no longer reached fails the run until `eslint . --prune-suppressions` shrinks the file (verified). Never pass `--pass-on-unpruned-suppressions` in CI.
- **jscpd:** run `npx jscpd --baseline .jscpd-baseline.json --update-baseline` once. After that, `npx jscpd --baseline .jscpd-baseline.json --fail-on-new-clones --threshold 100` exits 1 only on clones marked `[NEW]`; the `--threshold 100` overrides the config's `threshold: 0`, which would otherwise still fail on old clones. Or use `--baseline-from-ref origin/main`, which builds the baseline from that ref.
- **dependency-cruiser:** `npx depcruise-baseline src --config .dependency-cruiser.cjs` writes `.dependency-cruiser-known-violations.json`, and `depcruise src --config .dependency-cruiser.cjs --ignore-known` then fails only on new violations.
- **Coverage and type coverage:** Vitest `thresholds.autoUpdate: true` raises thresholds as coverage rises. `type-coverage --update-if-higher` does the same for `typeCoverage.atLeast`. Both only ratchet up.
- **Mutation:** Stryker `incremental` plus `--mutate` on changed files (above). `suppression_audit.py --write-baseline` / `--baseline` covers everything else. betterer is an alternative general-purpose ratchet (verify for your version: its `latest` tag is a 6.0 alpha).

## Pre-commit wiring

`lefthook.yml` (verified with `lefthook validate`, and by a commit that a staged `any` blocked). `npm i` runs `prepare`, which installs the hooks:

```yaml
pre-commit:
  parallel: true
  jobs:
    - name: biome
      glob: "*.{ts,tsx,js,mjs,cjs,json,jsonc,css}"
      run: npx biome check --no-errors-on-unmatched {staged_files}
    - name: eslint
      glob: "*.{ts,tsx}"
      run: npx eslint --max-warnings 0 {staged_files}
    - name: types
      glob: "*.{ts,tsx}"
      run: npx tsc -p .
    - name: file-budget
      glob: "*.{ts,tsx,js,css,scss}"
      run: python3 tools/quality/loc_budget.py {staged_files}
    - name: stylelint            # frontends only
      glob: "*.{css,scss}"
      run: npx stylelint {staged_files}
pre-push:
  jobs:
    - name: quality-fast
      run: npm run quality:fast
```

husky + lint-staged alternative: `npx husky init` adds `"prepare": "husky"` and a `.husky/pre-commit` containing `npm test`. Replace that line with `npx lint-staged`, then add `"lint-staged": { "*.{ts,tsx}": ["biome check --no-errors-on-unmatched", "eslint --max-warnings 0"], "*.{css,scss}": ["stylelint"] }` to package.json and run `npm run quality:fast` from `.husky/pre-push`.
