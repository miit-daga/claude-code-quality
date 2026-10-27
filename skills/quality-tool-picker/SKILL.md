---
name: quality-tool-picker
description: >-
  Research and compare the current options for one tooling slot in a project (formatter or
  style guide, linter or lint preset, type checker, test runner, coverage tool, mutation
  tester, HTTP client, retry library, logger, and similar), using live web research with
  cited sources, then help the user choose and record the decision. Checks the org's
  toolkit first. Use when the user or the code-quality skill needs to choose between tools,
  e.g. "which Java formatter should we use", "Spotless with google-java-format or
  palantir?", "compare ruff and black", "pick a retry library for Go". Not for configuring
  a tool that has already been chosen.
---

# Quality tool picker

Picks between tools that fill the same slot, such as google-java-format vs
palantir-java-format vs the Eclipse formatter for Java formatting. The decision belongs to
the user or the org. This skill does the research, lays out the trade-offs with sources,
recommends one option, and records whatever the user decides.

Tool landscapes change quickly: projects get abandoned, forked or replaced, and a new
tool can overtake the old default within a year. Never answer from memory alone. Check
the current state on the web and cite what you found.

## 1. Pin down the slot and the constraints

Collect these from the project and the user before researching:

- **Slot:** exactly what the tool must do (for example "Java formatting, enforced in CI",
  not "Java quality").
- **Stack:** language and version, build tool, framework, CI provider, editors in use.
- **Existing setup:** what the project already uses for this slot, and what migrating
  away would cost.
- **Org toolkit:** shared configs, parent POMs, convention plugins, CI templates, an
  internal library. **If the org mandates a tool for this slot, stop and report that
  choice.** There is nothing to pick.
- **Must-haves and deal-breakers:** licence, offline use, auto-fix, speed, IDE support,
  compatibility with other tools (for example a formatter that doesn't fight the linter).

## 2. Build the candidate list

Start from `references/catalog.md` (a seed list, which may be out of date), then search
the web for current alternatives and recent comparisons, for example "<slot> <language>
<current year>", "<tool A> vs <tool B>", and "<tool> deprecated" or "<tool> alternative".
Keep 2 to 4 serious candidates. Include "keep what we have" when something already exists.

## 3. Research each candidate

Prefer primary sources: the official repo, release notes, documentation and the package
registry page. Use blog posts and comparisons for context only, never as the only source
for a fact. For each candidate, find:

| Aspect | What to check |
|---|---|
| Maintenance | latest release and its date, release cadence, recent commits, how issues get answered, whether it's deprecated or has a successor |
| Adoption | registry downloads or well-known users, where the ecosystem publishes them |
| Compatibility | supports the project's language and runtime versions, build tool and framework |
| Fit | covers the slot completely; overlaps or conflicts with tools already chosen |
| Cost | setup effort, migration effort (for a formatter: one large reformat commit), CI time |
| Developer experience | IDE and editor integration, auto-fix, quality of error messages |
| Licence | compatible with the project |

Write down where each fact came from and the date you checked. If you can't verify
something, say "unknown". Never estimate numbers such as download counts or release
dates.

## 4. Compare and recommend

Present a short comparison and one recommendation:

```markdown
## <Slot>: options for <project>

| | <Option A> | <Option B> | <Option C> |
|---|---|---|---|
| Latest release | 1.2.3 (2026-09-14) | ... | ... |
| Maintenance | active, monthly releases | ... | ... |
| Fits our stack | yes (JDK 21, Gradle 9) | ... | ... |
| Main trade-off | ... | ... | ... |
| Migration cost | ... | ... | ... |

**Recommendation: <Option>**, because <reasons tied to the constraints in step 1>.
Runner-up: <Option>, if <condition>.

Sources (checked <date>): <links>
```

Keep it to what matters for this decision. If the options are effectively equivalent,
say so and recommend the one that's cheapest to adopt, which is often the one already in
use or the one the wider ecosystem defaults to.

## 5. Let the user decide

Ask the user to choose, listing the recommended option first. If they choose differently,
that's their call: record it without arguing further.

## 6. Record the decision

Write a short decision record so the choice isn't reopened every few months, and so
future agents follow it. Use the project's existing convention if it has one, otherwise
`docs/adr/NNNN-<slot>.md`:

```markdown
# NNNN. <Slot>: <chosen tool>

Date: <date>. Status: accepted. Review by: <date, about a year out>.

## Context
<slot, constraints, org toolkit status>

## Options considered
<one line each, with the main trade-off>

## Decision
<tool and version, plus the key configuration choices, such as a style preset>

## Consequences
<migration steps, CI changes, what becomes harder>

Sources (checked <date>): <links>
```

If the `code-quality` skill sent you here, return the choice so it can configure the tool
using its language reference.
