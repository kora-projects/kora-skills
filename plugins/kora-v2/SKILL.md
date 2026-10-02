---
name: kora-v2
description: "Build and maintain Java/Kotlin services on the Kora Framework 2.0 (io.koraframework) — compile-time DI, zero reflection, synchronous contracts on virtual threads, annotation processors (Java) or KSP (Kotlin). Routes to 40 domain sub-skills. Use when the request mentions Kora, or uses Kora APIs: @KoraApp, @Component, @Module, @KoraSubmodule, @Root, @Tag, @Conditional, @FactoryModule, @HttpController, @HttpRoute, @HttpClient, @Repository, @Query, @EntityJdbc, @KafkaListener, @KafkaPublisher, gRPC, SOAP/WSDL, @S3.Client, @S3.Head, MapStruct, Konvert, @Json, @ConfigSource, @ConfigMapper (HOCON/YAML), OpenAPI codegen, @KoraAppTest, Testcontainers, @Valid, @Validate, @Log, @Mdc, @Retryable, @CircuitBreakable, @Timeout, @RateLimited, @Fallback, @Schedule*, @Cacheable, @CachePut, @CacheInvalidate, @CacheInvalidateAll, Micrometer/Prometheus metrics, OpenTelemetry/OTLP tracing, Undertow, Hikari, PostgreSQL, db-scheduler. Also use for Kora project setup, Gradle/BOM dependencies, DI graph errors, or explaining Kora concepts. Do not use for Spring Boot, Micronaut, or Quarkus work. For projects still on Kora 1.x (ru.tinkoff.kora) use the kora-v1 plugin instead."
license: Apache-2.0
metadata:
  version: "0.2.0"
  kora-version: "2.x"
---

# Kora Framework 2.0 — Meta-skill

Single entry point for all Kora 2.0 development. This file is **routing and rules only** — the
implementation knowledge lives in the 40 sub-skills listed below.

| | |
|---|---|
| **Framework** | Kora 2.0, group `io.koraframework`, BOM `io.koraframework:kora-bom` |
| **Version** | `2.0.0.RC2`. `2.0.0-SNAPSHOT` is the `master` development line and needs a snapshot repository |
| **Java** | **25 minimum.** Kora 2.0 artifacts are compiled to class-file 69; older JVMs cannot load them |
| **Gradle JVM** | The JDK running Gradle itself must also be ≥ 25 when `io.koraframework:openapi-generator` is on the buildscript classpath |
| **Kotlin** | 2.4.20 with KSP 2.3.12 — the versions the framework itself is built with |
| **Build** | Gradle 9.7.1 (the wrapper the framework itself pins) |
| **Docs** | [koraframework.io/v2/en](https://koraframework.io/v2/en/) ([ru](https://koraframework.io/v2/ru/)) — see R0 for how much to trust it |
| **Synced with** | Kora tag `2.0.0.RC2` = `master` at `78351e1cf` (2026-10-02) |

**This meta-skill is the single entry point for Kora Framework development.** It routes to 40
specialized domain skills, each with its own narrow area of expertise.

**Read this file first when:**
- Starting a new Kora 2.0 microservice project from scratch (Java or Kotlin)
- Adding or refactoring a `@KoraApp` application graph with `*Module` interfaces
- Choosing which Kora modules to plug in (HTTP, Database, Kafka, gRPC, SOAP, S3, Telemetry)
- Debugging DI container issues ("dependency not found", ambiguous bindings, graph build failures)
- Configuring typed config with `@ConfigSource` / `@ConfigMapper` and environment substitution
- Planning a multi-module Gradle project with `@KoraSubmodule` boundaries
- Migrating an existing Kora 1.x service — see §6

---

## 1. Operating rules

Four rules. They apply to **every** Kora task, on every turn, from the first message.
Each is stated once — here.

R0 is a **gate**: satisfy it before doing anything else. R1–R3 govern the work itself.

### R0 — Ground the workspace before starting, on 2.0 refs

The upstream material is level 5 of the R1 chain and the final authority for every Kora question.
It must be on disk **before** you begin, not fetched reactively once you are already stuck.

Kora 2.0 has its own documentation: [koraframework.io/v2/en](https://koraframework.io/v2/en/)
([ru](https://koraframework.io/v2/ru/)), built from the `kora-docs` branch `feature/kora-2.0`
(`mkdocs/docs/v2/{en,ru}/`). It is rewritten for 2.0, but it trails the framework — some pages still
describe behaviour that has since changed. Evidence order, highest first:

1. **Framework source and tests** at the 2.0 ref — the only authority for API names, config keys and defaults
2. **Migrated example applications** (`kora-examples`, branch `migration/2.0`) — working code, may lag the source
3. **Kora 2.0 docs** (`docs/v2`) — concepts, intent, recipes; verify any key, default or signature in source
4. **Kora 1.x docs** (`kora-projects.github.io/kora-docs`, `docs/v1`) — vocabulary and background only,
   and only when you say so out loud. They describe `ru.tinkoff.kora` and are never an authority for 2.0

**Run this at the start of every Kora task.** It is idempotent — it does nothing when the material
is already present, so there is no cost to running it every time:

```bash
if [ ! -d .kora-agent/kora-source-2.0 ] || [ ! -d .kora-agent/kora-examples-2.0 ] \
   || [ ! -d .kora-agent/kora-docs-2.0 ]; then
  mkdir -p .kora-agent
  [ -d .kora-agent/kora-source-2.0 ] \
    || git clone --depth 1 --branch 2.0.0.RC2 \
         https://github.com/kora-projects/kora.git .kora-agent/kora-source-2.0 \
    || git clone --depth 1 \
         https://github.com/kora-projects/kora.git .kora-agent/kora-source-2.0
  [ -d .kora-agent/kora-examples-2.0 ] \
    || git clone --depth 1 --branch migration/2.0 \
         https://github.com/kora-projects/kora-examples.git .kora-agent/kora-examples-2.0
  [ -d .kora-agent/kora-docs-2.0 ] \
    || git clone --depth 1 --branch feature/kora-2.0 \
         https://github.com/kora-projects/kora-docs.git .kora-agent/kora-docs-2.0
  rm -rf .kora-agent/kora-source-2.0/.git .kora-agent/kora-examples-2.0/.git .kora-agent/kora-docs-2.0/.git
  grep -qxF '.kora-agent/' .gitignore 2>/dev/null || echo '.kora-agent/' >> .gitignore
fi
```

**Gate:** `.kora-agent/kora-source-2.0/` and `.kora-agent/kora-examples-2.0/` both exist → proceed.
`.kora-agent/kora-docs-2.0/` is wanted but not a gate; without it, read the published site.

- Clone fails (no network, restricted environment) → say so explicitly and continue with sub-skills
  only. Never silently substitute recollection for the source you could not fetch.
- The `2.0.0.RC2` tag is missing, so the block fell back to `master` → say that you grounded on
  `master`, not on a release.
- The service targets `2.0.0-SNAPSHOT` rather than `2.0.0.RC2` → clone the framework at `master`
  instead, and say which ref you grounded on.
- The service pins an older release (`2.0.0.RC1`) → clone the framework at that tag. Several features
  taught by the sub-skills (PostgreSQL mappers, DB scheduling, distributed resilience, Logback JSON
  encoder, telemetry masking) do not exist there.
- The user declines the clone → note that level 5 is unavailable for this session, and flag any
  answer that would normally have been verified against it.

**Recovery:** started Kora work and only then noticed `.kora-agent/` is missing → run the block now,
then re-verify anything you already produced against it.

### R1 — Route before you write

Resolve every Kora question through this chain, in order. Stop at the first level that answers it.

```
1. This file                        → pick the sub-skill
2. skills/<sub-skill>/SKILL.md      → the actual expertise, templates, scripts
3. skills/<sub-skill>/references/   → detailed patterns for that domain
4. kora-journal (search)            → known mistakes and fixes from past sessions
5. .kora-agent/kora-source-2.0/     → framework source and tests: the final authority
   .kora-agent/kora-examples-2.0/   → working migrated applications
   .kora-agent/kora-docs-2.0/       → Kora 2.0 docs (mkdocs/docs/v2/{en,ru}/): verify before trusting
```

- **Never** write Kora code straight from memory. Open the sub-skill first.
- **Never** skip to level 5 because "it's a small change". Levels 2–3 hold the vetted patterns.
- Sub-skill and source disagree → **source wins**; fix the sub-skill and journal it (R3).
- Within level 5, framework source outranks the examples, and the examples outrank the docs: an
  example or a doc page can be behind, the source cannot.

**Recovery:** caught writing Kora code without having opened the sub-skill → stop, discard the
draft, open the sub-skill, rewrite.

### R2 — Kora only, and only what is asked

Kora is a self-contained framework with its own annotations, modules, and generated code.

- **Never** use Spring / Micronaut / Quarkus / Helidon annotations or idioms.
- **Never** invent a Kora annotation, class, or config key. If it is not in a sub-skill,
  a `references/` file, or `.kora-agent/`, it does not exist — go verify it.
- **Never** carry a Kora 1.x API into 2.0 code. `ru.tinkoff.kora.*` does not exist in 2.0, and
  several 1.x names still *compile* while doing nothing (§4).
- **Never** add comments or Javadoc, unless the user asked for them or the logic is genuinely
  opaque (bit manipulation, encodings, cryptography, non-obvious protocol handling).
- **Never** mix paradigms for one target: OpenAPI-generated controller → implement its delegate,
  do not hand-write a parallel controller; Kora `@HttpClient` → do not also call the same service
  with a raw HTTP library.
- **Always** express behaviour through Kora's compile-time model — no reflection, no runtime proxies.

**Recovery:** a framework foreign to Kora slipped in → delete it, re-derive from the sub-skill,
journal it (R3).

### R3 — Journal incorrect Kora usage

When you realise — or the user tells you — that you used **the Kora Framework** incorrectly,
record it. This is the feedback loop that improves the skills.

| Record | Do not record |
|---|---|
| Wrong Kora annotation used | Business / domain logic |
| Hallucinated Kora API or config key | Project-specific workarounds |
| Kora 1.x API used in a 2.0 project | Non-Kora issues |
| Kora pattern misapplied (DI, AOP, config, telemetry) | UI/UX or style preferences |
| Kora best practice from a sub-skill violated | Anything already correct |
| Sub-skill documentation wrong, stale, or unclear | |
| Unrequested comments/Javadoc written (R2 breach) | |

Entries are one file each, at `~/.kora-journal/<project>/<module>/<YYYY-MM-DD>_slug.md`, shared
across all projects and sessions. Full CLI and workflow:
[`skills/kora-journal/SKILL.md`](skills/kora-journal/SKILL.md).

**Recovery:** discovered a Kora mistake and moved on without an entry → add the entry now.

---

## 2. Per-task procedure

Follow these steps for every Kora request. Do not compress them.

0. **Satisfy R0** — run the grounding block, confirm `.kora-agent/` holds both 2.0 checkouts.
   Do not begin step 1 until this gate passes or you have told the user it cannot.
1. **Classify** the request against the routing tables in §3. More than one domain → handle them
   one at a time, in dependency order (project setup → config → DI → domain modules → telemetry → tests).
2. **Read** the sub-skill's `SKILL.md` end to end, then the `references/` entries it points at
   for your case.
3. **Search the journal** before implementing anything non-trivial:
   ```bash
   # path is relative to this skill's own directory, not the project you are working in
   python3 skills/kora-journal/scripts/kora_journal.py search "http interceptor auth" --limit 5
   ```
   Hit → apply it, then mark it applied with `integrate <entry-file>`.
   Miss → continue, and expect to add an entry afterwards under R3.
4. **Implement** in the smallest increment that compiles — one annotation, method, or class at a time.
5. **Compile** — `./gradlew clean classes`. Mandatory after any annotation change; the annotation
   processors, not the compiler, are what actually validate Kora code.
6. **Test** — write `@KoraAppTest` / Testcontainers coverage for real endpoints, queries, and
   messages, then `./gradlew test`.
7. **Verify the rules** — R1 route followed, R2 no foreign framework, no 1.x API, no stray comments,
   R3 journal entry added for any Kora mistake made along the way.

**Definition of done:** it compiles, tests pass, no rule was violated, journal updated if applicable.

> Compilation is necessary but **not sufficient** in Kora 2.0. Ports, interceptor tags, telemetry
> switches, circuit-breaker windows and mapper wiring all fail *silently* at runtime while the build
> stays green (§4). Anything in that list needs a test, not a successful build.

### Build commands

| Purpose | Command |
|---|---|
| Compile + run annotation processors / KSP | `./gradlew clean classes` |
| Run tests | `./gradlew test` |
| First build after changing packages or generator settings | `./gradlew clean --continue` then `./gradlew classes testClasses --continue --no-build-cache` |
| Kotlin: see processor errors first | `./gradlew <module>:kspKotlin --console=plain` |
| Build hangs, or `clean` fails with "Unable to delete directory" | `./gradlew --stop`, then retry |

---

## 3. Sub-skill routing

Read the matching sub-skill's `SKILL.md` **before** writing any code for that domain (R1).

### Foundation — start here for new projects

| When the task is about | Sub-skill |
|---|---|
| Gradle scaffolding, wrapper, build scripts, project layout (Java) | [`kora-project-setup-java`](skills/kora-project-setup-java/SKILL.md) |
| Gradle scaffolding, KSP, Kotlin DSL (Kotlin) | [`kora-project-setup-kotlin`](skills/kora-project-setup-kotlin/SKILL.md) |
| Kora BOM, module artifacts, annotation processors, dependency choices | [`kora-project-dependencies`](skills/kora-project-dependencies/SKILL.md) |
| Generating a runnable starter project (Initializr-style) | [`generate_project.py`](skills/kora-project-dependencies/scripts/generate_project.py) |
| HOCON config, typed `@ConfigSource` / `@ConfigMapper`, env substitution | [`kora-config-hocon`](skills/kora-config-hocon/SKILL.md) |
| YAML config (alternative to HOCON) | [`kora-config-yaml`](skills/kora-config-yaml/SKILL.md) |

### Dependency injection

| When the task is about | Sub-skill |
|---|---|
| `@KoraApp`, `@Component`, `@Module`, factory methods, `@KoraSubmodule`, graph build failures | [`kora-di-compile`](skills/kora-di-compile/SKILL.md) |
| `@Root`, `Lifecycle`, `@Tag`, `All<T>`, `ValueOf<T>`, `Wrapped<T>`, `@Conditional`, `GraphInterceptor` | [`kora-di-runtime`](skills/kora-di-runtime/SKILL.md) |

### Database

| When the task is about | Sub-skill |
|---|---|
| JDBC repositories, `@EntityJdbc`, `@Query`, SQL macros, transactions via `executor().inTx()`, Hikari | [`kora-database-jdbc`](skills/kora-database-jdbc/SKILL.md) |
| PostgreSQL types (`database-jdbc-postgres`) — `@Pg` arrays and `interval`, `PgRange`, `@PgJson` / `@PgJsonb`, `= ANY(?)` | [`kora-database-jdbc`](skills/kora-database-jdbc/references/postgres-mappers-reference.md) |
| Cassandra / ScyllaDB, `@EntityCassandra`, `@UDT`, CQL, driver profiles | [`kora-database-cassandra`](skills/kora-database-cassandra/SKILL.md) |
| Flyway / Liquibase migrations, SQL versioning, the `kora_scheduling_db_scheduler_jobs` table for `scheduling-db-scheduler` | [`kora-database-migration`](skills/kora-database-migration/SKILL.md) |

R2DBC and Vert.x SQL were **removed** in Kora 2.0. There is no reactive database integration —
JDBC on virtual threads is the only path.

### Communication

| When the task is about | Sub-skill |
|---|---|
| HTTP server, `@HttpController`, `@HttpRoute`, `@Path`, `@Query`, interceptors | [`kora-http-server`](skills/kora-http-server/SKILL.md) |
| HTTP server auth — Basic, Bearer, API keys, `HttpServerPrincipalExtractor`, principals | [`kora-http-server-auth`](skills/kora-http-server-auth/SKILL.md) |
| HTTP client, `@HttpClient`, declarative interfaces, interceptors, response mappers | [`kora-http-client`](skills/kora-http-client/SKILL.md) |
| HTTP client auth — Basic, Bearer, API keys, token refresh | [`kora-http-client-auth`](skills/kora-http-client-auth/SKILL.md) |
| gRPC server, `GrpcServerModule`, service handlers | [`kora-grpc-server`](skills/kora-grpc-server/SKILL.md) |
| gRPC client, `GrpcClientModule`, generated stubs injected by type | [`kora-grpc-client`](skills/kora-grpc-client/SKILL.md) |
| SOAP / WSDL client, `SoapClientModule`, generated clients | [`kora-soap-client`](skills/kora-soap-client/SKILL.md) |
| Kafka publishing, `@KafkaPublisher`, transactional producers | [`kora-kafka-producer`](skills/kora-kafka-producer/SKILL.md) |
| Kafka consuming, `@KafkaListener`, batch mode, error handling | [`kora-kafka-consumer`](skills/kora-kafka-consumer/SKILL.md) |
| OpenAPI → server code, delegates, controllers | [`kora-openapi-generator-server`](skills/kora-openapi-generator-server/SKILL.md) |
| OpenAPI → client code, typed `Api` interfaces, `clientResponseMode` `SEALED` / `SUCCESSFUL` with typed error exceptions | [`kora-openapi-generator-client`](skills/kora-openapi-generator-client/SKILL.md) |
| Serving the spec — Swagger UI, Scalar, publishing | [`kora-openapi-management`](skills/kora-openapi-management/SKILL.md) |
| JSON DTOs, `@Json`, sealed discriminators, custom (de)serialization | [`kora-json`](skills/kora-json/SKILL.md) |

### Telemetry

| When the task is about | Sub-skill |
|---|---|
| OpenTelemetry tracing, OTLP export, spans, Jaeger/Zipkin | [`kora-telemetry-tracing`](skills/kora-telemetry-tracing/SKILL.md) |
| Micrometer metrics, Prometheus scrape endpoint, custom meters | [`kora-telemetry-metrics`](skills/kora-telemetry-metrics/SKILL.md) |
| SLF4J / Logback, structured logs, JSON log encoder, `kora.logging.encoder` | [`kora-telemetry-logging`](skills/kora-telemetry-logging/SKILL.md) |
| Masking secrets in telemetry logs — HTTP / gRPC / Kafka headers, queries, payloads (`DataMasker`) | [`kora-aop-logging`](skills/kora-aop-logging/references/logging-masking.md), then the transport sub-skill |

In Kora 2.0 **per-component metrics and logging are disabled by default** (`<component>.telemetry.metrics.enabled`,
`…logging.enabled`); the global `metrics.enabled` switch defaults to `true` — see §4. Common metric tags
(`metrics.tags`, `MetricsTagsProvider`) and tracing resource attributes (`OpentelemetryTracingAttributesProvider`)
live in the metrics and tracing sub-skills.

### AOP

| When the task is about | Sub-skill |
|---|---|
| `@Retryable`, `@CircuitBreakable`, `@Timeout`, `@RateLimited`, `@Fallback` and their `*Spec` types, token-bucket / fixed-window limiter, `RetryBudget`, `NonRetryableException` / `NonCircuitableException` | [`kora-aop-resilient`](skills/kora-aop-resilient/SKILL.md) |
| Redis-backed distributed rate limiter and retry budget — `@RateLimiterDistributedSpec`, `LettuceDistributedResilientModule`, `DistributedRetryBudgetFactory` | [`kora-aop-resilient`](skills/kora-aop-resilient/references/distributed-reference.md) |
| `@Log`, `@Mdc`, method logging aspects | [`kora-aop-logging`](skills/kora-aop-logging/SKILL.md) |
| `@Cacheable`, `@CachePut`, `@CacheInvalidate`, `@CacheInvalidateAll`, Caffeine / Redis-Lettuce | [`kora-aop-caching`](skills/kora-aop-caching/SKILL.md) |
| `@ScheduleJdkAtFixedRate`, `@ScheduleJdkWithFixedDelay`, `@ScheduleJdkWithCron`, `@ScheduleJdkOnce` in-process (JDK executor, virtual threads) | [`kora-aop-scheduling-jdk`](skills/kora-aop-scheduling-jdk/SKILL.md) |
| Quartz scheduling, `@ScheduleQuartzWithCron`, `@ScheduleQuartzWithTrigger`, clustered jobs, job stores | [`kora-aop-scheduling-quartz`](skills/kora-aop-scheduling-quartz/SKILL.md) |
| Database-backed clustered jobs on db-scheduler (`scheduling-db-scheduler`): `@ScheduleDbWithCron` / `@ScheduleDbWithFixedDelay` / `@ScheduleDbOnce`, one execution per cluster | [`kora-aop-scheduling-db`](skills/kora-aop-scheduling-db/SKILL.md) |
| `@Valid`, `@Validate`, constraint annotations, custom validators | [`kora-aop-validation`](skills/kora-aop-validation/SKILL.md) |

### Testing

| When the task is about | Sub-skill |
|---|---|
| `@KoraAppTest`, `@TestComponent`, mocks, JUnit 5 (Java) | [`kora-testing-junit-java`](skills/kora-testing-junit-java/SKILL.md) |
| `@KoraAppTest`, MockK, JUnit 5 (Kotlin) | [`kora-testing-junit-kotlin`](skills/kora-testing-junit-kotlin/SKILL.md) |
| Black-box E2E, Testcontainers, Docker | [`kora-testing-blackbox`](skills/kora-testing-blackbox/SKILL.md) |

### Other

| When the task is about | Sub-skill |
|---|---|
| S3 object storage — declarative `@S3` client and the AWS SDK wrapper | [`kora-s3`](skills/kora-s3/SKILL.md) |
| DTO ↔ entity mapping — MapStruct in Java, Konvert in Kotlin (never crossed) | [`kora-mapstruct`](skills/kora-mapstruct/SKILL.md) |
| Recording incorrect Kora usage (R3), searching past mistakes | [`kora-journal`](skills/kora-journal/SKILL.md) |
| Teaching Kora, guided tutorials, explaining concepts to a newcomer | [`kora-teacher`](skills/kora-teacher/SKILL.md) |

---

## 4. Architecture facts that drive decisions

- **Everything is generated at compile time.** DI → `*ComponentImpl` / `*Graph`, HTTP →
  `*HttpRouter`, AOP → `*Aspect`, JSON → `*JsonReader` / `*JsonWriter`, repositories →
  `*RepositoryImpl`, OpenAPI → `*Delegate`. No reflection, no dynamic proxies, no runtime scanning.
- **The generated sources are the ground truth.** When wiring or aspect behaviour is unclear,
  read them:
  - Java: `build/generated/sources/annotationProcessor/`
  - Kotlin: `build/generated/ksp/`
  Never edit generated code as a fix — regenerate instead.
- **Contracts are synchronous, executed on virtual threads.** Reactive types (`Mono`/`Flux`) are
  gone framework-wide — there is no response mapper for `Mono`/`Flux` — and `suspend`
  repositories, controllers and HTTP clients are gone with them; the database KSP processor rejects
  `suspend` outright with *"Suspend methods are not supported by the repository generator."*
  Wrapping a Kora call in `withContext(Dispatchers.IO)` is now pointless overhead, and real
  parallelism moves to Java `StructuredTaskScope`.

  **Async is not rejected everywhere, though, and what happens instead differs per generator —
  never diagnose from the one-line rule.**

  | Generator | Async shape | What happens |
  |---|---|---|
  | `@KafkaPublisher` | `Future`/`CompletionStage`, + `suspend`/`Deferred` in Kotlin | **first-class and awaited** — do not "fix" it |
  | `@KafkaListener` | `suspend`, batch or key/value | accepted, wrapped in `runBlocking` — compiles, buys nothing |
  | `@KafkaListener` | `suspend`, single `ConsumerRecord` | **does not compile** — no such branch |
  | `@KafkaListener` | async **return type** | **silently discarded — see the silent-failure table** |
  | Cassandra repository | `CompletionStage` | accepted, **Java only** |
  | repositories, controllers, HTTP clients, scheduling, SOAP | any | rejected with a named error |

  Two things apply to every Kotlin async path above: `runBlocking` runs to completion on the calling
  thread, so it buys no concurrency; and `kotlinx-coroutines` is a dependency of **no** Kora module,
  so generated code that uses it compiles only if your project supplies coroutines itself. Write a
  plain `fun` in listeners — because it is pointless, not because it is rejected.
  **Two verified exceptions, both source-backed:**
  *Cassandra repositories* still generate Java `CompletionStage`/`CompletableFuture` methods —
  `CassandraRepositoryGenerator` emits `prepareAsync(...).thenCompose(...)`, and the migrated
  `kora-java-database-cassandra` example ships and tests one; the Kotlin side is synchronous there.
  *Kafka publishers* accept async return types in **both** languages — the Java generator branches on
  `isFuture() || isCompletionStage()`, the KSP one also on `isSuspend() || isDeferred()`, with a
  passing `testReturnRecordMetadataSuspend` and a shipped `Future<RecordMetadata> sendMetaAsync(...)`
  in `kora-java-kafka`. Do not "fix" either into a synchronous signature.
- **`Context` no longer exists** anywhere in the framework. A signature that threaded a Kora
  `Context` has to be rewritten, not mechanically patched.
- **Nullability is JSpecify in Java** (`org.jspecify.annotations.Nullable`) and **the type in
  Kotlin** (`T?`). JSpecify annotations are *type-use*: `Outer.@Nullable Inner`,
  `List<@Nullable String>`, `String @Nullable []`. Kora contracts are `@NullMarked`, so Kotlin
  overrides must match exactly — `HttpServerResponseMapper<T>.apply(request, result: T?)` with a
  non-null `result` fails as `'apply' overrides nothing`, a message that never mentions nullability.
- **Aspects need a non-final target.** In Kotlin an AOP-annotated class and method must be `open`,
  otherwise the aspect is silently not generated.

### Silent failures — green build, broken service

These are the Kora 2.0 traps that compile cleanly and fail only at runtime. Treat every one as a
test case, never as something a successful build has proved.

| Symptom | Cause |
|---|---|
| Kafka records vanish after a crash, and telemetry showed every one of them succeeding | An **async return type on a `@KafkaListener`**. Neither consumer generator inspects the return type, so the call is emitted as a bare statement: `handle()` returns the instant the future is created, `commitSync(offset + 1)` runs immediately, and an exception completed inside the future reaches neither telemetry nor redelivery |
| Global interceptor never runs — auth/error handling silently gone | `@Tag(HttpServerModule.class)`. 2.0 collects interceptors by `@Tag(HttpServer.class)`; the old class still exists, so it compiles |
| Service starts fine but nothing answers on the ports you configured | `publicApiHttpPort`/`privateApiHttpPort` still in config. Unrecognised HOCON keys are ignored without a warning, so both servers fall back to their defaults — 8080 public, 8085 system. Probes, scrapers and load balancers hit nothing |
| `ConfigValueException: … got null at path: 'ROOT.jdbc.username'` | Datasource section still called `db`; 2.0 wires `new JdbcDatabaseFactoryModule("jdbc")` |
| `/metrics` returns 200 but has no `http_server_*` / `db_*` series | Component metrics default to **off** in 2.0. Set `telemetry.metrics.enabled = true` per component. Logging is off by default too; tracing is on |
| `/metrics` returns 200 with an **empty** body | The global `metrics.enabled = false` swaps in a no-op `MeterRegistry` for the whole service |
| `metrics.tags` and every `MetricsTagsProvider` are ignored | The application declares its own `PrometheusMeterRegistryInitializer`; the built-in common-tags initializer is a `@DefaultComponent` and drops out of the graph |
| Console stays empty although `logback.xml` looks right | The encoder class is still `io.koraframework.logging.logback.ConsoleTextRecordEncoder`; it moved to `io.koraframework.logging.logback.text.ConsoleTextRecordEncoder`, and the failure is hidden behind `NopStatusListener` |
| Log lines go missing under load | `KoraAsyncAppender` defaults to `neverBlock = true` with `queueSize = 512`: a full queue **drops** events |
| Secrets appear in TRACE Kafka / HTTP body logs | Header masking is on by default (`maskHeaders`), but bodies are masked only by a `DataMasker` you register under the transport's telemetry tag — none is registered by default |
| DB-scheduled jobs (`scheduling-db-scheduler`) never run, the app starts green | The job table is missing. `scheduling.dbScheduler.initializeTable` — the name the module README and the `DbSchedulerConfig` Javadoc gave until kora-projects/kora PR #966 — is not read; the key is `tableInitialize`, and the default table is now `kora_scheduling_db_scheduler_jobs`. `KoraDbScheduler` is `@Root` itself, so no starter component is needed — see [`kora-aop-scheduling-db`](skills/kora-aop-scheduling-db/SKILL.md) |
| A JDBC `afterCommit` fires for a transaction that rolled back (or `afterRollback` for one that committed); an `afterCommit` that opens `inTx` ends in `StackOverflowError` | `ConnectionContext` keeps its actions after the transaction ends, so a later `inTx` in the same `withConnection` scope runs them again, and the first failing action skips the rest. Fixed in `2.0.0.RC2` (kora-projects/kora PR #967) — only `2.0.0.RC1` is affected; a post-commit failure still propagates out of `inTx` for committed work — see [`kora-database-jdbc`](skills/kora-database-jdbc/references/transactions-reference.md#post-commit-and-post-rollback-actions) |
| A scheduled job never does its work; with job logging off nothing says so | The scheduled method sits on a `@Conditional` component whose condition failed. The generated job factory does not carry the condition, so a JDK or DB job is still scheduled and every run fails in `ValueOf.get()` with `Graph node value was not initialized because condition failed` (a Quartz job fails graph init instead). Fixed in `2.0.0.RC2` (kora-projects/kora PR #962) — only `2.0.0.RC1` is affected; on RC1 keep schedules on an unconditional component — see [`kora-aop-scheduling-jdk`](skills/kora-aop-scheduling-jdk/SKILL.md) |
| Scheduler concurrency or shutdown settings have no effect after moving off RC1 / an earlier 2.0 snapshot | Renamed keys are unknown keys: `scheduling.jdk.maxConcurrentExecutions` is now `executionParallelism`, `scheduling.quartz.waitForJobComplete` is now the duration `shutdownWait` — after which Quartz jobs are interrupted — and the annotations are `@ScheduleJdk*` / `@ScheduleQuartz*` / `@ScheduleDb*` |
| `telemetry.logging.mask = "…"` has no effect | The `mask` key is gone; the replacement text comes from a tagged `MaskingStrategy` component. Unknown keys are ignored silently |
| Tracing is on, spans are created, and the collector receives nothing | The exporter's `endpoint` is unset. `spanExporter`/`spanProcessor` return `SpanExporter.composite()` / `SpanProcessor.composite()` — a no-op — with no warning, while `tracing.enabled` defaults to **true**, so the service looks fully instrumented |
| `No component found for dependency: …Mapper` | A mapper *with* constructor dependencies needs `@Component` — the generated module injects it rather than building it |
| `Multiple components match` for a mapper | A mapper *without* dependencies must **not** carry `@Component` — Kora constructs it itself. Decide per mapper, by its constructor |
| Hundreds of `package ru.tinkoff.kora … does not exist` in files you never wrote | Stale generator output in `build/generated`. `./gradlew clean --continue` then `classes testClasses --continue --no-build-cache` |
| `ConfigValueException: … got null after parsing at path: 'ROOT.openapi.management.files'` during graph build | `openapi.management.file` — 2.0 reads `files`, a **required** `List<String>` with no default. It fails loudly at startup, even with `enabled = false` |
| Generated OpenAPI client hangs until timeout | Config path must lower-case the first letter of the API name: `PetApi` → `httpClient.<client>.petApi` |
| Enum parsing fails only on real data | Generated enums must be parsed with `fromValue(raw)`, not `valueOf` |
| native-image builds fine, registrations never apply | The file must be named `reflect-config.json`; `reflection-config.json` is ignored without a warning |

### Troubleshooting

| Symptom | Action |
|---|---|
| `No component found for dependency:` naming `Foo` | Check `@Component` on the class, that the `*Module` is extended by `@KoraApp`, and that `@KoraSubmodule` exists in multi-module builds |
| Ambiguous dependency / more than one candidate | Disambiguate with `@Tag`, or inject `All<T>` |
| `ApplicationGraph` missing after `clean` | Run `./gradlew classes` — processors must run before anything references the graph |
| Aspect annotation has no effect | Processor/KSP dependency missing, or the Kotlin class is not `open` |
| `incompatible types: String cannot be converted to Class<? extends Timeouter>` | 1.x string-named resilient annotation; 2.0 takes a spec **type** |
| KSP crashes with `ClassCastException: String → KSType` | Same cause, seen from Kotlin: a leftover string-named resilient annotation |
| `error: SQL query placeholder has no matching method parameter: :id … - :arg0` | Incremental build read the repository from a class file. `--rerun-tasks` or `clean` on the module |
| `Graph node value was not initialized because condition failed` although the dependency is `@Nullable` / `T?` | A nullable dependency on a `@Conditional` component is generated as `g.get(node)`. Fixed in `2.0.0.RC2` (kora-projects/kora PR #960) — only `2.0.0.RC1` is affected; on RC1 inject `All<T>` — see [`kora-di-runtime`](skills/kora-di-runtime/SKILL.md) |
| `@KoraAppTest` fails to start with `Graph node belongs to another application graph` | The tested graph contains a `@Conditional` component; `ApplicationGraphDraw.copy()`/`subgraph()` keep its condition bound to the original graph. Fixed in `2.0.0.RC2` (kora-projects/kora PR #963) — only `2.0.0.RC1` is affected — see [`kora-testing-junit-java`](skills/kora-testing-junit-java/SKILL.md) |
| Generated classes stale or broken after a refactor | Delete `build/generated/`, rebuild with `--no-build-cache` |
| Build hangs, or `clean` fails to delete a directory | `./gradlew --stop`, then retry |
| IDE shows errors but Gradle compiles fine | IDE caching — invalidate caches and restart |
| Behaviour contradicts a sub-skill | Verify against `.kora-agent/kora-source-2.0/`, fix the sub-skill, journal it (R3) |

---

## 5. Upstream sources

Availability of this material is **R0**, the gate in §1 — it is a precondition for starting work,
not a step you reach once you need it.

Module-by-module map of the framework source, the 2.0 docs pages, the migrated example apps, and the
areas this plugin does not cover: [`references/kora-docs-map.md`](references/kora-docs-map.md).

---

## 6. Coming from Kora 1.x

This plugin teaches and generates **native Kora 2.0** code. It is not a migration tool.

- A project still on `ru.tinkoff.kora` should use the **`kora-v1`** plugin, which is maintained
  separately and installs alongside this one.
- Migrating a real service is a semantic job, not a rename: typed resilient specifications, removed
  `Context`, synchronous contracts replacing `suspend`/reactive chains, JSpecify placement, the S3
  redesign and the generated-OpenAPI adaptation all require decisions a search-and-replace cannot
  make. The upstream migration corpus lives at
  [kora-examples `migration/2.0`](https://github.com/kora-projects/kora-examples/tree/migration/2.0/migration)
  and is fetched by the R0 block above as part of `.kora-agent/kora-examples-2.0/`.
- Sub-skills flag 1.x APIs where a 2.0 agent is likely to reach for one by habit. Those notes exist
  to help you *recognise and replace* legacy input — never to justify emitting it.
