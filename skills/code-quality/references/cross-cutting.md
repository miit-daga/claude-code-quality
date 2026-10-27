# Cross-cutting conventions: one way to call, retry, time out, log and fail

Service-to-service calls, retries, timeouts, logging and error handling appear in every
module. Without a rule, each module grows its own version: one uses a raw HTTP client
with no timeout, the next wraps it in a retry loop with `sleep`, a third logs with
`print`. Agents make this worse, because they copy whichever pattern they saw last.

This file is about **one way per concern, enforced by tooling**. Which library that one
way uses is the org's decision: follow the org toolkit if there is one, otherwise let the
user choose (the `quality-tool-picker` skill can research the options). Library names
below are examples only.

## Contents

1. What to agree
2. CONVENTIONS.md template
3. Service-to-service calls
4. Retries
5. Timeouts and deadlines
6. Circuit breakers and bulkheads
7. Logging
8. Errors
9. Tracing and metrics
10. Enforcement
11. Finding divergence in an existing codebase
12. Converging on one way
13. Org level: put it in the toolkit

---

## 1. What to agree

For each concern, agree with the user (or take from the org toolkit):

| Concern | Decide |
|---|---|
| Service calls | the one client module or wrapper; how base URLs, auth and headers are configured |
| Retries | the one helper or library; which errors are retryable; attempts and backoff |
| Timeouts | default connect and total timeouts; how deadlines propagate |
| Circuit breaking | whether it's needed, and the one library if so |
| Logging | the one logger setup; format (JSON in production); field names; level policy |
| Errors | the error types; where errors are logged; how they map to responses |
| Tracing and metrics | the one instrumentation setup (usually OpenTelemetry) |

## 2. CONVENTIONS.md template

Write the agreement into `CONVENTIONS.md` and reference it from `CLAUDE.md` / `AGENTS.md`.
Keep each entry short: the rule, where the sanctioned code lives, and what enforces it.

```markdown
# Conventions

## Calling other services
Use `ServiceClient` in `src/infra/http/` for every outbound HTTP call. It sets timeouts,
auth, the correlation-ID header and the retry policy. Never import the HTTP library
elsewhere. Enforced by: <lint rule>, <architecture test>.

## Retries
Only through `src/infra/retry` (wraps <library>). Retry only idempotent operations and
only on transient errors (connection errors, timeouts, 429, 502, 503, 504), at most 3
attempts, exponential backoff with full jitter, honour `Retry-After`. Never write a loop
with sleep. Enforced by: semgrep rule `hand-rolled-retry`.

## Timeouts
Every outbound call: connect 2 s, total 10 s unless the downstream's config says
otherwise. Incoming request deadlines propagate to outbound calls.

## Logging
`src/infra/logging` configures the one logger. JSON in production. Fields: `timestamp`,
`level`, `message`, `service`, `trace_id`, `span_id`, `request_id`. Never log secrets or
personal data. Never print. Enforced by: <lint rule>.

## Errors
Domain errors live in `src/domain/errors`. Infrastructure errors are wrapped with their
cause at the boundary. Errors are logged once, where they are handled, and mapped to
`application/problem+json` (RFC 9457) at the HTTP edge.
```

## 3. Service-to-service calls

The sanctioned client (a module, class or package) is the only code that touches the
HTTP or RPC library. It owns:

- base URLs and credentials, read from config
- timeouts (section 5) and the retry policy (section 4)
- propagation of the correlation ID and the W3C `traceparent` header
- parsing responses into typed values at the boundary (the same rule as gate 10:
  untyped data stops at the edge)
- mapping transport failures to the project's error types (section 8)
- one log line and one metric per call, with the downstream's name

Callers depend on a small typed interface (`orders.get(id)`), never on the HTTP library.
That also makes them easy to fake in tests.

## 4. Retries

Retries cause more incidents than they prevent when every module improvises them. The
rules worth enforcing:

- **Only idempotent operations.** GET, PUT and DELETE, or a POST with an idempotency key.
  Never retry a non-idempotent write blindly.
- **Only transient failures.** Connection errors, timeouts, 429, 502, 503, 504. Never
  retry 400, 401, 403, 404 or validation errors.
- **Bounded.** A small attempt limit (typically 3) and a total time limit that fits
  inside the caller's deadline.
- **Exponential backoff with full jitter.** Honour `Retry-After` when the server sends
  it.
- **One layer only.** If the client retries, its callers must not retry again: three
  layers that each retry 3 times turn one failure into 27 calls.
- **Visible.** Each retry is logged (attempt number, reason) and counted in a metric.
- **Budgeted.** Cap retries as a share of all requests to a downstream (for example, at
  most 10% extra calls). When a dependency is down, per-request attempt limits alone
  still multiply its load; a retry budget or token bucket stops that.

Example libraries (the org chooses): Python tenacity or stamina; TypeScript p-retry or
cockatiel; Go cenkalti/backoff or hashicorp/go-retryablehttp (its default policy retries
POST too, so restrict it with a custom `CheckRetry` or a non-retrying client for
non-idempotent calls); Java Resilience4j or the retry support built into Spring
Framework 7 (the separate Spring Retry project is archived); .NET Polly or
Microsoft.Extensions.Http.Resilience; Ruby the Faraday retry middleware; PHP Guzzle
retry middleware; Rust backon or reqwest-retry (the `backoff` crate is unmaintained,
RUSTSEC-2025-0012).

## 5. Timeouts and deadlines

- Every outbound call has a timeout. Several common defaults are "wait forever":
  Python `requests` without `timeout=`, a Go `http.Client` with a zero `Timeout`, many
  JDBC and socket defaults.
- Set both a connect timeout and a total (or read) timeout.
- Propagate deadlines: Go `context.Context`, gRPC deadlines, `AbortSignal` in
  TypeScript, cancellation tokens in .NET. A downstream call must not outlive the
  request that triggered it.

## 6. Circuit breakers and bulkheads

Add them when a slow or failing downstream could exhaust threads, connections or
memory. Use one library for both (Resilience4j, Polly, opossum, gobreaker, …) and apply
them inside the sanctioned client, never at call sites.

## 7. Logging

- **One setup module** configures the logger. Everything else asks it for a logger.
- **Structured.** Key-value fields, JSON in production. Never build messages with
  string interpolation of data: pass fields (`log.info("order created", order_id=id)`).
- **Fixed field names** across services: `timestamp`, `level`, `message`, `service`,
  `env`, `trace_id`, `span_id`, `request_id`.
- **Level policy.** ERROR: someone must act. WARN: degraded but handled. INFO: business
  events and request summaries. DEBUG: development detail, off in production.
- **Log once,** where the error is handled. Log-and-rethrow produces duplicates.
- **No secrets or personal data.** Redact in the logger setup, not at every call site.
- **Correlation.** Middleware puts the request or trace ID in the logging context, so
  every line of a request carries it.

## 8. Errors

- Separate domain errors (expected outcomes: not found, invalid state) from
  infrastructure errors (timeouts, connection failures).
- Wrap infrastructure errors with their cause at the boundary (`raise X from e`,
  `{ cause: e }`, `fmt.Errorf("...: %w", err)`, `anyhow::Context`).
- Map errors to responses in one place at the edge, using RFC 9457
  (`application/problem+json`) for HTTP APIs.
- Never swallow: `except Exception: pass` and empty catch blocks are already banned by
  the gates (see `slop-catalog.md`).

## 9. Tracing and metrics

Use one instrumentation setup, usually OpenTelemetry, configured in one module. The
sanctioned client, retry helper and logger read the current span from it, so traces,
logs and metrics share the same IDs.

## 10. Enforcement

Each convention needs a mechanical check, or agents drift away from it within weeks.
Combine:

1. **One sanctioned module** that owns the library.
2. **A ban rule** that fails when the library, a raw logger or `print` is used anywhere
   else.
3. **A pattern rule** (semgrep or ast-grep) for shapes a ban can't express, such as a
   loop with sleep.
4. **An architecture test** where the language has one (ArchUnit, NetArchTest, import
   contracts).

| Language | Ban the library / raw logger outside the module | Notes |
|---|---|---|
| Python | ruff `TID251` banned-api; import-linter forbidden contracts; ruff `T20` (print) | ruff `S113` requires a timeout on `requests` calls |
| TypeScript / JS | ESLint `no-restricted-imports`, `no-console`; dependency-cruiser | |
| Go | golangci-lint `depguard` (imports), `forbidigo` (calls such as `http.Get`, `log.Printf`) | |
| Java / Kotlin | ArchUnit; Checkstyle `IllegalImport`; detekt `ForbiddenImport`, `ForbiddenMethodCall` | |
| C# / .NET | BannedApiAnalyzers (`BannedSymbols.txt`), NetArchTest | |
| Ruby | packwerk; RuboCop custom cops or semgrep | |
| PHP | phpstan-disallowed-calls; deptrac | |
| Rust | clippy `disallowed_methods`, `disallowed_types` in `clippy.toml` | |
| Any | semgrep or ast-grep | |

Each language reference has a "Cross-cutting conventions" section with working config.

A semgrep rule that catches hand-rolled retries and polls. It was tested on `for`,
`for…of`, `while`, `do…while` and Python `async for` loops; promise sleeps written as an
arrow or a block; `delay()` / `sleep()` / `wait()` helpers; and `setTimeout` from
`node:timers/promises`. It leaves single sleeps and the sanctioned module alone:

```yaml
rules:
  - id: hand-rolled-retry-python
    languages: [python]
    severity: ERROR
    message: Sleeping inside a loop is a hand-rolled retry or poll. Use the shared retry helper named in CONVENTIONS.md.
    patterns:
      - pattern-either:
          - pattern: time.sleep(...)
          - pattern: await asyncio.sleep(...)
          - pattern: await anyio.sleep(...)
          - pattern: await trio.sleep(...)
      - pattern-either:
          - pattern-inside: |
              for $X in $Y:
                  ...
          - pattern-inside: |
              async for $X in $Y:
                  ...
          - pattern-inside: |
              while $COND:
                  ...
    paths:
      exclude:
        - src/infra/retry*
  - id: hand-rolled-retry-ts
    languages: [typescript, javascript]
    severity: ERROR
    message: Waiting inside a loop is a hand-rolled retry or poll. Use the shared retry helper named in CONVENTIONS.md.
    patterns:
      - pattern-either:
          - pattern: await new Promise(...)
          - pattern: |
              await $WAIT(...)
      - pattern-either:
          - pattern: await new Promise(($R) => setTimeout(...))
          - pattern: |
              await new Promise(($R) => { ... setTimeout(...); ... })
          - patterns:
              - pattern: await $WAIT(...)
              - metavariable-regex:
                  metavariable: $WAIT
                  regex: ^(sleep|delay|wait|pause|setTimeout|scheduler\.wait)$
      - pattern-either:
          - pattern-inside: |
              for (...) { ... }
          - pattern-inside: |
              while ($C) { ... }
          - pattern-inside: |
              do { ... } while ($C)
    paths:
      exclude:
        - src/infra/retry*
```

Adjust the exclude path to the project's sanctioned module (the template above uses
`src/infra/retry`). Two things it cannot see: a sleep helper imported under another
name (`import { setTimeout as pauseFor }`; add the alias to the regex), and a retry loop
that doesn't sleep at all. The census below and code review cover those.

Run it in `quality-fast` with `semgrep scan --config .semgrep/ --error`. By default
semgrep skips `test/` and `tests/` and only scans files git tracks; add a `.semgrepignore`
if you need different behaviour.

## 11. Finding divergence in an existing codebase

Take a census before proposing anything. `scripts/convention_census.py` counts every
way the code calls services, retries and logs, per module, across ten languages:

```bash
python <skill-dir>/scripts/convention_census.py src            # who does what, where
python <skill-dir>/scripts/convention_census.py src --depth 3  # finer module grouping
```

Show the user the table, agree which way survives for each concern, and record it in
`CONVENTIONS.md`. The census covers HTTP libraries and raw calls, retry libraries and
sleep calls, and every logging library and print-style output, including competing
libraries such as logrus, zap and zerolog side by side. It doesn't cover timeouts or
error handling, so check those directly:

```bash
# Timeouts: Python requests calls without timeout= (ruff S113); Go clients built without Timeout
ruff check --select S113 src
rg -n 'http\.Client\s*\{' --type go src | rg -v 'Timeout'
# Errors: empty catch blocks and broad excepts
rg -n 'catch\s*(\([^)]*\))?\s*\{\s*\}' --type ts --type java --type cs src
rg -n '^\s*except(\s+(Exception|BaseException))?\s*:' --type py src
```

## 12. Converging on one way

1. Write or pick the sanctioned module first, with its own tests.
2. Migrate callers one module per change, busiest paths first, keeping behaviour the
   same (characterisation tests where it matters).
3. Ratchet the census: write a baseline with the sanctioned modules allowed
   (`convention_census.py src --allow 'src/infra/*' --write-baseline
   .quality/conventions.json`), and run it with `--baseline` in CI so no count can
   grow. Add the lint ban rules for each concern in ratchet mode too.
4. When a concern's count reaches zero, gate it with `--zero <concern>`, drop its
   baseline entries and leave the lint rules on.

## 13. Org level: put it in the toolkit

Uniformity across repos needs the conventions in the org toolkit, not copied into each
repo: a shared library for the client, retry and logging setup, and a shared lint preset
that carries the ban rules. A repo's `CONVENTIONS.md` then just names the shared pieces.
When this skill finds a convention the toolkit lacks, propose adding it there.
