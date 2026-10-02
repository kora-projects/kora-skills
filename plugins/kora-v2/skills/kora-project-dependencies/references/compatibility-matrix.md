# Kora 2.0 Compatibility Matrix

JDK, Kotlin/KSP, Gradle, and the third-party versions Kora 2.0 builds against.

## Contents

- [At a glance](#at-a-glance)
- [Resolving the artifacts](#resolving-the-artifacts)
- [JDK: two different requirements](#jdk-two-different-requirements)
- [Kotlin and KSP](#kotlin-and-ksp)
- [Gradle](#gradle)
- [Build plugins](#build-plugins)
- [Third-party versions Kora ships](#third-party-versions-kora-ships)
- [Externally versioned dependencies](#externally-versioned-dependencies)

---

## At a glance

| Component | Value | Source |
|---|---|---|
| BOM | `io.koraframework:kora-bom` | — |
| Kora version | **`2.0.0.RC2`** — published on Maven Central | `kora-bom` maven-metadata |
| Bytecode floor | **JVM 25** | Kora 2.0 jars are class-file 69; the `kora-bom` POM sets `java.version = 25` |
| Toolchain | 25 or newer — reference examples use 25 | reference examples |
| Gradle JVM | **25 or newer** whenever `openapi-generator` is on the buildscript classpath | see below |
| Kotlin | `2.4.20` | framework version catalog |
| KSP plugin | `2.3.12` | framework version catalog |
| Gradle | `9.7.1` (the framework's wrapper; the examples repo still pins `9.5.1`) | wrapper properties |

The third-party versions further down come from the framework's version catalog
(`gradle/libs.versions.toml`) for `2.0.0.RC2`.

---

## Resolving the artifacts

A release build needs nothing but Maven Central:

```groovy
repositories {
    mavenCentral()
}
```

`2.0.0-SNAPSHOT` is the `master` development line, not a version for a new project. Tracking it
deliberately also requires the snapshot repository, or a local `publishToMavenLocal`:

```groovy
repositories {
    mavenCentral()
    maven { url = "https://central.sonatype.com/repository/maven-snapshots" }
}
```

---

## JDK: two different requirements

They are separate, and confusing them is the most common first failure of a 2.0 migration.

**1. The toolchain — what compiles your code.** Kora 2.0 artifacts are compiled at JVM 25, so
anything consuming them must target 25 or newer:

```groovy
java {
    toolchain {
        languageVersion = JavaLanguageVersion.of(25)
        vendor = JvmVendorSpec.ADOPTIUM
    }
}
```

```kotlin
kotlin {
    jvmToolchain {
        languageVersion.set(JavaLanguageVersion.of(25))
        vendor.set(JvmVendorSpec.ADOPTIUM)
    }
}
```

**2. The JVM running Gradle itself.** `io.koraframework:openapi-generator` goes on the
**buildscript classpath**, which Gradle resolves with its own JVM — the toolchain has no say. On an
older Gradle JVM the build dies during configuration, before any compilation:

```
Dependency requires at least JVM runtime version 25. This build uses a Java 21 JVM.
> Run this build using a Java 25 or newer JVM.
```

Check it with `JAVA_HOME=<jdk> ./gradlew projects`.

Do not put `org.gradle.java.home` in a committed `gradle.properties` — the path is machine-specific.
Set `JAVA_HOME`, or configure a Gradle daemon toolchain.

**Which number to pick.** 25 is the hard floor, derived from the framework's own build. The migration
guides recommend running on the **latest GA feature release** rather than freezing a number: check
<https://openjdk.org/projects/jdk/> on the day you set this up and take the latest GA (it was JDK 26
when the guides were last refreshed). Re-derive it instead of copying a stale value.

**`--enable-preview` is not a Kora requirement.** It appears only in Kora's own test task and in the
BOM's Maven surefire `argLine`. Add it only if your own code uses a preview API (for example
`StructuredTaskScope`), and then pin to the preview iteration of the exact JDK you chose — the API
changes between releases.

---

## Kotlin and KSP

| Kotlin | KSP plugin |
|---|---|
| `2.4.20` | `2.3.12` |

```kotlin
plugins {
    kotlin("jvm") version "2.4.20"
    id("com.google.devtools.ksp") version "2.3.12"
}
```

KSP 2 no longer exports the `KspTask` Gradle type — match tasks by name instead. See
[annotation-processors-reference.md](annotation-processors-reference.md#ksp-2-differences).

If the Kotlin compiler cannot target the toolchain JDK exactly, set
`kotlin.jvm.target.validation.mode=warning` in `gradle.properties` so the mismatch is a warning
rather than a build failure — that is what the reference examples do.

---

## Gradle

The framework pins Gradle **9.7.1** through the wrapper (the examples repository is still on 9.5.1;
both are Gradle 9):

```properties
# gradle/wrapper/gradle-wrapper.properties
distributionUrl=https\://services.gradle.org/distributions/gradle-9.7.1-bin.zip
```

---

## Build plugins

### Java

```groovy
plugins {
    id "java"
    id "application"
}
```

### Kotlin

```kotlin
plugins {
    id("application")
    kotlin("jvm") version "2.4.20"
    id("com.google.devtools.ksp") version "2.3.12"
}
```

### OpenAPI codegen

```groovy
buildscript {
    repositories { mavenCentral() }
    dependencies {
        classpath "io.koraframework:openapi-generator:$koraVersion"
    }
}

plugins {
    id "org.openapi.generator" version "7.25.0"
}
```

**These are two different, independently versioned things — do not conflate them:**

| | What it is | Version |
|---|---|---|
| `io.koraframework:openapi-generator` | Kora's own `kora` generator, on the **buildscript classpath** | `$koraVersion` (`2.0.0.RC2`) |
| `org.openapi.generator` | The OpenAPI Tools **Gradle plugin** that runs it | its own release line |
| `org.openapitools:openapi-generator` | The upstream generator library Kora's module depends on | `7.25.0`, from Kora's version catalog |

The reference examples do not even agree on the plugin version: the Java projects use `7.23.0`, the
Kotlin ones `7.24.0`. All of these work. Pick a recent 7.x; it is not pinned by Kora and does not have to
match `org.openapitools:openapi-generator`.

### GraalVM native image

`org.graalvm.buildtools.native` moved to **`1.1.7`** (from `0.11.5`), for Gradle 9 support and the
per-project build service. Toolchain and native launcher move to 25, and the Docker base image
becomes `ghcr.io/graalvm/native-image-community:25`.

---

## Third-party versions Kora ships

These arrive transitively with the modules that need them. Listed so you can recognise a conflict —
**do not pin them yourself**.

| Library | Version | Arrives with |
|---|---|---|
| Jackson (`tools.jackson.core`) | `3.2.3` | `json-common`, `jackson-module` |
| Jackson 2 compat line | `2.22.3` | compat modules only |
| Undertow | `2.4.3.Final` | `http-server-undertow` |
| OkHttp | `5.5.0` | `http-client-ok`, gRPC transport |
| Apache HttpClient 5 | `5.6.4` | `http-client-apache` |
| Netty | `4.2.18.Final` | Redis, Cassandra, gRPC |
| HikariCP | `7.1.0` | `database-jdbc` |
| PostgreSQL JDBC driver | `42.7.13` | `database-jdbc-postgres` (`api`) |
| Flyway | `13.9.0` (`flyway-core` only) | `database-flyway` |
| Liquibase | `5.0.4` | `database-liquibase` |
| Cassandra driver | `4.19.3`, module `org.apache.cassandra:java-driver-core` | `database-cassandra` |
| Kafka clients | `4.3.1` | `kafka` |
| gRPC Java | `1.84.0` | `grpc-server`, `grpc-client` |
| gRPC Kotlin | `1.5.0` | — |
| protobuf Gradle plugin | `0.10.0` | — |
| protobuf-java | **`3.25.9`** reaches you transitively via `grpc-protobuf` — *not* the `4.36.2` in Kora's catalog | `grpc-server`, `grpc-client` (see below) |
| Micrometer | `1.17.1` | `micrometer-module` |
| Prometheus metrics | `1.9.0` | `micrometer-module` |
| OpenTelemetry | `1.66.0` | tracing exporters |
| Logback / SLF4J | `1.6.5` / `2.0.20` | `logging-logback` |
| Caffeine | `3.3.0` | `cache-caffeine` |
| Lettuce | `7.8.0.RELEASE` | `redis-lettuce`, `cache-redis-lettuce`, `resilient-kora-distributed-redis-lettuce` |
| Quartz | `2.5.2` | `scheduling-quartz` |
| db-scheduler | `16.12.0` (`com.github.kagkarlsson:db-scheduler`) | `scheduling-db-scheduler` |
| CXF (SOAP) | `4.2.3` | `soap-client` |
| AWS SDK S3 | `2.55.10` | `s3-client-aws` |
| Camunda 7 | `7.24.0` | `camunda-engine-bpmn` |
| Zeebe / Camunda 8 | `8.10.0`, client `io.camunda:camunda-client-java` | `camunda-zeebe-worker` |
| MapStruct (Java only) | `1.6.3` in Kora's catalog | — **you add it**; see note below |
| Konvert (Kotlin only) | `4.5.1` in Kora's catalog | — **you add it**; the Kotlin `crud` example pins the same `4.5.1` |
| JSpecify | `1.0.1` | every module (`api`) |
| JUnit | `6.1.3` | `test-junit5` |

**MapStruct and Konvert are not shipped by Kora.** MapStruct is the Java path, Konvert the Kotlin
path — never MapStruct (or `kapt`) in a Kotlin module. The extensions inside the aggregate processors
only *discover* generated mappers; the library and its processor are entirely your dependency, and
`kora-bom` does not constrain them. `1.6.3` is what Kora's own `mapstruct-java-extension` tests
against — it is not a requirement, and the reference Java examples pin **`1.5.5.Final`** instead.
Either works; choose deliberately rather than copying a number from this table.

**protobuf is the one row where Kora's catalog is not what you get.** `grpc/grpc-server/build.gradle`
declares `protobuf-java` as **`compileOnly`**, so the catalog's `4.36.2` never propagates to a
consumer. What actually lands on your classpath is `com.google.protobuf:protobuf-java:3.25.9`,
declared at compile scope by `io.grpc:grpc-protobuf:1.84.0`. All twelve migrated projects that
generate protobuf pin the matching `protoc:3.25.3`. Pinning `protoc:4.36.2` without also pinning
`protobuf-java:4.36.2` makes protoc emit code against APIs the resolved 3.25.9 runtime does not have,
and the build fails with `cannot find symbol: class Generated`.

Two coordinate moves that break a pinned dependency rather than a compile:

- Jackson is under **`tools.jackson.core`** (Jackson 3). A pinned `com.fasterxml.jackson.core:*` no
  longer participates.
- The Cassandra driver is **`org.apache.cassandra:java-driver-core`**, not `com.datastax.oss`.

---

## Externally versioned dependencies

Not in the BOM. The app pins them, and a mismatch usually fails at **runtime**, not at compile time.

| Dependency | What to pin | Symptom when it is wrong |
|---|---|---|
| JDBC driver | e.g. `org.postgresql:postgresql:42.7.13` — `database-jdbc` ships Hikari, never a driver (`database-jdbc-postgres` does bring the PostgreSQL one) | `No suitable driver` at startup |
| Flyway dialect | `org.flywaydb:flyway-database-postgresql` at the same version as the resolved `flyway-core` | `FlywayException: Unsupported Database: PostgreSQL 16.x` at startup |
| gRPC test transports | `grpc-inprocess` / `grpc-netty` / `grpc-testing` at **`1.84.0`**, matching `grpc-core` from `grpc-server` | `AbstractMethodError: ... buildClientTransportServers(List, MetricRecorder)` |
| protoc | **`3.25.3`** — matches the `protobuf-java:3.25.9` that `grpc-protobuf` brings; what all the migrated projects use | `cannot find symbol: class Generated` when protoc is 4.x but the resolved runtime is 3.x |
| Mockito | a `mockito-core` whose Byte Buddy understands class file 69 (Java 25). Kora validates against `5.24.0` / Byte Buddy `1.18.14` | `IllegalArgumentException: Java 25 (69) is not supported by the current version of Byte Buddy`, often hidden inside `Application graph failed to initialize with N errors` |
| `mockito-kotlin` | pins its own older `mockito-core` — declare `mockito-core` explicitly next to it | same Byte Buddy failure |
| MockK | `1.14.9` minimum for Java 25; Kora validates against `1.14.11` | same Byte Buddy failure |
| Testcontainers | see below | `Could not find org.testcontainers:postgresql` after a 2.x bump |
| JUnit | comes with `test-junit5` (`6.1.3`); pin `org.junit:junit-bom` only if you need to override | — |

**Flyway dialect.** Since Flyway 10 the per-database support lives in its own artifact, and
`database-flyway` ships `flyway-core` only:

```groovy
implementation "io.koraframework:database-flyway"
implementation "org.flywaydb:flyway-database-postgresql:13.9.0"
```

The artifact names are not uniform: PostgreSQL is `org.flywaydb:flyway-database-postgresql`, MySQL is
`org.flywaydb:flyway-mysql` (there is no `flyway-database-mysql`).

Confirm the version to use with `./gradlew dependencyInsight --dependency flyway-core` rather than
copying a number — the dialect must match the `flyway-core` your build actually resolves.

**Testcontainers module names changed in 2.x.** Kora's own build uses Testcontainers `2.0.5`, where
the database/broker modules were renamed:

| 1.x module | 2.x module |
|---|---|
| `org.testcontainers:postgresql` | `org.testcontainers:testcontainers-postgresql` |
| `org.testcontainers:kafka` | `org.testcontainers:testcontainers-kafka` |
| `org.testcontainers:cassandra` | `org.testcontainers:testcontainers-cassandra` |

The migrated reference examples stay on Testcontainers `1.21.4` with the old names — Testcontainers
is entirely the app's own dependency and Kora does not constrain it. Either line works; what does
not work is a 2.x version with 1.x module names.

**Byte Buddy floor.** Several reference examples still pin `mockito-core:5.18.0`. If mocks start
failing with the class-file-69 message on JDK 25+, raise `mockito-core` (Kora validates `5.24.0`)
or MockK (`1.14.11`) — the failure is a runtime one and its stack trace does not name the cause.

---

## See Also

- [SKILL.md](../SKILL.md) — quick start
- [artifact-catalog.md](artifact-catalog.md) — every published artifact
- [bom-usage-reference.md](bom-usage-reference.md) — BOM setup
- [annotation-processors-reference.md](annotation-processors-reference.md) — processors / KSP setup
