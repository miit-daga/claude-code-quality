# Slop catalog: what agent-written code gets wrong, and the fix

Use this as a checklist while reviewing agent-written code (Path B step 5.2, or any
review). Each entry gives the pattern, how to spot it, and the fix. The fix is usually
deletion.

## Contents

1. Comments
2. Error handling
3. Defensive noise
4. Abstraction and indirection
5. Duplication and reinvention
6. Types
7. Tests
8. Leftovers
9. Dependencies and config
10. Structure

---

## 1. Comments

| Pattern | Spot it | Fix |
|---|---|---|
| Narrating comments: `# Loop over the items` above `for item in items` | `comment_density.py` narration report | Delete. If the code needs the comment to be clear, rename things instead |
| Commented-out code "for reference" | ruff ERA001, sonarjs no-commented-code, `comment_density.py` | Delete. Git remembers |
| Section banners in a short file (`# ===== Helpers =====`) | grep for `====`/`----` comment lines | Delete, or split the file if it genuinely has sections |
| Docstrings that restate the signature (`"""Gets the user. Args: user_id: the user id"""`) | review | Keep a doc comment only if it adds contract information: units, invariants, errors raised, side effects |
| Comments about the change history (`# Updated to use new API`, `// Fixed bug`) | grep `fixed|updated|changed|now uses|new version` in comments | Delete. That belongs in the commit message |
| Apologetic or hedging comments (`# This might not handle all cases`) | review | Find the cases and handle them or test them, then delete the comment |

## 2. Error handling

| Pattern | Spot it | Fix |
|---|---|---|
| Swallowed exceptions: `except Exception: pass`, `catch (e) {}` | ruff BLE001 / S110, ESLint `no-empty`, errcheck, RuboCop `Lint/SuppressedException` | Let it propagate, or catch the *specific* error you can actually handle |
| Catch, log, then continue as if nothing happened | grep `catch` blocks that only log | Decide: handle (with a test for the failure path) or propagate |
| `try` around 40 lines | review; cognitive complexity | Narrow the `try` to the one call that can fail |
| Re-wrapping every error in a generic error that loses the cause | grep `raise .*Error(` without `from e`, `new Error(` without `cause` | Keep the cause chain (`raise X from e`, `{ cause: e }`, `%w`, `anyhow::Context`) or don't wrap |
| Fallback defaults that hide failures: `config.get("url") or "http://localhost"`, `?? []` on data that must exist | grep `or ""`, `or {}`, `?? []`, `|| {}`, `getOrDefault` | Fail loudly at startup or at the boundary. Defaults only for truly optional values |
| Returning `None`/`null`/`-1` for errors | review | Raise, or use the language's Result/error type |

## 3. Defensive noise

| Pattern | Spot it | Fix |
|---|---|---|
| Null checks on values the type system already guarantees | TS `no-unnecessary-condition`, pyright `reportUnnecessaryComparison`, mypy `warn_unreachable`, mutation survivors | Delete the check |
| Re-validating data already validated at the boundary | review; mutation survivors | Validate once at the edge, then trust the type |
| `isinstance`/`typeof` checks in typed internal code | grep | Fix the types instead |
| Retry loops around operations that are not transient | grep `retry`, `for attempt in` | Remove, or limit retries to known-transient errors with backoff and a test |
| Timeouts or sleeps "just in case" | grep `sleep(`, `setTimeout(` | Remove, or wait on the actual condition |

## 4. Abstraction and indirection

| Pattern | Spot it | Fix |
|---|---|---|
| Wrapper that only forwards: `def get_user(id): return repo.get_user(id)` | review; jscpd sometimes; mutation (delete-call mutants survive if unused) | Inline it |
| Interface or abstract base with exactly one implementation and no test double | grep `implements`/`ABC` | Delete the interface until a second implementation exists |
| Factory / builder / manager / service for a plain constructor call | names ending in `Factory`, `Manager`, `Helper`, `Util`, `Handler` with tiny bodies | Use the constructor directly |
| Config option for something that never varies | grep config keys; dead-code tools | Hard-code the value, delete the option |
| Generic "utils" module that keeps growing | file-size gate; name `utils`, `helpers`, `common`, `misc` | Move each function next to its only caller, or into a named module by topic |
| Premature plugin systems, event buses, DI containers in small apps | review | Use direct calls until there is a measured need |

## 5. Duplication and reinvention

| Pattern | Spot it | Fix |
|---|---|---|
| The same helper written twice under different names (`format_date`, `fmt_date`, `date_to_str`) | jscpd; grep for similar names | Keep one and delete the others |
| Re-implementing the standard library (custom `chunk`, `deep_equal`, `retry`, `slugify`, `uuid`) | review | Use stdlib or an existing dependency |
| Copy-pasted blocks with one value changed | jscpd / CPD / dupl / flay | Extract with a parameter for the difference |
| Parallel `if region == "eu" ... elif region == "uk"` ladders repeated in several places | grep the literal values | One lookup table or one function |

## 6. Types

| Pattern | Spot it | Fix |
|---|---|---|
| `any` / `Any` / `interface{}` / `dynamic` / `mixed` / `T.untyped` | `suppression_audit.py` any-type category; compiler strict modes | Real type; parse at the boundary |
| Casting instead of validating (`as User`, `cast(User, x)`, `(User) obj`) | grep casts | Validate with a schema, or fix the producer's type |
| Stringly-typed values (`status: str` with magic strings) | grep repeated string literals | Enum / literal union / sealed type |
| Optional everywhere (`foo?: string` on fields that are always set) | review | Make it required. Optionality is a decision |
| Primitive obsession: `user_id: str`, `amount: float` for money | review | Newtype / branded type / value object. Use decimal or integer cents for money |

## 7. Tests

| Pattern | Spot it | Fix |
|---|---|---|
| Tests without assertions, or `assert True` / `expect(true).toBe(true)` | `jest/expect-expect`, mutation testing (Python: no stock rule, mutation catches these) | Assert observable outcomes |
| Tests that assert the mock was called with exactly what the code passed it | review | Assert on outputs and state, and mock only at real boundaries |
| Snapshot tests of large objects as a coverage shortcut | grep `toMatchSnapshot`, snapshot file sizes | Targeted assertions on the fields that matter |
| Logic in tests (`if`, loops, try/except) | `jest/no-conditional-in-test`, review | Parametrize / table-driven tests |
| Skipped, focused or xfail tests left behind | `suppression_audit.py --zero skipped` | Fix or delete |
| Tests that re-implement the function under test to compute "expected" | review | Use literal expected values or properties |
| Tests depending on time, randomness or order | flaky reruns, review | Inject the clock and seed, and isolate state |
| Test files that duplicate fixtures everywhere | jscpd on tests | Shared fixtures and factories |

## 8. Leftovers

| Pattern | Spot it | Fix |
|---|---|---|
| Debug output (`print`, `console.log`, `fmt.Println`, `puts`, `dd()`) | ruff T20, ESLint `no-console`, forbidigo, RuboCop `Lint/Debugger` | Delete, or use the project logger at the right level |
| TODO / FIXME / "implement later" stubs | `suppression_audit.py` todo category | Implement now, delete, or link an issue |
| Placeholder implementations (`return []`, `pass`, `throw new Error("Not implemented")`) on reachable paths | grep; coverage of those lines | Implement or remove the feature path |
| Example or demo files committed with the feature | `git ls-files` review | Delete |
| Backward-compatibility shims for code that was never released | review | Delete |
| Old and new implementations side by side (`process_v2`, `newHandler`) | grep `_v2`, `new`, `old`, `legacy` | Migrate callers and delete the old one |

## 9. Dependencies and config

| Pattern | Spot it | Fix |
|---|---|---|
| Dependencies added for a single trivial function | knip / deptry / cargo-machete / depcheck | Remove; write the three lines yourself or use stdlib |
| Unused dependencies left in the manifest | same | Remove |
| Two libraries doing the same job (axios and fetch wrappers, moment and date-fns) | review the manifest | Pick one |
| Config files for tools that are not used | `ls -a` the repo root | Delete |
| Hallucinated APIs or options (methods that don't exist in the installed version) | type checker; tests | Check against the installed version's docs or source |

## 10. Structure

| Pattern | Spot it | Fix |
|---|---|---|
| God file that grows with every feature | `loc_budget.py` | Split by responsibility |
| Circular imports papered over with local imports | ruff PLC0415, madge / dependency-cruiser, import-linter | Fix the layering |
| Business logic in controllers, handlers or views | review; architecture rules | Move it into the domain layer and keep handlers thin |
| Inconsistent patterns for the same job across the codebase (three ways to call the API) | review | Pick one, write it in CLAUDE.md/AGENTS.md, migrate the rest |
| Feature flags that are always on | grep flag names | Remove the flag and the dead branch |
