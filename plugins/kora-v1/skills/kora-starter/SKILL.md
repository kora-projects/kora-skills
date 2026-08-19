---
name: kora-v1
description: "Build and maintain Java/Kotlin services on the Kora Framework 1.x (ru.tinkoff.kora) — compile-time DI, zero reflection, annotation processors (Java) or KSP (Kotlin). Routes to 39 domain sub-skills. Use when the request mentions Kora, or uses Kora APIs: @KoraApp, @Component, @Module, @KoraSubmodule, @Root, @Tag, @HttpController, @HttpRoute, @HttpClient, @Repository, @Query, @EntityJdbc, @KafkaListener, @KafkaPublisher, gRPC, SOAP/WSDL, @S3.Client, MapStruct, @Json, @ConfigSource (HOCON/YAML), OpenAPI codegen, @KoraAppTest, Testcontainers, @Valid, @Validate, @Log, @Mdc, @Retry, @CircuitBreaker, @Timeout, @Fallback, @Schedule*, @Cacheable, @CachePut, @CacheInvalidate, Micrometer/Prometheus metrics, OpenTelemetry/OTLP tracing, Undertow, Hikari. Also use for Kora project setup, Gradle/BOM dependencies, DI graph errors, or explaining Kora concepts. Do not use for Spring Boot, Micronaut, or Quarkus work."
license: Apache-2.0
disable-model-invocation: true   # Claude Code: this is the Codex-only mirror of the root kora-v1 meta; stay dormant here
user-invocable: false
metadata:
  version: "0.2.0"
  kora-version: "1.x"
---

# Kora Framework — Meta-skill

Single entry point for all Kora development. This file is **routing and rules only** — the
implementation knowledge lives in the 39 sub-skills listed below.

| |                                                                                                                                                                                                 |
|---|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **Framework** | Kora 1.x (`ru.tinkoff.kora`) — check the [changelog](https://raw.githubusercontent.com/kora-projects/kora-docs/refs/heads/master/mkdocs/docs/en/changelog/changelog.md) for the current release |
| **Java** | 17+ supported, 25+ recommended (annotation processors)                                                                                                                                          |
| **Kotlin** | 1.9+ on JDK 21 (KSP)                                                                                                                                                                        |
| **Build** | Gradle 7+ supported, 9+ recommended (wrapper pins 9.5.1)                                                                                                                                        |

**This meta-skill is the single entry point for Kora Framework development.** It routes to 39 specialized domain skills, each with its own narrow area of expertise.

**Read this file first when:**
- Starting a new Kora microservice project from scratch (Java or Kotlin)
- Adding or refactoring `@KoraApp` application graph with `*Module` interfaces
- Choosing which Kora modules to plug in (HTTP, Database, Kafka, gRPC, SOAP, S3, Telemetry)
- Debugging DI container issues ("dependency not found", ambiguous bindings, graph build failures)
- Configuring typed config with `@ConfigSource` and environment variable substitution
- Planning a multi-module Gradle project with `@KoraSubmodule` boundaries

---

## 1. Operating rules

Four rules. They apply to **every** Kora task, on every turn, from the first message.
Each is stated once — here.

R0 is a **gate**: satisfy it before doing anything else. R1–R3 govern the work itself.

### R0 — Ground the workspace before starting

The upstream documentation and the runnable example apps are levels 4–5 of the R1 chain and the
final authority for every Kora question. They must be on disk **before** you begin, not fetched
reactively once you are already stuck.

**Run this at the start of every Kora task.** It is idempotent — it does nothing when the material
is already present, so there is no cost to running it every time:

```bash
if [ ! -d .kora-agent/kora-docs ] || [ ! -d .kora-agent/kora-examples ]; then
  mkdir -p .kora-agent
  [ -d .kora-agent/kora-docs ] \
    || git clone --depth 1 https://github.com/kora-projects/kora-docs.git .kora-agent/kora-docs
  [ -d .kora-agent/kora-examples ] \
    || git clone --depth 1 https://github.com/kora-projects/kora-examples.git .kora-agent/kora-examples
  rm -rf .kora-agent/kora-docs/.git .kora-agent/kora-examples/.git
  grep -qxF '.kora-agent/' .gitignore 2>/dev/null || echo '.kora-agent/' >> .gitignore
fi
```

**Gate:** `.kora-agent/kora-docs/` and `.kora-agent/kora-examples/` both exist → proceed.

- Clone fails (no network, restricted environment) → say so explicitly and continue with sub-skills
  only. Never silently substitute recollection for the docs you could not fetch.
- Material is present but predates the Kora version in the build → re-clone before trusting it.
- The user declines the clone → note that levels 4–5 are unavailable for this session, and flag any
  answer that would normally have been verified against them.

**Recovery:** started Kora work and only then noticed `.kora-agent/` is missing → run the block now,
then re-verify anything you already produced against it.

### R1 — Route before you write

Resolve every Kora question through this chain, in order. Stop at the first level that answers it.

```
1. This file                       → pick the sub-skill
2. ../<sub-skill>/SKILL.md     → the actual expertise, templates, scripts
3. ../<sub-skill>/references/  → detailed patterns for that domain
4. kora-journal (search)           → known mistakes and fixes from past sessions
5. .kora-agent/ docs + examples    → upstream source of truth
```

- **Never** write Kora code straight from memory. Open the sub-skill first.
- **Never** skip to level 5 because "it's a small change". Levels 2–3 hold the vetted patterns.
- Sub-skill and upstream docs disagree → upstream wins; fix the sub-skill and journal it (R3).

**Recovery:** caught writing Kora code without having opened the sub-skill → stop, discard the
draft, open the sub-skill, rewrite.

### R2 — Kora only, and only what is asked

Kora is a self-contained framework with its own annotations, modules, and generated code.

- **Never** use Spring / Micronaut / Quarkus / Helidon annotations or idioms.
- **Never** invent a Kora annotation, class, or config key. If it is not in a sub-skill,
  a `references/` file, or `.kora-agent/`, it does not exist — go verify it.
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
| Kora pattern misapplied (DI, AOP, config, telemetry) | Non-Kora issues |
| Kora best practice from a sub-skill violated | UI/UX or style preferences |
| Sub-skill documentation wrong, stale, or unclear | Anything already correct |
| Unrequested comments/Javadoc written (R2 breach) | |

Entries are one file each, at `~/.kora-journal/<project>/<module>/<YYYY-MM-DD>_slug.md`, shared
across all projects and sessions. Full CLI and workflow:
[`skills/kora-journal/SKILL.md`](../kora-journal/SKILL.md).

**Recovery:** discovered a Kora mistake and moved on without an entry → add the entry now.

---

## 2. Per-task procedure

Follow these steps for every Kora request. Do not compress them.

0. **Satisfy R0** — run the grounding block, confirm `.kora-agent/` holds both repositories.
   Do not begin step 1 until this gate passes or you have told the user it cannot.
1. **Classify** the request against the routing tables in §3. More than one domain → handle them
   one at a time, in dependency order (project setup → config → DI → domain modules → telemetry → tests).
2. **Read** the sub-skill's `SKILL.md` end to end, then the `references/` entries it points at
   for your case.
3. **Search the journal** before implementing anything non-trivial:
   ```bash
   # path is relative to this skill's own directory, not the project you are working in
   python ../kora-journal/scripts/kora_journal.py search "http interceptor auth" --limit 5
   ```
   Hit → apply it, then mark it applied with `integrate <entry-file>`.
   Miss → continue, and expect to add an entry afterwards under R3.
4. **Implement** in the smallest increment that compiles — one annotation, method, or class at a time.
5. **Compile** — `./gradlew clean classes`. Mandatory after any annotation change; the annotation
   processors, not the compiler, are what actually validate Kora code.
6. **Test** — write `@KoraAppTest` / Testcontainers coverage for real endpoints, queries, and
   messages, then `./gradlew test`.
7. **Verify the rules** — R1 route followed, R2 no foreign framework and no stray comments,
   R3 journal entry added for any Kora mistake made along the way.

**Definition of done:** it compiles, tests pass, no rule was violated, journal updated if applicable.

### Build commands

| Purpose | Command |
|---|---|
| Compile + run annotation processors / KSP | `./gradlew clean classes` |
| Run tests | `./gradlew test` |
| Build hangs, or `clean` fails with "Unable to delete directory" | `./gradlew --stop`, then retry |

---

## 3. Sub-skill routing

Read the matching sub-skill's `SKILL.md` **before** writing any code for that domain (R1).

### Foundation — start here for new projects

| When the task is about | Sub-skill |
|---|---|
| Gradle scaffolding, wrapper, build scripts, project layout (Java) | [`kora-project-setup-java`](../kora-project-setup-java/SKILL.md) |
| Gradle scaffolding, KSP, Kotlin DSL (Kotlin) | [`kora-project-setup-kotlin`](../kora-project-setup-kotlin/SKILL.md) |
| Kora BOM, module artifacts, annotation processors, dependency choices | [`kora-project-dependencies`](../kora-project-dependencies/SKILL.md) |
| Generating a runnable starter project (Initializr-style) | [`generate_project.py`](../kora-project-dependencies/scripts/generate_project.py) |
| HOCON config, typed `@ConfigSource`, env substitution | [`kora-config-hocon`](../kora-config-hocon/SKILL.md) |
| YAML config (alternative to HOCON) | [`kora-config-yaml`](../kora-config-yaml/SKILL.md) |

### Dependency injection

| When the task is about | Sub-skill |
|---|---|
| `@KoraApp`, `@Component`, `@Module`, factory methods, `@KoraSubmodule`, graph build failures | [`kora-di-compile`](../kora-di-compile/SKILL.md) |
| `@Root`, `Lifecycle`, `@Tag`, `All<T>`, `ValueOf<T>` | [`kora-di-runtime`](../kora-di-runtime/SKILL.md) |

### Database

| When the task is about | Sub-skill |
|---|---|
| JDBC repositories, `@EntityJdbc`, `@Query`, SQL macros, transactions, Hikari | [`kora-database-jdbc`](../kora-database-jdbc/SKILL.md) |
| Cassandra, `@EntityCassandra`, `@UDT`, CQL, driver profiles | [`kora-database-cassandra`](../kora-database-cassandra/SKILL.md) |
| Flyway / Liquibase migrations, SQL versioning | [`kora-database-migration`](../kora-database-migration/SKILL.md) |

### Communication

| When the task is about | Sub-skill |
|---|---|
| HTTP server, `@HttpController`, `@HttpRoute`, `@Path`, `@Query`, interceptors | [`kora-http-server`](../kora-http-server/SKILL.md) |
| HTTP server auth — BasicAuth, Bearer, API keys, `SecurityContext`, principals | [`kora-http-server-auth`](../kora-http-server-auth/SKILL.md) |
| HTTP client, `@HttpClient`, declarative interfaces, interceptors, response mappers | [`kora-http-client`](../kora-http-client/SKILL.md) |
| HTTP client auth — BasicAuth, Bearer, API keys, token refresh | [`kora-http-client-auth`](../kora-http-client-auth/SKILL.md) |
| gRPC server, `GrpcServerModule`, service handlers | [`kora-grpc-server`](../kora-grpc-server/SKILL.md) |
| gRPC client, `GrpcClientModule`, `@Tag` stub injection | [`kora-grpc-client`](../kora-grpc-client/SKILL.md) |
| SOAP / WSDL client, `SoapClientModule`, generated clients | [`kora-soap-client`](../kora-soap-client/SKILL.md) |
| Kafka publishing, `@KafkaPublisher`, transactional producers | [`kora-kafka-producer`](../kora-kafka-producer/SKILL.md) |
| Kafka consuming, `@KafkaListener`, batch mode, error handling | [`kora-kafka-consumer`](../kora-kafka-consumer/SKILL.md) |
| OpenAPI → server code, delegates, controllers | [`kora-openapi-generator-server`](../kora-openapi-generator-server/SKILL.md) |
| OpenAPI → client code, typed `Api` interfaces | [`kora-openapi-generator-client`](../kora-openapi-generator-client/SKILL.md) |
| Serving the spec — Swagger UI, RapiDoc, publishing | [`kora-openapi-management`](../kora-openapi-management/SKILL.md) |
| JSON DTOs, `@Json`, sealed discriminators, custom (de)serialization | [`kora-json`](../kora-json/SKILL.md) |

### Telemetry

| When the task is about | Sub-skill |
|---|---|
| OpenTelemetry tracing, OTLP export, spans, Jaeger/Zipkin | [`kora-telemetry-tracing`](../kora-telemetry-tracing/SKILL.md) |
| Micrometer metrics, Prometheus scrape endpoint, custom meters | [`kora-telemetry-metrics`](../kora-telemetry-metrics/SKILL.md) |
| SLF4J / Logback, structured logs, `KoraAsyncAppender` | [`kora-telemetry-logging`](../kora-telemetry-logging/SKILL.md) |

### AOP

| When the task is about | Sub-skill |
|---|---|
| `@Retry`, `@CircuitBreaker`, `@Timeout`, `@Fallback` | [`kora-aop-resilient`](../kora-aop-resilient/SKILL.md) |
| `@Log`, `@Mdc`, method logging aspects | [`kora-aop-logging`](../kora-aop-logging/SKILL.md) |
| `@Cacheable`, `@CachePut`, `@CacheInvalidate`, Caffeine / Redis | [`kora-aop-caching`](../kora-aop-caching/SKILL.md) |
| `@ScheduleAtFixedRate`, `@ScheduleWithCron` (JDK executor) | [`kora-aop-scheduling-jdk`](../kora-aop-scheduling-jdk/SKILL.md) |
| Quartz scheduling, clustered jobs, job stores | [`kora-aop-scheduling-quartz`](../kora-aop-scheduling-quartz/SKILL.md) |
| `@Valid`, `@Validate`, constraint annotations, custom validators | [`kora-aop-validation`](../kora-aop-validation/SKILL.md) |

### Testing

| When the task is about | Sub-skill |
|---|---|
| `@KoraAppTest`, `@TestComponent`, mocks, JUnit 5 (Java) | [`kora-testing-junit-java`](../kora-testing-junit-java/SKILL.md) |
| `@KoraAppTest`, MockK, JUnit 5 (Kotlin) | [`kora-testing-junit-kotlin`](../kora-testing-junit-kotlin/SKILL.md) |
| Black-box E2E, `AppContainer`, Testcontainers, Docker | [`kora-testing-blackbox`](../kora-testing-blackbox/SKILL.md) |

### Other

| When the task is about | Sub-skill |
|---|---|
| S3 object storage, `@S3.Client`, AWS S3 / MinIO, multipart uploads | [`kora-s3`](../kora-s3/SKILL.md) |
| MapStruct mappers, DTO ↔ entity mapping | [`kora-mapstruct`](../kora-mapstruct/SKILL.md) |
| Recording incorrect Kora usage (R3), searching past mistakes | [`kora-journal`](../kora-journal/SKILL.md) |
| Teaching Kora, guided tutorials, explaining concepts to a newcomer | [`kora-teacher`](../kora-teacher/SKILL.md) |

---

## 4. Architecture facts that drive decisions

- **Everything is generated at compile time.** DI → `*ComponentImpl` / `*Graph`, HTTP →
  `*HttpRouter`, AOP → `*Aspect`, JSON → `*JsonReader` / `*JsonWriter`, repositories →
  `*RepositoryImpl`, OpenAPI → `*Delegate`. No reflection, no dynamic proxies, no runtime scanning.
- **The generated sources are the ground truth.** When wiring or aspect behaviour is unclear,
  read them:
  - Java: `build/generated/sources/annotationProcessor/`
  - Kotlin: `build/generated/ksp/`
- **Compilation is the primary validator.** If it compiles and the tests pass, the wiring is correct.
- **Aspects need a non-final target.** In Kotlin an AOP-annotated class and method must be `open`,
  otherwise the aspect is silently not generated.

### Troubleshooting

| Symptom | Action |
|---|---|
| `Required dependency was not found: Foo` | Check `@Component` on the class, the `*Module` is extended by `@KoraApp`, and `@KoraSubmodule` exists in multi-module builds |
| Ambiguous dependency / more than one candidate | Disambiguate with `@Tag`, or inject `All<T>` |
| `ApplicationGraph` missing after `clean` | Run `./gradlew classes` — processors must run before anything references the graph |
| Aspect annotation has no effect | Annotation processor / KSP dependency missing, or the Kotlin class is not `open` |
| Generated classes stale or broken after a refactor | Delete `build/generated/`, rebuild |
| Build hangs, or `clean` fails to delete a directory | `./gradlew --stop`, then retry |
| IDE shows errors but Gradle compiles fine | IDE caching — invalidate caches and restart |
| Behaviour contradicts a sub-skill | Verify against `.kora-agent/` docs, fix the sub-skill, journal it (R3) |

---

## 5. Upstream sources

Availability of this material is **R0**, the gate in §1 — it is a precondition for starting work,
not a step you reach once you need it.

### Where to look

Module-by-module map of docs, guides, and runnable example apps — plus the areas this plugin does
not cover: [`references/kora-docs-map.md`](../../references/kora-docs-map.md).
