---
name: kora-developer
description: Build production-grade Java/Kotlin microservices on the Kora framework (ru.tinkoff.kora). Compile-time DI, reflection-free, annotation-processor-driven (Java `annotation-processors`) or KSP-driven (Kotlin `symbol-processors`). Triggers on any task involving Kora — `@KoraApp`, `@Component`, `@Module`, `@KoraSubmodule`, `@HttpController`, `@HttpClient`, `@Repository`, `@Query`, `@KafkaListener`, `@KafkaPublisher`, gRPC server/client stubs, `@S3.Client` for object storage, MapStruct mappers, `@KoraAppTest` and Testcontainers integration tests, HOCON/YAML config via `@ConfigSource`, OpenAPI codegen (`kora` generator), JSON serialization with `@Json`, metrics (Micrometer + Prometheus on the private port via `MetricsModule`), tracing (OpenTelemetry OTLP exporter), structured logging (Logback + `KoraAsyncAppender`), liveness/readiness probes, AOP-style annotations for validation (`@Valid`, `@Validate`), method logging (`@Log`, `@Mdc`), resilience (`@CircuitBreaker`, `@Retry`, `@Timeout`, `@Fallback`), scheduling (`@ScheduleAtFixedRate`, `@ScheduleWithCron`), caching (`@Cacheable`, `@CachePut`, `@CacheInvalidate` over Caffeine/Lettuce-Redis), JDBC repositories via Hikari + Undertow HTTP server. Use when the user mentions Kora, `kora-parent` BOM, builds a microservice with these concepts, or asks to scaffold/extend a Kora service.
---

# Kora Developer — Meta-skill for development on the Kora Framework

**Kora Version:** 1.x (for the latest version see the [changelog](https://raw.githubusercontent.com/kora-projects/kora-docs/refs/heads/master/mkdocs/docs/en/changelog/changelog.md))  
**Languages:** Java 25, Kotlin 1.9+  
**Build:** Gradle 9+ (recommended)

Read this first when:
- starting a new Kora microservice project from scratch (Java or Kotlin),
- adding or refactoring `@KoraApp` application graph with `*Module` interfaces,
- choosing which Kora modules to plug in (HTTP, Database, Kafka, gRPC, S3, Telemetry),
- debugging DI container issues ("dependency not found", ambiguous bindings, graph build failures),
- configuring typed config with `@ConfigSource` and environment variable substitution,
- planning a multi-module Gradle project with `@KoraSubmodule` boundaries.

---

## How to use this meta-skill

This meta-skill is the **single entry point** for development on the Kora Framework. It contains 14 specialized sub-skills, each with its own area of expertise.

### Navigation priority

```
1. This meta-skill (navigation + architectural principles)
        ↓
2. Sub-skill for the relevant area (SKILL.md in its folder)
        ↓
3. Reference documents inside the sub-skill (references/)
        ↓
4. External documentation and examples (.kora-agent/)
```

**Important:** Don't jump straight to the external documentation. First study the relevant sub-skill — it contains concentrated expertise with ready-made templates, scripts, and patterns.

---

## Sub-skill navigation

**14 specialized sub-skills** in this folder. Read the SKILL.md of the relevant sub-skill **before** writing code.

| Task                                                                    | Sub-skill | Path |
|-------------------------------------------------------------------------|-----------|------|
| **Project scaffolding**, DI container, lifecycle, config, env vars      | `kora-bootstrap` | [`kora-bootstrap/SKILL.md`](kora-bootstrap/SKILL.md) |
| **JSON DTOs**, sealed discriminators, custom (de)serialization          | `kora-json` | [`kora-json/SKILL.md`](kora-json/SKILL.md) |
| **Continuous improvement journal**, collecting fixes and improvements   | `kora-journal` | [`kora-journal/SKILL.md`](kora-journal/SKILL.md) |
| **HTTP server** (controllers, routes, request/response, error mapping)  | `kora-http-server` | [`kora-http-server/SKILL.md`](kora-http-server/SKILL.md) |
| **HTTP clients** (declarative `@HttpClient`, interceptors)              | `kora-http-client` | [`kora-http-client/SKILL.md`](kora-http-client/SKILL.md) |
| **OpenAPI codegen** (server delegates / clients, `openapi-management`)  | `kora-openapi` | [`kora-openapi/SKILL.md`](kora-openapi/SKILL.md) |
| **AOP** (validation, logging, resilient, scheduling, caching)           | `kora-aop` | [`kora-aop/SKILL.md`](kora-aop/SKILL.md) |
| **Kafka** (producers/consumers, batch listeners, transactions)          | `kora-kafka` | [`kora-kafka/SKILL.md`](kora-kafka/SKILL.md) |
| **Telemetry** (metrics, tracing, structured logging, liveness/readiness) | `kora-telemetry` | [`kora-telemetry/SKILL.md`](kora-telemetry/SKILL.md) |
| **Database JDBC** (repositories, `@Query`, transactions, migrations)    | `kora-database` | [`kora-database/SKILL.md`](kora-database/SKILL.md) |
| **gRPC** (server handlers + client stubs)                               | `kora-grpc` | [`kora-grpc/SKILL.md`](kora-grpc/SKILL.md) |
| **S3** (object storage: AWS, MinIO, Yandex)                             | `kora-s3` | [`kora-s3/SKILL.md`](kora-s3/SKILL.md) |
| **Integration tests** (`@KoraAppTest`, Testcontainers)                  | `kora-testing` | [`kora-testing/SKILL.md`](kora-testing/SKILL.md) |
| **MapStruct** (DTO ↔ entity mappers)                                    | `kora-mapstruct` | [`kora-mapstruct/SKILL.md`](kora-mapstruct/SKILL.md) |

---

## Recommended reading order

For a new Kora service:

1. **kora-bootstrap** — scaffolding + DI + config
2. **kora-http-server** or **kora-http-client** — HTTP communication
3. **kora-database** — JDBC repositories
4. **kora-telemetry** — observability
5. **kora-aop** — validation, logging, resilience, caching
6. The rest — as needed

Don't wire in everything at once — only what your service needs for its endpoints/storage/messaging.

---

### Development Workflow Requirements

**Iterative Development with Validation**:
- Write minimal code increments
- Compile after every major change (`./gradlew clean classes`)
- Run tests immediately (`./gradlew test`)
- Validate against examples before proceeding

---

## Kora architectural principles

These principles apply to **every** sub-skill.

### 1. Compile-time first

Kora avoids reflection, dynamic proxies, and runtime bytecode generation. All the magic happens at compile time:
- DI container → `*ComponentImpl.java`
- HTTP routes → `*HttpRouter.java`
- AOP aspects → `*Aspect.java`
- JSON readers/writers → `*JsonReader.java`, `*JsonWriter.java`
- Repositories → `*RepositoryImpl.java`

**Validate code by compiling + testing.** Kora is a compile-time framework: if the code compiles and the tests pass, the implementation is correct. Use runtime checks only as a last resort.

### 2. Annotation processors are mandatory

```groovy
// Java
annotationProcessor "ru.tinkoff.kora:annotation-processors"

// Kotlin
ksp "ru.tinkoff.kora:symbol-processors"
```

Without them, **nothing works**.

### 3. BOM dependency

Always use the `kora-parent` BOM:

```groovy
dependencies {
    koraBom platform("ru.tinkoff.kora:kora-parent:1.2.15")
}
```

All Kora modules will be on the same version.

### 4. Modules as interfaces

External Kora capabilities (Json, HTTP, Kafka, ...) are delivered as `*Module` interfaces. The `@KoraApp` interface declares which ones to plug in via `extends ...Module`.

```java
@KoraApp
public interface Application extends
    HoconConfigModule,
    JsonModule,
    LogbackModule,
    UndertowHttpServerModule { }
```

### 5. Strongly typed config

Define `@ConfigSource("path.to.section")` interfaces and inject them as components:

```java
@ConfigSource("app.database")
public interface DatabaseConfig {
    String url();                    // required
    @Nullable String username();     // optional
    String password();               // required
    default int poolSize() { return 20; } // default
}
```

Externalize every credential: `${VAR}` / `${?VAR}` / `${?VAR:default}`.

### 6. Observability from day one

Plug in `metrics-micrometer`, `tracing-otel-*`, `probes`, `logging-logback`. Every Kora module emits telemetry that can be toggled in config.

### 7. Testing with Testcontainers

Integration tests should spin up a real DB / Kafka / dependent service via Testcontainers, not mocks. See `kora-java-crud` for the canonical pattern.

### 8. HTTP server defaults

- `httpServer.publicApiHttpPort` — public traffic
- `httpServer.privateApiHttpPort` — metrics/probes

Don't co-mingle them.

### 9. Repository patterns

- Named `@Query` parameters
- `RETURNING` for auto-generated IDs
- `@Column` on every record field used as a DAO row

### 10. Don't mix paradigms

- If you generate a controller from OpenAPI — use the delegate, don't write a manual controller
- If you use Kora `@HttpClient` — don't use OkHttp by hand for the same target

---

## 💡 Tips for debugging and understanding

### If something is unclear — look at the generated code

Kora is a compile-time framework. If it's unclear how DI, AOP, or another mechanism works:

1. Open `$buildDir/generated/sources/annotationProcessor/`
2. Find the generated class (`*ComponentImpl`, `*Graph`, `*Aspect`)
3. Study how the code is wired together

This helps you understand how Kora processes your annotations.

### Study the generated delegate code (OpenAPI)

Before implementing the delegate, open `$buildDir/generated/` and look at:
- The structure of the `*Delegate` interfaces
- Which methods to implement
- Return types (`ApiResponses` and subclasses)
- HTTP status handling

---

## Build troubleshooting

Annotation processors / KSP run at compile time.

| Problem | Solution |
|---------|----------|
| **Build hangs / fails after clean** | `./gradlew --stop` — terminate the daemons, then retry |
| **Generated classes broken after a refactor** | Clean `build/generated/` (annotationProcessor/, proto/, openapi/), rebuild |
| **"Required dependency not found: Foo"** | Check: `@Component` on the class, `extends *Module` on `@KoraApp`, `@KoraSubmodule` for multi-module |
| **`ApplicationGraph` missing after clean** | Run `./gradlew classes` — annotation processors must run first |
| **IDE shows errors but compilation passes** | The IDE is caching — invalidate caches / restart, or wait for indexing |

---

## Local documentation setup

**Critical first step:** Clone the documentation and examples:

```bash
mkdir -p .kora-agent
git clone --depth 1 https://github.com/kora-projects/kora-docs.git .kora-agent/kora-docs
git clone --depth 1 https://github.com/kora-projects/kora-examples.git .kora-agent/kora-examples
rm -rf .kora-agent/kora-docs/.git .kora-agent/kora-examples/.git
echo ".kora-agent/" >> .gitignore
```

**Paths:**
- `.kora-agent/kora-docs/mkdocs/docs/en/documentation/` — per-module documentation
- `.kora-agent/kora-examples/` — working example projects

---

## 🗺️ Quick reference map of examples

Full mapping table: **Kora module → documentation → examples**.

| Kora module | Documentation | Examples |
|-------------|--------------|---------|
| **Bootstrap** | `config.md`, `container.md`, `general.md` | `kora-java-helloworld`, `kora-java-config-hocon`, `kora-java-config-yaml` |
| **HTTP Server** | `http-server.md` | `kora-java-http-server`, `kora-java-http-server-undertow` |
| **HTTP Client** | `http-client.md` | `kora-java-http-client`, `kora-java-http-client-apache` |
| **OpenAPI** | `openapi.md` | `kora-java-openapi-generator-http-server`, `kora-java-openapi-generator-http-client` |
| **Database JDBC** | `database-jdbc.md`, `database-repository.md` | `kora-java-database-jdbc`, `kora-java-crud` |
| **Database Cassandra** | `database-cassandra.md` | `kora-java-database-cassandra` |
| **gRPC** | `grpc.md` | `kora-java-grpc-server`, `kora-java-grpc-client` |
| **Kafka** | `kafka.md` | `kora-java-kafka`, `kora-java-kafka-batch` |
| **JSON** | `json.md`, `json.md` | `kora-java-json`, `kora-java-json-module` |
| **Validation** | `validation.md` | `kora-java-validation` |
| **Telemetry** | `telemetry.md`, `metrics.md`, `tracing.md` | `kora-java-telemetry`, `kora-java-metrics-micrometer`, `kora-java-tracing-opentelemetry` |
| **Logging** | `logging.md` | `kora-java-logging-logback` |
| **Cache Caffeine** | `cache-caffeine.md` | `kora-java-cache-caffeine` |
| **Cache Redis** | `cache-redis.md` | `kora-java-cache-redis` |
| **Resilience** | `resilient.md` | `kora-java-resilient` |
| **Scheduling** | `scheduling.md` | `kora-java-scheduling-jdk`, `kora-java-scheduling-quartz` |
| **S3** | `s3.md` | `kora-java-s3-client-aws`, `kora-java-s3-client-minio` |
| **MapStruct** | `mapper.md` | `kora-java-mapper-mapstruct` |
| **GraalVM** | `native-image.md` | `kora-java-graalvm-crud-*` |
| **Camunda** | `camunda.md` | `kora-java-camunda-engine`, `kora-java-camunda-zeebe-worker` |

**Paths:**
- Documentation: `.kora-agent/kora-docs/mkdocs/docs/en/documentation/<module>.md`
- Examples: `.kora-agent/kora-examples/kora-java-<name>/`

---

## Out-of-scope modules

The following modules are **not covered** by these skills (narrow use cases):
- SOAP client
- R2DBC / Vert.x drivers (Cassandra is covered in `kora-database`)
- Camunda (BPMN/REST, Zeebe)
- GraalVM native-image

For these, read `.kora-agent/kora-docs/.../<module>.md` directly.

---

## Database drivers — important note

This meta-skill covers **JDBC** as the canonical Kora path. Kora also provides `database-r2dbc` and `database-vertx` with the same `@Repository`/`@Query` API — but **the Kora maintainers do not recommend them**.

Start every service with **JDBC + Hikari**. Deviate only with a hard requirement and prod-experience sign-off. See [`kora-database/SKILL.md`](kora-database/SKILL.md) for the full rationale.

---

## Sources

**Source priority:**

1. **Sub-skills** — concentrated expertise with templates and scripts
2. **Reference documents** inside each sub-skill (`references/`)
3. **External documentation:** `.kora-agent/kora-docs/mkdocs/docs/en/documentation/<module>.md`
4. **Examples:** `.kora-agent/kora-examples/kora-java-<name>/`
5. **Changelog:** https://github.com/kora-projects/kora-docs

**If there's a discrepancy** between this skill and the source — trust the source and update the skill.

---

## Continuous Improvement Journal

Use the separate **kora-journal** sub-skill to maintain a continuous improvement journal.

```bash
# Add a journal entry
python kora-journal/scripts/kora_journal.py add "Title" \
  --context "..." --problem "..." --solution "..." \
  --files kora-http/CLAUDE.md

# List entries
python kora-journal/scripts/kora_journal.py list --limit 10

# Export entries
python kora-journal/scripts/kora_journal.py export --since 2026-05-01
```

**Documentation:** [kora-journal/SKILL.md](kora-journal/SKILL.md)

**Important:** The journal is stored locally in `.kora-agent/journal/guideline.md` and is not committed to git.
