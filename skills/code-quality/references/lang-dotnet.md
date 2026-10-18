# C# / .NET gates

Roslyn does most of the work at build time: `AnalysisMode=All`, nullable reference types and `TreatWarningsAsErrors` turn the CA, IDE, SonarAnalyzer.CSharp, BannedApiAnalyzers and ReferenceTrimmer rules into compile errors. coverlet enforces coverage, Stryker.NET mutants, ArchUnitNET boundaries, and jscpd plus the bundled scripts cover duplication, Halstead, file length and comments. Versions below were current in Oct 2026 (.NET 10 SDK).

**Threshold semantics:** CA1502/CA1506 and every Sonar rule here fire at value `>` setting, so set the budget itself (21, not 22). CA1505 fires when maintainability index `<` setting. Prove each boundary with a 21/22 fixture (SKILL.md A6).

## Tool map

| Gate | Tool | Setting / rule |
|---|---|---|
| Cyclomatic < 22 | CA1502 + Sonar S1541 | `CodeMetricsConfig.txt`: `CA1502(Method): 21`; SonarLint.xml `maximumFunctionComplexityThreshold=21` |
| Cognitive < 22 | Sonar S3776 | `threshold=21` (off by default in the NuGet package; enable it) |
| Halstead < 80 | none native | `scripts/halstead_gate.py` (per file, multimetric) |
| File < 500 lines | `scripts/loc_budget.py` (physical lines); Sonar S104 | S104 counts code lines only: `maximumFileLocThreshold=499` as a second check |
| 100% line + branch | coverlet.msbuild | `/p:Threshold=100 /p:ThresholdType=\"line,branch,method\" /p:ThresholdStat=total` |
| CRAP < 25 | `scripts/complexity_gate.py` | `--coverage coverage/coverage.cobertura.xml` |
| 0 surviving mutants | Stryker.NET | `thresholds: {high:100, low:100, break:100}` (counts NoCoverage as undetected) |
| 0 dead code | IDE0051, IDE0052, IDE0060, IDE0005; Sonar S1144, S1172; CA1812 (in `All`) | severity `error` in `.editorconfig`; IDE rules need `EnforceCodeStyleInBuild` |
| 0 duplication | jscpd (no clone detector in the NuGet analyzers; Sonar CPD is server-side only) | `npx jscpd src --format csharp --threshold 0` |
| 0 `any`-style types | `<Nullable>enable` + warnings as errors; Nullable.Extended.Analyzer for `!`; `suppression_audit.py` for `dynamic` | no analyzer bans `dynamic` or `object` parameters; review those |
| ABC ≤ 17 | none | `lizard -l csharp -T token_count=<n>` as a proxy |
| Function ≤ 50 NLOC | Sonar S138 | `max=50` |
| Params ≤ 5 | Sonar S107 | `max=5` (off by default; enable) |
| Nesting ≤ 3 | Sonar S134 | `maximumNestingLevel=3` |
| Boolean ops ≤ 3 | Sonar S1067 | `max=3` |
| Coupling | CA1506 | defaults 95 (types) / 40 (members) |
| Comments | Sonar S125 (commented-out code); `scripts/comment_density.py` | |
| Suppression ratchet | `scripts/suppression_audit.py` | counts `#pragma warning disable`, `SuppressMessage`, `ExcludeFromCodeCoverage`, `Stryker disable`, `[Ignore]`/`Skip=` |
| Architecture | ArchUnitNET (`TngTech.ArchUnitNET.xUnit`); NetArchTest.Rules is unmaintained since 2021 (fork: NetArchTest.eNhancedEdition) | rules in a test project |
| Banned APIs | `Microsoft.CodeAnalysis.BannedApiAnalyzers`, RS0030 | `BannedSymbols.txt` |
| Unused deps | ReferenceTrimmer | RT0001/RT0002/RT0003 |
| Tests assert | Sonar S2699 | no native "no logic in tests" rule; review |
| TODO ban | Sonar S1135 (TODO), S1134 (FIXME) | default Info: raise to `error` |

## Configuration

### Layout and bootstrap (new project)

```bash
dotnet new sln -n App
dotnet new classlib -o src/App
dotnet new xunit -o tests/App.Tests
dotnet sln add src/App tests/App.Tests
dotnet add tests/App.Tests reference src/App
dotnet add tests/App.Tests package coverlet.msbuild
dotnet add tests/App.Tests package TngTech.ArchUnitNET.xUnit
dotnet add tests/App.Tests package CsCheck
dotnet new tool-manifest && dotnet tool install dotnet-stryker
```

```
App.sln  Directory.Build.props  .editorconfig  CodeMetricsConfig.txt  SonarLint.xml  BannedSymbols.txt
Makefile  .pre-commit-config.yaml  .config/dotnet-tools.json  tools/quality/ (vendored scripts)
src/App/  tests/App.Tests/ (stryker-config.json here)
```

### Directory.Build.props (applies to every project below it)

```xml
<Project>
  <PropertyGroup>
    <Nullable>enable</Nullable>
    <TreatWarningsAsErrors>true</TreatWarningsAsErrors>
    <AnalysisMode>All</AnalysisMode>                       <!-- still leaves CA1502/1505/1506 off: enabled by ID below -->
    <EnforceCodeStyleInBuild>true</EnforceCodeStyleInBuild>  <!-- IDE rules run in dotnet build -->
    <GenerateDocumentationFile>true</GenerateDocumentationFile> <!-- IDE0005 and ReferenceTrimmer need it -->
    <NoWarn>$(NoWarn);CS1591</NoWarn>                      <!-- the doc file is a tool input, not a mandate to document every member -->
  </PropertyGroup>
  <ItemGroup>
    <PackageReference Include="SonarAnalyzer.CSharp" Version="10.35.0.4138" PrivateAssets="all" />
    <PackageReference Include="Microsoft.CodeAnalysis.BannedApiAnalyzers" Version="5.6.0" PrivateAssets="all" />
    <PackageReference Include="ReferenceTrimmer" Version="3.5.13" PrivateAssets="all" />
    <PackageReference Include="Nullable.Extended.Analyzer" Version="1.16.6891" PrivateAssets="all" />
    <AdditionalFiles Include="$(MSBuildThisFileDirectory)CodeMetricsConfig.txt" />
    <AdditionalFiles Include="$(MSBuildThisFileDirectory)SonarLint.xml" />
    <AdditionalFiles Include="$(MSBuildThisFileDirectory)BannedSymbols.txt" />
  </ItemGroup>
</Project>
```

`AnalysisLevel` wins over `AnalysisMode` if both are set (`latest-all` is the one-property equivalent). With either property enabling rules, bulk `dotnet_analyzer_diagnostic.category-*.severity` lines are ignored, so configure by rule ID.

### CodeMetricsConfig.txt

```
# 'RuleId'(Optional 'SymbolKind'): 'Threshold'. Fires when value > threshold. A malformed line raises CA1509.
# Always qualify with (Method): once any other CA1502 line exists, an unqualified one is ignored and methods fall back to 25.
CA1502(Method): 21
```

### SonarLint.xml (rule parameters for the NuGet analyzer; looked up by exact file name)

```xml
<?xml version="1.0" encoding="utf-8"?>
<AnalysisInput>
  <Settings/>
  <Rules>
    <Rule><Key>S3776</Key><Parameters><Parameter><Key>threshold</Key><Value>21</Value></Parameter>
      <Parameter><Key>propertyThreshold</Key><Value>3</Value></Parameter></Parameters></Rule>
    <Rule><Key>S1541</Key><Parameters><Parameter><Key>maximumFunctionComplexityThreshold</Key><Value>21</Value></Parameter></Parameters></Rule>
    <Rule><Key>S138</Key><Parameters><Parameter><Key>max</Key><Value>50</Value></Parameter></Parameters></Rule>
    <Rule><Key>S104</Key><Parameters><Parameter><Key>maximumFileLocThreshold</Key><Value>499</Value></Parameter></Parameters></Rule>
    <Rule><Key>S107</Key><Parameters><Parameter><Key>max</Key><Value>5</Value></Parameter></Parameters></Rule>
    <Rule><Key>S1067</Key><Parameters><Parameter><Key>max</Key><Value>3</Value></Parameter></Parameters></Rule>
    <Rule><Key>S134</Key><Parameters><Parameter><Key>maximumNestingLevel</Key><Value>3</Value></Parameter></Parameters></Rule>
  </Rules>
</AnalysisInput>
```

An unparsable SonarLint.xml makes the analyzer throw, so a typo fails loudly. Rule keys are bare (`S3776`, not `csharpsquid:S3776`).

### .editorconfig (severities; `error` because the build already treats warnings as errors)

```ini
root = true

[*.cs]
dotnet_diagnostic.CA1502.severity = error
dotnet_diagnostic.CA1505.severity = error
dotnet_diagnostic.CA1506.severity = error
# unused code; IDE0051 is in category CodeQuality, so a Style category line would not reach it
dotnet_diagnostic.IDE0005.severity = error
dotnet_diagnostic.IDE0051.severity = error
dotnet_diagnostic.IDE0052.severity = error
dotnet_diagnostic.IDE0060.severity = error
dotnet_code_quality_unused_parameters = all
# Sonar: S3776 and S107 are off in the NuGet package; S1541/S138/S104/S134/S1067 are outside Sonar way
dotnet_diagnostic.S3776.severity = error
dotnet_diagnostic.S1541.severity = error
dotnet_diagnostic.S138.severity = error
dotnet_diagnostic.S104.severity = error
dotnet_diagnostic.S107.severity = error
dotnet_diagnostic.S1067.severity = error
dotnet_diagnostic.S134.severity = error
dotnet_diagnostic.S1144.severity = error
dotnet_diagnostic.S1172.severity = error
dotnet_diagnostic.S125.severity = error
dotnet_diagnostic.S1134.severity = error
dotnet_diagnostic.S1135.severity = error
dotnet_diagnostic.S2699.severity = error
dotnet_diagnostic.RS0030.severity = error

[tests/**.cs]
dotnet_diagnostic.CA1707.severity = none   # test method names use underscores
```

`AnalysisMode=All` also enables noisy rules (CA2007 ConfigureAwait in apps, CA1303 literal strings). Turn one off only by ID, with a one-line reason above it, and report it.

### BannedSymbols.txt (`{DocCommentId}[;message]`)

```
P:System.DateTime.Now;Inject TimeProvider and call GetUtcNow()
P:System.DateTime.UtcNow;Inject TimeProvider and call GetUtcNow()
M:System.Console.WriteLine(System.String);Use ILogger
T:Newtonsoft.Json.Linq.JObject;Deserialize into a record at the boundary
```

### tests/App.Tests/stryker-config.json

```json
{
  "stryker-config": {
    "project": "App.csproj",
    "reporters": ["html", "json", "progress", "cleartext"],
    "thresholds": { "high": 100, "low": 100, "break": 100 },
    "since": { "enabled": false, "target": "main" }
  }
}
```

`break` must be ≤ `low` ≤ `high`, hence all three at 100. Stryker exits 1 when the score is below `break`. The score is detected ÷ valid, and NoCoverage counts as undetected, so one survivor or one uncovered mutant fails the run.

## One command for every gate

```make
S := tools/quality
SRC := src
COV := /p:CollectCoverage=true /p:CoverletOutputFormat=cobertura /p:CoverletOutput=$(CURDIR)/coverage/ \
       /p:Threshold=100 /p:ThresholdType=\"line,branch,method\" /p:ThresholdStat=total
quality-fast:
	dotnet format --verify-no-changes
	python3 $(S)/loc_budget.py src tests
	python3 $(S)/comment_density.py $(SRC) --fail-on-commented-code
	# mutation left out: equivalent-mutant comments are allowed, each named and reported; ratchet with --baseline
	python3 $(S)/suppression_audit.py src tests --zero coverage skipped any-type todo
	python3 $(S)/complexity_gate.py $(SRC) --params-max 5 --nloc-max 50
	python3 $(S)/halstead_gate.py $(SRC)
	npx --yes jscpd $(SRC) --format csharp --threshold 0
quality: quality-fast
	dotnet build --no-incremental        # CA, IDE, Sonar, RS0030, RT, nullable: all errors
	dotnet test --no-build $(COV)        # fails below 100% line, branch, method
	python3 $(S)/complexity_gate.py $(SRC) --coverage coverage/coverage.cobertura.xml
	cd tests/App.Tests && dotnet stryker --since:main   # full run nightly: drop --since
.PHONY: quality quality-fast
```

Vendor the scripts into `tools/quality/` and `pip install lizard radon multimetric`. With several test projects each writes its own coverage file; use one test project per solution or merge (coverlet `MergeWith`, or `dotnet-coverage merge`).

## Coverage report for CRAP

- coverlet.msbuild (above): `coverage/coverage.cobertura.xml`.
- coverlet.collector (template default, no thresholds): `dotnet test --collect:"XPlat Code Coverage"` writes `TestResults/<guid>/coverage.cobertura.xml`.
- dotnet-coverage: `dotnet-coverage collect -f cobertura -o coverage.cobertura.xml dotnet test` (no threshold option).

Then `python <skill-dir>/scripts/complexity_gate.py src --coverage coverage/coverage.cobertura.xml --top 20`.

## Mutation testing

- **Install:** `dotnet new tool-manifest && dotnet tool install dotnet-stryker`; run `dotnet stryker` from the test project folder (it finds `stryker-config.json` there).
- **Changed code:** `dotnet stryker --since:main` mutates only files changed against `main` (needs git history; in CI fetch with depth 0). `--with-baseline:main` also reuses the stored report of the target branch (`baseline.provider`: Disk, Dashboard, AzureFileStorage, S3); it is mutually exclusive with `--since`.
- **Read survivors:** the `cleartext` reporter prints them; the HTML report is `StrykerOutput/<date-time>/reports/mutation-report.html`, filterable by status (Survived, NoCoverage).
- **Equivalent mutants:** a comment on the line above, naming the mutator and the reason:
  ```csharp
  // Stryker disable once Equality : boundary is unreachable, Parse rejects length 0
  if (items.Count >= 1) { ... }
  ```
  Grammar: `Stryker disable|restore [once] all|<Mutator,...> [: reason]`. Never use `disable all` without `once`, and never `all` when one mutator is meant. `[ExcludeFromCodeCoverage]` also hides a member from Stryker, so it dodges two gates at once; the audit counts both.
- **Runtime:** Stryker compiles all mutants into one assembly (mutant schemata) and runs only covering tests (`coverage-analysis: perTest`), so small projects take minutes. Run `--since` on PRs and a full run nightly.
- **CI:** the non-zero exit from `break: 100` fails the job; publish the HTML report as an artifact.

## Killing untyped escape hatches

- `<Nullable>enable</Nullable>` + `TreatWarningsAsErrors` makes every CS86xx nullable warning an error. The null-forgiving `!` silences them; Nullable.Extended.Analyzer reports each `!` (NX0001–NX0004) unless it carries the package's justification comment.
- `dynamic`: no analyzer rule; `suppression_audit.py --zero any-type` fails on it. `object` parameters, `Dictionary<string, object>`, `JsonElement`/`JObject` passed inward: no rule; ban the JSON DOM types in `BannedSymbols.txt` outside the boundary project, review the rest.
- **Boundary pattern:** `JsonSerializer.Deserialize<OrderDto>(json, options)` once (`RespectRequiredConstructorParameters` / `required` members), validate, map to a domain type, and pass only that inward.
- **Do not replace** `dynamic` with `object` + casts, `ExpandoObject`, `IDictionary<string, object?>`, pattern-matching on `object` scattered through the code, or `default!` to satisfy nullable warnings.

## Language-specific slop to hunt

- `catch (Exception ex) { _logger.LogError(ex, ...); }` that swallows, or `throw ex;` (loses the stack): catch specific types, rethrow with `throw;`.
- An `IFooService` for every `FooService` with one implementation and no test double: drop the interface.
- `async` methods that only `return await` one call, `Task.Run` wrapping synchronous code in ASP.NET, `.Result`/`.Wait()`.
- `ArgumentNullException.ThrowIfNull` on non-nullable parameters inside internal code: the compiler already checks.
- `/// <summary>Gets the name.</summary>` on `Name`: delete.
- Hand-rolled loops that rebuild LINQ (`Any`, `ToDictionary`, `GroupBy`), or LINQ chains so long nobody can read them.
- `record` types with `init` setters plus constructor validation: `with` expressions bypass the validation. Use get-only properties or validate in the property `init`.
- `#region` blocks hiding a 900-line class: split the class.

## Invariants

Rungs: `sealed record` with a private constructor and a static `Parse`/`Create` that returns or throws; get-only properties so `with` cannot skip validation; closed hierarchies as `abstract record` + nested `sealed record` cases with exhaustive `switch` expressions; `required` members; ArchUnitNET rules; banned APIs (RS0030); CsCheck/FsCheck properties; Dafny (`dafny translate cs` or `dafny build --target:cs`) for algorithms that must be proven (see `invariants.md`).

```csharp
public sealed record Email
{
    public string Value { get; }                              // no init: `with` cannot bypass Parse
    private Email(string value) => Value = value;
    public static Email Parse(string raw) =>
        MailAddress.TryCreate(raw, out var a) ? new Email(a.Address) : throw new FormatException("invalid email");
}

public class ArchitectureTests
{
    static readonly Architecture Arch = new ArchLoader().LoadAssemblies(typeof(Email).Assembly).Build();
    [Fact] public void Domain_does_not_touch_infrastructure() =>
        Types().That().ResideInNamespace("App.Domain").Should()
            .NotDependOnAny(Types().That().ResideInNamespace("App.Infrastructure")).Check(Arch);
    [Fact] public void Parse_keeps_valid_addresses() =>
        Gen.Select(Gen.String[Gen.Char.AlphaNumeric, 1, 10], Gen.String[Gen.Char.AlphaNumeric, 1, 10], (u, d) => $"{u}@{d}.com")
           .Sample(s => Email.Parse(s).Value == s);
}
```
(`using ArchUnitNET.Domain; using ArchUnitNET.Loader; using ArchUnitNET.xUnit; using static ArchUnitNET.Fluent.ArchRuleDefinition; using CsCheck;`)

## Ratchets for legacy code

- Roslyn has no baseline file. Raise rules to `error` globally and add `[legacy/**.cs]` sections that lower named rules to `warning`; the section list may only shrink. Never `NoWarn` a gate rule project-wide.
- `suppression_audit.py --write-baseline .quality/suppressions.json`, then `--baseline` in the audit line.
- Sonar "new code" gating needs SonarQube/SonarCloud; the NuGet analyzer has no equivalent.
- Coverage: `diff-cover coverage/coverage.cobertura.xml --compare-branch=origin/main --fail-under=100`, with the global coverlet `Threshold` at today's value.
- Mutation: `dotnet stryker --since:main` or `--with-baseline:main`. Duplication: `npx jscpd src --baseline-from-ref origin/main --fail-on-new-clones 0`.

## Pre-commit wiring

```yaml
repos:
  - repo: local
    hooks:
      - id: dotnet-fast-gates
        name: format, budgets, suppressions, duplication
        language: system
        pass_filenames: false
        files: \.(cs|csproj|props|editorconfig)$
        entry: make quality-fast
      - id: quality
        name: all gates
        language: system
        pass_filenames: false
        stages: [pre-push]
        entry: make quality
```
Install with `pre-commit install && pre-commit install --hook-type pre-push`. Analyzer errors surface on `dotnet build`, so the PostToolUse hook should run `dotnet build --no-restore` on the edited project.
