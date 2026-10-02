---
name: kora-project-dependencies
description: "Kora 2.0 Gradle artifacts + project generator — io.koraframework:kora-bom, annotation-processors/symbol-processors, the koraBom configuration (Java) vs BOM-on-implementation (Kotlin), real module names (json-common, cache-redis-lettuce, http-client-apache), externally-versioned deps. Use when wiring build.gradle, choosing modules, or fixing \"dependency not found\"/version conflicts/1.x coordinates."
license: Apache-2.0
metadata:
  kora-version: "2.x"
---

# Kora Project Dependencies — Module Catalog

> **Kora sub-skill — obey the [kora-v2 meta rules](../../SKILL.md) on every task:** **R0** ground the workspace on Kora 2.0 refs before starting (framework source at tag `2.0.0.RC2` + `kora-examples` at `migration/2.0` + Kora 2.0 docs at koraframework.io/v2, which trail the source; 1.x `kora-docs` pages are never an authority) · **R1** read this sub-skill before writing code · **R2** Kora 2.0 APIs only — no Spring/Micronaut/Quarkus, no Kora 1.x APIs, no invented annotations or config keys · **R3** journal any incorrect Kora usage. Add comments/Javadoc only if asked.

**Group:** `io.koraframework` — except the `experimental/` tree, which is `io.koraframework.experimental`
**BOM:** `io.koraframework:kora-bom:2.0.0.RC2` — on Maven Central
**JDK:** bytecode floor **25** | **Kotlin:** 2.4.20 | **KSP:** 2.3.12 | **Gradle:** 9.7.1

> **Critical:** always import the `kora-bom` platform, and **never put a version on an
> `io.koraframework:*` artifact** — the BOM does it. The one deliberate exception is the Kotlin
> `ksp("io.koraframework:symbol-processors:$koraVersion")` line, because the BOM is not applied to
> the `ksp` configuration.

Read this first when:

- Selecting which Kora modules to include in a build
- Setting up the BOM in `build.gradle` / `build.gradle.kts`
- Configuring annotation processors (Java) or KSP (Kotlin)
- Resolving "No component found for dependency" (a module artifact missing) or transitive version conflicts
- Translating 1.x coordinates (`ru.tinkoff.kora:kora-parent`, `json-module`, `cache-redis`, …)
- Scaffolding a new project (see [Project Generator](#project-generator))

**NOT when:** writing DI code (→ [`kora-di-compile`](../kora-di-compile/SKILL.md)), HTTP controllers
(→ [`kora-http-server`](../kora-http-server/SKILL.md)), repositories
(→ [`kora-database-jdbc`](../kora-database-jdbc/SKILL.md)), or Kafka handlers
(→ [`kora-kafka-consumer`](../kora-kafka-consumer/SKILL.md)).

---

## Quick Start — BOM Setup

Pin the version in `gradle.properties` and resolve from Maven Central:

```properties
koraVersion=2.0.0.RC2
```

```groovy
repositories {
    mavenCentral()
}
```

`2.0.0.RC2` is published on Central, so nothing else is needed. `2.0.0-SNAPSHOT` is the `master` development line — never pin it in a new project;
tracking it deliberately also requires
`maven { url = "https://central.sonatype.com/repository/maven-snapshots" }`.

### Java (build.gradle) — the `koraBom` configuration

A `platform` on `implementation` does not reach Java's `annotationProcessor` classpath, so Java
declares a `koraBom` configuration and wires it with `extendsFrom`. Miss that and
`annotation-processors` fails to resolve.

```groovy
plugins {
    id "java"
    id "application"
}

repositories {
    mavenCentral()
}

java {
    toolchain {
        languageVersion = JavaLanguageVersion.of(25)
        vendor = JvmVendorSpec.ADOPTIUM
    }
}

configurations {
    koraBom
    annotationProcessor.extendsFrom(koraBom)
    compileOnly.extendsFrom(koraBom)
    implementation.extendsFrom(koraBom)
    api.extendsFrom(koraBom)
    testImplementation.extendsFrom(koraBom)
    testAnnotationProcessor.extendsFrom(koraBom)
}

dependencies {
    koraBom platform("io.koraframework:kora-bom:$koraVersion")
    annotationProcessor "io.koraframework:annotation-processors"

    implementation "io.koraframework:http-server-undertow"
    implementation "io.koraframework:json-common"
    implementation "io.koraframework:config-hocon"
    implementation "io.koraframework:logging-logback"

    testAnnotationProcessor "io.koraframework:annotation-processors"
    testImplementation "io.koraframework:test-junit5"
}
```

### Kotlin (build.gradle.kts) — BOM straight on `implementation`

Kotlin does **not** create a `koraBom` configuration and does **not** use `extendsFrom`. The
processor carries an explicit version instead.

```kotlin
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
    implementation("io.koraframework:json-common")
    implementation("io.koraframework:config-hocon")
    implementation("io.koraframework:logging-logback")

    testImplementation("io.koraframework:test-junit5")
}

kotlin {
    jvmToolchain {
        languageVersion.set(JavaLanguageVersion.of(25))
        vendor.set(JvmVendorSpec.ADOPTIUM)
    }
}
```

Both shapes are deliberate. Do not port one into the other's language.

**Depth:** [`references/bom-usage-reference.md`](references/bom-usage-reference.md),
[`references/annotation-processors-reference.md`](references/annotation-processors-reference.md)

---

## JDK — two separate requirements

1. **Toolchain (compiles your code):** Kora 2.0 artifacts are built at JVM 25 and `kora-bom` declares
   `java.version = 25`, so **25 is the floor**. The reference examples use exactly 25.
2. **The JVM running Gradle:** `io.koraframework:openapi-generator` lands on the **buildscript**
   classpath, which Gradle resolves with its own JVM — the toolchain has no say. Below 25 the build
   dies during configuration with
   `Dependency requires at least JVM runtime version 25. This build uses a Java 21 JVM.`
   Check with `JAVA_HOME=<jdk> ./gradlew projects`.

**Which number:** 25 is the hard floor; the migration guides recommend the **latest GA feature
release** instead of a frozen number — check <https://openjdk.org/projects/jdk/> on the day and
re-derive. `--enable-preview` is not a Kora requirement; add it only if your own code uses a preview
API.

---

## Project Generator

`scripts/generate_project.py` scaffolds a compile-ready 2.0 project (build script, `@KoraApp`, HOCON
config, sample controller/repository/Kafka handlers) for a chosen set of modules.

```bash
# List available module keys
python3 scripts/generate_project.py --list-modules

# Preview without writing anything
python3 scripts/generate_project.py --name my-service --package com.example \
  --lang java --modules http-server,jdbc-postgres,metrics --dry-run

# Java REST API + PostgreSQL + clustered DB jobs, JSON logs
python3 scripts/generate_project.py \
  --name my-service --package com.example --lang java \
  --modules http-server,jdbc-postgres,scheduling-db,logging-json,metrics

# Java REST API + PostgreSQL
python3 scripts/generate_project.py \
  --name my-service --package com.example --lang java \
  --modules http-server,jdbc-postgres,metrics

# Kotlin Kafka service
python3 scripts/generate_project.py \
  --name kafka-service --package com.example --lang kotlin \
  --modules kafka,metrics
```

Output is 2.0-native: `io.koraframework` coordinates, the `kora-bom` platform, the Java vs Kotlin BOM
shapes above, `@KoraApp` from `io.koraframework.common.annotation`, `UndertowPublicHttpServerModule`,
`jdbc-postgres` on `database-jdbc-postgres` / `PostgresJdbcDatabaseModule`,
`@Repository extends JdbcRepository` with `io.koraframework.database.jdbc.annotation.EntityJdbc`, and
a config using `httpServer.port` / `httpServer.system.port` / `jdbc { … }` with telemetry explicitly
enabled. Re-running over an existing directory rewrites the generated files in place.

**Details:** [`scripts/generate_project.py`](scripts/generate_project.py)

---

## Core Modules (almost every service)

| Artifact | Module interface | Purpose |
|---|---|---|
| `io.koraframework:config-hocon` | `HoconConfigModule` | HOCON config (or `config-yaml` → `YamlConfigModule`) |
| `io.koraframework:json-common` | `JsonModule` | JSON (de)serialization for DTOs, HTTP, Kafka |
| `io.koraframework:logging-logback` | `LogbackModule` | SLF4J via Logback |
| `io.koraframework:annotation-processors` | — | Java annotation processor (mandatory, Java) |
| `io.koraframework:symbol-processors` | — | KSP symbol processor (mandatory, Kotlin) |

**Depth:** [`references/core-modules-reference.md`](references/core-modules-reference.md)

---

## Module Catalog

Every artifact below is published from the Kora 2.0 `settings.gradle`. The complete list — including
the per-domain processors and the internal, unpublished modules — is in
[`references/artifact-catalog.md`](references/artifact-catalog.md). **Do not invent a coordinate:
if it is not in that file, it does not exist.**

### HTTP

| Artifact | Module interface | Notes |
|---|---|---|
| `http-server-undertow` | `UndertowPublicHttpServerModule` | Public server on `httpServer`; extends the system server module, so `httpServer.system` (metrics, readiness, liveness) comes with it |
| `http-client-ok` | `OkHttpClientModule` | OkHttp transport |
| `http-client-jdk` | `JdkHttpClientModule` | JDK `HttpClient` transport |
| `http-client-apache` | `ApacheHttpClientModule` | Apache HttpClient 5 transport |

No separate auth artifact: server auth is `HttpServerPrincipalExtractor` (`http-server-common`),
client auth is `HttpClientTokenProvider` (`http-client-common`). There is no `ProbesModule` — probes
are system-server endpoints. `http-client-async` was **removed** with no replacement.

**Skills:** [`kora-http-server`](../kora-http-server/SKILL.md), [`kora-http-client`](../kora-http-client/SKILL.md), [`kora-http-server-auth`](../kora-http-server-auth/SKILL.md), [`kora-http-client-auth`](../kora-http-client-auth/SKILL.md)

### Database

| Artifact | Module interface | Notes |
|---|---|---|
| `database-jdbc` | `JdbcDatabaseModule` | JDBC repositories; config section is **`jdbc`** (was `db`) |
| `database-jdbc-postgres` | `PostgresJdbcDatabaseModule` | PostgreSQL on top of `database-jdbc` (the module extends `JdbcDatabaseModule`): `@Pg` / `@PgJson` / `@PgJsonb` mappers for arrays, `List<T>`, `PgRange<T>`, intervals and JSON; ships the `org.postgresql:postgresql` driver — [postgres mappers](../kora-database-jdbc/references/postgres-mappers-reference.md) |
| `database-cassandra` | `CassandraDatabaseModule` | Ships `org.apache.cassandra:java-driver-core` |
| `database-flyway` | `FlywayJdbcDatabaseModule` | Ships `flyway-core` **only** — add your dialect artifact |
| `database-liquibase` | `LiquibaseJdbcDatabaseModule` | Liquibase migrations |

JDBC drivers are **not** in the BOM — except that `database-jdbc-postgres` brings the PostgreSQL driver
as an `api` dependency. `database-r2dbc` and `database-vertx` were **removed** —
repository contracts are synchronous, there is no reactive replacement.

**Skills:** [`kora-database-jdbc`](../kora-database-jdbc/SKILL.md), [`kora-database-cassandra`](../kora-database-cassandra/SKILL.md), [`kora-database-migration`](../kora-database-migration/SKILL.md)

### Messaging

| Artifact | Module interface | Notes |
|---|---|---|
| `kafka` | `KafkaModule` | One artifact for `@KafkaPublisher` and `@KafkaListener` |
| `jms` | `JmsConsumerModule` | JMS consumers; the JMS provider is your own dependency |

There are no `kafka-producer` / `kafka-consumer` artifacts.

**Skills:** [`kora-kafka-producer`](../kora-kafka-producer/SKILL.md), [`kora-kafka-consumer`](../kora-kafka-consumer/SKILL.md)

### Telemetry

| Artifact | Module interface | Notes |
|---|---|---|
| `micrometer-module` | `MetricsModule` | Micrometer metrics; Prometheus scrape on the **system** server (`/metrics`) |
| `opentelemetry-tracing-exporter-grpc` | `OpentelemetryGrpcExporterModule` | OTLP/gRPC trace exporter |
| `opentelemetry-tracing-exporter-http` | `OpentelemetryHttpExporterModule` | OTLP/HTTP trace exporter |
| `logging-logback-json` | — (Logback encoder SPI) | JSON console encoder; on the classpath it wins the automatic encoder choice, `kora.logging.encoder` / `KORA_LOGGING_ENCODER` overrides it, a Logback config file disables the selection |

**Adding the artifact is not enough.** `telemetry.metrics.enabled` and `telemetry.logging.enabled`
default to `false` in 2.0 — turn them on per component (`httpServer { telemetry.metrics.enabled = true }`).

**Skills:** [`kora-telemetry-metrics`](../kora-telemetry-metrics/SKILL.md), [`kora-telemetry-tracing`](../kora-telemetry-tracing/SKILL.md), [`kora-telemetry-logging`](../kora-telemetry-logging/SKILL.md)

### gRPC and SOAP

| Artifact | Module interface |
|---|---|
| `grpc-server` | `GrpcServerModule` |
| `grpc-client` | `GrpcClientModule` |
| `soap-client` | `SoapClientModule` |

gRPC test transports are your own dependency and must match the gRPC version the module brings
(`1.84.0`) or server construction fails with `AbstractMethodError`.

**Skills:** [`kora-grpc-server`](../kora-grpc-server/SKILL.md), [`kora-grpc-client`](../kora-grpc-client/SKILL.md), [`kora-soap-client`](../kora-soap-client/SKILL.md)

### OpenAPI

| Artifact | Where | Notes |
|---|---|---|
| `openapi-generator` | `buildscript { dependencies { classpath … } }` | Codegen for the `org.openapi.generator` plugin, `generatorName = "kora"`. Forces the Gradle JVM to 25+ |
| `openapi-management` | `implementation` | `OpenApiManagementModule` — spec + Swagger UI / **Scalar** |

Only four modes remain: `java-client`, `java-server`, `kotlin-client`, `kotlin-server`.

**Skills:** [`kora-openapi-generator-server`](../kora-openapi-generator-server/SKILL.md), [`kora-openapi-generator-client`](../kora-openapi-generator-client/SKILL.md), [`kora-openapi-management`](../kora-openapi-management/SKILL.md)

### AOP

| Artifact | Module interface | Annotations |
|---|---|---|
| `resilient-kora` | `ResilientModule` | `@CircuitBreakable`, `@Retryable`, `@Timeout`, `@RateLimited`, `@Fallback` — all take a **spec interface**, not a string |
| `resilient-kora-distributed` | — | Distributed rate limiter and retry budget shared across instances (`@RateLimiterDistributedSpec`, `DistributedRetryBudgetFactory`); needs a backend |
| `resilient-kora-distributed-redis-lettuce` | `LettuceDistributedResilientModule` | Redis (Lettuce) backend for `resilient-kora-distributed`; extends `LettuceModule` |
| `cache-caffeine` | `CaffeineCacheModule` | `@Cacheable`, `@CachePut`, `@CacheInvalidate`, `@CacheInvalidateAll` (in-process) |
| `cache-redis-lettuce` | `LettuceRedisCacheModule` | Same annotations over Lettuce/Redis |
| `cache-redis-common` | `RedisCacheModule` | Transport-neutral — supplies **no** client; on its own the graph fails to build |
| `scheduling-jdk` | `SchedulingJdkModule` | `@ScheduleJdkAtFixedRate`, `@ScheduleJdkWithFixedDelay`, `@ScheduleJdkOnce`, `@ScheduleJdkWithCron` |
| `scheduling-quartz` | `QuartzModule` | `@ScheduleQuartzWithCron`, `@ScheduleQuartzWithTrigger` (`io.koraframework.scheduling.quartz.annotation`) |
| `scheduling-db-scheduler` | `DbSchedulerModule` | Clustered jobs stored in the database (db-scheduler): `@ScheduleDbOnce`, `@ScheduleDbWithCron`, `@ScheduleDbWithFixedDelay` from `io.koraframework.scheduling.db.scheduler.annotation`; needs a `DataSource` in the graph |
| `validation-module` | `ValidationModule` | `@Valid`, `@Validate` (Kora's own constraints, not Jakarta) |

`cache-redis` does not exist in 2.0. Resilience is Kora's own — no Resilience4j on the classpath.
`@Log` / `@Mdc` live in the logging modules, not a separate AOP artifact.

**Skills:** [`kora-aop-resilient`](../kora-aop-resilient/SKILL.md), [`kora-aop-caching`](../kora-aop-caching/SKILL.md), [`kora-aop-scheduling-jdk`](../kora-aop-scheduling-jdk/SKILL.md), [`kora-aop-scheduling-quartz`](../kora-aop-scheduling-quartz/SKILL.md), [`kora-aop-scheduling-db`](../kora-aop-scheduling-db/SKILL.md), [`kora-aop-validation`](../kora-aop-validation/SKILL.md), [`kora-aop-logging`](../kora-aop-logging/SKILL.md)

### S3 and Camunda

| Artifact | Group | Notes |
|---|---|---|
| `s3-client-aws` | **`io.koraframework`** | `AwsS3ClientModule` — AWS SDK wrapper. **No `@S3`, no models** |
| `s3-client-kora` | **`io.koraframework.experimental`** | `KoraS3ClientModule` + the declarative `@S3` client |
| `camunda-engine-bpmn` | `io.koraframework.experimental` | Camunda 7 embedded BPMN |
| `camunda-rest-undertow` | `io.koraframework.experimental` | Camunda 7 REST API |
| `camunda-zeebe-worker` | `io.koraframework.experimental` | Camunda 8 Zeebe worker (`ZeebeWorkerModule`) |

The S3 group split is the classic trap: `s3-client-aws` is **not** experimental, `s3-client-kora`
is. They are alternatives, not a pair, and each needs an HTTP client transport module alongside it.
`s3-client-minio` does not exist in 2.0.

**Skill:** [`kora-s3`](../kora-s3/SKILL.md)

### Mapping

The language picks the library: **Java → MapStruct, Kotlin → Konvert**, never the other way round.
The Kora extension ships **inside** the aggregate processor (`mapstruct-java-extension` in
`annotation-processors`, `konvert-ksp-extension` in `symbol-processors`) — do not list it yourself.
Add only the third-party half:

- Java: `annotationProcessor "org.mapstruct:mapstruct-processor:1.6.3"` + `implementation "org.mapstruct:mapstruct:1.6.3"`
- Kotlin: `ksp("io.mcarle:konvert:4.5.1")` + `implementation("io.mcarle:konvert-api:4.5.1")` — no `kapt`, no MapStruct

`mapstruct-extension` is a 1.x name and does not exist.

**Skill:** [`kora-mapstruct`](../kora-mapstruct/SKILL.md)

### Testing

| Artifact | Purpose |
|---|---|
| `test-junit5` | `@KoraAppTest` JUnit 5 extension; brings JUnit 5 |

Mockito, MockK and `kotlin-reflect` are `compileOnly` in `test-junit5` — add your own. Black-box
tests are `test-junit5` plus Testcontainers; there is no `test-blackbox` artifact.

**Skills:** [`kora-testing-junit-java`](../kora-testing-junit-java/SKILL.md), [`kora-testing-junit-kotlin`](../kora-testing-junit-kotlin/SKILL.md), [`kora-testing-blackbox`](../kora-testing-blackbox/SKILL.md)

---

## Coming from Kora 1.x

| 1.x | 2.0 |
|---|---|
| `ru.tinkoff.kora:*` | `io.koraframework:*` |
| `ru.tinkoff.kora.experimental:*` | `io.koraframework.experimental:*` — **except** `s3-client-aws`, now plain `io.koraframework` |
| `kora-parent` | `kora-bom` |
| `json-module` | `json-common` |
| `cache-redis` | `cache-redis-lettuce` |
| `mapstruct-extension` | nothing to declare — `mapstruct-java-extension` is inside `annotation-processors`; Kotlin moves to Konvert |
| `http-client-async` | **removed** — use `http-client-jdk` / `-ok` / `-apache` |
| `database-r2dbc`, `database-vertx` | **removed** — no replacement |
| `s3-client-minio` | **removed** — `s3-client-aws` or `s3-client-kora` |
| `UndertowHttpServerModule` | `UndertowPublicHttpServerModule` |

Those artifacts still have **directories** on Maven Central, along with other 1.x/alpha leftovers
(`declarative-logging-annotation-processor`, `declarative-logging-symbol-processor`,
`scheduling-ksp`, `experimental/s3-client`). The listing is cumulative; none of them is in the
`2.0.0.RC2` BOM.

Worse, `io.koraframework:kora-parent` and `io.koraframework:cache-redis` are **published** at
`2.0.0.alpha5`/`2.0.0.alpha6`. A blind `ru.tinkoff.kora` → `io.koraframework` replace that keeps the
old artifact id can therefore *resolve* — silently pinning a pre-release BOM instead of failing.
Rename the **artifact**, not just the group, and never take "the build resolved" as proof.

A rename is not the whole migration: config keys moved too (`db` → `jdbc`,
`publicApiHttpPort` → `port`, `privateApiHttpPort` → `system.port`) and telemetry now defaults to
off. See [`references/core-modules-reference.md`](references/core-modules-reference.md#config-sections-that-changed-in-20).

---

## Externally Versioned Dependencies (not in the BOM)

Pin these yourself. Every one of them fails at **runtime**, not at compile time.

```groovy
dependencies {
    // JDBC driver — database-jdbc ships Hikari, never a driver (database-jdbc-postgres does bring one)
    implementation "org.postgresql:postgresql:42.7.13"

    // Flyway dialect — database-flyway ships flyway-core only
    implementation "org.flywaydb:flyway-database-postgresql:13.9.0"

    testImplementation "io.koraframework:test-junit5"
    testImplementation "org.testcontainers:testcontainers-postgresql:2.0.5"

    // test-junit5 declares these compileOnly — bring your own, new enough for Java 25 Byte Buddy
    testImplementation "org.mockito:mockito-core:5.24.0"   // Java
    testImplementation "io.mockk:mockk:1.14.11"            // Kotlin

    // gRPC test transports must match the gRPC version grpc-server brings
    testImplementation "io.grpc:grpc-inprocess:1.84.0"
}
```

Two coordinate moves that silently orphan a pinned version: Jackson is now
**`tools.jackson.core`** (Jackson 3), and the Cassandra driver is
**`org.apache.cassandra:java-driver-core`**.

**Testcontainers 2.x renamed its modules** — `postgresql` → `testcontainers-postgresql`,
`kafka` → `testcontainers-kafka`, `cassandra` → `testcontainers-cassandra`. Kora does not constrain
Testcontainers; Kora's own build uses `2.0.5`, the reference examples stay on `1.21.4` with the old
names. A 2.x version with 1.x module names does not resolve.

**Depth:** [`references/compatibility-matrix.md`](references/compatibility-matrix.md)

---

## Typical Combinations

### REST API (HTTP server + JSON + metrics)

```groovy
dependencies {
    koraBom platform("io.koraframework:kora-bom:$koraVersion")
    annotationProcessor "io.koraframework:annotation-processors"

    implementation "io.koraframework:http-server-undertow"
    implementation "io.koraframework:json-common"
    implementation "io.koraframework:micrometer-module"
    implementation "io.koraframework:logging-logback"
    implementation "io.koraframework:config-hocon"
}
```

### JDBC service (PostgreSQL + Flyway)

```groovy
dependencies {
    koraBom platform("io.koraframework:kora-bom:$koraVersion")
    annotationProcessor "io.koraframework:annotation-processors"

    implementation "io.koraframework:database-jdbc-postgres"   // database-jdbc + PG mappers + driver
    implementation "io.koraframework:database-flyway"
    implementation "org.flywaydb:flyway-database-postgresql:13.9.0"

    implementation "io.koraframework:logging-logback"
    implementation "io.koraframework:config-hocon"

    testImplementation "io.koraframework:test-junit5"
}
```

### Kafka service (JSON)

```groovy
dependencies {
    koraBom platform("io.koraframework:kora-bom:$koraVersion")
    annotationProcessor "io.koraframework:annotation-processors"

    implementation "io.koraframework:kafka"
    implementation "io.koraframework:json-common"

    implementation "io.koraframework:logging-logback"
    implementation "io.koraframework:config-hocon"
}
```

Full multi-module example: [`assets/build.gradle-full.template`](assets/build.gradle-full.template)

---

## Common Pitfalls

| Symptom | Cause | Fix |
|---|---|---|
| `annotation-processors` fails to resolve (Java) | `koraBom` not `extendsFrom` `annotationProcessor` | Wire the configuration — a `platform` on `implementation` does not reach the processor classpath |
| `symbol-processors` fails to resolve (Kotlin) | Versionless `ksp("io.koraframework:symbol-processors")` | The BOM does not apply to `ksp` — give the dependency an explicit version |
| `Cannot resolve external dependency … because no repositories are defined` | The build has no `repositories` block | Add `repositories { mavenCentral() }` — RC2 resolves from Central alone |
| `Could not find io.koraframework:…:2.0.0-SNAPSHOT` | Snapshot line without the snapshot repo | Pin `2.0.0.RC2` instead, or add `maven { url = "https://central.sonatype.com/repository/maven-snapshots" }` |
| "`cache-redis`/`kora-parent` must still work — I can see the directory on Maven Central" | The Central listing is cumulative and full of 1.x/alpha leftovers | Check what `kora-bom:2.0.0.RC2` constrains, or the artifact's `maven-metadata.xml`, not the directory |
| A group-only rename builds fine, but modules resolve oddly | `io.koraframework:kora-parent` **resolves** at `2.0.0.alpha5`/`alpha6` — the build silently pinned a pre-release BOM | Rename the artifact too: `kora-bom`. "It resolved" is not evidence the coordinate is right |
| `Could not find ru.tinkoff.kora:…` | 1.x coordinate | See [Coming from Kora 1.x](#coming-from-kora-1x) |
| `Could not find io.koraframework:json-module` / `cache-redis` / `kora-parent` | Artifact does not exist in 2.0 | `json-common` / `cache-redis-lettuce` / `kora-bom` |
| `Could not find io.koraframework.experimental:s3-client-aws` | Wrong group | `s3-client-aws` is plain `io.koraframework`; only `s3-client-kora` is experimental |
| `Dependency requires at least JVM runtime version 25` at configuration time | Gradle itself runs on an older JDK | Run Gradle on JDK 25+; the toolchain alone does not fix it |
| `FlywayException: Unsupported Database: PostgreSQL 16.x` | `database-flyway` ships `flyway-core` only | Add `org.flywaydb:flyway-database-postgresql` at the resolved `flyway-core` version |
| `AbstractMethodError … buildClientTransportServers` in tests | gRPC test transport pinned to an older version | Align `grpc-inprocess`/`grpc-netty` with `1.84.0` |
| `Java 25 (69) is not supported by the current version of Byte Buddy` | Old Mockito/MockK; often hidden inside `Application graph failed to initialize with N errors` | Raise `mockito-core` / `mockk`; pin `mockito-core` next to `mockito-kotlin` |
| `Could not find org.testcontainers:postgresql` | Testcontainers 2.x with 1.x module names | `testcontainers-postgresql` etc. (Kora builds with `2.0.5`), or stay on 1.21.4 |
| Hundreds of `package ru.tinkoff.kora… does not exist` in `build/generated/` | Stale generator output after the group rename | `./gradlew clean` then build with `--no-build-cache`; never edit generated code |
| Metrics missing though `micrometer-module` is present | `telemetry.metrics.enabled` defaults to `false` | Enable it per component |
| Service starts green but probes/metrics/LB hit nothing | Stale `publicApiHttpPort`/`privateApiHttpPort` — unrecognised keys are ignored, so each server uses its own default (8080 public, **8085** system) | `httpServer.port` / `httpServer.system.port`. `SystemHttpServerConfig` overrides `port()` to 8085, so the servers do **not** collide on 8080 |
| Module added but nothing wired | `*Module` interface not extended | Extend it on the `@KoraApp` interface |
| `KspTask` no longer compiles | KSP 2 removed the type | `tasks.matching { it.name.startsWith("ksp") }` |

---

## References

| Document | Description |
|---|---|
| [`references/artifact-catalog.md`](references/artifact-catalog.md) | **Every published artifact**, by group, plus renames/removals |
| [`references/bom-usage-reference.md`](references/bom-usage-reference.md) | BOM setup for Java and Kotlin, multi-module, version verification |
| [`references/annotation-processors-reference.md`](references/annotation-processors-reference.md) | Processors + KSP 2, aggregate vs per-domain, generated-code locations |
| [`references/compatibility-matrix.md`](references/compatibility-matrix.md) | JDK derivation, Kotlin/KSP/Gradle, third-party and externally-versioned deps |
| [`references/core-modules-reference.md`](references/core-modules-reference.md) | Core modules, 2.0 config keys, a minimal `@KoraApp` |

## See Also

- [`kora-project-setup-java`](../kora-project-setup-java/SKILL.md) — Java Gradle scaffolding
- [`kora-project-setup-kotlin`](../kora-project-setup-kotlin/SKILL.md) — Kotlin Gradle scaffolding
- [`kora-di-compile`](../kora-di-compile/SKILL.md) — compile-time DI (`@KoraApp`, `@Component`, `@Module`)
- [`kora-config-hocon`](../kora-config-hocon/SKILL.md) — typed `@ConfigSource` configuration
