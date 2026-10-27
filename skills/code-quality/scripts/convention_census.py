#!/usr/bin/env python3
"""Count the different ways a codebase calls services, retries and logs, per module.

Cross-cutting code drifts: one module uses a raw HTTP client, the next wraps it in
its own retry loop, a third logs with print. This script takes the census that the
convergence step needs, then holds the line while modules migrate:

  http     HTTP client libraries and raw calls (requests, httpx, axios, fetch,
           net/http, RestTemplate, WebClient, HttpClient, Faraday, Guzzle, reqwest, ...)
  retry    retry and resilience libraries (tenacity, p-retry, cenkalti/backoff,
           Resilience4j, Polly, retriable, backon, ...) plus sleep calls, which are
           often hand-rolled retries or polls
  logging  print/console output and every logging library in use (logging,
           structlog, pino, winston, slog, zap, logrus, SLF4J, Log4j, Serilog, ...)

Usage:
  python convention_census.py src                          # census table, never fails
  python convention_census.py src --allow 'src/infra/*'    # sanctioned modules are not counted
  python convention_census.py src --allow 'src/infra/*' --write-baseline .quality/conventions.json
  python convention_census.py src --allow 'src/infra/*' --baseline .quality/conventions.json   # ratchet
  python convention_census.py src --allow 'src/infra/*' --zero http logging                  # converged

Hits inside --allow globs are reported but never counted against the gate. Lines
that are comments are skipped. The patterns are line-based heuristics: they find
candidates for a human or agent to review, and a semgrep or lint rule should take
over once a concern has converged.

Exit code 1 if a count grew against --baseline or a --zero concern has hits outside
the allowed paths, 0 otherwise.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _files import SOURCE_EXTS, list_files, read_text

PY = {".py"}
JS = {".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".mts", ".cts"}
GO = {".go"}
JVM = {".java", ".kt", ".kts", ".scala", ".groovy"}
CS = {".cs"}
RB = {".rb", ".rake"}
PHP = {".php"}
RS = {".rs"}
COMMENT_START = ("#", "//", "/*", "*", "--")


@dataclass(frozen=True)
class Variant:
    concern: str
    name: str
    pattern: str
    exts: frozenset[str]


def v(concern: str, name: str, pattern: str, exts: set[str]) -> Variant:
    return Variant(concern, name, pattern, frozenset(exts))


VARIANTS = [
    # http
    v("http", "requests", r"^\s*(import requests\b|from requests\b)", PY),
    v("http", "httpx", r"^\s*(import httpx\b|from httpx\b)", PY),
    v("http", "aiohttp", r"^\s*(import aiohttp\b|from aiohttp\b)", PY),
    v(
        "http",
        "urllib",
        r"^\s*(import urllib3\b|from urllib3\b|import urllib\.request|from urllib\.request\b|from urllib import request)",
        PY,
    ),
    v("http", "axios", r"""(from|require\()\s*['"]axios['"]""", JS),
    v("http", "got / ky / superagent / node-fetch", r"""(from|require\()\s*['"](got|ky|superagent|node-fetch)['"]""", JS),
    v("http", "undici", r"""(from|require\()\s*['"]undici['"]""", JS),
    v("http", "fetch()", r"(?<![\w.])fetch\(", JS),
    v("http", "net/http raw calls", r"\bhttp\.(Get|Post|Head|PostForm|NewRequest|NewRequestWithContext)\(", GO),
    v("http", "net/http clients", r"\bhttp\.(DefaultClient\b|Client\s*\{)", GO),
    v("http", "resty", r"go-resty/resty", GO),
    v("http", "RestTemplate / RestClient", r"\b(RestTemplate|RestClient)\b", JVM),
    v("http", "WebClient", r"\bWebClient\b", JVM),
    v(
        "http",
        "java.net.http / HttpURLConnection",
        r"\b(java\.net\.http\.HttpClient|HttpClient\.new(HttpClient|Builder)|HttpURLConnection)\b",
        JVM,
    ),
    v(
        "http",
        "OkHttp / Apache / Feign / Ktor",
        r"\b(OkHttpClient|CloseableHttpClient|HttpClients\.|@FeignClient|io\.ktor\.client)",
        JVM,
    ),
    v("http", "new HttpClient()", r"\bnew HttpClient\(", CS),
    v("http", "RestSharp / Refit / Flurl", r"\b(RestSharp|RestService\.For|Flurl\.Http)\b", CS),
    v("http", "Net::HTTP", r"\bNet::HTTP\b", RB),
    v(
        "http",
        "Faraday / HTTParty / RestClient / http.rb",
        r"\b(Faraday\.(new|get|post)|HTTParty|RestClient\.|HTTP\.(get|post|put|delete))",
        RB,
    ),
    v("http", "Guzzle", r"GuzzleHttp\\", PHP),
    v("http", "curl", r"\bcurl_(init|exec)\(", PHP),
    v("http", "Symfony HttpClient", r"Symfony\\Component\\HttpClient|Symfony\\Contracts\\HttpClient", PHP),
    v("http", "reqwest", r"\breqwest::", RS),
    v("http", "hyper / ureq / surf", r"\b(hyper::Client|hyper_util::client|ureq::|surf::)", RS),
    # retry
    v("retry", "tenacity / stamina / backoff", r"^\s*(import|from)\s+(tenacity|stamina|backoff)\b", PY),
    v(
        "retry",
        "p-retry / async-retry / cockatiel / axios-retry",
        r"""(from|require\()\s*['"](p-retry|async-retry|cockatiel|axios-retry|retry)['"]""",
        JS,
    ),
    v("retry", "Go retry libraries", r"(cenkalti/backoff|go-retryablehttp|avast/retry-go|sethvargo/go-retry|failsafe-go)", GO),
    v(
        "retry",
        "Resilience4j / Spring retry / Failsafe",
        r"(io\.github\.resilience4j|@Retryable|RetryTemplate|dev\.failsafe|net\.jodah\.failsafe)",
        JVM,
    ),
    v(
        "retry",
        "Polly / resilience handlers",
        r"\b(Polly|AddStandardResilienceHandler|AddResilienceHandler|ResiliencePipeline)\b",
        CS,
    ),
    v("retry", "retriable / faraday-retry", r"(\bRetriable\b|faraday/retry|retry_on\b)", RB),
    v("retry", "Guzzle / Symfony retry", r"(Middleware::retry|RetryableHttpClient)", PHP),
    v("retry", "Rust retry crates", r"\b(backoff::|backon::|tokio_retry::|reqwest_retry::)", RS),
    v("retry", "sleep calls (possible hand-rolled retry or poll)",
      r"(\btime\.sleep\(|\basyncio\.sleep\(|\bThread\.sleep\(|\bTask\.Delay\(|\btime\.Sleep\(|\bsetTimeout\(|\busleep\(|\bsleep\(|std::thread::sleep|tokio::time::sleep)",
      PY | JS | GO | JVM | CS | RB | PHP | RS),
    # logging
    v("logging", "print()", r"(?<![\w.])print\(", PY),
    v("logging", "stdlib logging", r"^\s*(import logging\b|from logging\b)|\blogging\.getLogger\(", PY),
    v("logging", "structlog / loguru", r"^\s*(import|from)\s+(structlog|loguru)\b", PY),
    v("logging", "console.*", r"\bconsole\.(log|info|warn|error|debug|trace)\(", JS),
    v("logging", "pino / winston / bunyan / log4js", r"""(from|require\()\s*['"](pino|winston|bunyan|log4js)['"]""", JS),
    v("logging", "fmt.Print / log.Print", r"\b(fmt\.Print(f|ln)?|log\.(Print|Printf|Println|Fatal|Fatalf|Panic|Panicf))\(", GO),
    v("logging", "log/slog", r"\blog/slog\b|\bslog\.(Info|Warn|Error|Debug|New|Default)\b", GO),
    v("logging", "logrus / zap / zerolog", r"(sirupsen/logrus|go\.uber\.org/zap|rs/zerolog)", GO),
    v("logging", "System.out / System.err", r"\bSystem\.(out|err)\.print", JVM),
    v("logging", "java.util.logging", r"\bjava\.util\.logging\b", JVM),
    v("logging", "SLF4J", r"\borg\.slf4j\b", JVM),
    v("logging", "Log4j / Logback direct", r"\b(org\.apache\.logging\.log4j|org\.apache\.log4j|ch\.qos\.logback)\b", JVM),
    v("logging", "kotlin-logging", r"\b(mu\.KotlinLogging|io\.github\.oshai\.kotlinlogging)\b", JVM),
    v("logging", "Console.Write / Debug.Write", r"\b(Console|Debug|Trace)\.Write(Line)?\(", CS),
    v("logging", "Microsoft.Extensions.Logging", r"\bILogger(<|\b)", CS),
    v("logging", "Serilog / NLog / log4net", r"\b(Serilog|NLog|log4net)\b", CS),
    v("logging", "puts / pp", r"^\s*(puts|pp)\b", RB),
    v("logging", "Rails.logger / Logger.new", r"\b(Rails\.logger|Logger\.new)\b", RB),
    v("logging", "semantic_logger / lograge", r"\b(SemanticLogger|Lograge)\b", RB),
    v("logging", "error_log / var_dump / print_r", r"\b(error_log|var_dump|print_r|dump|dd)\(", PHP),
    v("logging", "Monolog / PSR-3", r"(Monolog\\|Psr\\Log\\LoggerInterface)", PHP),
    v("logging", "println! / eprintln! / dbg!", r"\b(println!|eprintln!|dbg!)", RS),
    v("logging", "log / tracing / slog crates", r"\b(log::(info|warn|error|debug|trace)|tracing::|slog::)", RS),
]
CONCERNS = sorted({var.concern for var in VARIANTS})
COMPILED = [(var, re.compile(var.pattern)) for var in VARIANTS]


@dataclass
class Hit:
    variant: Variant
    path: Path
    line: int
    allowed: bool


def module_of(path: Path, depth: int) -> str:
    parts = path.parts[:-1]
    return "/".join(parts[:depth]) or "."


def scan(path: Path, allowed: bool) -> list[Hit]:
    hits = []
    for number, line in enumerate(read_text(path).splitlines(), start=1):
        if line.lstrip().startswith(COMMENT_START):
            continue
        for variant, rx in COMPILED:
            if path.suffix in variant.exts and rx.search(line):
                hits.append(Hit(variant, path, number, allowed))
    return hits


def counted(hits: list[Hit]) -> dict[str, int]:
    tally = Counter(f"{h.variant.concern}/{h.variant.name}" for h in hits if not h.allowed)
    return dict(sorted(tally.items()))


def print_census(hits: list[Hit], depth: int) -> None:
    by_variant: dict[Variant, list[Hit]] = defaultdict(list)
    for hit in hits:
        by_variant[hit.variant].append(hit)
    for concern in CONCERNS:
        variants = [var for var in by_variant if var.concern == concern]
        outside = {var for var in variants if any(not h.allowed for h in by_variant[var])}
        print(f"\n{concern}: {len(outside)} way(s) in use outside the allowed modules")
        for var in sorted(variants, key=lambda x: -len(by_variant[x])):
            modules = Counter(module_of(h.path, depth) for h in by_variant[var] if not h.allowed)
            allowed = sum(h.allowed for h in by_variant[var])
            where = ", ".join(f"{m}: {n}" for m, n in modules.most_common(6))
            note = f"  [allowed: {allowed}]" if allowed else ""
            print(f"  {sum(modules.values()):5d}  {var.name}  ({where or '-'}){note}")


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="*", default=["."])
    ap.add_argument("--allow", action="append", default=[], metavar="GLOB",
                    help="sanctioned module paths (fnmatch); hits there are not counted; repeat for more")
    ap.add_argument("--depth", type=int, default=2, help="path parts that name a module (default 2, e.g. src/orders)")
    ap.add_argument("--baseline", help="JSON from --write-baseline; fail if any count grew")
    ap.add_argument("--write-baseline", help="write current counts to this JSON file and exit 0")
    ap.add_argument("--zero", nargs="*", default=[], help=f"concerns that must have no hits outside --allow: {CONCERNS}")
    ap.add_argument("--exclude", action="append", default=[], metavar="GLOB", help="paths to skip; repeat for more")
    return ap.parse_args()


def gate(current: dict[str, int], args: argparse.Namespace) -> list[str]:
    problems = [f"'{c}' must be zero outside --allow: {k} = {n}"
                for k, n in current.items() for c in args.zero if k.startswith(c + "/")]
    if args.baseline:
        baseline = json.loads(Path(args.baseline).read_text())
        problems += [f"grew vs baseline: {k} = {n} (baseline {baseline.get(k, 0)})"
                     for k, n in current.items() if n > baseline.get(k, 0)]
    return problems


def split_concerns(args: argparse.Namespace) -> None:
    """--zero takes several values, so file names a pre-commit hook appends land there too."""
    strays = [z for z in args.zero if z not in CONCERNS]
    args.zero = [z for z in args.zero if z in CONCERNS]
    if strays:
        args.paths = [p for p in args.paths if p != "."] + strays


def main() -> int:
    args = parse_args()
    split_concerns(args)
    this_file = Path(__file__).resolve()
    files = [f for f in list_files(args.paths, SOURCE_EXTS, args.exclude) if f.resolve() != this_file]
    hits = [h for f in files for h in scan(f, any(fnmatch.fnmatch(f.as_posix(), g) for g in args.allow))]
    current = counted(hits)
    if args.write_baseline:
        Path(args.write_baseline).parent.mkdir(parents=True, exist_ok=True)
        Path(args.write_baseline).write_text(json.dumps(current, indent=2) + "\n")
        print(f"convention_census: baseline with {sum(current.values())} hits written to {args.write_baseline}")
        return 0
    print_census(hits, args.depth)
    problems = gate(current, args)
    for problem in problems:
        print(f"FAIL: {problem}")
    total = sum(current.values())
    print(f"\nconvention_census: {'FAIL' if problems else 'OK'} - {len(files)} files, {total} hits outside --allow")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
