#!/usr/bin/env python3
"""Mutation-score gate that reads the reports of the common mutation tools.

Most tools' built-in thresholds count a mutant in untested code as "not killed",
so the mutation score then repeats what coverage already measures. This script
reports both numbers and gates on the one that measures test strength:

    covered score = killed / (killed + survived)                 # default gate
    total score   = killed / (killed + survived + no_coverage)

Timeouts count as killed (the change was detected), as do PIT's memory and run
errors. Compile errors, unviable and ignored mutants are excluded from both.

If the report has mutants but none of them is covered by a test, the changed code
is entirely untested and the gate FAILS (the covered score would otherwise be n/a).
A report with no mutants at all passes: there was nothing to mutate.

Reports accepted (format detected from the content):
  * Stryker mutation-testing-report JSON (StrykerJS, Stryker.NET, stryker4s):
      reports/mutation/mutation.json
  * PIT mutations.xml:            target/pit-reports/mutations.xml
  * mutmut 3 CI/CD stats:         mutants/mutmut-cicd-stats.json (run `mutmut export-cicd-stats`)
  * gremlins JSON:                gremlins unleash --output gremlins.json
  * cargo-mutants outcomes.json:  mutants.out/outcomes.json (it has no coverage step,
                                  so its covered and total scores are the same)
PIT (`testStrengthThreshold`) and Infection (`--min-covered-msi`) gate covered-code scores
natively. mutant (Ruby) has no score option; see the language reference.

Examples:
  python mutation_score.py reports/mutation/mutation.json                # covered score >= 80
  python mutation_score.py target/pit-reports/mutations.xml --min-covered 90
  python mutation_score.py mutants/mutmut-cicd-stats.json --max-survived 0   # strict profile

Exit code 1 if a threshold is missed, 2 if the report can't be read.
"""

from __future__ import annotations

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

# PIT counts memory and run errors as detected, so they count as killed here too.
KILLED = {"killed", "timeout", "timed_out", "timed out", "caught", "memory_error", "run_error"}
SURVIVED = {"survived", "lived", "missed"}
NO_COVERAGE = {"nocoverage", "no_coverage", "not covered", "no_tests"}


@dataclass
class Counts:
    killed: int = 0
    survived: int = 0
    no_coverage: int = 0
    excluded: int = 0

    def add(self, status: str) -> None:
        key = status.strip().lower()
        if key in KILLED:
            self.killed += 1
        elif key in SURVIVED:
            self.survived += 1
        elif key in NO_COVERAGE:
            self.no_coverage += 1
        else:
            self.excluded += 1

    def covered_score(self) -> float | None:
        tested = self.killed + self.survived
        return 100.0 * self.killed / tested if tested else None

    def total_score(self) -> float | None:
        valid = self.killed + self.survived + self.no_coverage
        return 100.0 * self.killed / valid if valid else None


def from_stryker(data: dict) -> Counts:
    counts = Counts()
    for file in data["files"].values():
        for mutant in file.get("mutants", []):
            counts.add(mutant["status"])
    return counts


def from_gremlins(data: dict) -> Counts:
    counts = Counts()
    for file in data["files"]:
        for mutation in file.get("mutations", []):
            counts.add(mutation["status"])
    return counts


def from_mutmut(data: dict) -> Counts:
    return Counts(
        killed=data["killed"] + data.get("timeout", 0),
        survived=data["survived"],
        no_coverage=data.get("no_tests", 0),
        excluded=data.get("skipped", 0) + data.get("suspicious", 0) + data.get("segfault", 0),
    )


def from_cargo_mutants(data: dict) -> Counts:
    return Counts(
        killed=data["caught"] + data.get("timeout", 0),
        survived=data["missed"],
        excluded=data.get("unviable", 0),
    )


def from_pit(text: str) -> Counts:
    counts = Counts()
    for mutation in ET.fromstring(text).iter("mutation"):
        counts.add(mutation.get("status", ""))
    return counts


def load(path: Path) -> tuple[str, Counts]:
    text = path.read_text(encoding="utf-8", errors="replace")
    if text.lstrip().startswith("<"):
        return "PIT", from_pit(text)
    data = json.loads(text)
    files = data.get("files")
    if isinstance(files, dict):
        return "Stryker", from_stryker(data)
    if isinstance(files, list):
        return "gremlins", from_gremlins(data)
    if "killed" in data and "survived" in data:
        return "mutmut", from_mutmut(data)
    if "caught" in data and "missed" in data:
        return "cargo-mutants", from_cargo_mutants(data)
    raise ValueError("unrecognised mutation report format")


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("report")
    ap.add_argument("--min-covered", type=float, default=80.0, help="minimum covered-code score in %% (default 80)")
    ap.add_argument("--min-total", type=float, default=None, help="optional minimum total score in %%")
    ap.add_argument("--max-survived", type=int, default=None, help="optional cap on survivors (0 = strict profile)")
    return ap.parse_args()


def fmt(score: float | None) -> str:
    return "n/a" if score is None else f"{score:.1f}%"


def failures(counts: Counts, args: argparse.Namespace) -> list[str]:
    found = []
    covered, total = counts.covered_score(), counts.total_score()
    if covered is None and counts.no_coverage:
        found.append(f"no covered mutants: {counts.no_coverage} mutants are in code no test runs")
    if covered is not None and covered < args.min_covered:
        found.append(f"covered score {fmt(covered)} < {args.min_covered:g}%")
    if args.min_total is not None and total is not None and total < args.min_total:
        found.append(f"total score {fmt(total)} < {args.min_total:g}%")
    if args.max_survived is not None and counts.survived > args.max_survived:
        found.append(f"{counts.survived} survived > {args.max_survived}")
    return found


def main() -> int:
    args = parse_args()
    try:
        tool, counts = load(Path(args.report))
    except (OSError, ValueError, KeyError, TypeError, ET.ParseError) as err:
        print(f"mutation_score: cannot read {args.report}: {err}", file=sys.stderr)
        return 2
    print(
        f"{tool}: killed={counts.killed} survived={counts.survived} no_coverage={counts.no_coverage} "
        f"excluded={counts.excluded}  covered score={fmt(counts.covered_score())} total score={fmt(counts.total_score())}"
    )
    problems = failures(counts, args)
    for problem in problems:
        print(f"FAIL: {problem}")
    print(f"mutation_score: {'FAIL' if problems else 'OK'}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
