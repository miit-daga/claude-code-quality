# Rust gates

Two places hold the lint policy. The Cargo `[lints]` table sets rustc and clippy lint
levels, and `clippy.toml` sets thresholds. cargo-llvm-cov handles coverage,
cargo-mutants handles mutation testing and cargo-shear handles unused dependencies.
Clippy has no cyclomatic, Halstead or file-length lint, and its `cognitive_complexity`
is not SonarSource's metric. For those, use lizard (via `scripts/complexity_gate.py` and
`lizard -Ecognitive`) and the other bundled scripts. Lint groups and defaults below were
checked against clippy master of 2026-10-17 (stable 1.99), cargo-mutants 27.1 and
cargo-llvm-cov 0.9.

## Tool map

| Gate | Tool | Setting / rule |
|------|------|----------------|
| Cyclomatic < 22 | **no clippy lint**. `scripts/complexity_gate.py` (lizard) | default `--ccn-max 21` |
| Cognitive < 22 | `lizard -Ecognitive` (SonarSource spec; tested with lizard 1.24.1); clippy `cognitive_complexity` as an editor-time signal | lizard `-T cognitive_complexity=21` warns at `> 21`. Clippy: `restriction` group, `cognitive-complexity-threshold = 21`, fires at `> 21`. Clippy's own docs say the lint does not measure true cognitive complexity |
| Halstead difficulty < 80 | `scripts/halstead_gate.py` (per file, via multimetric) | default `--max 80` |
| File < 500 lines | `scripts/loc_budget.py` | no clippy lint exists |
| 100% coverage | cargo-llvm-cov | Lines: `--fail-uncovered-lines 0`. Branch coverage needs **nightly** (`--branch`, unstable) and has no fail flag, so check `BRF`/`BRH` in the lcov file. On stable, `--fail-uncovered-regions 0` is a partial proxy (see Coverage) |
| CRAP < 25 | `complexity_gate.py --coverage lcov.info` | |
| 0 surviving mutants | cargo-mutants | exit 0 only when every viable mutant is caught |
| 0 dead code | rustc `unused` group (includes `dead_code`) at deny + `unreachable_pub`; cargo-shear (unused deps and unlinked `.rs` files) | `unreachable_pub` forces `pub(crate)` on crate-internal items so `dead_code` can see them |
| 0 duplication | `jscpd --format rust`; clippy `complexity` and `style` groups for redundant code | `--min-tokens 50 --exit-code 1` |
| 0 `any` equivalents | clippy `disallowed_types` (`style`; covers types and traits); ast-grep `rust-no-untyped`; `unsafe_code = "forbid"` | `std::any::Any`, `serde_json::Value` |
| ABC ≤ 17 | none for Rust | lizard token count is the only proxy |
| Function ≤ 50 NLOC | clippy `too_many_lines` (`pedantic`) | `too-many-lines-threshold = 50`. Counts only lines containing code. Fires at `> 50` |
| Params ≤ 5 | clippy `too_many_arguments` (`complexity`) | `too-many-arguments-threshold = 5`, fires at `> 5`. Also `fn_params_excessive_bools` (`pedantic`) |
| Nesting ≤ 3 | clippy `excessive_nesting` (`complexity`; inert until a threshold is set) | `excessive-nesting-threshold = 5`. It counts **every `{}` block** plus `impl`/`trait`/inline `mod`, and fires at `> 5`. That allows 3 control levels inside an `impl` method and 4 in a free function |
| Bool operators ≤ 3 | ast-grep `rust-max-bool-ops` | `nonminimal_bool` / `overly_complex_bool_expr` (`pedantic`) only simplify; they do not count |
| Comment density, commented-out code | `scripts/comment_density.py --fail-on-commented-code` | no clippy lint for commented-out code |
| Suppression ratchet | clippy `allow_attributes` + `allow_attributes_without_reason` (`restriction`); rustc `unfulfilled_lint_expectations`; `scripts/suppression_audit.py` | forces `#[expect(lint, reason = "...")]`, and a stale `expect` fails. The script counts `#[allow(`/`#[expect(`, `#[mutants::skip]`/`exclude_re` and tarpaulin exclusions |
| Architecture | workspace crates + visibility | a crate cannot use what its `Cargo.toml` does not depend on |
| Unused deps | `cargo shear --deny-warnings` (stable); cargo-machete (stable, exit 1 on findings); cargo-udeps (nightly, slower, compiler-accurate) | |
| No logic in tests | ast-grep `rust-no-logic-in-tests` | flags `if`/`match`/loops inside `mod tests` and `tests/` |
| TODO ban | clippy `todo`, `unimplemented` (`restriction`); `suppression_audit.py --zero todo` for comments | |

## Configuration

Layout for a new crate (split into workspace crates once `domain` must stay I/O-free):

```text
Cargo.toml  clippy.toml  rust-toolchain.toml  .cargo/mutants.toml
src/lib.rs          # all logic; #![forbid(unsafe_code)] also visible here
src/main.rs         # thin: parse args, call the lib, map errors to an exit code
src/domain/         # newtypes and invariants; no serde_json, no I/O
src/adapters/       # deserialize at the boundary
tests/              # integration tests
sgconfig.yml  .ast-grep/rules/rust.yml  lefthook.yml  Makefile
tools/quality/      # vendored copies of the skill's scripts (see agent-loop.md)
```

Install:

```bash
rustup component add clippy rustfmt llvm-tools-preview
cargo install --locked cargo-llvm-cov cargo-mutants cargo-shear jscpd   # or cargo binstall
python3 -m venv .venv && .venv/bin/pip install lizard radon multimetric ast-grep-cli
brew install lefthook      # or: pipx install lefthook
mkdir -p tools/quality .quality && cp <skill-dir>/scripts/*.py tools/quality/
```

### rust-toolchain.toml

```toml
[toolchain]
channel = "stable"   # pin an exact version (e.g. "1.99") so new clippy lints arrive deliberately
components = ["clippy", "rustfmt", "llvm-tools-preview"]
```

### Cargo.toml

```toml
[package]
name = "app"
version = "0.1.0"
edition = "2024"
rust-version = "1.85"

[dependencies]
thiserror = "2"

[dev-dependencies]
proptest = "1"

[lints.rust]
unsafe_code = "forbid"
unused = { level = "deny", priority = -1 }     # dead_code, unused_imports, unused_variables, ...
unreachable_pub = "deny"                        # internal items must be pub(crate)
unfulfilled_lint_expectations = "deny"          # stale #[expect] fails the build
unexpected_cfgs = { level = "deny", check-cfg = ["cfg(coverage)", "cfg(coverage_nightly)", "cfg(loom)", "cfg(kani)"] }

[lints.clippy]
all = { level = "deny", priority = -1 }         # correctness, suspicious, style, complexity, perf
pedantic = { level = "deny", priority = -1 }
# restriction lints are cherry-picked: enabling the whole group trips blanket_clippy_restriction_lints
cognitive_complexity = "deny"
unwrap_used = "deny"
expect_used = "deny"
panic = "deny"
todo = "deny"
unimplemented = "deny"
dbg_macro = "deny"
print_stdout = "deny"            # a CLI's output module gets #[expect(clippy::print_stdout, reason = "...")]
print_stderr = "deny"
indexing_slicing = "deny"        # use .get(); allowed in tests via clippy.toml
allow_attributes = "deny"        # suppressions must be #[expect(..)], which errors once stale
allow_attributes_without_reason = "deny"
wildcard_enum_match_arm = "deny" # new variants of your enums must be handled explicitly
```

Cargo `[lints]` needs Rust 1.74+. Lower `priority` is overridden by higher, so groups
take `-1` and individual lints the default `0`.

### clippy.toml

```toml
cognitive-complexity-threshold = 21   # fires at > 21
too-many-lines-threshold = 50         # counts lines with code; fires at > 50
too-many-arguments-threshold = 5      # fires at > 5
excessive-nesting-threshold = 5       # blocks + impl/trait/inline mod; 5 = 3 control levels in a method
max-fn-params-bools = 1               # fires at > 1 bool parameter (flag arguments)
allow-unwrap-in-tests = true
allow-expect-in-tests = true
allow-panic-in-tests = true
allow-indexing-slicing-in-tests = true
disallowed-types = [
  { path = "std::any::Any", reason = "untyped escape hatch: use an enum or a trait with real methods" },
  # add once serde_json is a dependency (an unresolvable path produces a warning):
  # { path = "serde_json::Value", reason = "deserialize into a concrete type at the boundary" },
]
```

### .ast-grep/rules/rust.yml (with `sgconfig.yml` containing `ruleDirs: [.ast-grep/rules]`)

```yaml
id: rust-no-untyped
language: rust
severity: error
message: "Untyped escape hatch (serde_json::Value / dyn Any). Deserialize into a concrete type."
rule:
  any:
    - { kind: scoped_type_identifier, regex: '^(::)?serde_json::(value::)?Value$' }
    - { kind: use_declaration, regex: 'serde_json::.*\bValue\b' }
    - kind: dynamic_type
      has: { regex: '^(std::any::|core::any::)?Any$' }
---
id: rust-max-bool-ops
language: rust
severity: error
message: "More than 3 boolean operators in one expression. Name the condition."
rule:
  kind: binary_expression
  regex: '(&&|\|\|)(?s:.*)(&&|\|\|)(?s:.*)(&&|\|\|)(?s:.*)(&&|\|\|)'
  not:
    inside: { kind: binary_expression, stopBy: end }
---
id: rust-no-logic-in-tests
language: rust
severity: error
message: "Branch or loop in test code. Write one test per case, or use proptest."
rule:
  any: [{ kind: if_expression }, { kind: match_expression }, { kind: for_expression },
        { kind: while_expression }, { kind: loop_expression }]
  inside:
    stopBy: end
    kind: mod_item
    has: { field: name, regex: ^tests$ }
---
id: rust-no-logic-in-integration-tests
language: rust
severity: error
message: "Branch or loop in test code. Write one test per case, or use proptest."
files: ["tests/**/*.rs"]
rule:
  any: [{ kind: if_expression }, { kind: match_expression }, { kind: for_expression },
        { kind: while_expression }, { kind: loop_expression }]
```

These rules were tested with ast-grep 0.51. `use serde_json::{self, Value}`, `Box<dyn Any + Send>`,
`a && b || c && d || e` and a `for` inside `mod tests` are flagged. `a && b && c && d`
passes. `ast-grep scan` exits 1 on any error-severity match.

### .cargo/mutants.toml

```toml
cap_lints = true          # deny-level lints would otherwise make many mutants "unviable"
timeout_multiplier = 3.0  # per-mutant test timeout relative to the baseline test run
test_tool = "cargo"       # "nextest" can be faster but does not run doctests
```

## One command for every gate

```make
SHELL := bash
S     := tools/quality
PY    := .venv/bin/python
BASE  ?= origin/main

quality-fast:
	cargo fmt --all --check
	cargo clippy --all-targets --all-features --locked -- -D warnings
	.venv/bin/ast-grep scan
	$(PY) $(S)/loc_budget.py src tests
	$(PY) $(S)/complexity_gate.py src --params-max 5 --nloc-max 50
	.venv/bin/lizard -l rust -Ecognitive -C 21 -T cognitive_complexity=21 -w src   # -C 21 overrides lizard's default CCN 15 warning
	$(PY) $(S)/halstead_gate.py src
	$(PY) $(S)/comment_density.py src --fail-on-commented-code
	$(PY) $(S)/suppression_audit.py src tests --zero coverage mutation skipped any-type todo
	cargo test --all-features --locked

quality: quality-fast
	cargo llvm-cov --all-features --workspace --locked --lcov --output-path lcov.info \
	  --fail-uncovered-lines 0 --fail-uncovered-regions 0 --fail-uncovered-functions 0
	$(PY) $(S)/complexity_gate.py src --coverage lcov.info
	cargo shear --deny-warnings
	jscpd --format rust --min-tokens 50 --exit-code 1 src
	git diff "$$(git merge-base $(BASE) HEAD)" > git.diff
	cargo mutants --in-diff git.diff

.PHONY: quality quality-fast
```

Diffing the merge-base against the working tree keeps the diff's new side identical to
the tree, which `--in-diff` requires (exit 5 otherwise). Before the first commit on
`main` exists, run plain `cargo mutants`.

## Coverage report for CRAP

```bash
cargo llvm-cov --all-features --workspace --lcov --output-path lcov.info
python3 <skill-dir>/scripts/complexity_gate.py src --coverage lcov.info
cargo llvm-cov --all-features --workspace --cobertura --output-path coverage.xml   # for CI UIs
```

Branch coverage (nightly only; `--branch` is unstable and has no `--fail-under` flag):

```bash
cargo +nightly llvm-cov --branch --all-features --workspace --lcov --output-path lcov.info
awk -F: '/^BRF:/{f+=$2} /^BRH:/{h+=$2} END{printf "branches %d/%d\n",h,f; exit (h<f)}' lcov.info
```

Confirm the file actually contains `BRF`/`BRH` lines before relying on this (verify for
your toolchain). On stable, `--fail-uncovered-regions 0` catches unexecuted blocks and
short-circuited operands, but not an `if` without `else` whose condition was never
false. Coverage exclusions use `#[cfg_attr(coverage_nightly, coverage(off))]` plus
`#![cfg_attr(coverage_nightly, feature(coverage_attribute))]`. `suppression_audit.py`
counts `coverage(off)`. cargo-tarpaulin (`--out Lcov --fail-under 100`) also works,
but its `--branch` flag is documented as "NOT IMPLEMENTED", and its exclusions
(`#[cfg(not(tarpaulin_include))]`, `#[tarpaulin::skip]`) are counted by the audit.

## Mutation testing

`cargo install --locked cargo-mutants`. `cargo mutants --list` previews mutants,
`cargo mutants` runs them all, and `cargo mutants --in-diff git.diff` runs only mutants
overlapping the diff. Locally, `--iterate` skips mutants already caught or unviable. In
CI, split with `--shard k/n` and use `--baseline=skip` only after a previous step has
proved the tests pass.

Results go to `mutants.out/`: `missed.txt`, `timeout.txt`, `caught.txt`, `unviable.txt`,
`outcomes.json`, and a `diff/` file plus a log per mutant. Add `/mutants.out*` to
`.gitignore`. For each line in `missed.txt`: delete the code if the mutation ("replace
`f -> bool` with true", "delete `!`", "replace `<` with `<=`") changed nothing
observable, otherwise add the assertion that would fail.

Exit codes: **0** every viable mutant caught; **1** usage error; **2** missed mutants;
**3** timeouts; **4** tests fail before mutation; **5** `--in-diff` diff does not match
the tree; **6** invalid diff; **70** internal error. Any non-zero exit fails CI, which
also covers "0 surviving" (missed and timeouts both fail).

Equivalent mutants: add `mutants = "0.0.4"` as a regular `[dependencies]` entry, since
the attribute sits on non-test code and has no effect on the compiled output. Then:

```rust
#[mutants::skip] // equivalent: capacity hint only; replacing it with 0 cannot change output
fn initial_capacity(n: usize) -> usize { n.next_power_of_two() }
```

`suppression_audit.py` counts `#[mutants::skip]` and the narrower
`#[mutants::exclude_re("with 0")]` (the latter needs the `mutants` crate ≥ 0.0.5, not on
crates.io as of 2026-10, so verify for your version). Config-level exclusions
(`exclude_re` / `skip_calls` in `mutants.toml`) escape the audit, so review them by hand.

Runtime: each mutant costs one incremental build plus one test run, so total time is
roughly mutant count × (incremental build + test suite). Check the count with `--list`
first. Start with `-j2` or `-j3`. Each job needs its own copy of `target/`, often 2 GB or more.
Keep `--in-diff` on PRs and run the full set nightly with shards.

## Killing `any` / untyped escape hatches

Settings: `disallowed-types` in clippy.toml, the `rust-no-untyped` ast-grep rule, and
`unsafe_code = "forbid"`. Allowed pattern: deserialize once, at the edge, into a type
whose constructor enforces the invariant:

```rust
#[derive(Debug, serde::Deserialize)]
#[serde(deny_unknown_fields)]
struct CreateOrderReq { sku: String, qty: u32 }

pub(crate) fn decode_create_order(body: &[u8]) -> Result<order::Line, DecodeError> {
    let req: CreateOrderReq = serde_json::from_slice(body)?;
    Ok(order::Line::new(&req.sku, req.qty)?) // domain never sees JSON
}
```

Do not replace them with `HashMap<String, String>` bags, `String` for every field,
`Box<dyn Error>` or `anyhow::Error` in library signatures (use a `thiserror` enum;
`anyhow` is fine in `main`), `serde_json::Value` renamed through a type alias,
`Box<dyn Trait>` with a `downcast` method, or generics that only pass `T` through.

## Language-specific slop to hunt

- `.unwrap()` / `.expect("should never fail")` in non-test code. Fix: `?` with a typed
  error, or a type that makes the failure impossible.
- `.clone()` to quiet the borrow checker. Fix: borrow (`&str`, `&[T]`), restructure
  ownership (`needless_pass_by_value`, `redundant_clone`).
- `Rc<RefCell<_>>` / `Arc<Mutex<_>>` webs. Fix: single owner, pass `&mut`, or message passing.
- Stringly-typed states (`status: String`). Fix: an enum, matched without `_ =>`.
- Traits with one implementation "for testability". Fix: concrete types. Introduce a
  trait at the second implementation.
- `#[allow(dead_code)]` / `#[allow(unused)]` sprinkled to get green. Fix: delete the code
  (`allow_attributes` blocks the shortcut).
- `as` casts that can truncate or wrap. Fix: `TryFrom` (pedantic `cast_*` lints).
- Hand-written loops duplicating iterator adapters, manual `Default`/`Display` boilerplate.
  Fix: iterators, derives (clippy `style`/`complexity` flag most).
- `println!`/`dbg!` debugging left in; `todo!()` placeholders (`print_stdout`, `dbg_macro`, `todo`).
- Tests asserting `result.is_ok()` (hides the value) or `#[ignore]` without a reason. Fix:
  `assert_eq!(f()?, expected)` in a `-> Result` test, and `#[ignore = "reason"]`
  (`ignore_without_reason`, pedantic).

## Invariants

1. **Newtypes with private fields and a fallible constructor.** Outside the module, the
   only way to get a value is through validation. Route serde through it too:
   ```rust
   pub mod email {
       #[derive(Debug, Clone, PartialEq, Eq, serde::Deserialize)]
       #[serde(try_from = "String")]
       pub struct Email(String); // private field: no Email("junk".into()) outside this module

       #[derive(Debug, thiserror::Error)]
       #[error("invalid email address")]
       pub struct InvalidEmail;

       impl TryFrom<String> for Email {
           type Error = InvalidEmail;
           fn try_from(raw: String) -> Result<Self, Self::Error> {
               let ok = raw.split_once('@').is_some_and(|(u, d)| !u.is_empty() && d.contains('.'));
               ok.then_some(Self(raw)).ok_or(InvalidEmail)
           }
       }
       impl Email { pub fn as_str(&self) -> &str { &self.0 } }
   }
   ```
   Use enums for state machines (each state carries only its valid data) and typestate
   (`Order<Draft>` → `Order<Paid>`) where transitions must be ordered.
2. **Crate boundaries.** Put `domain` in its own workspace crate without `serde_json`,
   `sqlx` or `reqwest` in its `Cargo.toml`. The compiler then rejects I/O in the domain.
   Inside a crate, `pub(crate)` / `pub(super)` limit who can call what.
3. **Banned APIs.** `disallowed-methods` / `disallowed-types` in clippy.toml, plus ast-grep rules.
4. **Property tests.** proptest:
   ```rust
   proptest::proptest! {
       #[test]
       fn valid_emails_round_trip(u in "[a-z]{1,10}", d in "[a-z]{1,10}") {
           let raw = format!("{u}@{d}.com");
           let email = Email::try_from(raw.clone()).unwrap();
           proptest::prop_assert_eq!(email.as_str(), raw.as_str());
       }
   }
   ```
5. **Concurrency.** loom explores thread interleavings: put `loom = "0.7"` under
   `[target.'cfg(loom)'.dependencies]`, use `loom::sync` / `loom::thread` inside
   `loom::model(|| ...)`, and run `RUSTFLAGS="--cfg loom" cargo test --release`.
6. **Formal verification**, for the few functions where it pays:
   - **Kani** (bounded model checking): `cargo install --locked kani-verifier && cargo kani setup`,
     then `#[cfg(kani)] #[kani::proof] fn f() { let x: u32 = kani::any(); ... }` and
     run `cargo kani`. It proves the assertions for every input up to the bound, and
     panics and overflow are checked for free.
   - **Verus** (SMT-based specs and proofs in a `verus!` macro), **Creusot**
     (deductive, via Why3) and **Prusti** (Viper-based) prove full functional
     contracts. Each needs its own toolchain, so check maintenance status before adopting.

## Ratchets for legacy code

- Clippy has no baseline. Keep the strict `[lints]` table on new crates. On a legacy
  crate, start at `warn` and ratchet the count (`cargo clippy --message-format=short 2>&1
  | grep -c '^warning'` stored in `.quality/`), or promote one lint at a time to `deny`.
- Mutation on the diff: `cargo mutants --in-diff git.diff`.
- Coverage on the diff: `diff-cover lcov.info --compare-branch=origin/main --fail-under=100`.
- Duplication: `jscpd --format rust --baseline-from-ref origin/main --fail-on-new-clones src`.
- Suppressions: `suppression_audit.py . --write-baseline .quality/suppressions.json`, then `--baseline` in CI.

## Pre-commit wiring

```yaml
# lefthook.yml  (lefthook v2; `lefthook install` once per clone)
pre-commit:
  parallel: true
  jobs:
    - name: fmt
      glob: "*.rs"
      run: cargo fmt --all --check
    - name: clippy
      glob: "*.rs"
      run: cargo clippy --all-targets --all-features --locked -- -D warnings
    - name: ast-grep
      glob: "*.rs"
      run: .venv/bin/ast-grep scan {staged_files}
    - name: budgets
      glob: "*.rs"
      run: >-
        .venv/bin/python tools/quality/loc_budget.py {staged_files} &&
        .venv/bin/python tools/quality/complexity_gate.py {staged_files} --params-max 5 --nloc-max 50 &&
        .venv/bin/lizard -l rust -Ecognitive -C 21 -T cognitive_complexity=21 -w {staged_files}
pre-push:
  jobs:
    - name: quality-fast
      run: make quality-fast
```
