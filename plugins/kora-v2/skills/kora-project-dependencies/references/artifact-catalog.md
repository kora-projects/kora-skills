# Kora 2.0 Artifact Catalog

Every artifact Kora 2.0 publishes, by group. This list is exhaustive: if a name is not here, it is
not published. Do not guess a coordinate — look it up.

It is the set `io.koraframework:kora-bom:2.0.0.RC2` constrains — **100 modules** (every leaf project
of the framework's own `settings.gradle` outside `internal/`, plus `kora-bom` itself).

## Contents

- [Groups](#groups)
- [Checking a coordinate](#checking-a-coordinate)
  - [Worse: some of them still resolve](#worse-some-of-them-still-resolve)
- [Core and processors](#core-and-processors)
- [Config](#config)
- [JSON](#json)
- [HTTP](#http)
- [Database](#database)
- [Messaging](#messaging)
- [gRPC and SOAP](#grpc-and-soap)
- [Telemetry and logging](#telemetry-and-logging)
- [Cache and Redis](#cache-and-redis)
- [AOP: resilience, scheduling, validation](#aop-resilience-scheduling-validation)
- [Mapping extensions](#mapping-extensions)
- [OpenAPI](#openapi)
- [S3](#s3)
- [Camunda (experimental)](#camunda-experimental)
- [Testing](#testing)
- [Not published](#not-published)
- [Renamed and removed since 1.x](#renamed-and-removed-since-1x)

---

## Groups

| Group | Contents |
|---|---|
| `io.koraframework` | Everything except the `experimental/` tree |
| `io.koraframework.experimental` | `s3-client-kora`, `s3-client-annotation-processor`, `s3-client-symbol-processor`, and all `camunda-*` |

`s3-client-aws` is the trap: it lives outside `experimental/`, so its group is **`io.koraframework`**,
while `s3-client-kora` right next to it in the docs is **`io.koraframework.experimental`**.

BOM: **`io.koraframework:kora-bom`**. The current release is **`2.0.0.RC2`** (Maven Central). `2.0.0-SNAPSHOT` is the `master` development line and needs the
Sonatype snapshot repository; do not pin it in a new project.

---

## Checking a coordinate

**The Maven Central directory listing is not the artifact list.**
`repo1.maven.org/maven2/io/koraframework/` is cumulative, so 1.x and alpha leftovers still have
directories there: `kora-parent`, `cache-redis`, `declarative-logging-annotation-processor`,
`declarative-logging-symbol-processor`, `scheduling-ksp`, `experimental/s3-client`. **None of them is
in the 2.0.0.RC2 BOM.**

### Worse: some of them still resolve

`io.koraframework:kora-parent` and `io.koraframework:cache-redis` are published at **`2.0.0.alpha5`
and `2.0.0.alpha6`**. So a blind group-only rename —
`ru.tinkoff.kora:kora-parent` → `io.koraframework:kora-parent` — does **not** fail with "could not
find". At an alpha version it resolves, and the build silently pins a **pre-release BOM** whose
module set predates the 2.0 renames.

```groovy
// Resolves. Also wrong: an alpha BOM, not the release.
koraBom platform("io.koraframework:kora-parent:2.0.0.alpha6")

// Correct
koraBom platform("io.koraframework:kora-bom:2.0.0.RC2")
```

`kora-parent` has **no** `2.0.0.RC*` version (that request is a 404), so the failure mode depends
entirely on which version string survived the rename. Treat "it resolved" as no evidence at all —
check the artifact id, not just the build result.

Two reliable checks:

```bash
# What the release actually constrains — the authority behind this file
curl -s https://repo1.maven.org/maven2/io/koraframework/kora-bom/2.0.0.RC2/kora-bom-2.0.0.RC2.pom

# Whether one artifact has a 2.0.x version at all
curl -s https://repo1.maven.org/maven2/io/koraframework/<artifact>/maven-metadata.xml
```

---

## Core and processors

| Artifact | Purpose |
|---|---|
| `kora-bom` | Bill of materials — import as a `platform`, pins every module below |
| `common` | `@KoraApp`, `@Component`, `@Module`, `@Tag`, `@Root`, `@Conditional`, `@FactoryModule`, `@Mapping` (`io.koraframework.common.annotation`) |
| `application-graph` | `KoraApplication`, `Graph`, `All`, `ValueOf`, `Lifecycle`, `GraphCondition`, `TypeRef` |
| **`annotation-processors`** | **Java: the one aggregate processor.** Pulls in every `*-annotation-processor` plus `mapstruct-java-extension` |
| **`symbol-processors`** | **Kotlin: the one aggregate KSP processor.** Pulls in every `*-symbol-processor` plus `konvert-ksp-extension` |
| `annotation-processor-common`, `symbol-processor-common` | Building blocks for writing your own processor |
| `kora-app-annotation-processor`, `kora-app-symbol-processor` | `@KoraApp` graph generation only |
| `aop-annotation-processor`, `aop-symbol-processor` | AOP proxy generation only |
| `netty-common` | Shared Netty plumbing (transitive) |

Per-domain processors exist for every domain below (`config-`, `json-`, `http-server-`,
`http-client-`, `soap-client-`, `database-`, `kafka-`, `scheduling-`, `resilient-`, `cache-`,
`validation-`, `logging-`, `grpc-client-`, `s3-client-`, `camunda-zeebe-worker-`, each in
`-annotation-processor` and `-symbol-processor` form). **A normal service adds only the aggregate**
(`annotation-processors` / `symbol-processors`). Reach for an individual processor only when a
library module must generate code for one domain and you want to keep its processor classpath small.

---

## Config

| Artifact | Module interface | Notes |
|---|---|---|
| `config-common` | — | `@ConfigSource`, `@ConfigMapper`, `ConfigValueMapper` (transitive) |
| `config-hocon` | `HoconConfigModule` | `application.conf`; brings `com.typesafe:config` |
| `config-yaml` | `YamlConfigModule` | `application.yaml`; brings `org.snakeyaml:snakeyaml-engine` |

Pick exactly one of `config-hocon` / `config-yaml`.

---

## JSON

| Artifact | Module interface | Notes |
|---|---|---|
| **`json-common`** | `JsonModule` (`io.koraframework.json.common.JsonModule`) | Compile-time `@Json` readers/writers. Brings `tools.jackson.core:jackson-core` |
| `jackson-module` | `JacksonModule` | Reflective Jackson databind fallback; brings `tools.jackson.core:jackson-databind` |

`json-module` **does not exist in 2.0** — the artifact is `json-common`, and the module interface
moved from `io.koraframework.json.module.JsonModule` to `io.koraframework.json.common.JsonModule`.

Jackson is on the **`tools.jackson.core`** coordinates (Jackson 3) in 2.0, not `com.fasterxml.jackson.core`.

---

## HTTP

| Artifact | Module interface | Notes |
|---|---|---|
| `http-common` | — | `HttpMethod`, `HttpResponseEntity`, `@HttpRoute`/`@Path`/`@Query`/`@Header`/`@Cookie`/`@InterceptWith` |
| `http-server-common` | — | `HttpServerInterceptor`, request/response contracts, the system API |
| `http-server-undertow` | **`UndertowPublicHttpServerModule`** | Public server on `httpServer`. It **extends** `UndertowSystemHttpServerModule`, so extending it also gives you the system server on `httpServer.system` (metrics, readiness, liveness) |
| `http-client-common` | — | `@HttpClient`, `HttpClientResponseException`, token providers |
| `http-client-ok` | `OkHttpClientModule` | OkHttp transport |
| `http-client-jdk` | `JdkHttpClientModule` | JDK `HttpClient` transport |
| **`http-client-apache`** | `ApacheHttpClientModule` | Apache HttpClient 5 transport — the one the reference S3 and SOAP examples use |

There is no `UndertowHttpServerModule` in 2.0 and no separate auth artifact: server auth is
`HttpServerPrincipalExtractor` in `http-server-common`, client auth is `HttpClientTokenProvider` in
`http-client-common`. Readiness/liveness are served by the system server, not by a `ProbesModule`.

`http-client-async` was removed with no replacement — use `http-client-jdk`, `http-client-ok`, or
`http-client-apache`.

---

## Database

| Artifact | Module interface | Brings | Notes |
|---|---|---|---|
| `database-common` | — | — | `@Repository`, `@Query`, `@Id`, `@Column`, `@Table`, `UpdateCount` |
| `database-jdbc` | `JdbcDatabaseModule` | HikariCP | Config section is **`jdbc`** (was `db` in 1.x). **No JDBC driver** — the app adds it |
| `database-cassandra` | `CassandraDatabaseModule` | `org.apache.cassandra:java-driver-core` | Driver ships with the module; note the group moved off `com.datastax.oss` |
| `database-flyway` | `FlywayJdbcDatabaseModule` | `org.flywaydb:flyway-core` only | **The app must add its own dialect artifact** (see below) |
| `database-liquibase` | `LiquibaseJdbcDatabaseModule` | `org.liquibase:liquibase-core` | |
| **`database-jdbc-postgres`** | **`PostgresJdbcDatabaseModule`** (extends `JdbcDatabaseModule`) | `database-jdbc`, `json-common`, `org.postgresql:postgresql` | PostgreSQL mappers: `@Pg` arrays / `List<T>` / intervals / `PgRange<T>`, `@PgJson` / `@PgJsonb`. Use it *instead of* `database-jdbc` for PostgreSQL — see [postgres mappers](../../kora-database-jdbc/references/postgres-mappers-reference.md) |

Flyway default `locations` is `db/migration`, so scripts go in `src/main/resources/db/migration/`.

`database-r2dbc` and `database-vertx` were removed in 2.0. Repository contracts are synchronous;
there is no reactive replacement.

---

## Messaging

| Artifact | Module interface | Notes |
|---|---|---|
| `kafka` | `KafkaModule` | One artifact covers `@KafkaPublisher` and `@KafkaListener`; brings `org.apache.kafka:kafka-clients` |
| **`jms`** | `JmsConsumerModule` | JMS consumers; brings `javax.jms:javax.jms-api` (the JMS provider itself is the app's dependency) |

There are no `kafka-producer` / `kafka-consumer` artifacts.

---

## gRPC and SOAP

| Artifact | Module interface | Notes |
|---|---|---|
| `grpc-server` | `GrpcServerModule` | Brings `grpc-stub` + `grpc-okhttp` at gRPC `1.84.0` |
| `grpc-client` | `GrpcClientModule` | Same transport family |
| `soap-client` | `SoapClientModule` | Needs an HTTP client transport module alongside it |

gRPC test transports (`grpc-inprocess`, `grpc-netty`, `grpc-testing`) are the app's own dependencies
and **must be pinned to the same gRPC version the module brings**. So is `protoc` — pin `3.25.3` to
match the `protobuf-java:3.25.9` that arrives transitively through `grpc-protobuf`, not the `4.36.2`
in Kora's version catalog, which is `compileOnly` inside Kora's own build and never reaches you. See
[compatibility-matrix.md](compatibility-matrix.md#externally-versioned-dependencies).

---

## Telemetry and logging

| Artifact | Module interface | Notes |
|---|---|---|
| `telemetry-common` | — | `TelemetryConfig` — the `logging`/`metrics`/`tracing` sub-sections every component exposes |
| `micrometer-common`, `micrometer-module` | `MetricsModule` | Micrometer + Prometheus registry; scrape served on the system server's `metricsPath` (`/metrics`) |
| `opentelemetry-common`, `opentelemetry-tracing` | — | Tracing plumbing (transitive) |
| `opentelemetry-tracing-exporter-grpc` | `OpentelemetryGrpcExporterModule` | OTLP/gRPC exporter |
| `opentelemetry-tracing-exporter-http` | `OpentelemetryHttpExporterModule` | OTLP/HTTP exporter |
| `logging-common` | — | `@Log`, `@Mdc` and their processors' runtime |
| `logging-logback` | `LogbackModule` | SLF4J via Logback |
| **`logging-logback-json`** | — (`LogbackEncoderFactory` SPI) | JSON console encoder. On the classpath it wins the automatic encoder choice; `kora.logging.encoder` (env `KORA_LOGGING_ENCODER`) selects another, a Logback config file bypasses the selection — see [`kora-telemetry-logging`](../../kora-telemetry-logging/SKILL.md) |

**Adding `micrometer-module` is not enough to get metrics.** In 2.0
`TelemetryConfig.MetricsConfig.enabled()` and `LoggingConfig.enabled()` both default to `false`
(only `tracing` defaults to `true`), so each component needs it turned on explicitly:

```hocon
httpServer { telemetry.logging.enabled = true, telemetry.metrics.enabled = true }
jdbc       { telemetry.metrics.enabled = true }
```

---

## Cache and Redis

| Artifact | Module interface | Notes |
|---|---|---|
| `cache-common` | — | `@Cacheable`, `@CachePut`, `@CacheInvalidate`, `@CacheInvalidateAll` |
| `cache-caffeine` | `CaffeineCacheModule` | In-process; brings Caffeine |
| **`cache-redis-common`** | `RedisCacheModule` | Transport-neutral. **Supplies no `RedisCacheClient`** — on its own the graph will not build |
| **`cache-redis-lettuce`** | **`LettuceRedisCacheModule`** | The one to depend on for Redis. Pulls `cache-redis-common` + `redis-lettuce` |
| **`redis-lettuce`** | — | Raw Lettuce client wiring, usable without the cache aspects |

`cache-redis` does not exist in 2.0.

---

## AOP: resilience, scheduling, validation

| Artifact | Module interface | Annotations |
|---|---|---|
| `resilient-kora` | `ResilientModule` | `@CircuitBreakable`, `@Retryable`, `@Timeout`, `@RateLimited`, `@Fallback` — all take a **specification interface**, not a string name |
| **`resilient-kora-distributed`** | — | Distributed rate limiter / retry budget shared across instances: `@RateLimiterDistributedSpec`, `DistributedRetryBudgetFactory`. Backend-neutral — add a backend module — see [`kora-aop-resilient`](../../kora-aop-resilient/SKILL.md) |
| **`resilient-kora-distributed-redis-lettuce`** | `LettuceDistributedResilientModule` | Redis backend for the above over Lettuce; pulls `resilient-kora-distributed` + `redis-lettuce` |
| `scheduling-common` | — | Shared scheduling runtime |
| `scheduling-jdk` | `SchedulingJdkModule` | `@ScheduleJdkAtFixedRate`, `@ScheduleJdkWithFixedDelay`, `@ScheduleJdkOnce`, `@ScheduleJdkWithCron` |
| `scheduling-quartz` | `QuartzModule` | `@ScheduleQuartzWithCron`, `@ScheduleQuartzWithTrigger` (`io.koraframework.scheduling.quartz.annotation`); brings Quartz |
| **`scheduling-db-scheduler`** | `DbSchedulerModule` | Clustered, DB-persisted jobs on `com.github.kagkarlsson:db-scheduler`: `@ScheduleDbOnce`, `@ScheduleDbWithCron`, `@ScheduleDbWithFixedDelay` (`io.koraframework.scheduling.db.scheduler.annotation`). Needs a `DataSource` in the graph — see [`kora-aop-scheduling-db`](../../kora-aop-scheduling-db/SKILL.md) |
| `validation-common`, `validation-module` | `ValidationModule` | `@Valid`, `@Validate` and Kora's own constraints |

Resilience in 2.0 carries **no Resilience4j dependency** — the implementations are Kora's own.

---

## Mapping extensions

These are compile-time extensions, not runtime modules. They are already inside the aggregate
processors, so a normal service never lists them. **Java maps with MapStruct, Kotlin with Konvert** —
never the other way round, and never `kapt`:

| Language | Artifact | Inside | You still add |
|---|---|---|---|
| Java | **`mapstruct-java-extension`** | `annotation-processors` | `implementation "org.mapstruct:mapstruct"` + `annotationProcessor "org.mapstruct:mapstruct-processor"` |
| Kotlin | **`konvert-ksp-extension`** | `symbol-processors` | `implementation("io.mcarle:konvert-api")` + `ksp("io.mcarle:konvert")` |

`symbol-processors` also contains `mapstruct-ksp-extension`; it is not a supported mapping path.
`mapstruct-extension` (the 1.x name) does not exist.

The third-party libraries are yours to version — `kora-bom` does not constrain them. Kora's catalog
names MapStruct `1.6.3` (what its extension is tested against) while the reference Java examples pin
`1.5.5.Final`; Konvert is `4.5.1` in both. See [`kora-mapstruct`](../../kora-mapstruct/SKILL.md).

---

## OpenAPI

| Artifact | Where it goes | Notes |
|---|---|---|
| `openapi-generator` | **`buildscript { dependencies { classpath ... } }`** | The `kora` generator for the `org.openapi.generator` Gradle plugin. Because it lands on the buildscript classpath it is resolved by the JVM running Gradle — see [compatibility-matrix.md](compatibility-matrix.md) |
| `openapi-management` | `implementation` | `OpenApiManagementModule` — serves the spec plus Swagger UI / Scalar over the HTTP server |

Only four generator modes exist in 2.0: `java-client`, `java-server`, `kotlin-client`, `kotlin-server`.

---

## S3

| Artifact | Group | Contents |
|---|---|---|
| `s3-client-aws` | **`io.koraframework`** | `AwsS3ClientModule` — an AWS SDK wrapper. Hands `software.amazon.awssdk.services.s3.S3Client` to the graph. **No `@S3`, no Kora models** |
| `s3-client-kora` | **`io.koraframework.experimental`** | `KoraS3ClientModule` and the declarative `@S3` client (`io.koraframework.s3.client.kora.annotation`) |

They are alternatives, not a pair. Both need an HTTP client transport module on the classpath — the
reference examples pair each with `http-client-apache` (Java) or `http-client-jdk` (Kotlin).

`s3-client-minio` does not exist in 2.0.

---

## Camunda (experimental)

All under group `io.koraframework.experimental`:

| Artifact | Module interface |
|---|---|
| `camunda-engine-bpmn` | `CamundaEngineBpmnModule` (Camunda 7 embedded) |
| `camunda-rest-undertow` | `CamundaRestUndertowModule` |
| `camunda-zeebe-worker` | `ZeebeWorkerModule` (Camunda 8; supplies `Wrapped<CamundaClient>`) |

---

## Testing

| Artifact | Purpose |
|---|---|
| `test-junit5` | `@KoraAppTest`, `@TestComponent`, `KoraAppTestConfigModifier` / `KoraAppTestGraphModifier` |

`test-junit5` declares Mockito, MockK and `kotlin-reflect` as **`compileOnly`**, so the app must add
its own mocking library. It brings JUnit 5 (`junit-jupiter` + `junit-platform-launcher`) as `api`.

There is no `test-blackbox` artifact — black-box tests are `test-junit5` plus Testcontainers.

---

## Not published

The `internal/` tree is build-only and never reaches Maven Central: `test-logging`, `test-postgres`,
`test-kafka`, `test-cassandra`, `test-redis`. Do not add them as dependencies.

---

## Renamed and removed since 1.x

| 1.x coordinate | 2.0 |
|---|---|
| `ru.tinkoff.kora:*` | `io.koraframework:*` |
| `ru.tinkoff.kora.experimental:*` | `io.koraframework.experimental:*` (except `s3-client-aws`, now plain `io.koraframework`) |
| `kora-parent` (BOM) | **`kora-bom`** |
| `json-module` | **`json-common`** |
| `cache-redis` | **`cache-redis-lettuce`** (`cache-redis-common` is the transport-neutral half) |
| `mapstruct-extension` | nothing to declare — **`mapstruct-java-extension`** is inside `annotation-processors`; Kotlin moves to Konvert |
| `http-client-async` | **removed** — no replacement; use `http-client-jdk` / `-ok` / `-apache` |
| `database-r2dbc`, `database-vertx` | **removed** — no replacement, contracts are synchronous |
| `s3-client-minio` | **removed** — use `s3-client-aws` or `s3-client-kora` |
| `kora-parent`-era `UndertowHttpServerModule` | `UndertowPublicHttpServerModule` |

`kora-parent`, `cache-redis`, `declarative-logging-annotation-processor`,
`declarative-logging-symbol-processor`, `scheduling-ksp` and `experimental/s3-client` still have
directories on Maven Central, and `kora-parent` / `cache-redis` still **resolve** at
`2.0.0.alpha5`/`2.0.0.alpha6`. They are pre-release leftovers, absent from the 2.0.0.RC2 BOM — see
[Checking a coordinate](#checking-a-coordinate).

Easy to miss coming from 1.x — these have no 1.x counterpart under the same name:
`http-client-apache`, `cache-redis-common`, `cache-redis-lettuce`, `redis-lettuce`,
`konvert-ksp-extension`, `jms`, and the 2.0 additions `database-jdbc-postgres`, `scheduling-db-scheduler`,
`resilient-kora-distributed`, `resilient-kora-distributed-redis-lettuce`, `logging-logback-json`.

---

## See Also

- [SKILL.md](../SKILL.md) — quick start and module picking
- [bom-usage-reference.md](bom-usage-reference.md) — BOM wiring for Java and Kotlin
- [annotation-processors-reference.md](annotation-processors-reference.md) — processor / KSP setup
- [compatibility-matrix.md](compatibility-matrix.md) — JDK, Kotlin/KSP, Gradle, third-party versions
- [core-modules-reference.md](core-modules-reference.md) — the always-on modules and a minimal `@KoraApp`
