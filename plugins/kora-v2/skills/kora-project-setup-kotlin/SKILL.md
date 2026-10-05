---
name: kora-project-setup-kotlin
description: "Scaffold a new Kotlin Kora 2.x service (Gradle Kotlin DSL) — KSP io.koraframework:symbol-processors, the io.koraframework:kora-bom platform, @KoraApp + generated ApplicationGraph, Kotlin 2.4.20 / KSP 2.3.12, JDK 25 toolchain, Gradle wrapper. Use when starting a Kotlin Kora project, wiring build.gradle.kts or KSP, or fixing \"ApplicationGraph unresolved\" and KspTask no longer resolving. For Java see kora-project-setup-java."
license: Apache-2.0
metadata:
  kora-version: "2.x"
---

# Kora Project Setup — Kotlin

> **Kora sub-skill — obey the [kora-v2 meta rules](../../SKILL.md) on every task:** **R0** ground the workspace on Kora 2.0 refs before starting (framework source at tag `2.0.0.RC2` + `kora-examples` at `migration/2.0` + Kora 2.0 docs at koraframework.io/v2, which trail the source; 1.x `kora-docs` pages are never an authority) · **R1** read this sub-skill before writing code · **R2** Kora 2.0 APIs only — no Spring/Micronaut/Quarkus, no Kora 1.x APIs, no invented annotations or config keys · **R3** journal any incorrect Kora usage. Add comments/Javadoc only if asked.

Scaffold a runnable Kotlin Kora 2.x service: Gradle Kotlin DSL build, KSP symbol
processors, the `io.koraframework:kora-bom` platform, and a `@KoraApp` interface
that plugs in Kora capabilities by extending `*Module` interfaces.

## Pinned versions

| What | Value | Why this exact value |
|---|---|---|
| Kora | `2.0.0.RC2` (property `koraVersion`) | the current `2.0.x` release of `io.koraframework:kora-bom` on Maven Central; resolves from plain `mavenCentral()` |
| groupId | `io.koraframework` | was `ru.tinkoff.kora` in 1.x |
| BOM | `io.koraframework:kora-bom` | was `ru.tinkoff.kora:kora-parent` |
| Kotlin | `2.4.20` | the version Kora 2.0 itself is built with |
| KSP | `2.3.12` | ditto — see [version drift](#version-drift-is-not-cosmetic) |
| JVM toolchain | `25` | bytecode floor of Kora 2.0 artifacts; see [JDK](#jdk-choice) |
| Gradle wrapper | `9.8.0` | the version the framework itself builds with |
| JUnit | `6.1.3` (property `junitVersion`) | |

Never version individual `io.koraframework:*` artifacts — the BOM aligns them.
The two exceptions are the **`ksp` / `kspTest` configurations**, which resolve
against their own classpath and so carry an explicit `${property("koraVersion")}`.

`2.0.0-SNAPSHOT` is the `master` development line, not a version to put in a new
project: it resolves only from
`https://central.sonatype.com/repository/maven-snapshots` or after a local
`publishToMavenLocal`. A new service pins `2.0.0.RC2` and needs nothing but
`mavenCentral()`.

### Version drift is not cosmetic

Kotlin `2.4.20` and KSP `2.3.12` are the versions Kora 2.0 itself is built with.
The symbol processors are compiled against that exact KSP API and embed
`kotlin-compiler-embeddable` of that Kotlin line. Drifting either one does not
produce a clean "incompatible version" message — it produces
`NoSuchMethodError` / `ClassCastException` from inside the processor, or
generated code that fails to compile for reasons that point at your sources.
Change both together, and only after checking what the Kora release you target
is built with.

---

## Core principle

Kora generates code at compile time. For Kotlin this runs through **KSP** (the
`com.google.devtools.ksp` plugin + `io.koraframework:symbol-processors`), never
Java's `annotationProcessor` and never `kapt`. Without KSP nothing is generated
and there is no application graph to run.

For `@KoraApp interface Application`, KSP generates `class ApplicationGraph`
(the interface's simple name + `Graph`) in the same package, with a companion
`fun graph(): ApplicationGraphDraw`. It does not resolve in the IDE until the
first build.

---

## Project structure

```
my-app/
├── build.gradle.kts
├── settings.gradle.kts
├── gradle.properties
├── gradle/wrapper/gradle-wrapper.properties
├── src/main/
│   ├── kotlin/com/example/Application.kt
│   └── resources/
│       ├── application.conf     # HOCON config
│       └── logback.xml          # logging appenders
└── src/test/kotlin/com/example/
```

---

## Quick Start

### 1. settings.gradle.kts

The `foojay-resolver-convention` plugin lets the Java toolchain auto-download the
requested JDK instead of relying only on locally installed ones.

```kotlin
plugins {
    id("org.gradle.toolchains.foojay-resolver-convention") version "1.0.0"
}

rootProject.name = "kora-example"
```

### 2. gradle.properties

```properties
koraVersion=2.0.0.RC2
junitVersion=6.1.3

org.gradle.java.installations.auto-detect=true
org.gradle.java.installations.auto-download=true
kotlin.jvm.target.validation.mode=warning
kotlin.incremental=false

org.gradle.jvmargs=-Dfile.encoding=UTF-8
org.gradle.parallel=true
org.gradle.caching=true
```

`kotlin.incremental=false` is deliberate: on an incremental build Kora's
processors can read an interface from a class file whose parameter names are
synthetic and report errors like `SQL query placeholder has no matching method
parameter: :id / Available parameters: - :arg0` against source that is correct.
Turning it back on is fine as long as you reach for `--rerun-tasks` when a
processor complains about something the source clearly does have.

### 3. build.gradle.kts

```kotlin
import org.gradle.jvm.toolchain.JavaLanguageVersion
import org.gradle.jvm.toolchain.JvmVendorSpec

plugins {
    id("application")
    kotlin("jvm") version "2.4.20"
    id("com.google.devtools.ksp") version "2.3.12"
}

repositories {
    mavenCentral()
}

dependencies {
    implementation(platform("io.koraframework:kora-bom:${property("koraVersion")}"))
    ksp("io.koraframework:symbol-processors:${property("koraVersion")}")

    implementation("io.koraframework:http-server-undertow")
    implementation("io.koraframework:config-hocon")
    implementation("io.koraframework:json-common")
    implementation("io.koraframework:logging-logback")

    testImplementation(platform("org.junit:junit-bom:${property("junitVersion")}"))
    testImplementation("org.junit.jupiter:junit-jupiter")
    testImplementation("io.koraframework:test-junit5")
}

kotlin {
    jvmToolchain {
        languageVersion.set(JavaLanguageVersion.of(25))
        vendor.set(JvmVendorSpec.ADOPTIUM)
    }
    sourceSets.main { kotlin.srcDir("build/generated/ksp/main/kotlin") }
    sourceSets.test { kotlin.srcDir("build/generated/ksp/test/kotlin") }
}

java {
    toolchain {
        languageVersion.set(JavaLanguageVersion.of(25))
        vendor.set(JvmVendorSpec.ADOPTIUM)
    }
}

application {
    applicationName = "application"
    mainClass.set("com.example.ApplicationKt")
    applicationDefaultJvmArgs = listOf("-Dfile.encoding=UTF-8")
}

tasks.distTar {
    archiveFileName.set("application.tar")
}

tasks.test {
    useJUnitPlatform()
}
```

Full file: [`assets/build.gradle.kts.template`](assets/build.gradle.kts.template)

**Kotlin modules do not create a `koraBom` configuration.** The BOM goes
straight on `implementation` and the processor version is stated explicitly.
The `koraBom` + `extendsFrom` wiring is a **Java-module** pattern; carrying it
into a Kotlin build is a migration regression, not a style choice.

### 4. Application.kt

`@KoraApp` marks the application graph root. Each Kora capability is added by
extending its `*Module` interface.

```kotlin
package com.example

import io.koraframework.application.graph.KoraApplication
import io.koraframework.common.annotation.KoraApp
import io.koraframework.config.hocon.HoconConfigModule
import io.koraframework.http.server.undertow.UndertowPublicHttpServerModule
import io.koraframework.json.common.JsonModule
import io.koraframework.logging.logback.LogbackModule

@KoraApp
interface Application :
    HoconConfigModule,
    JsonModule,
    LogbackModule,
    UndertowPublicHttpServerModule

fun main() {
    KoraApplication.run { ApplicationGraph.graph() }
}
```

Full file: [`assets/Application.kt.template`](assets/Application.kt.template)

`UndertowPublicHttpServerModule` extends `UndertowSystemHttpServerModule`, so
extending it alone gives you both the public server (config path `httpServer`)
and the system server (config path `httpServer.system`), which always registers
`/system/readiness`, `/system/liveness` and `/metrics`. `/metrics` answers `200`
with the body `# Metric Scraper disabled` until you add
`io.koraframework:micrometer-module` — so a status-code check against it proves
nothing about metrics.

### 5. A first component

Components are registered with `@Component`; an HTTP controller adds
`@HttpController` and `@HttpRoute`. Controller methods are **synchronous** —
Kora 2.0 runs them on virtual threads.

```kotlin
package com.example

import io.koraframework.common.annotation.Component
import io.koraframework.http.common.HttpMethod
import io.koraframework.http.common.annotation.HttpRoute
import io.koraframework.http.common.body.HttpBody
import io.koraframework.http.server.common.annotation.HttpController
import io.koraframework.http.server.common.response.HttpServerResponse

@Component
@HttpController
class HelloController {

    @HttpRoute(method = HttpMethod.GET, path = "/hello")
    fun hello(): HttpServerResponse =
        HttpServerResponse.of(200, HttpBody.plaintext("Hello, Kora!"))
}
```

### 6. application.conf (HOCON)

```hocon
httpServer {
  port = 8080
  system.port = 8085
  telemetry.logging.enabled = true
}

logging.levels {
  "root": "WARN"
  "root": ${?LOGGING_LEVEL_ROOT}

  "io.koraframework": "INFO"
  "io.koraframework": ${?LOGGING_LEVEL_KORA}

  "com.example": "INFO"
  "com.example": ${?LOGGING_LEVEL_APP}
}
```

Full file: [`assets/application.conf.template`](assets/application.conf.template)

Effective defaults, all from `HttpServerConfig` / `SystemHttpServerConfig`:
public `port = 8080`, `system.port = 8085`, `system.readinessPath =
/system/readiness`, `system.livenessPath = /system/liveness`,
`system.metricsPath = /metrics`.

Telemetry logging and metrics both default to **disabled**, so a scaffold meant
to show request logs must enable them explicitly. Tracing defaults to enabled —
except under `httpServer.system`, where `SystemHttpServerTracingConfig`
overrides it back to `false` so probe traffic is not traced.

#### Stale 1.x keys fail silently, and not the way you would guess

`publicApiHttpPort` → `port`, `privateApiHttpPort` → `system.port`,
`privateApiHttpReadinessPath|LivenessPath|MetricsPath` →
`system.readinessPath|livenessPath|metricsPath`, `logging.level` →
`logging.levels`.

A stale key is just an unrecognised HOCON key. Kora's config layer has no
strict-key validation, so nothing warns — the key is simply never read and the
setting falls back to its own default. The dangerous case is therefore **not** a
port clash: a 1.x config that ran on non-default ports comes up **green on the
wrong ports**, and probes, scrapers and load balancers pointed at the old ones
hit nothing. `Address already in use` only appears if stale keys happen to
collapse both servers onto one port.

Note that `SystemHttpServerConfig.port()` overrides the inherited default to
`8085`, so the system server does not fall back to 8080 — any guidance claiming
both servers bind 8080 describes a pre-release build, not Kora 2.0.

### 7. logback.xml

```xml
<configuration debug="false">
    <statusListener class="ch.qos.logback.core.status.NopStatusListener"/>

    <appender name="STDOUT" class="ch.qos.logback.core.ConsoleAppender">
        <encoder class="io.koraframework.logging.logback.text.ConsoleTextRecordEncoder"/>
    </appender>

    <appender name="ASYNC" class="io.koraframework.logging.logback.KoraAsyncAppender">
        <appender-ref ref="STDOUT"/>
    </appender>

    <root level="WARN">
        <appender-ref ref="ASYNC"/>
    </root>
    <!-- Per-logger levels live in application.conf under logging.levels -->
</configuration>
```

Full file: [`assets/logback.xml.template`](assets/logback.xml.template)

### 8. Gradle wrapper

`gradle/wrapper/gradle-wrapper.properties`:

```properties
distributionBase=GRADLE_USER_HOME
distributionPath=wrapper/dists
distributionUrl=https\://services.gradle.org/distributions/gradle-9.8.0-bin.zip
networkTimeout=10000
retries=0
retryBackOffMs=500
validateDistributionUrl=true
zipStoreBase=GRADLE_USER_HOME
zipStorePath=wrapper/dists
```

---

## JDK choice

Kora 2.0 artifacts are compiled for **JVM 25**: the published `common` jar
carries class-file major version 69 and the published `kora-bom` pom declares
`java.version = 25`. That is a hard floor, not a recommendation — 25 is the
lowest toolchain that can consume them.

Two distinct JVMs matter, and a toolchain only fixes the first:

1. **Compilation / runtime** — `jvmToolchain(25)` (or higher). The Kora 2.0
   example set pins `25` everywhere.
2. **The JVM running Gradle itself** — anything on the *buildscript* classpath is
   resolved by it, not by the toolchain. `io.koraframework:openapi-generator`
   goes there, so as soon as you add OpenAPI generation, a Gradle process on
   JDK 21 fails at configuration time with
   `Dependency requires at least JVM runtime version 25. This build uses a Java 21 JVM.`
   Check with `JAVA_HOME=<jdk25+> ./gradlew projects`.

Above the floor, pick the **latest GA feature release** at the time you set the
project up (`openjdk.org/projects/jdk`) rather than copying a number out of a
document — this file states the floor, not a ceiling. Do not run production on
an EA build to get a newer preview API.

Container runtime must be the same major version as the bytecode you produced —
the examples ship on `eclipse-temurin:25-jre-jammy`.

---

## When `kspTest` is needed

`kspTest("io.koraframework:symbol-processors:${property("koraVersion")}")` is
**not** a default line. Add it exactly when `src/test` declares its own
`@KoraApp` — a `TestApplication` interface that a `@KoraAppTest(...)` points at:

```kotlin
// src/test/kotlin/com/example/TestApplication.kt — this is what requires kspTest
@KoraApp
interface TestApplication : Application {

    @Root
    @Component
    @Repository
    interface TestUserRepository : JdbcRepository {
        @Query("DELETE FROM users")
        fun deleteAll()
    }
}
```

`@KoraAppTest(Application::class)` pointing at the **main** application does not
need `kspTest` — that graph was already generated by `ksp` on main sources.

When a test `@KoraApp` **extends** another `@KoraApp` (as above), the extended
module must additionally be compiled with the submodule KSP argument:

```kotlin
ksp {
    arg("kora.app.submodule.enabled", "true")
}
```

Without it KSP only *warns* — `Expected @KoraApp as SubModule, but Submodule
implementation not found for: com.example.Application` — and silently drops the
parent's components from the test graph. See
[`kora-testing-junit-kotlin`](../kora-testing-junit-kotlin/SKILL.md) for the
test side.

---

## Coming from Kora 1.x

Regressions that compile, or that fail with a message pointing somewhere else.

| 1.x | 2.x | What happens if you keep the 1.x form |
|---|---|---|
| `import com.google.devtools.ksp.gradle.KspTask`, `tasks.withType<KspTask>()` | `tasks.matching { it.name.startsWith("ksp") }.configureEach { … }` or `tasks.named("kspKotlin")` | KSP 2 no longer exports the type — build script does not compile |
| `koraBom` configuration + `extendsFrom` | BOM on `implementation`, explicit version on `ksp` | Java-only pattern; in Kotlin it is unnecessary indirection and drops the processor version |
| `ru.tinkoff.kora:kora-parent` | `io.koraframework:kora-bom` | no 2.x release under either group — see [legacy coordinates](#legacy-coordinates-still-visible-on-maven-central) |
| `ru.tinkoff.kora:json-module` | `io.koraframework:json-common` | no 2.x release |
| `ru.tinkoff.kora.common.KoraApp` | `io.koraframework.common.annotation.KoraApp` | DI annotations moved one package deeper |
| `UndertowHttpServerModule` | `UndertowPublicHttpServerModule` | |
| `publicApiHttpPort` / `privateApiHttpPort` | `port` / `system.port` | key silently unread; each server falls back to its own default (8080 / 8085) and the service comes up green on the wrong ports |
| `logging.level` | `logging.levels` | levels silently not applied |
| `suspend` repositories / controllers / HTTP clients | synchronous methods on virtual threads | contract removed; a scaffold must not pull in `kotlinx-coroutines-*` |
| `Dispatchers.IO` / `runBlocking` around Kora I/O | nothing — calls block a virtual thread | pure overhead |
| `@field:Nullable` on Kotlin properties | `val name: String?` | invalid annotation target under Kotlin 2.4 |
| `kapt` for Kora | KSP | Kora ships no Kotlin `kapt` processor |
| MapStruct `@Mapper` via `kapt` | Konvert `@Konverter` via `ksp("io.mcarle:konvert")` | MapStruct is Java-only in 2.0; see [`kora-mapstruct`](../kora-mapstruct/SKILL.md) |

**First build after a package rename must be clean and uncached.** Generator
tasks (OpenAPI, protobuf) do not delete their previous output and the build
cache key does not account for a changed `apiPackage`, so the old and new
packages coexist in one source set and you get `Unresolved reference` errors
pointing at files under `build/generated/` that are not in your sources:

```shell
./gradlew clean --continue
./gradlew classes testClasses --continue --no-build-cache
```

Never edit generated code to make those errors go away.

### Legacy coordinates still visible on Maven Central

The `io.koraframework` group directory on Central still lists artifacts left over
from the 1.x and alpha lines — `kora-parent`, `cache-redis`,
`declarative-logging-annotation-processor`, `declarative-logging-symbol-processor`,
`scheduling-ksp`, `experimental/s3-client`. The new group name makes them look
current; none of them is constrained by the 2.0 BOM. Browsing the group listing
is not how you pick a coordinate — take it from the BOM, and if the BOM does not
constrain it, the artifact is not part of Kora 2.x.

---

## Commands

```bash
./gradlew kspKotlin       # runs the symbol processors alone — first wave of errors
./gradlew classes         # KSP + compile; first real proof the graph assembles
./gradlew run             # starts the application
./gradlew test            # tests
./gradlew clean build     # full build + tests
```

`classes` is a meaningful check in Kora: it runs the symbol processors, so it
verifies not only Kotlin syntax but that the application graph can be assembled.

---

## When to use vs NOT

| Use this skill when | Do NOT use when |
|---|---|
| Starting a new Kotlin Kora service | Project is Java → use [`kora-project-setup-java`](../kora-project-setup-java/SKILL.md) |
| Wiring `build.gradle.kts`, KSP, the BOM, the wrapper | Adding modules to an existing Kora app → [`kora-project-dependencies`](../kora-project-dependencies/SKILL.md) |
| Splitting a service into Gradle modules with `@KoraSubmodule` | Configuring HOCON details → [`kora-config-hocon`](../kora-config-hocon/SKILL.md) |

---

## Common pitfalls

| Symptom | Cause | Fix |
|---|---|---|
| `ApplicationGraph` unresolved | KSP never ran | Run `./gradlew classes`; check the KSP plugin and the `ksp("io.koraframework:symbol-processors:…")` dependency |
| `Unresolved reference: KspTask` in the build script | KSP 2 dropped the type | `tasks.matching { it.name.startsWith("ksp") }.configureEach { … }` |
| `Could not find io.koraframework:symbol-processors` with no version | Version omitted on `ksp` | `ksp` resolves on its own classpath — state `${property("koraVersion")}` explicitly |
| `Unresolved reference` in files under `build/generated/` | Stale generated sources from the old package | `clean`, then build once with `--no-build-cache` |
| Processor reports `:arg0` instead of your parameter names | Incremental compilation fed the processor a class file | `kotlin.incremental=false`, or `--rerun-tasks` |
| `Dependency requires at least JVM runtime version 25` | The Gradle JVM, not the toolchain, is too old | Run Gradle on JDK 25+ |
| `Java 25 (69) is not supported by the current version of Byte Buddy` | Mock library pins an old Byte Buddy | MockK ≥ `1.14.9`; with `mockito-kotlin`, pin `mockito-core` next to it. `-Dnet.bytebuddy.experimental=true` only disables the check — not a fix |
| Test graph missing the main app's components, only a KSP warning | Test `@KoraApp` extends the main one | `ksp { arg("kora.app.submodule.enabled", "true") }` on the extended module |
| Service starts clean but probes/scrapers get nothing; ports are 8080/8085 rather than the configured ones | Stale 1.x config keys are unread and each server fell back to its default | Rename to `port` / `system.port` / `system.*Path`; there is no warning to look for, so diff the keys against `HttpServerConfig` and `SystemHttpServerConfig` |
| `Required dependency not found` | A `*Module` not extended, or `@Component` missing | Extend the module on `@KoraApp`; annotate the class with `@Component` |
| Version conflicts on Kora artifacts | An `io.koraframework:*` dep pinned by hand | Remove the explicit version; let the BOM align it (`ksp`/`kspTest` excepted) |

---

## Multi-module / @KoraSubmodule

Most services are a single module. To split across Gradle modules with
`@KoraSubmodule` feature modules aggregated by a `@KoraApp` app module, see
[`references/multi-module-reference.md`](references/multi-module-reference.md).

## Preview features (Java StructuredTaskScope)

Only relevant if the service needs real parallelism: Kotlin structured
concurrency has no Kora 2.x contract and migrates to Java `StructuredTaskScope`,
which is a preview API and needs preview enabled at every compile and every JVM
launch. Build wiring in
[`references/preview-features-reference.md`](references/preview-features-reference.md).

---

## Assets

| File | Description |
|---|---|
| [`assets/build.gradle.kts.template`](assets/build.gradle.kts.template) | Single-module Kotlin build config |
| [`assets/settings.gradle.kts.template`](assets/settings.gradle.kts.template) | Settings with foojay toolchain resolver |
| [`assets/gradle.properties`](assets/gradle.properties) | `koraVersion`, `junitVersion`, Gradle/Kotlin properties |
| [`assets/gradle-wrapper.properties`](assets/gradle-wrapper.properties) | Gradle wrapper config |
| [`assets/Application.kt.template`](assets/Application.kt.template) | `@KoraApp` root + `main()` |
| [`assets/application.conf.template`](assets/application.conf.template) | HOCON with 2.x port and logging keys |
| [`assets/logback.xml.template`](assets/logback.xml.template) | Logback appenders for `logging-logback` |

---

## Next steps

- [`kora-project-dependencies`](../kora-project-dependencies/SKILL.md) — add modules (HTTP, Database, Kafka, ...)
- [`kora-config-hocon`](../kora-config-hocon/SKILL.md) — typed `@ConfigSource` configuration
- [`kora-di-compile`](../kora-di-compile/SKILL.md) — compile-time DI patterns
- [`kora-testing-junit-kotlin`](../kora-testing-junit-kotlin/SKILL.md) — `@KoraAppTest` component tests

---

## References

| Document | Description |
|---|---|
| [`references/multi-module-reference.md`](references/multi-module-reference.md) | Gradle multi-module + `@KoraSubmodule` setup |
| [`references/preview-features-reference.md`](references/preview-features-reference.md) | Enabling JDK preview for `StructuredTaskScope` |
| [`bom-usage-reference.md`](../kora-project-dependencies/references/bom-usage-reference.md) | BOM setup details |
| [`compatibility-matrix.md`](../kora-project-dependencies/references/compatibility-matrix.md) | Version compatibility |
| [`core-modules-reference.md`](../kora-project-dependencies/references/core-modules-reference.md) | Core modules catalogue |
