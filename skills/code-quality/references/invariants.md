# Invariants: writing them down and making them mechanical

Most people find invariants hard to define and harder to keep. For an LLM they are
oxygen. An agent has no memory of the incident that made a rule necessary. Unless the
rule is written down *and* checked by a machine, the agent will eventually
"simplify" it away while making a test pass.

## Contents

1. What counts as an invariant
2. Finding them (new project and existing code)
3. INVARIANTS.md format
4. The enforcement ladder
5. Worked example: "never store a user row unless the user has authenticated"
6. A catalog of common invariants and their best enforcement
7. Property-based and model-based testing
8. Formal methods: when they pay off and how to use them with agents

---

## 1. What counts as an invariant

A statement that must hold in **every** reachable state, not just in the cases the tests
happen to try:

- **Data**: "every order has at least one line item", "balances never go negative",
  "money is stored as integer minor units".
- **Authorization**: "a user can only read documents of their own tenant", "only the auth
  module creates sessions".
- **Lifecycle / state machine**: "an invoice moves draft → issued → paid | void and never
  back", "a job is processed by at most one worker at a time".
- **Architecture**: "the domain layer never imports the web framework", "only the billing
  service talks to Stripe".
- **Operational**: "PII never reaches logs", "every migration is backward compatible with
  the previous release".

If a rule has exceptions, write the exceptions into the rule. An invariant with unwritten
exceptions is a suggestion, and agents treat suggestions as optional.

## 2. Finding them

**New project:** ask the user before any code exists. Useful prompts:
- What must never happen, even once? (data loss, cross-tenant leak, double charge)
- Which states must be impossible?
- Who is allowed to do each write?
- What has burned you on previous projects?
- What do regulators, auditors or customers require?

**Existing code:** mine them from
- database constraints, unique indexes and foreign keys (and notice which are *missing*)
- validation code, `assert`s, guard clauses that raise
- comments containing *must*, *never*, *always*, *only*, *do not*
- incident postmortems and bug-tracker labels
- tests named `test_cannot_*` / `should not *`

## 3. INVARIANTS.md format

One entry per invariant, short enough that an agent reads all of it:

```markdown
## INV-1: Users exist only after authentication
**Rule:** A row in `users` is created only for an identity that the auth provider has verified.
**Why:** Pre-auth rows let attackers enumerate and squat on emails (incident 2024-03).
**Enforced by:**
- Type: `users.create()` requires `AuthenticatedIdentity`, constructible only in `auth/verify.py`
- DB: `users.auth_subject NOT NULL REFERENCES auth_identities(subject)`
- Boundary: import-linter contract `users-write` (only `app.users` imports the repository)
- Lint: semgrep rule `user-insert-outside-repository`
- Test: `tests/users/test_signup_requires_auth.py`, property test `test_users_subset_of_verified`
**Owner:** @platform-team
```

Reference INVARIANTS.md from CLAUDE.md/AGENTS.md, and make it CODEOWNED.

## 4. The enforcement ladder

Enforce each invariant at the lowest rung that can express it. Lower rungs fail
earlier, need no discipline, and are harder to game. Combine rungs for the important
ones.

| Rung | Mechanism | Fails at | Examples |
|---|---|---|---|
| 1 | **Types**: make the illegal state unrepresentable | compile / type-check | branded/newtypes, private constructors, sealed hierarchies, non-empty collections, enums instead of strings, `Money` value types |
| 2 | **Database constraints** | write time, for every writer including scripts and other services | NOT NULL, CHECK, FK, UNIQUE, exclusion constraints, row-level security, column grants |
| 3 | **Module boundaries**: one module owns the action | lint / build | Go `internal/`, Java modules/package-private, import-linter, dependency-cruiser, ArchUnit, Konsist, NetArchTest, deptrac, packwerk, depguard |
| 4 | **Custom lint rules** | lint | semgrep, ast-grep, ESLint `no-restricted-syntax`/`no-restricted-imports`, BannedApiAnalyzers, forbidigo, RuboCop custom cops |
| 5 | **Runtime checks at the boundary** | runtime | schema validation at the edge, contracts (icontract/deal, Code Contracts-style guards), DB triggers as a last resort |
| 6 | **Property-based / model-based tests** | test | Hypothesis, fast-check, rapid, jqwik, FsCheck/CsCheck, proptest, StreamData, prop_check, ScalaCheck |
| 7 | **Model checking / formal proof** | design or CI | TLA+/Quint, P, Alloy, Dafny, Kani/Verus/Prusti/Creusot, CrossHair, CBMC |

Example-based unit tests are not on the ladder on purpose. They check the invariant
for the inputs someone thought of, which is necessary but not enforcement.

## 5. Worked example: "never store a row in the user table unless the user has authenticated"

### Rung 1: types

The repository's only insert method demands proof of authentication, and only the auth
module can produce that proof.

TypeScript (branded type, constructed in one file):

```ts
// auth/identity.ts: the only place an AuthenticatedIdentity can be created
declare const verified: unique symbol;
export type AuthenticatedIdentity = { readonly subject: string; readonly [verified]: true };

export async function verifySession(token: string): Promise<AuthenticatedIdentity> {
  const claims = await provider.verify(token);            // throws if invalid
  return { subject: claims.sub } as AuthenticatedIdentity; // the one sanctioned cast
}

// users/repository.ts
export function createUser(identity: AuthenticatedIdentity, profile: NewProfile): Promise<User> { /* ... */ }
```

Ban `as AuthenticatedIdentity` everywhere else with a lint rule (rung 4).

Go (unexported field, so only package `auth` can construct it):

```go
package auth

type Identity struct{ subject string } // zero value is unusable; no exported constructor except Verify

func Verify(ctx context.Context, token string) (Identity, error) { /* ... */ }
func (i Identity) Subject() string { return i.subject }

// package users
func (r *Repo) Create(ctx context.Context, id auth.Identity, p Profile) (User, error) {
    if id.Subject() == "" { return User{}, ErrUnverified } // rejects the zero value
    // ...
}
```

Python (only the auth module can make one; enforced by a lint rule, because Python
has no truly private constructors):

```python
# app/auth/identity.py
@dataclass(frozen=True, slots=True)
class AuthenticatedIdentity:
    subject: str

def verify_session(token: str) -> AuthenticatedIdentity:
    claims = provider.verify(token)  # raises on failure
    return AuthenticatedIdentity(subject=claims["sub"])
```

Java/Kotlin/C#: a constructor visible only inside the auth package or assembly
(package-private in Java, `internal` in Kotlin/C#), plus a public `verify` factory.

### Rung 2: database

```sql
CREATE TABLE auth_identities (
  subject     text PRIMARY KEY,
  verified_at timestamptz NOT NULL
);
CREATE TABLE users (
  id           bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  auth_subject text NOT NULL UNIQUE REFERENCES auth_identities(subject),
  email        text NOT NULL
);
-- Only the auth service's role may write auth_identities; the app role cannot forge one.
-- Grants do not bind a table's owner (or a superuser), so neither role may own the table:
-- a separate migrations role owns it.
ALTER TABLE auth_identities OWNER TO migrations_role;
REVOKE INSERT, UPDATE ON auth_identities FROM app_role;
GRANT  INSERT, UPDATE ON auth_identities TO auth_role;
```

Now a hand-written script or another service connecting as `app_role` cannot insert an
unauthenticated user. Anything connecting as the owner or a superuser still can, so keep
those credentials out of application code.

### Rung 3: module boundary

Python, import-linter (`.importlinter` or `[tool.importlinter]` in pyproject):

```ini
[importlinter]
root_package = app

[importlinter:contract:users-write]
name = Only app.users may use the users repository
type = forbidden
source_modules =
    app.api
    app.billing
    app.jobs
forbidden_modules =
    app.users.repository
```

TypeScript, dependency-cruiser (`.dependency-cruiser.js`):

```js
module.exports = {
  forbidden: [
    {
      name: "users-repository-owned-by-users",
      severity: "error",
      from: { pathNot: "^src/users/" },
      to: { path: "^src/users/repository" },
    },
  ],
};
```

Java, ArchUnit:

```java
@ArchTest
static final ArchRule usersRepositoryOwnedByUsers =
    noClasses().that().resideOutsideOfPackage("..users..")
        .should().dependOnClassesThat().haveSimpleName("UserRepository");
```

Go: put the repository under `users/internal/`. The Go toolchain then refuses imports
from outside `users/`.

### Rung 4: custom lint rule (semgrep)

```yaml
# .semgrep/invariants.yml
rules:
  - id: user-insert-outside-repository
    languages: [python]
    severity: ERROR
    message: Users may only be created via app/users/repository.py (INVARIANTS.md INV-1)
    pattern-either:
      - pattern: User.objects.create(...)
      - pattern: User(...).save()
      - pattern-regex: (?i)insert\s+into\s+users\b
    paths:
      exclude:
        - app/users/repository.py
        - migrations/
```

Run `semgrep --config .semgrep/ --error` in `quality-fast`. Agents are good at writing
semgrep and ast-grep rules, so for every invariant that can be described as a code
pattern, have the agent write the rule *and* a fixture file showing that it fires.

### Rung 6: property test

Hypothesis stateful test: whatever sequence of signup, login and admin calls happens,
the set of user subjects is always a subset of verified identities:

```python
import contextlib

from hypothesis import strategies as st
from hypothesis.stateful import RuleBasedStateMachine, invariant, rule


class SignupMachine(RuleBasedStateMachine):
    @rule(email=st.emails(), verified=st.booleans())
    def attempt_signup(self, email, verified):
        token = make_token(email) if verified else forge_token(email)
        # Rejecting a forged token is the expected outcome; an exception from a rule would
        # otherwise fail the test. Name the API's real rejection error so anything else still fails.
        with contextlib.suppress(AuthRejected):
            api.signup(token, email)

    @invariant()
    def users_are_verified(self):
        assert db.user_subjects() <= db.verified_subjects()

TestSignup = SignupMachine.TestCase
```

The same shape works with fast-check `fc.commands`, rapid's state machines (Go) and
jqwik's actions.

## 6. Catalog: common invariants and their best rung

| Invariant | Best enforcement |
|---|---|
| Tenant isolation (every query scoped to the tenant) | Postgres row-level security + a lint rule banning unscoped queries + a property test across two tenants |
| Money is never floating point | `Money` value type (integer minor units or decimal) + lint ban on float in money modules |
| State machine transitions only along allowed edges | sealed state types or a transition table as the only mutator + a CHECK limiting the status to known values + transitions enforced in the database by a conditional update (`UPDATE invoices SET status = 'paid' WHERE id = $1 AND status = 'issued'`, then require exactly one row changed) or a trigger, because a CHECK sees only the new row, never the old one + a model-based test |
| Idempotency (a request applied at most once) | UNIQUE constraint on the idempotency key + a property test with retries |
| PII never logged | logger wrapper that accepts only a `Redacted` type + a semgrep rule on raw logger calls with user fields |
| All timestamps UTC | `timestamptz` columns + a lint ban on naive datetimes (ruff `DTZ` rules for Python) |
| Migrations backward compatible | strong_migrations (Rails), squawk (Postgres SQL linter), and the rule "expand, then contract" in CLAUDE.md |
| Domain layer independent of frameworks | import-linter / dependency-cruiser / ArchUnit layer contracts |
| Only one module talks to an external API | module boundary + a banned-import rule for that SDK elsewhere |
| No job processed twice concurrently | DB row lock or lease + a TLA+/Quint model of the claim protocol (section 8) |

## 7. Property-based and model-based testing

Property tests generate hundreds of inputs and shrink failures to a minimal
counterexample. They are the cheapest way to check an invariant over many states.
Model-based (stateful) tests generate *sequences of operations* and check invariants
after each step. That is what catches ordering bugs.

| Language | Library |
|---|---|
| Python | Hypothesis (`RuleBasedStateMachine` for stateful) |
| TypeScript / JS | fast-check (`fc.commands` / `fc.modelRun` for model-based) |
| Go | `pgregory.net/rapid` (state machines), also native `go test -fuzz` |
| Java | jqwik (actions / state machines) |
| Kotlin | jqwik, Kotest property testing |
| C# / F# | FsCheck, CsCheck |
| Rust | proptest, quickcheck, plus `cargo fuzz` |
| Ruby | prop_check, rantly |
| PHP | Eris |
| Elixir | StreamData, PropEr |
| Scala | ScalaCheck |

Turn every shrunk counterexample into a plain regression test as well, so the
specific bug stays covered even if the generator changes.

## 8. Formal methods: when they pay off and how to use them with agents

**Worth it when** tests can't explore the state space: concurrency (thread pools,
reactors, locks, async cancellation), distributed protocols (leader election,
replication, exactly-once delivery, sagas), complex state machines, permission
models, and parsers or arithmetic where a single wrong case is costly. People have
reported decent results pointing these tools at real servers such as Puma.

**Not worth it** for CRUD, UI and glue code. There, types, constraints and property
tests already cover the invariants.

**Tools by job:**

| Job | Tools |
|---|---|
| Design-level model checking of concurrent or distributed protocols | TLA+ (TLC, Apalache) / PlusCal, Quint (TLA-based, friendlier syntax and simulator), P (used at AWS) |
| Data-model and permission consistency | Alloy |
| Verified implementation | Dafny (compiles to C#, Java, Go, Python, JS), Lean 4, Rocq (Coq), Isabelle |
| Verifying real code in place | Rust: Kani, Verus, Prusti, Creusot. C: CBMC, Frama-C. Python: CrossHair (symbolic execution of contracts and type hints). Java: OpenJML, KeY. Go: Gobra |
| In-language concurrency exploration | Rust loom, Java jcstress, .NET Coyote, Go `-race` + rapid |
| Whole-system fault injection | deterministic simulation testing (FoundationDB-style, TigerBeetle's VOPR, Antithesis) |

**Workflow with an agent:**

1. State the invariants in English (from INVARIANTS.md).
2. Have the agent write the smallest model that contains only the state and actions that
   affect those invariants. Not the whole system.
3. Model-check with small bounds (2–3 workers, 2–3 jobs). Most protocol bugs show up
   at small sizes.
4. A human reviews the **spec** against the code: does each action correspond to real
   code? An agent can write a spec that is wrong in the same way as the code.
5. Each counterexample trace becomes a failing test in the real code. Fix the code until
   that test and the model check both pass.
6. Commit the spec next to the code, run the model checker in CI, and CODEOWN the spec
   with the module so changes to one prompt a review of the other.

**Minimal TLA+ example**: a job queue with crashing workers. The invariants are that
no job is held by two workers at once and that no job is ever lost.

```tla
---- MODULE JobQueue ----
CONSTANTS Jobs, Workers
VARIABLES queue, inFlight, done
vars == <<queue, inFlight, done>>

Init == /\ queue = Jobs
        /\ inFlight = [w \in Workers |-> {}]
        /\ done = {}

Claim(w, j) == /\ j \in queue
               /\ queue' = queue \ {j}
               /\ inFlight' = [inFlight EXCEPT ![w] = @ \cup {j}]
               /\ UNCHANGED done

Finish(w, j) == /\ j \in inFlight[w]
                /\ inFlight' = [inFlight EXCEPT ![w] = @ \ {j}]
                /\ done' = done \cup {j}
                /\ UNCHANGED queue

Crash(w) == /\ inFlight[w] # {}
            /\ queue' = queue \cup inFlight[w]   \* claimed jobs go back to the queue
            /\ inFlight' = [inFlight EXCEPT ![w] = {}]
            /\ UNCHANGED done

Next == \E w \in Workers : Crash(w) \/ \E j \in Jobs : Claim(w, j) \/ Finish(w, j)
Spec == Init /\ [][Next]_vars

NoDoubleClaim == \A w1, w2 \in Workers : w1 # w2 => inFlight[w1] \cap inFlight[w2] = {}
NothingLost   == queue \cup done \cup UNION {inFlight[w] : w \in Workers} = Jobs
====
```

`JobQueue.cfg`:

```
SPECIFICATION Spec
CONSTANTS Jobs = {j1, j2, j3}  Workers = {w1, w2}
INVARIANTS NoDoubleClaim NothingLost
CHECK_DEADLOCK FALSE
```

`CHECK_DEADLOCK FALSE` is needed because the system legitimately stops once every job is
done. Run with `java -jar tla2tools.jar -config JobQueue.cfg JobQueue.tla` (TLC), or use
the TLA+ VS Code extension. To see a counterexample, change `Crash` to drop the jobs
instead of re-queuing them, and TLC will report a trace that violates `NothingLost`.
That trace is exactly the regression test to write against the real worker code.
