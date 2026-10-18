# Java / Kotlin gates

Java: PMD 7 + CPD for complexity, unused code and duplication, Checkstyle for size, nesting and boolean limits, Error Prone + NullAway with `-Xlint:all -Werror` for types, JaCoCo for coverage, PIT for mutants, ArchUnit for boundaries, jqwik for properties. Kotlin: detekt + ktlint, `allWarningsAsErrors`, Kover, PIT, Konsist. Maven and Gradle (Kotlin DSL) both work for Java; use Gradle for Kotlin. Versions below were current in Oct 2026; build on JDK 21+ (Error Prone 2.43+ requires it).

**Threshold semantics differ.** PMD reports at `>=` level (set level = budget + 1). Checkstyle reports at `>` max (set max = budget). detekt 1.23 reports at `>=` threshold (budget + 1); detekt 2.0 renames keys to `allowedXxx` and uses `>`. Prove each boundary with a 21/22 fixture (SKILL.md A6).

## Tool map

| Gate | Tool (Java / Kotlin) | Setting / rule |
|---|---|---|
| Cyclomatic < 22 | PMD + Checkstyle / detekt | PMD `CyclomaticComplexity` `methodReportLevel=22`; Checkstyle `CyclomaticComplexity` `max=21` / `CyclomaticComplexMethod` `threshold: 22` |
| Cognitive < 22 | PMD / detekt | `CognitiveComplexity` `reportLevel=22` / `CognitiveComplexMethod` `threshold: 22` (inactive by default) |
| Halstead < 80 | none native | `scripts/halstead_gate.py` (per file, multimetric): advisory unless a calibrated `--file-max` is set |
| File < 500 lines | Checkstyle / bundled script | `FileLength` `max=499` / `scripts/loc_budget.py` (detekt has no file-length rule) |
| 100% line + branch | JaCoCo / Kover | `check`: LINE and BRANCH `COVEREDRATIO` 1.00 / `verify`: LINE and BRANCH bounds at 100 |
| CRAP < 25 | bundled script | `complexity_gate.py --coverage target/site/jacoco/jacoco.xml` / `build/reports/kover/report.xml` |
| 0 surviving mutants | PIT / PIT + Arcmutate Kotlin plugin (commercial) | `maxSurviving=0`, not `mutationThreshold` (see Mutation testing) |
| 0 dead code | PMD + Error Prone / detekt | `UnusedPrivateMethod`, `UnusedPrivateField`, `UnusedLocalVariable`, `UnusedFormalParameter`, `UnusedAssignment`, `UnnecessaryImport`, EP `UnusedVariable`/`UnusedMethod` / `UnusedPrivateMember`, `UnusedPrivateProperty`, `UnusedPrivateClass`, `UnusedParameter`, `UnusedImports` (enable) |
| 0 duplication | PMD CPD / CPD or jscpd | `cpd-check` `minimumTokens=100` (Gradle `de.aaschmid.cpd`) / `language = "kotlin"` |
| 0 `any`-style types | javac + Checkstyle + NullAway / kotlinc + detekt | `-Xlint:all -Werror` (rawtypes, unchecked), `IllegalType` bans `Object` / `allWarningsAsErrors` (UNCHECKED_CAST), `UnsafeCallOnNullableType` (`!!`), `UnsafeCast`, `CastToNullableType`; no rule for `Any` |
| ABC ≤ 17 | none | `lizard -T token_count=<n>` as a proxy |
| Function ≤ 50 NLOC | PMD + Checkstyle / detekt | `NcssCount` `methodReportLevel=51`; `MethodLength` `max=50` / `LongMethod` `threshold: 51` |
| Params ≤ 5 | PMD + Checkstyle / detekt | `ExcessiveParameterList` `minimum=6`; `ParameterNumber` `max=5` / `LongParameterList` `functionThreshold: 6` |
| Nesting ≤ 3 | PMD + Checkstyle / detekt | `AvoidDeeplyNestedIfStmts` `problemDepth=4`; `NestedIfDepth` `max=2` (counts from 0) / `NestedBlockDepth` `threshold: 4` |
| Boolean ops ≤ 3 | Checkstyle / detekt | `BooleanExpressionComplexity` `max=3` / `ComplexCondition` `threshold: 5` (counts operators + 1) |
| Comments, commented-out code | bundled script | `comment_density.py --fail-on-commented-code` (no native rule) |
| Suppression ratchet | bundled script + PMD / detekt | `suppression_audit.py`; PMD `UnnecessaryWarningSuppression` / `ForbiddenSuppress` |
| Architecture | ArchUnit / Konsist | `layeredArchitecture()`, `slices().beFreeOfCycles()` / `assertArchitecture { }` |
| Unused deps | Maven dependency plugin / Gradle dependency-analysis | `analyze-only` `failOnWarning=true` / `buildHealth` with `severity("fail")` |
| Test logic, asserts | PMD / none | `UnitTestShouldIncludeAssert` + the `NoLogicInTests` XPath rule below / review |
| TODO ban | Checkstyle / detekt | `TodoComment` / `ForbiddenComment` with a regex |

## Configuration

Layout (Java, Maven; Gradle swaps `pom.xml` + `.mvn/` for `build.gradle.kts`, Kotlin adds `config/detekt/detekt.yml`):

```
pom.xml  .mvn/jvm.config  Makefile  .pre-commit-config.yaml  .quality/suppressions.json
config/pmd/ruleset.xml  config/checkstyle/checkstyle.xml
tools/quality/            # copy of <skill-dir>/scripts/*.py so CI has them
src/main/java/com/example/package-info.java   # @org.jspecify.annotations.NullMarked
src/test/java/com/example/ArchitectureTest.java
```

### config/pmd/ruleset.xml (Java, Maven and Gradle)

```xml
<?xml version="1.0"?>
<ruleset name="gates" xmlns="http://pmd.sourceforge.net/ruleset/2.0.0"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xsi:schemaLocation="http://pmd.sourceforge.net/ruleset/2.0.0 https://pmd.sourceforge.io/ruleset_2_0_0.xsd">
  <description>Quality budgets. PMD reports at value >= level, so level = budget + 1.</description>
  <rule ref="category/java/design.xml/CyclomaticComplexity"><properties><property name="methodReportLevel" value="22"/></properties></rule>
  <rule ref="category/java/design.xml/CognitiveComplexity"><properties><property name="reportLevel" value="22"/></properties></rule>
  <rule ref="category/java/design.xml/NcssCount"><properties><property name="methodReportLevel" value="51"/></properties></rule>
  <rule ref="category/java/design.xml/ExcessiveParameterList"><properties><property name="minimum" value="6"/></properties></rule>
  <!-- reports the if that sits at depth problemDepth, so 4 allows three nested ifs -->
  <rule ref="category/java/design.xml/AvoidDeeplyNestedIfStmts"><properties><property name="problemDepth" value="4"/></properties></rule>
  <rule ref="category/java/design.xml/GodClass"/>
  <rule ref="category/java/design.xml/SimplifyBooleanReturns"/>
  <rule ref="category/java/bestpractices.xml/UnusedPrivateMethod"/>
  <rule ref="category/java/bestpractices.xml/UnusedPrivateField"/>
  <rule ref="category/java/bestpractices.xml/UnusedLocalVariable"/>
  <rule ref="category/java/bestpractices.xml/UnusedAssignment"/>
  <rule ref="category/java/bestpractices.xml/UnusedFormalParameter"><properties><property name="checkAll" value="true"/></properties></rule>
  <rule ref="category/java/bestpractices.xml/UnnecessaryWarningSuppression"/> <!-- since 7.14: unused @SuppressWarnings("PMD...") -->
  <rule ref="category/java/bestpractices.xml/UnitTestShouldIncludeAssert"/>
  <rule ref="category/java/bestpractices.xml/SystemPrintln"/>
  <rule ref="category/java/bestpractices.xml/AvoidPrintStackTrace"/>
  <rule ref="category/java/codestyle.xml/UnnecessaryImport"/>
  <rule ref="category/java/errorprone.xml/EmptyCatchBlock"/>
  <rule name="NoLogicInTests" language="java" message="No branching or loops in a test method; split it or use @ParameterizedTest"
        class="net.sourceforge.pmd.lang.rule.xpath.XPathRule">
    <priority>3</priority>
    <properties><property name="xpath"><value><![CDATA[
//MethodDeclaration[pmd-java:hasAnnotation('org.junit.jupiter.api.Test')]
  //(IfStatement|ForStatement|ForeachStatement|WhileStatement|DoStatement)
    ]]></value></property></properties>
  </rule>
</ruleset>
```

### config/checkstyle/checkstyle.xml (Checkstyle reports at value > max)

```xml
<?xml version="1.0"?>
<!DOCTYPE module PUBLIC "-//Checkstyle//DTD Checkstyle Configuration 1.3//EN" "https://checkstyle.org/dtds/configuration_1_3.dtd">
<module name="Checker">
  <property name="severity" value="error"/>
  <module name="SuppressWarningsFilter"/>
  <module name="FileLength"><property name="max" value="499"/></module>
  <module name="TreeWalker">
    <module name="SuppressWarningsHolder"/>
    <module name="CyclomaticComplexity"><property name="max" value="21"/></module>
    <module name="NPathComplexity"><property name="max" value="200"/></module>
    <module name="MethodLength"><property name="max" value="50"/><property name="countEmpty" value="false"/></module>
    <module name="ParameterNumber"><property name="max" value="5"/><property name="ignoreOverriddenMethods" value="true"/></module>
    <module name="BooleanExpressionComplexity"><property name="max" value="3"/></module>
    <module name="ClassFanOutComplexity"><property name="max" value="20"/></module>
    <!-- top-level if is depth 0, so max=2 allows three nested ifs -->
    <module name="NestedIfDepth"><property name="max" value="2"/></module>
    <module name="NestedForDepth"><property name="max" value="2"/></module>
    <module name="NestedTryDepth"><property name="max" value="1"/></module>
    <module name="UnusedImports"/>
    <module name="UnusedLocalVariable"/>
    <module name="TodoComment"><property name="format" value="(TODO|FIXME|HACK|XXX)"/></module>
    <!-- bans Object as a declared type; setting ignoredMethodNames replaces its defaults -->
    <module name="IllegalType">
      <property name="illegalClassNames" value="Object, java.lang.Object"/>
      <property name="ignoredMethodNames" value="equals"/>
    </module>
  </module>
</module>
```

### .mvn/jvm.config (Maven only; Error Prone on JDK 16+)

```
--add-exports jdk.compiler/com.sun.tools.javac.api=ALL-UNNAMED
--add-exports jdk.compiler/com.sun.tools.javac.file=ALL-UNNAMED
--add-exports jdk.compiler/com.sun.tools.javac.main=ALL-UNNAMED
--add-exports jdk.compiler/com.sun.tools.javac.model=ALL-UNNAMED
--add-exports jdk.compiler/com.sun.tools.javac.parser=ALL-UNNAMED
--add-exports jdk.compiler/com.sun.tools.javac.processing=ALL-UNNAMED
--add-exports jdk.compiler/com.sun.tools.javac.tree=ALL-UNNAMED
--add-exports jdk.compiler/com.sun.tools.javac.util=ALL-UNNAMED
--add-opens jdk.compiler/com.sun.tools.javac.code=ALL-UNNAMED
--add-opens jdk.compiler/com.sun.tools.javac.comp=ALL-UNNAMED
```

### pom.xml (Java, Maven; `<build><plugins>` content plus properties and test deps)

```xml
<properties>
  <maven.compiler.release>21</maven.compiler.release>
  <project.build.sourceEncoding>UTF-8</project.build.sourceEncoding>
  <pmd.version>7.28.0</pmd.version>
</properties>
<dependencies>
  <dependency><groupId>org.jspecify</groupId><artifactId>jspecify</artifactId><version>1.0.1</version></dependency>
  <!-- declare the API you import and the engine you run separately, so dependency:analyze stays exact -->
  <dependency><groupId>org.junit.jupiter</groupId><artifactId>junit-jupiter-api</artifactId><version>5.14.4</version><scope>test</scope></dependency>
  <dependency><groupId>org.junit.jupiter</groupId><artifactId>junit-jupiter-engine</artifactId><version>5.14.4</version><scope>test</scope></dependency>
  <dependency><groupId>org.assertj</groupId><artifactId>assertj-core</artifactId><version>3.27.7</version><scope>test</scope></dependency>
  <dependency><groupId>com.tngtech.archunit</groupId><artifactId>archunit</artifactId><version>1.5.1</version><scope>test</scope></dependency>
  <dependency><groupId>com.tngtech.archunit</groupId><artifactId>archunit-junit5-api</artifactId><version>1.5.1</version><scope>test</scope></dependency>
  <dependency><groupId>com.tngtech.archunit</groupId><artifactId>archunit-junit5-engine</artifactId><version>1.5.1</version><scope>test</scope></dependency>
  <dependency><groupId>net.jqwik</groupId><artifactId>jqwik-api</artifactId><version>1.10.2</version><scope>test</scope></dependency>
  <dependency><groupId>net.jqwik</groupId><artifactId>jqwik-engine</artifactId><version>1.10.2</version><scope>test</scope></dependency>
</dependencies>
<build><plugins>
  <plugin><groupId>com.diffplug.spotless</groupId><artifactId>spotless-maven-plugin</artifactId><version>3.10.4</version>
    <configuration><java><googleJavaFormat/></java></configuration>
    <executions><execution><phase>validate</phase><goals><goal>check</goal></goals></execution></executions></plugin>
  <plugin><groupId>org.apache.maven.plugins</groupId><artifactId>maven-checkstyle-plugin</artifactId><version>3.6.0</version>
    <dependencies><dependency><groupId>com.puppycrawl.tools</groupId><artifactId>checkstyle</artifactId><version>14.3.0</version></dependency></dependencies>
    <configuration><configLocation>config/checkstyle/checkstyle.xml</configLocation><includeTestSourceDirectory>true</includeTestSourceDirectory>
      <consoleOutput>true</consoleOutput><violationSeverity>warning</violationSeverity></configuration>
    <executions><execution><phase>validate</phase><goals><goal>check</goal></goals></execution></executions></plugin>
  <plugin><groupId>org.apache.maven.plugins</groupId><artifactId>maven-compiler-plugin</artifactId><version>3.16.0</version>
    <configuration><compilerArgs>
      <arg>-Xlint:all,-processing</arg> <!-- -processing: javac warns when no processor claims an annotation -->
      <arg>-Werror</arg>
      <arg>-XDcompilePolicy=simple</arg>
      <arg>--should-stop=ifError=FLOW</arg>
      <arg>-Xplugin:ErrorProne -XepDisableWarningsInGeneratedCode -Xep:NullAway:ERROR -XepOpt:NullAway:OnlyNullMarked=true</arg>
      <arg>-XDaddTypeAnnotationsToSymbol=true</arg> <!-- only needed on JDK 21 -->
    </compilerArgs>
    <annotationProcessorPaths>
      <path><groupId>com.google.errorprone</groupId><artifactId>error_prone_core</artifactId><version>2.50.0</version></path>
      <path><groupId>com.uber.nullaway</groupId><artifactId>nullaway</artifactId><version>0.14.2</version></path>
    </annotationProcessorPaths></configuration></plugin>
  <plugin><groupId>org.apache.maven.plugins</groupId><artifactId>maven-surefire-plugin</artifactId><version>3.6.0</version></plugin>
  <plugin><groupId>org.jacoco</groupId><artifactId>jacoco-maven-plugin</artifactId><version>0.8.15</version>
    <executions>
      <execution><id>agent</id><goals><goal>prepare-agent</goal></goals></execution>
      <execution><id>report</id><phase>verify</phase><goals><goal>report</goal></goals></execution>
      <execution><id>check</id><goals><goal>check</goal></goals><configuration><rules><rule><element>BUNDLE</element><limits>
        <limit><counter>LINE</counter><value>COVEREDRATIO</value><minimum>1.00</minimum></limit>
        <limit><counter>BRANCH</counter><value>COVEREDRATIO</value><minimum>1.00</minimum></limit>
      </limits></rule></rules></configuration></execution>
    </executions></plugin>
  <plugin><groupId>org.apache.maven.plugins</groupId><artifactId>maven-pmd-plugin</artifactId><version>3.28.0</version>
    <dependencies> <!-- plugin 3.28.0 defaults to PMD 7.17.0 -->
      <dependency><groupId>net.sourceforge.pmd</groupId><artifactId>pmd-core</artifactId><version>${pmd.version}</version></dependency>
      <dependency><groupId>net.sourceforge.pmd</groupId><artifactId>pmd-java</artifactId><version>${pmd.version}</version></dependency>
    </dependencies>
    <configuration><rulesets><ruleset>config/pmd/ruleset.xml</ruleset></rulesets><includeTests>true</includeTests>
      <minimumTokens>100</minimumTokens><printFailingErrors>true</printFailingErrors><linkXRef>false</linkXRef></configuration>
    <executions><execution><goals><goal>check</goal><goal>cpd-check</goal></goals></execution></executions></plugin>
  <plugin><groupId>org.apache.maven.plugins</groupId><artifactId>maven-dependency-plugin</artifactId><version>3.11.0</version>
    <executions><execution><goals><goal>analyze-only</goal></goals><configuration><failOnWarning>true</failOnWarning>
      <ignoredUnusedDeclaredDependencies> <!-- runtime-only test engines -->
        <param>org.junit.jupiter:junit-jupiter-engine</param><param>com.tngtech.archunit:archunit-junit5-engine</param><param>net.jqwik:jqwik-engine</param>
      </ignoredUnusedDeclaredDependencies></configuration></execution></executions></plugin>
  <plugin><groupId>org.pitest</groupId><artifactId>pitest-maven</artifactId><version>1.30.1</version>
    <dependencies><dependency><groupId>org.pitest</groupId><artifactId>pitest-junit5-plugin</artifactId><version>1.2.3</version></dependency></dependencies>
    <!-- No <targetClasses> here: PIT defaults to ${project.groupId}*, and a pom value would
         override -DtargetClasses, breaking the changed-classes-only run below. -->
    <configuration><mutators><mutator>STRONGER</mutator></mutators>
      <maxSurviving>0</maxSurviving> <!-- counts SURVIVED + NO_COVERAGE -->
      <features><feature>+auto_threads</feature></features><outputFormats><param>XML</param><param>HTML</param></outputFormats>
      <timestampedReports>false</timestampedReports>
      <historyInputFile>${project.basedir}/.pitest/history.bin</historyInputFile><historyOutputFile>${project.basedir}/.pitest/history.bin</historyOutputFile></configuration>
    <executions><execution><goals><goal>mutationCoverage</goal></goals></execution></executions></plugin> <!-- default phase verify -->
</plugins></build>
```

### build.gradle.kts (Java, Gradle 9)

```kotlin
import net.ltgt.gradle.errorprone.CheckSeverity
import net.ltgt.gradle.errorprone.errorprone

plugins {
    java
    checkstyle
    pmd
    jacoco
    id("com.diffplug.spotless") version "8.10.4"
    id("net.ltgt.errorprone") version "5.1.1"          // forks javac with the --add-exports for you
    id("info.solidsoft.pitest") version "1.19.0"
    id("de.aaschmid.cpd") version "3.5"                // verify Gradle 9 compatibility for your version
    id("com.autonomousapps.dependency-analysis") version "3.19.2"
}
java { toolchain { languageVersion = JavaLanguageVersion.of(21) } }
repositories { mavenCentral() }
dependencies {
    implementation("org.jspecify:jspecify:1.0.1")
    errorprone("com.google.errorprone:error_prone_core:2.50.0")
    errorprone("com.uber.nullaway:nullaway:0.14.2")
    testImplementation("org.junit.jupiter:junit-jupiter-api:5.14.4")
    testRuntimeOnly("org.junit.jupiter:junit-jupiter-engine:5.14.4")
    testRuntimeOnly("org.junit.platform:junit-platform-launcher")
    testImplementation("org.assertj:assertj-core:3.27.7")
    testImplementation("com.tngtech.archunit:archunit:1.5.1")
    testImplementation("com.tngtech.archunit:archunit-junit5-api:1.5.1")
    testRuntimeOnly("com.tngtech.archunit:archunit-junit5-engine:1.5.1")
    testImplementation("net.jqwik:jqwik-api:1.10.2")
    testRuntimeOnly("net.jqwik:jqwik-engine:1.10.2")
}
tasks.withType<JavaCompile>().configureEach {
    options.compilerArgs.addAll(listOf("-Xlint:all,-processing", "-Werror"))
    options.errorprone {
        disableWarningsInGeneratedCode = true
        check("NullAway", CheckSeverity.ERROR)
        option("NullAway:OnlyNullMarked", "true")
    }
}
spotless { java { googleJavaFormat() } }
checkstyle { toolVersion = "14.3.0"; maxWarnings = 0 }      // reads config/checkstyle/checkstyle.xml
pmd { toolVersion = "7.24.0"; ruleSets = listOf(); ruleSetFiles = files("config/pmd/ruleset.xml"); isConsoleOutput = true }
cpd { minimumTokenCount = 100; toolVersion = "7.24.0" }      // Gradle 9.8 docs list PMD up to 7.24.0
tasks.test { useJUnitPlatform(); finalizedBy(tasks.jacocoTestReport) }
tasks.jacocoTestReport { reports { xml.required = true } }   // build/reports/jacoco/test/jacocoTestReport.xml
tasks.jacocoTestCoverageVerification {
    violationRules { rule {
        limit { counter = "LINE"; minimum = "1.0".toBigDecimal() }
        limit { counter = "BRANCH"; minimum = "1.0".toBigDecimal() }
    } }
}
tasks.check { dependsOn(tasks.jacocoTestCoverageVerification) } // not wired by default
pitest {
    pitestVersion = "1.30.1"
    junit5PluginVersion = "1.2.3"
    targetClasses = providers.gradleProperty("pitTargets").map { it.split(",").toSet() }.orElse(setOf("com.example.*"))
    mutators = setOf("STRONGER")
    maxSurviving = 0
    outputFormats = setOf("XML", "HTML")
    timestampedReports = false
    historyInputLocation = layout.projectDirectory.file(".pitest/history.bin")
    historyOutputLocation = layout.projectDirectory.file(".pitest/history.bin")
}
dependencyAnalysis { issues { all { onAny { severity("fail") } } } }
```

### build.gradle.kts (Kotlin additions; same pitest and dependencyAnalysis blocks)

```kotlin
plugins {
    kotlin("jvm") version "2.4.21"
    id("io.gitlab.arturbosch.detekt") version "1.23.8"  // built against Kotlin 2.0.21 / Gradle 8.12: verify detektMain on your versions
    id("org.jlleitschuh.gradle.ktlint") version "14.2.0"
    id("org.jetbrains.kotlinx.kover") version "0.9.11"
    // + info.solidsoft.pitest, de.aaschmid.cpd, com.autonomousapps.dependency-analysis as above
}
kotlin { jvmToolchain(21); compilerOptions { allWarningsAsErrors = true; extraWarnings = true } }
dependencies { testImplementation("com.lemonappdev:konsist:0.18.1"); testImplementation("net.jqwik:jqwik-kotlin:1.10.2") }
detekt { buildUponDefaultConfig = true; config.setFrom("config/detekt/detekt.yml"); baseline = file("config/detekt/baseline.xml") }
ktlint { version = "1.8.0" }
kover { reports {
    verify {
        rule("line") { minBound(100) }
        rule("branch") { bound { minValue = 100; coverageUnits = kotlinx.kover.gradle.plugin.dsl.CoverageUnit.BRANCH } }
    }
} }                                                    // total koverVerify runs on `check`
tasks.named<de.aaschmid.gradle.plugins.cpd.Cpd>("cpdCheck") {
    language = "kotlin"; setSource(files("src/main/kotlin", "src/test/kotlin"))
}
```

### config/detekt/detekt.yml (1.23: reported when value >= threshold)

```yaml
build: { maxIssues: 0 }
config: { validation: true, warningsAsErrors: true }
complexity:
  CyclomaticComplexMethod: { active: true, threshold: 22 }
  CognitiveComplexMethod: { active: true, threshold: 22 }
  LongMethod: { active: true, threshold: 51 }            # counts lines with code tokens only
  LongParameterList: { active: true, functionThreshold: 6, constructorThreshold: 6 }
  NestedBlockDepth: { active: true, threshold: 4 }
  ComplexCondition: { active: true, threshold: 5 }       # count = (&& + ||) + 1, so 5 allows 3 operators
  LargeClass: { active: true, threshold: 500 }
style:
  UnusedImports: { active: true }
  ForbiddenComment: { active: true, comments: [ { value: '(?i)\b(TODO|FIXME|HACK|XXX)\b', reason: 'Link an issue or do it now' } ] }
  ForbiddenSuppress: { active: true, rules: [CyclomaticComplexMethod, CognitiveComplexMethod, LongMethod, UNCHECKED_CAST] }
potential-bugs:
  CastToNullableType: { active: true }                   # UnsafeCallOnNullableType/UnsafeCast are on, need detektMain
```

## One command for every gate

`Makefile` at the repo root; hooks, CI and CLAUDE.md all call `make quality`. Vendor the scripts into `tools/quality/` (with `_files.py` and `coverage_formats.py`) and `pip install lizard radon multimetric`.

```make
S := tools/quality
# src/main/kotlin for Kotlin. Keep comments off assignment lines (make keeps the spaces).
SRC := src/main/java
quality-fast:
	./mvnw -B -q validate        # spotless + checkstyle, no compile
	python3 $(S)/loc_budget.py src
	python3 $(S)/comment_density.py src --fail-on-commented-code
	# any-type skips equals(Object o) / equals(other: Any?) lines; IllegalType also covers Java
	python3 $(S)/suppression_audit.py src --zero coverage skipped any-type todo --baseline .quality/suppressions.json
	python3 $(S)/complexity_gate.py $(SRC) --params-max 5 --nloc-max 50
	python3 $(S)/halstead_gate.py $(SRC)
quality: quality-fast
	./mvnw -B verify             # -Werror + Error Prone + NullAway, tests, JaCoCo, PMD, CPD, unused deps, PIT
	python3 $(S)/complexity_gate.py $(SRC) --coverage target/site/jacoco/jacoco.xml
.PHONY: quality quality-fast
```

Gradle: `quality-fast` runs `./gradlew -q spotlessCheck checkstyleMain checkstyleTest` (Kotlin: `ktlintCheck detekt`), and `quality` runs `./gradlew pmdMain pmdTest cpdCheck test jacocoTestCoverageVerification buildHealth pitest` (Kotlin: `detektMain detektTest cpdCheck test koverVerify koverXmlReport buildHealth pitest`; only `detektMain`/`detektTest` run type-resolution rules such as `!!`). In ratchet mode add `--baseline .quality/suppressions.json` to the audit line.

## Coverage report for CRAP

- Maven: `./mvnw verify` writes `target/site/jacoco/jacoco.xml`.
- Gradle Java: `./gradlew test jacocoTestReport` writes `build/reports/jacoco/test/jacocoTestReport.xml`.
- Kotlin: `./gradlew koverXmlReport` writes `build/reports/kover/report.xml` (JaCoCo format).

Then `python <skill-dir>/scripts/complexity_gate.py src/main/java --coverage target/site/jacoco/jacoco.xml --top 20`.

## Mutation testing

- **Fail on any survivor with `maxSurviving=0`.** `mutationThreshold` is an integer percentage that rounds by default (`thresholdPrecision=0`), so `mutationThreshold=100` passes at 99.6%. `maxSurviving` counts total minus detected, so NO_COVERAGE mutants count too.
- **Incremental:** `historyInputFile`/`historyOutputFile` (Gradle `historyInputLocation`/`historyOutputLocation`, or `enableDefaultIncrementalAnalysis = true`) reuse earlier results; cache `.pitest/` in CI. `scmMutationCoverage` was removed from pitest-maven (warned in 1.17.1), so restrict to changed classes yourself:
  ```bash
  T=$(git diff --name-only origin/main...HEAD -- 'src/main/java/*.java' | sed -e 's#src/main/java/##' -e 's#\.java$#*#' -e 's#/#.#g' | paste -sd, -)
  [ -z "$T" ] || ./mvnw -B test-compile org.pitest:pitest-maven:mutationCoverage -DtargetClasses="$T"   # Gradle: ./gradlew pitest -PpitTargets="$T"
  ```
  The trailing `*` keeps inner classes in scope. This works only because the pom sets no `<targetClasses>` (a pom value beats `-D`).
- **Read survivors:** `target/pit-reports/index.html` (Gradle `build/reports/pitest/`) colours each line; `mutations.xml` lists `status="SURVIVED"` / `"NO_COVERAGE"` with the mutator and line.
- **Equivalent mutants:** PIT's `FANN` feature (on by default) skips classes and methods carrying any annotation whose simple name is `Generated`, `DoNotMutate` or `CoverageIgnore` with CLASS or RUNTIME retention. PIT ships no such annotation; define one with a mandatory reason. It is method-granular, so extract the equivalent line into its own small method first. `suppression_audit.py` counts it under `mutation`, so each new one raises the baseline and needs the user's approval. Never name it `*Generated*`: JaCoCo also drops such methods from coverage.
  ```java
  @Retention(RetentionPolicy.CLASS) @Target({ElementType.METHOD, ElementType.TYPE})
  public @interface DoNotMutate { String reason(); }
  ```
- **Kotlin:** stock PIT mutates compiler-generated bytecode (null-check intrinsics, coroutine state machines, `when` on sealed types, inlined code), producing junk survivors. The Arcmutate plugin (`pitest("com.arcmutate:pitest-kotlin-plugin:<ver>")`, licence file `arcmutate-licence.txt`) filters them. Without it, 0 survivors is not realistic; tell the user before promising the gate.
- **Runtime:** roughly (number of mutants) × (tests covering each), so whole-project runs take minutes to hours. Run changed classes in pre-push/PR and a full run nightly.

## Killing untyped escape hatches

- Java: `-Xlint:all -Werror` fails on raw types and unchecked casts. Checkstyle `IllegalType` bans `Object` in declarations, generics included. NullAway with `@NullMarked` makes nullness part of the type. Do not answer an unchecked warning with `@SuppressWarnings("unchecked")`; the audit counts every one.
- Kotlin: `allWarningsAsErrors` fails on `UNCHECKED_CAST`, and `ForbiddenSuppress` stops it being suppressed. detekt flags `!!` and unsafe casts. Nothing flags `Any`; `suppression_audit.py` counts `: Any`.
- **Boundary pattern:** deserialize once into a `record` (Java) or `data class` (Kotlin) with Jackson/kotlinx.serialization, validate in the compact constructor or `init`, and pass only that type inward. Unknown JSON shapes become a sealed hierarchy, not a `Map<String, Object>`.
- **Do not replace** `Object` with `Map<String, Object>`, `JsonNode` passed around, `<T> T` unconstrained generics, `Any?`, or `lateinit` + `!!` to silence nullness.

## Language-specific slop to hunt

- `Optional` used as a field or parameter, or `Optional.ofNullable(x).isPresent()` in place of a null check: use `@Nullable` + NullAway, or return `Optional` only.
- `catch (Exception e) { log.error(...); }` or `return null`: catch the specific exception or let it propagate; PMD `AvoidCatchingGenericException` if you want it machine-checked.
- Interface + single `Impl` with no second implementation or test double: inline the interface.
- Builders, factories and `Utils` classes wrapping one constructor or one stdlib call (`StringUtils.isEmpty` reimplemented): delete.
- Javadoc that restates the signature (`@param id the id`): delete; `comment_density.py` flags narration.
- Defensive `Objects.requireNonNull` on every parameter of `@NullMarked` code: NullAway already proves it.
- Kotlin: `?.let { } ?: run { }` chains, `!!` after a null check, `companion object` holding unrelated helpers, `data class` with `var`s, `runBlocking` inside suspend code.
- Mockito-heavy tests that verify call order instead of outcomes: assert on returned values or state.

## Invariants

Rungs: records with validating compact constructors and private constructors behind static factories; `sealed interface` + records for closed state sets with exhaustive `switch`/`when` (no `default`); ArchUnit/Konsist rules; banned APIs via ArchUnit `noClasses().should().callMethod(...)` or detekt `ForbiddenMethodCall`; jqwik / Kotest properties; for protocols, TLA+ or JML/OpenJML (see `invariants.md`).

```java
@AnalyzeClasses(packages = "com.example", importOptions = ImportOption.DoNotIncludeTests.class)
class ArchitectureTest {
  @ArchTest static final ArchRule onlyAuthWritesUsers = noClasses()
      .that().resideOutsideOfPackage("..auth..")
      .should().callMethod(UserRepository.class, "insert", User.class)
      .because("INV-1: a user row exists only after authentication");
  @ArchTest static final ArchRule noCycles = slices().matching("com.example.(*)..").should().beFreeOfCycles();
}
```
Kotlin: `Konsist.scopeFromProduction().assertArchitecture { val domain = Layer("Domain", "com.example.domain.."); val data = Layer("Data", "com.example.data.."); domain.dependsOnNothing(); data.dependsOn(domain) }`. `dependsOn` alone forbids nothing; add `doesNotDependOn(...)` for forbidden edges. Property test: `@Property void roundTrips(@ForAll("orders") Order o) { assertThat(parse(render(o))).isEqualTo(o); }`.

## Ratchets for legacy code

- detekt: `./gradlew detektBaseline` writes `config/detekt/baseline.xml`; entries may only be removed.
- PMD/Checkstyle: no native baseline. PMD `excludeFromFailureFile` (Maven) or Checkstyle `SuppressionFilter` with a generated `suppressions.xml`, both ratcheted by line count in CI; ktlint `--baseline=ktlint-baseline.xml`; ArchUnit `FreezingArchRule.freeze(rule)` with `freeze.store.default.allowStoreCreation=true` set once.
- Coverage: JaCoCo/Kover check on the whole bundle cannot ratchet per line. Use diff coverage on the JaCoCo XML (`pip install diff-cover`; `diff-cover target/site/jacoco/jacoco.xml --compare-branch=origin/main --fail-under=100`) and leave the global floor at today's value, raised as it grows.
- Mutation: PIT on changed classes only (script above).

## Pre-commit wiring

`.pre-commit-config.yaml` (fast gates on commit, `make quality` on push):

```yaml
repos:
  - repo: local
    hooks:
      - id: jvm-fast-gates
        name: format, lint, budgets, suppressions
        language: system
        pass_filenames: false
        files: \.(java|kt|kts)$
        entry: make quality-fast
      - id: quality
        name: all gates
        language: system
        pass_filenames: false
        stages: [pre-push]
        entry: make quality
```
Install with `pre-commit install && pre-commit install --hook-type pre-push`.
