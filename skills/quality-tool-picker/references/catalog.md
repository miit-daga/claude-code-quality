# Seed catalog of candidates

A starting list of well-known options per slot, written in October 2026. **Verify every
entry on the web before recommending it.** Tools get deprecated, forked and replaced, and
newer options may be missing from this list.

## Formatters and style guides

| Language | Candidates |
|---|---|
| Java | google-java-format (Google style), palantir-java-format, Eclipse formatter XML; usually run through Spotless (Maven/Gradle) |
| Kotlin | ktlint (with the Android or official style), ktfmt (Google, Meta or KotlinLang style) |
| Python | ruff format, black |
| TypeScript / JS | Prettier, Biome, dprint |
| Go | gofmt, gofumpt, goimports |
| C# | `dotnet format` with `.editorconfig`, CSharpier |
| PHP | PHP-CS-Fixer, PHP_CodeSniffer (PSR-12 or PER-CS rule sets), Laravel Pint |
| Ruby | Standard, RuboCop with a shared config |
| Rust | rustfmt |
| C / C++ | clang-format (Google, LLVM, Chromium, Mozilla or WebKit base style) |
| Swift | swift-format (Apple), SwiftFormat (Nick Lockwood) |
| Scala | scalafmt |

## Linters and presets

| Language | Candidates |
|---|---|
| Java | Checkstyle (google_checks or sun_checks base), PMD, SpotBugs, Error Prone, SonarLint/SonarQube |
| Kotlin | detekt, ktlint, Android Lint |
| Python | ruff, pylint, flake8 plus plugins |
| TypeScript / JS | ESLint with typescript-eslint, Biome, Oxlint, Ultracite (Biome-based preset) |
| Go | golangci-lint (choose a preset), staticcheck |
| C# | Roslyn analyzers, SonarAnalyzer.CSharp, Roslynator |
| PHP | PHPStan, Psalm, PHPMD |
| Ruby | RuboCop, Standard, reek |
| Rust | clippy |
| C / C++ | clang-tidy, cppcheck |

## Type checkers

Python: mypy, pyright, basedpyright. Ruby: Sorbet, Steep (RBS). PHP: PHPStan, Psalm.

## Test runners, coverage and mutation testing

| Language | Test runner | Coverage | Mutation |
|---|---|---|---|
| Java / Kotlin | JUnit 5, Kotest | JaCoCo, Kover | PIT (pitest) |
| Python | pytest | coverage.py | mutmut, cosmic-ray |
| TypeScript / JS | Vitest, Jest, node:test | V8 or Istanbul via the runner | StrykerJS |
| Go | go test | go cover, go-test-coverage | gremlins, go-mutesting, ooze |
| C# | xUnit, NUnit, MSTest | coverlet, dotnet-coverage | Stryker.NET |
| PHP | PHPUnit, Pest | PHPUnit with Xdebug or PCOV | Infection, `pest --mutate` |
| Ruby | RSpec, Minitest | SimpleCov | mutant |
| Rust | cargo test, cargo-nextest | cargo-llvm-cov, cargo-tarpaulin | cargo-mutants |

## Cross-cutting libraries

| Language | HTTP client | Retries / resilience | Logging |
|---|---|---|---|
| Java | java.net.http.HttpClient, Spring RestClient / WebClient, OkHttp, Feign | Resilience4j, Spring Retry, Failsafe | SLF4J with Logback or Log4j2 |
| Kotlin | Ktor client, OkHttp, Spring clients | Resilience4j, Arrow resilience | SLF4J, kotlin-logging |
| Python | httpx, requests, aiohttp | tenacity, stamina, backoff | stdlib logging with a JSON formatter, structlog, loguru |
| TypeScript / JS | fetch / undici, ky, got, axios | p-retry, cockatiel, opossum | pino, winston |
| Go | net/http, resty | hashicorp/go-retryablehttp, cenkalti/backoff, failsafe-go | log/slog, zap, zerolog |
| C# | HttpClient via IHttpClientFactory, Refit | Polly, Microsoft.Extensions.Http.Resilience | Microsoft.Extensions.Logging, Serilog |
| PHP | Guzzle, Symfony HttpClient | Guzzle retry middleware, Symfony RetryableHttpClient | Monolog |
| Ruby | Faraday, Net::HTTP, HTTP.rb | faraday-retry, retriable | Rails.logger, semantic_logger, Lograge |
| Rust | reqwest, hyper | reqwest-retry, backoff, tower retry | tracing, log |

## Observability

OpenTelemetry SDKs exist for all of the languages above, and are usually the default
choice for traces and metrics unless the org has standardised on a vendor agent.
