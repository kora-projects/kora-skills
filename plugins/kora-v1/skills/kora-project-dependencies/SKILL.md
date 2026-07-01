---
name: kora-project-dependencies
description: "Catalog of Kora Framework Gradle artifacts plus a project generator. Covers the kora-parent BOM, annotation processors (Java annotation-processors) and KSP (Kotlin symbol-processors), the koraBom configuration with extendsFrom, real module artifact names (http-server-undertow, http-client-ok, database-jdbc, kafka, micrometer-module, opentelemetry-tracing-exporter-grpc, resilient-kora, cache-caffeine, validation-module, s3-client-aws), externally versioned deps (JDBC drivers, Testcontainers), and which versions the BOM owns. Use when wiring a build.gradle / build.gradle.kts, choosing Kora modules, fixing \"dependency not found\" or transitive version conflicts, or scaffolding a new service. Not for writing DI/HTTP/repository code."
---

# Kora Project Dependencies — Module Catalog

**BOM:** `ru.tinkoff.kora:kora-parent` (pin the version once; every Kora artifact inherits it)
**Java:** 21+ (examples build on JDK 21) | **Kotlin:** 1.9.25 | **KSP:** 1.9.25-1.0.20 | **Gradle:** 9+

> **Critical:** Always import the `kora-parent` BOM. It aligns every Kora module to one version and pins transitive libraries (Jackson, OkHttp, Undertow, Micrometer, OpenTelemetry, HikariCP, Kafka client, gRPC, Caffeine, Resilience4j). **Never put a version on a `ru.tinkoff.kora:*` artifact** — the BOM does it.

Read this first when:
- Selecting which Kora modules to include in a build
- Setting up the BOM and the `koraBom` configuration in `build.gradle` / `build.gradle.kts`
- Configuring annotation processors (Java) or KSP (Kotlin)
- Resolving "Required dependency not found" or transitive version conflicts
- Scaffolding a new project (see Project Generator below)

**NOT when:** writing DI code (→ `kora-di-compile`), HTTP controllers (→ `kora-http-server`), repositories (→ `kora-database-jdbc`), or Kafka handlers (→ `kora-kafka-consumer`).

---

## Quick Start — BOM Setup

Pin the BOM version in `gradle.properties` and reference it via `$koraVersion`.

### gradle.properties

```properties
koraVersion=1.2.17
```

### Java (build.gradle)

The `koraBom` configuration must feed `annotationProcessor`, `compileOnly`, `implementation` (and `api`/`testImplementation`/`testAnnotationProcessor` if used) via `extendsFrom`, otherwise the BOM does not apply to the processor classpath.

```groovy
plugins {
    id "java"
    id "application"
}

java {
    toolchain {
        languageVersion = JavaLanguageVersion.of(21)
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
    koraBom platform("ru.tinkoff.kora:kora-parent:$koraVersion")
    annotationProcessor "ru.tinkoff.kora:annotation-processors"

    implementation "ru.tinkoff.kora:http-server-undertow"
    implementation "ru.tinkoff.kora:json-module"
    implementation "ru.tinkoff.kora:config-hocon"
    implementation "ru.tinkoff.kora:logging-logback"

    testImplementation "ru.tinkoff.kora:test-junit5"
}
```

### Kotlin (build.gradle.kts)

Kotlin uses the KSP plugin and the `symbol-processors` artifact instead of `annotationProcessor`.

```kotlin
plugins {
    application
    kotlin("jvm") version "1.9.25"
    id("com.google.devtools.ksp") version "1.9.25-1.0.20"
}

val koraBom: Configuration by configurations.creating
configurations {
    ksp.get().extendsFrom(koraBom)
    compileOnly.get().extendsFrom(koraBom)
    api.get().extendsFrom(koraBom)
    implementation.get().extendsFrom(koraBom)
}

val koraVersion: String by project
dependencies {
    koraBom(platform("ru.tinkoff.kora:kora-parent:$koraVersion"))
    ksp("ru.tinkoff.kora:symbol-processors")

    implementation("ru.tinkoff.kora:http-server-undertow")
    implementation("ru.tinkoff.kora:json-module")
    implementation("ru.tinkoff.kora:config-hocon")
    implementation("ru.tinkoff.kora:logging-logback")

    testImplementation("ru.tinkoff.kora:test-junit5")
}

kotlin {
    jvmToolchain {
        languageVersion.set(JavaLanguageVersion.of(21))
        vendor.set(JvmVendorSpec.ADOPTIUM)
    }
}
```

**Depth:** [`references/bom-usage-reference.md`](references/bom-usage-reference.md), [`references/annotation-processors-reference.md`](references/annotation-processors-reference.md)

---

## Project Generator

`scripts/generate_project.py` scaffolds a compile-ready project (build script, `@KoraApp`, HOCON config, sample controller/repository/Kafka handlers) for a chosen set of modules.

```bash
# List available module keys
python scripts/generate_project.py --list-modules

# Java REST API + PostgreSQL
python scripts/generate_project.py \
  --name my-service --package com.example --lang java \
  --modules http-server,jdbc-postgres,metrics

# Kotlin Kafka service
python scripts/generate_project.py \
  --name kafka-service --package com.example --lang kotlin \
  --modules kafka,metrics
```

The generator emits real Kora APIs only: `@KoraApp` from `ru.tinkoff.kora.common`, `@HttpController` + `@HttpRoute`, `@Repository` + `extends JdbcRepository`, `@KafkaListener`/`@KafkaPublisher`, and a `httpServer { ... }` / `db { ... }` HOCON config.

**Details:** [`scripts/generate_project.py`](scripts/generate_project.py)

---

## Core Modules (almost every service)

| Artifact | Module interface | Purpose |
|----------|------------------|---------|
| `ru.tinkoff.kora:config-hocon` | `HoconConfigModule` | HOCON config (or `config-yaml` → `YamlConfigModule`) |
| `ru.tinkoff.kora:json-module` | `JsonModule` | JSON (de)serialization for DTOs, HTTP, Kafka |
| `ru.tinkoff.kora:logging-logback` | `LogbackModule` | SLF4J via Logback |
| `ru.tinkoff.kora:annotation-processors` | — | Java annotation processor (mandatory, Java) |
| `ru.tinkoff.kora:symbol-processors` | — | KSP symbol processor (mandatory, Kotlin) |

**Depth:** [`references/core-modules-reference.md`](references/core-modules-reference.md)

---

## Module Catalog

Artifact names below are the **real** ones verified against the Kora docs and example apps. Note the group is `ru.tinkoff.kora` except for **experimental** modules (S3, Camunda), which use `ru.tinkoff.kora.experimental`.

### HTTP

| Artifact | Module interface | Notes |
|----------|------------------|-------|
| `http-server-undertow` | `UndertowHttpServerModule` | Undertow-backed HTTP server |
| `http-client-ok` | `OkHttpClientModule` | OkHttp transport |
| `http-client-async` | `AsyncHttpClientModule` | Async (Netty) transport |
| `http-client-jdk` | `JdkHttpClientModule` | JDK `HttpClient` transport |

HTTP-server/client auth (BasicAuth, Bearer, API key) ships inside these artifacts as `BasicAuthModule`, `BearerAuthModule`, `ApiKeyAuthModule`. Authorization is configured in code, not via a separate auth artifact.

**Skills:** [`kora-http-server`](../kora-http-server/SKILL.md), [`kora-http-client`](../kora-http-client/SKILL.md)

### Database

| Artifact | Module interface | Notes |
|----------|------------------|-------|
| `database-jdbc` | `JdbcDatabaseModule` | JDBC repositories (recommended path) |
| `database-cassandra` | `CassandraDatabaseModule` | Cassandra CQL |
| `database-flyway` | `FlywayJdbcDatabaseModule` | Flyway SQL migrations |
| `database-liquibase` | `LiquibaseJdbcDatabaseModule` | Liquibase SQL migrations |
| `database-r2dbc` | — | R2DBC (not recommended; prefer JDBC) |
| `database-vertx` | — | Vert.x SQL (not recommended; prefer JDBC) |

JDBC drivers are **not** in the BOM — version them yourself (see Externally Versioned Dependencies).

**Skills:** [`kora-database-jdbc`](../kora-database-jdbc/SKILL.md), [`kora-database-cassandra`](../kora-database-cassandra/SKILL.md), [`kora-database-migration`](../kora-database-migration/SKILL.md)

### Messaging (Kafka)

| Artifact | Module interface | Notes |
|----------|------------------|-------|
| `kafka` | `KafkaModule` | Producers (`@KafkaPublisher`) and consumers (`@KafkaListener`) |

There is a single `kafka` artifact — there are no separate `kafka-producer`/`kafka-consumer` artifacts.

**Skills:** [`kora-kafka-producer`](../kora-kafka-producer/SKILL.md), [`kora-kafka-consumer`](../kora-kafka-consumer/SKILL.md)

### Telemetry

| Artifact | Module interface | Notes |
|----------|------------------|-------|
| `micrometer-module` | `MetricsModule` | Micrometer metrics; Prometheus scrape served on the **private** HTTP port |
| `opentelemetry-tracing-exporter-grpc` | `OpentelemetryGrpcExporterModule` | OTLP/gRPC trace exporter |
| `opentelemetry-tracing-exporter-http` | `OpentelemetryHttpExporterModule` | OTLP/HTTP trace exporter |

Probes (`ProbesModule`, readiness/liveness on the private port) and metrics both require an HTTP server module. There is no standalone `probes` artifact in the BOM; probes come with the HTTP server.

**Skills:** [`kora-telemetry-metrics`](../kora-telemetry-metrics/SKILL.md), [`kora-telemetry-tracing`](../kora-telemetry-tracing/SKILL.md), [`kora-telemetry-logging`](../kora-telemetry-logging/SKILL.md)

### gRPC

| Artifact | Module interface |
|----------|------------------|
| `grpc-server` | `GrpcServerModule` |
| `grpc-client` | `GrpcClientModule` |

**Skills:** [`kora-grpc-server`](../kora-grpc-server/SKILL.md), [`kora-grpc-client`](../kora-grpc-client/SKILL.md)

### OpenAPI

| Artifact | Module interface | Notes |
|----------|------------------|-------|
| `openapi-generator` | — | OpenAPI codegen (Gradle plugin `org.openapi.generator`, `generatorName = "kora"`) |
| `openapi-management` | `OpenApiManagementModule` | Swagger UI / RapiDoc, spec publishing |

**Skills:** [`kora-openapi-generator-server`](../kora-openapi-generator-server/SKILL.md), [`kora-openapi-generator-client`](../kora-openapi-generator-client/SKILL.md), [`kora-openapi-management`](../kora-openapi-management/SKILL.md)

### AOP

| Artifact | Module interface | Annotations |
|----------|------------------|-------------|
| `resilient-kora` | `ResilientModule` | `@Retry`, `@CircuitBreaker`, `@Timeout`, `@Fallback` |
| `cache-caffeine` | `CaffeineCacheModule` | `@Cacheable`, `@CachePut`, `@CacheInvalidate` (in-memory) |
| `cache-redis` | `RedisCacheModule` | same annotations over Lettuce/Redis |
| `scheduling-jdk` | `SchedulingJdkModule` | `@ScheduleAtFixedRate`, `@ScheduleWithCron` |
| `scheduling-quartz` | `QuartzModule` | Quartz-backed cron |
| `validation-module` | `ValidationModule` | `@Valid`, `@Validate` (JSR-380-style) |

The `@Log` / `@Mdc` logging aspect lives in the logging modules (`logging-logback`/`logging-common`), not a separate AOP artifact.

**Skills:** [`kora-aop-resilient`](../kora-aop-resilient/SKILL.md), [`kora-aop-caching`](../kora-aop-caching/SKILL.md), [`kora-aop-scheduling-jdk`](../kora-aop-scheduling-jdk/SKILL.md), [`kora-aop-scheduling-quartz`](../kora-aop-scheduling-quartz/SKILL.md), [`kora-aop-validation`](../kora-aop-validation/SKILL.md), [`kora-aop-logging`](../kora-aop-logging/SKILL.md)

### Other

| Artifact | Module interface | Notes |
|----------|------------------|-------|
| `ru.tinkoff.kora.experimental:s3-client-aws` | `AwsS3ClientModule` | S3 over AWS SDK (`@S3.Client`) |
| `ru.tinkoff.kora.experimental:s3-client-minio` | `MinioS3ClientModule` | S3 over MinIO |
| `ru.tinkoff.kora.experimental:camunda-engine-bpmn` | `CamundaEngineBpmnModule` | Camunda 7 embedded BPMN |
| `ru.tinkoff.kora.experimental:camunda-zeebe-worker` | `Camunda8WorkerModule` | Camunda 8 Zeebe worker |
| `soap-client` | `SoapClientModule` | SOAP client |

MapStruct integration (`MapStructModule`) uses the upstream `org.mapstruct:mapstruct` + `org.mapstruct:mapstruct-processor` artifacts plus the Kora annotation processor; there is no `ru.tinkoff.kora:mapper-mapstruct` artifact. GraalVM native image is a build-plugin concern (`org.graalvm.buildtools.native`), not a Kora artifact.

**Skill:** [`kora-mapstruct`](../kora-mapstruct/SKILL.md)

### Testing

| Artifact | Purpose |
|----------|---------|
| `test-junit5` | `@KoraAppTest` JUnit 5 extension (component tests) |

Black-box / E2E tests use `test-junit5` together with Testcontainers — there is no separate `test-blackbox` artifact.

**Skills:** [`kora-testing-junit-java`](../kora-testing-junit-java/SKILL.md), [`kora-testing-junit-kotlin`](../kora-testing-junit-kotlin/SKILL.md), [`kora-testing-blackbox`](../kora-testing-blackbox/SKILL.md)

---

## Externally Versioned Dependencies (not in the BOM)

These are not Kora artifacts; pin their versions explicitly.

```groovy
dependencies {
    // JDBC drivers
    implementation "org.postgresql:postgresql:42.7.7"
    runtimeOnly    "com.mysql:mysql-connector-j:8.3.0"

    // Testing
    testImplementation "ru.tinkoff.kora:test-junit5"
    testImplementation "org.testcontainers:junit-jupiter:1.21.4"
    testImplementation "io.goodforgod:testcontainers-extensions-postgres:0.13.1"
    testImplementation "org.mockito:mockito-core:5.14.2"   // Java mocks
    testImplementation "io.mockk:mockk:1.13.13"            // Kotlin mocks
}
```

---

## Versions the BOM Owns (do not override)

| Library | Purpose |
|---------|---------|
| Jackson | JSON (de)serialization (`json-module`) |
| OkHttp | HTTP client transport (`http-client-ok`) |
| Undertow | HTTP server (`http-server-undertow`) |
| Micrometer | Metrics (`micrometer-module`) |
| OpenTelemetry | Tracing exporters |
| Logback | SLF4J logging (`logging-logback`) |
| HikariCP | JDBC connection pool (`database-jdbc`) |
| Kafka client | Messaging (`kafka`) |
| gRPC | gRPC modules |
| Caffeine | In-memory cache (`cache-caffeine`) |
| Resilience4j | Resilience (`resilient-kora`) |

```groovy
// WRONG — fights the BOM, can break Kora at runtime
implementation "com.fasterxml.jackson.core:jackson-databind:2.16.0"

// RIGHT — let the BOM pin Jackson
implementation "ru.tinkoff.kora:json-module"
```

If you truly must change a transitive version, use `resolutionStrategy { force "..." }` rather than declaring a raw version.

---

## Typical Combinations

### REST API (HTTP server + JSON + metrics)

```groovy
dependencies {
    koraBom platform("ru.tinkoff.kora:kora-parent:$koraVersion")
    annotationProcessor "ru.tinkoff.kora:annotation-processors"

    implementation "ru.tinkoff.kora:http-server-undertow"
    implementation "ru.tinkoff.kora:json-module"
    implementation "ru.tinkoff.kora:micrometer-module"
    implementation "ru.tinkoff.kora:logging-logback"
    implementation "ru.tinkoff.kora:config-hocon"
}
```

### JDBC service (PostgreSQL + Flyway)

```groovy
dependencies {
    koraBom platform("ru.tinkoff.kora:kora-parent:$koraVersion")
    annotationProcessor "ru.tinkoff.kora:annotation-processors"

    implementation "ru.tinkoff.kora:database-jdbc"
    implementation "ru.tinkoff.kora:database-flyway"
    implementation "org.postgresql:postgresql:42.7.7"

    implementation "ru.tinkoff.kora:logging-logback"
    implementation "ru.tinkoff.kora:config-hocon"

    testImplementation "ru.tinkoff.kora:test-junit5"
    testImplementation "io.goodforgod:testcontainers-extensions-postgres:0.13.1"
}
```

### Kafka service (JSON)

```groovy
dependencies {
    koraBom platform("ru.tinkoff.kora:kora-parent:$koraVersion")
    annotationProcessor "ru.tinkoff.kora:annotation-processors"

    implementation "ru.tinkoff.kora:kafka"
    implementation "ru.tinkoff.kora:json-module"

    implementation "ru.tinkoff.kora:logging-logback"
    implementation "ru.tinkoff.kora:config-hocon"
}
```

Full multi-module example: [`assets/build.gradle-full.template`](assets/build.gradle-full.template)

---

## Common Pitfalls

| Symptom | Cause | Fix |
|---------|-------|-----|
| "Required dependency not found" for a generated impl | Processor not on the classpath | Add `annotation-processors` (Java) or `symbol-processors` (Kotlin); ensure `koraBom` is `extendsFrom` the processor configuration |
| Generated `*ComponentImpl`/`*RepositoryImpl` missing | Processor never ran | `./gradlew clean classes` — annotation processors run before normal compile |
| Version conflict on Jackson/OkHttp/Undertow | A raw version was declared | Remove the explicit version; let the BOM own it (or use `resolutionStrategy.force`) |
| Module not picked up at runtime | Artifact added but interface not extended | `extends`/implement the matching `*Module` on the `@KoraApp` interface |
| Wrong artifact name (e.g. `http-client-okhttp`, `resilient`, `validation`) | Guessed name | Use the verified names: `http-client-ok`, `resilient-kora`, `validation-module` |
| KSP fails after Kotlin upgrade | KSP/Kotlin mismatch | KSP version must match the Kotlin version (e.g. `1.9.25-1.0.20`) |

---

## References

| Document | Description |
|----------|-------------|
| [`references/bom-usage-reference.md`](references/bom-usage-reference.md) | BOM setup, `koraBom` configuration, multi-module, version verification |
| [`references/annotation-processors-reference.md`](references/annotation-processors-reference.md) | Java annotation processors + Kotlin KSP setup, generated-code locations |
| [`references/core-modules-reference.md`](references/core-modules-reference.md) | Core modules (config, JSON, logging) and a minimal `@KoraApp` |
| [`references/compatibility-matrix.md`](references/compatibility-matrix.md) | Java / Kotlin / KSP / Gradle compatibility |

## See Also

- [`kora-project-setup-java`](../kora-project-setup-java/SKILL.md) — Java Gradle scaffolding
- [`kora-project-setup-kotlin`](../kora-project-setup-kotlin/SKILL.md) — Kotlin Gradle scaffolding
- [`kora-di-compile`](../kora-di-compile/SKILL.md) — compile-time DI (`@KoraApp`, `@Component`, `@Module`)
- [`kora-config-hocon`](../kora-config-hocon/SKILL.md) — typed `@ConfigSource` configuration
