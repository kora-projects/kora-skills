---
name: kora-codex-metaskill
description: "Build Java/Kotlin services on Kora Framework (ru.tinkoff.kora). Compile-time DI, reflection-free, annotation-processor (Java) or KSP (Kotlin) driven. Triggers - any Kora task, @KoraApp, @Component, @Module, @KoraSubmodule, @HttpController, @HttpClient, @Repository, @Query, @KafkaListener, @KafkaPublisher, gRPC, SOAP/WSDL, @S3.Client, MapStruct, @KoraAppTest, Testcontainers, @ConfigSource HOCON/YAML, OpenAPI codegen, @Json, metrics (Micrometer/Prometheus), tracing (OpenTelemetry OTLP), logging, probes, @Valid/@Validate, @Log/@Mdc, @CircuitBreaker/@Retry/@Timeout/@Fallback, @Schedule*, @Cacheable/@CachePut/@CacheInvalidate, JDBC/Hikari/Undertow. Use when - Kora build/setup/project/dependency/services/concept/asks mentioned."
---

# Kora Developer — Meta-skill for development on the Kora Framework

**Kora Version:** 1.x (for the latest version see the [changelog](https://raw.githubusercontent.com/kora-projects/kora-docs/refs/heads/master/mkdocs/docs/en/changelog/changelog.md))  
**Languages:** Java (JDK 25), Kotlin 1.9+ (JDK 21)
**Build:** Gradle 9.5.1+ (recommended)

---

## READ THIS FIRST — CORE RULES

**Three non-negotiable rules that apply to EVERY Kora task, from the FIRST session load:**

| Rule | What | Why |
|------|------|------|
| **CORE RULE #1** | Follow navigation priority: CLAUDE.md → SKILL.md → references/ → **search journal** → .kora-agent/ | Sub-skills + references are primary; journal has recent discoveries |
| **CORE RULE #2** | Kora-only development — NO Spring/other frameworks, NO unnecessary comments/Javadoc | Kora is compile-time DI; code should be self-explanatory |
| **CORE RULE #3** | Journal Kora Framework incorrect usage (agent self-realized or user-pointed) | Journal feeds skill improvements and prevents repeating Kora mistakes |

**WORKFLOW:** Minimal code → compile (`./gradlew clean classes`) → tests → run (`./gradlew test`). Stuck? `./gradlew --stop`.

**CORE RULE #3 SCOPE:** ONLY for Kora Framework incorrect usage — NOT for project-specific business logic, domain rules, or non-Kora issues.

**VIOLATION RESPONSE:** If you catch yourself violating any rule — **STOP immediately**, acknowledge the violation, and restart from the correct step.

---

## Introduction

**This meta-skill is the single entry point for Kora Framework development.** It routes to 39 specialized domain skills, each with its own narrow area of expertise.

**Read this file first when:**
- Starting a new Kora microservice project from scratch (Java or Kotlin)
- Adding or refactoring `@KoraApp` application graph with `*Module` interfaces
- Choosing which Kora modules to plug in (HTTP, Database, Kafka, gRPC, SOAP, S3, Telemetry)
- Debugging DI container issues ("dependency not found", ambiguous bindings, graph build failures)
- Configuring typed config with `@ConfigSource` and environment variable substitution
- Planning a multi-module Gradle project with `@KoraSubmodule` boundaries

---

## CORE RULES — Detailed

**These three rules are NON-NEGOTIABLE. Read and follow them at EVERY session start, before ANY Kora task, and continuously throughout the work.**

### CORE RULE #1: Navigation Priority

**ALWAYS follow this order — NO EXCEPTIONS:**

```
1. This meta-skill (CLAUDE.md) — navigation + architectural principles
        ↓
2. Relevant sub-skill (SKILL.md in ../<name>/) — concentrated expertise with templates
        ↓
3. Reference documents inside sub-skill (references/) — detailed patterns
        ↓
4. Search kora-journal (~/.kora-journal/) — check for existing solutions
        ↓
5. External docs/examples (.kora-agent/) — ONLY if steps 1-4 don't cover the case
```

**VIOLATION:** Jumping straight to Kora documentation or examples without reading the sub-skill first → **STOP AND RESTART** from step 2.

**WHY:** Sub-skills contain battle-tested patterns, scripts, and templates. External docs may be outdated or miss Kora-specific nuances.

**Search commands:**
```bash
# Search by keywords (in content + tags)
python kora-journal/scripts/kora_journal.py search "http interceptor auth" --limit 5

# Search by tags only (more precise)
python kora-journal/scripts/kora_journal.py search "auth oauth2" --by-tags

# Filter by status
python kora-journal/scripts/kora_journal.py search "Principal" --status pending
```

**If journal has relevant entry:**
1. Read the entry file (`~/.kora-journal/<project>/<module>/YYYY-MM-DD_slug.md`)
2. Apply the solution from the entry
3. If entry is `pending` and you applied it → mark as `integrated`
4. If entry helped but needs update → add new entry with improvements

**If journal has NO relevant entry:**
- Continue to step 5 (external docs/examples)
- After solving → add new entry to journal (CORE RULE #3)

---

### CORE RULE #2: Kora-Only Development

**Kora is an AUTHENTIC framework with its own annotations, classes, libraries, and modules.**

**NEVER:**
- Use Spring annotations (`@Autowired`, `@Service`, `@Repository`, `@Configuration`, etc.)
- Use Micronaut/Quarkus/Helidon annotations
- Hallucinate non-existent Kora annotations
- Apply patterns from other frameworks without verifying in Kora skills first
- Write comments or Javadoc in code UNLESS user explicitly requested OR truly complex logic (byte operations, encodings, cryptography, etc.)

**ALWAYS:**
- Use ONLY Kora annotations (`@KoraApp`, `@Component`, `@Module`, `@HttpController`, `@Repository`, etc.)
- Verify every annotation/class in the relevant Kora sub-skill BEFORE using
- Follow Kora's compile-time DI model (no reflection, no runtime proxies)
- Write self-explanatory code with clear names — let code speak for itself

**VIOLATION:** Using Spring/other framework patterns → **STOP, DELETE, REWRITE** using Kora skills.
**VIOLATION:** Writing unnecessary comments/Javadoc → **REMOVE** unless user requested or complexity justifies it.

---

### CORE RULE #3: Continuous Improvement Journal

**ALWAYS use the kora-journal to record Kora Framework incorrect usage discovered during development.**

**SCOPE — Kora Incorrect Usage ONLY:**

| ✅ Record in Journal | ❌ Do NOT Record |
|----------------------|------------------|
| Agent used wrong Kora annotation (self-realized or user-pointed) | Application business logic |
| Agent hallucinated non-existent Kora API | Project-specific domain rules |
| Agent misapplied Kora pattern (DI, AOP, config, etc.) | Temporary project workarounds |
| Agent violated Kora best practices from skills | UI/UX preferences |
| Skill documentation was unclear/wrong | Non-Kora framework issues |
| Agent wrote unnecessary comments/Javadoc (user didn't request) | |

**Trigger:** When YOU (agent) realize OR USER points out that you used Kora Framework incorrectly.

**Location:** `~/.kora-journal/<project>/<module>/<YYYY-MM-DD>_slug.md` — each entry is a **separate file**, shared across ALL sessions and projects.

```bash
# Add a journal entry AFTER discovering Kora incorrect usage
python kora-journal/scripts/kora_journal.py add "Wrong annotation used" \
  --context "What we were doing" \
  --problem "What Kora pattern was misused" \
  --solution "Correct Kora pattern" \
  --files ../kora-xxx/SKILL.md
```

**WHY:** Journal entries become the source of truth for future improvements. They feed back into skill updates and prevent repeating Kora mistakes.

**VIOLATION:** Discovering Kora incorrect usage without recording it → **GO BACK AND ADD** a journal entry.

---

**ENFORCEMENT:** These three CORE RULES apply to EVERY Kora task, from the FIRST session load and continuously thereafter. If you catch yourself violating any rule — STOP immediately, acknowledge the violation, and restart from the correct step.

---

## Sub-skill Navigation

**39 granular domain skills** organized by domain. Read the SKILL.md of the relevant sub-skill **before** writing code and then follow **CORE RULE #1** if required.

### Foundation (start here for new projects)

| Task | Sub-skill | Path |
|------|-----------|------|
| Gradle scaffolding, wrapper, build scripts, project structure | `kora-project-setup-java` | [`../kora-project-setup-java/SKILL.md`](../kora-project-setup-java/SKILL.md) |
| Gradle scaffolding (Kotlin), KSP, Kotlin DSL | `kora-project-setup-kotlin` | [`../kora-project-setup-kotlin/SKILL.md`](../kora-project-setup-kotlin/SKILL.md) |
| Kora BOM, modules, dependencies, annotation processors | `kora-project-dependencies` | [`../kora-project-dependencies/SKILL.md`](../kora-project-dependencies/SKILL.md) |
| Project generator, Spring Initializr style, working examples | `kora-project-dependencies` (generator) | [`../kora-project-dependencies/scripts/generate_project.py`](../kora-project-dependencies/scripts/generate_project.py) |
| HOCON config, typed `@ConfigSource`, env substitution | `kora-config-hocon` | [`../kora-config-hocon/SKILL.md`](../kora-config-hocon/SKILL.md) |
| YAML config (alternative to HOCON) | `kora-config-yaml` | [`../kora-config-yaml/SKILL.md`](../kora-config-yaml/SKILL.md) |

### Dependency Injection

| Task | Sub-skill | Path |
|------|-----------|------|
| Compile-time DI, `@KoraApp`, `@Component`, `@Module`, factories | `kora-di-compile` | [`../kora-di-compile/SKILL.md`](../kora-di-compile/SKILL.md) |
| Runtime DI, `@Root`, `Lifecycle`, `@Tag`, `All<T>`, `ValueOf<T>` | `kora-di-runtime` | [`../kora-di-runtime/SKILL.md`](../kora-di-runtime/SKILL.md) |

### Database

| Task | Sub-skill | Path |
|------|-----------|------|
| JDBC repositories, `@EntityJdbc`, `@Query`, SQL macros, transactions | `kora-database-jdbc` | [`../kora-database-jdbc/SKILL.md`](../kora-database-jdbc/SKILL.md) |
| Cassandra, `@EntityCassandra`, `@UDT`, CQL, profiles | `kora-database-cassandra` | [`../kora-database-cassandra/SKILL.md`](../kora-database-cassandra/SKILL.md) |
| Flyway and Liquibase migrations, SQL-based versioning | `kora-database-migration` | [`../kora-database-migration/SKILL.md`](../kora-database-migration/SKILL.md) |

### Testing

| Task | Sub-skill | Path |
|------|-----------|------|
| JUnit 5 component tests, `@KoraAppTest`, `@TestComponent`, mocks | `kora-testing-junit-java` | [`../kora-testing-junit-java/SKILL.md`](../kora-testing-junit-java/SKILL.md) |
| JUnit 5 component tests (Kotlin), MockK | `kora-testing-junit-kotlin` | [`../kora-testing-junit-kotlin/SKILL.md`](../kora-testing-junit-kotlin/SKILL.md) |
| Black-box E2E tests, `AppContainer`, Testcontainers, Docker | `kora-testing-blackbox` | [`../kora-testing-blackbox/SKILL.md`](../kora-testing-blackbox/SKILL.md) |

### Communication

| Task | Sub-skill | Path |
|------|-----------|------|
| HTTP server, `@HttpController`, `@HttpRoute`, `@Path`, `@Query`, `@Json` | `kora-http-server` | [`../kora-http-server/SKILL.md`](../kora-http-server/SKILL.md) |
| HTTP server auth, BasicAuth, Bearer, API keys, SecurityContext | `kora-http-server-auth` | [`../kora-http-server-auth/SKILL.md`](../kora-http-server-auth/SKILL.md) |
| HTTP client, `@HttpClient`, declarative interfaces, interceptors | `kora-http-client` | [`../kora-http-client/SKILL.md`](../kora-http-client/SKILL.md) |
| HTTP client auth, BasicAuth, Bearer, API keys | `kora-http-client-auth` | [`../kora-http-client-auth/SKILL.md`](../kora-http-client-auth/SKILL.md) |
| gRPC server, `GrpcServerModule`, `@Component` handlers | `kora-grpc-server` | [`../kora-grpc-server/SKILL.md`](../kora-grpc-server/SKILL.md) |
| gRPC client, `GrpcClientModule`, `@Tag` stub injection | `kora-grpc-client` | [`../kora-grpc-client/SKILL.md`](../kora-grpc-client/SKILL.md) |
| SOAP client, WSDL-to-Java, `SoapClientModule`, generated clients | `kora-soap-client` | [`../kora-soap-client/SKILL.md`](../kora-soap-client/SKILL.md) |
| Kafka producer, `@KafkaPublisher`, transactional | `kora-kafka-producer` | [`../kora-kafka-producer/SKILL.md`](../kora-kafka-producer/SKILL.md) |
| Kafka consumer, `@KafkaListener`, batch, error handling | `kora-kafka-consumer` | [`../kora-kafka-consumer/SKILL.md`](../kora-kafka-consumer/SKILL.md) |
| OpenAPI server codegen, delegates, controllers | `kora-openapi-generator-server` | [`../kora-openapi-generator-server/SKILL.md`](../kora-openapi-generator-server/SKILL.md) |
| OpenAPI client codegen, typed Api interfaces | `kora-openapi-generator-client` | [`../kora-openapi-generator-client/SKILL.md`](../kora-openapi-generator-client/SKILL.md) |
| OpenAPI management, Swagger UI, RapiDoc, spec publishing | `kora-openapi-management` | [`../kora-openapi-management/SKILL.md`](../kora-openapi-management/SKILL.md) |

### Telemetry

| Task | Sub-skill | Path |
|------|-----------|------|
| OpenTelemetry tracing, OTLP, spans, Jaeger/Zipkin | `kora-telemetry-tracing` | [`../kora-telemetry-tracing/SKILL.md`](../kora-telemetry-tracing/SKILL.md) |
| Micrometer metrics, Prometheus scrape, custom metrics | `kora-telemetry-metrics` | [`../kora-telemetry-metrics/SKILL.md`](../kora-telemetry-metrics/SKILL.md) |
| SLF4J/Logback, structured logging, `KoraAsyncAppender` | `kora-telemetry-logging` | [`../kora-telemetry-logging/SKILL.md`](../kora-telemetry-logging/SKILL.md) |

### AOP

| Task | Sub-skill | Path |
|------|-----------|------|
| @Retry, @CircuitBreaker, @Timeout, @Fallback | `kora-aop-resilient` | [`../kora-aop-resilient/SKILL.md`](../kora-aop-resilient/SKILL.md) |
| @Log, @Mdc, method logging aspect | `kora-aop-logging` | [`../kora-aop-logging/SKILL.md`](../kora-aop-logging/SKILL.md) |
| @Cacheable, @CachePut, @CacheInvalidate, Caffeine/Redis | `kora-aop-caching` | [`../kora-aop-caching/SKILL.md`](../kora-aop-caching/SKILL.md) |
| @ScheduleAtFixedRate, @ScheduleWithCron | `kora-aop-scheduling-jdk` | [`../kora-aop-scheduling-jdk/SKILL.md`](../kora-aop-scheduling-jdk/SKILL.md) |
| Quartz scheduling, cron jobs, clustered | `kora-aop-scheduling-quartz` | [`../kora-aop-scheduling-quartz/SKILL.md`](../kora-aop-scheduling-quartz/SKILL.md) |
| @Valid, @Validate, JSR-380 constraints | `kora-aop-validation` | [`../kora-aop-validation/SKILL.md`](../kora-aop-validation/SKILL.md) |

### Other

| Task | Sub-skill | Path |
|------|-----------|------|
| JSON DTOs, sealed discriminators, custom (de)serialization | `kora-json` | [`../kora-json/SKILL.md`](../kora-json/SKILL.md) |
| S3 object storage, AWS S3/MinIO, `@S3.Client`, multipart uploads | `kora-s3` | [`../kora-s3/SKILL.md`](../kora-s3/SKILL.md) |
| MapStruct mappers, DTO ↔ entity mapping | `kora-mapstruct` | [`../kora-mapstruct/SKILL.md`](../kora-mapstruct/SKILL.md) |

### Development Tools

| Task | Sub-skill | Path |
|------|-----------|------|
| Continuous improvement journal, Kora incorrect usage tracking | `kora-journal` | [`../kora-journal/SKILL.md`](../kora-journal/SKILL.md) |
| Learn Kora from scratch, guided tutorials, explain concepts | `kora-teacher` | [`../kora-teacher/SKILL.md`](../kora-teacher/SKILL.md) |

---

## Development & Architecture

### Workflow (MANDATORY)

| Step | Command | When |
|------|---------|------|
| 1. Write minimal increments | — | One change at a time — single annotation/method/class |
| 2. Compile | `./gradlew clean classes` | After any Kora annotation change, before tests |
| 3. Write integration tests | — | Use `@KoraAppTest` + Testcontainers; test real endpoints/queries/messages |
| 4. Run tests | `./gradlew test` | After compilation succeeds, before commit |
| 5. Stop daemons if stuck | `./gradlew --stop` | When builds hang or `clean` fails with "Unable to delete directory" |

### Architectural Principles

**Compile-time first:** Kora avoids reflection, dynamic proxies, and runtime bytecode generation. All magic happens at compile time (DI → `*ComponentImpl.java`, HTTP → `*HttpRouter.java`, AOP → `*Aspect.java`, JSON → `*JsonReader.java`/`*JsonWriter.java`, Repositories → `*RepositoryImpl.java`).

**Validate by compiling + testing:** If code compiles and tests pass — implementation is correct.

**Don't mix paradigms:** If you generate a controller from OpenAPI — use the delegate, don't write a manual controller. If you use Kora `@HttpClient` — don't use OkHttp by hand for the same target.

---

## Debugging & Troubleshooting

### Look at generated code

Kora is compile-time. If DI, AOP, or other mechanisms are unclear:

1. Open `$buildDir/generated/sources/annotationProcessor/` (Java) or `$buildDir/generated/ksp/` (Kotlin)
2. Find generated class (`*ComponentImpl`, `*Graph`, `*Aspect`, `*Delegate`)
3. Study how code is wired together

**OpenAPI delegates:** Before implementing, check generated `*Delegate` interface — methods to implement, return types (`ApiResponses`), HTTP status handling.

### Build problems

| Problem | Solution |
|---------|----------|
| Build hangs / fails after clean | `./gradlew --stop` — terminate daemons, retry |
| Generated classes broken after refactor | Clean `build/generated/`, rebuild |
| "Required dependency not found: Foo" | Check: `@Component` on class, `extends *Module` on `@KoraApp`, `@KoraSubmodule` for multi-module |
| `ApplicationGraph` missing after clean | Run `./gradlew classes` — annotation processors must run first |
| IDE shows errors but compilation passes | IDE caching — invalidate caches / restart |

---

## Documentation & Resources

### Setup (CORE RULE #2 PREREQUISITE)

Clone docs and examples BEFORE any Kora development:

```bash
mkdir -p .kora-agent
git clone --depth 1 https://github.com/kora-projects/kora-docs.git .kora-agent/kora-docs
git clone --depth 1 https://github.com/kora-projects/kora-examples.git .kora-agent/kora-examples
rm -rf .kora-agent/kora-docs/.git .kora-agent/kora-examples/.git
echo ".kora-agent/" >> .gitignore
```

**Verify:** `.kora-agent/` must contain both `kora-docs/` and `kora-examples/`.

### Quick Reference

| Module | Docs | Guides | Guide apps | Example apps |
|--------|------|--------|------------|--------------|
| Bootstrap | `config.md`, `container.md`, `general.md` | `getting-started.md`, `dependency-injection.md`, `config-hocon.md`, `config-yaml.md` | `kora-java-guide-getting-started-app`, `kora-java-guide-dependency-injection-introduction-app`, `kora-java-guide-config-hocon-app`, `kora-java-guide-config-yaml-app` | `kora-java-helloworld`, `kora-java-config-hocon` |
| HTTP Server | `http-server.md` | `http-server.md`, `http-server-advanced.md` | `kora-java-guide-http-server-app`, `kora-java-guide-http-server-advanced-app` | `kora-java-http-server`, `kora-java-http-server-undertow` |
| HTTP Client | `http-client.md` | `http-client.md`, `http-client-advanced.md` | `kora-java-guide-http-client-app`, `kora-java-guide-http-client-advanced-app` | `kora-java-http-client`, `kora-java-http-client-apache` |
| OpenAPI | `openapi.md` | `openapi-http-server.md`, `openapi-http-server-advanced.md`, `openapi-http-client.md` | `kora-java-guide-openapi-http-server-app`, `kora-java-guide-openapi-http-server-advanced-app`, `kora-java-guide-openapi-http-client-app` | `kora-java-openapi-generator-http-server/client` |
| Database JDBC | `database-jdbc.md`, `database-repository.md` | `database-jdbc.md`, `database-jdbc-advanced.md` | `kora-java-guide-database-jdbc-app`, `kora-java-guide-database-jdbc-advanced-app` | `kora-java-database-jdbc`, `kora-java-crud` |
| Database Cassandra | `database-cassandra.md` | `database-cassandra.md` | `kora-java-guide-database-cassandra-app` | `kora-java-database-cassandra` |
| gRPC | `grpc.md` | `grpc-server.md`, `grpc-server-advanced.md`, `grpc-client.md`, `grpc-client-advanced.md` | `kora-java-guide-grpc-server-app`, `kora-java-guide-grpc-server-advanced-app`, `kora-java-guide-grpc-client-app`, `kora-java-guide-grpc-client-advanced-app` | `kora-java-grpc-server`, `kora-java-grpc-client` |
| Kafka | `kafka.md` | `messaging-kafka.md` | `kora-java-guide-messaging-kafka-app` | `kora-java-kafka`, `kora-java-kafka-batch` |
| JSON | `json.md` | `json.md` | `kora-java-guide-json-app` | `kora-java-json`, `kora-java-json-module` |
| Validation | `validation.md` | `validation.md` | `kora-java-guide-validation-app` | `kora-java-validation` |
| Telemetry | `telemetry.md`, `metrics.md`, `tracing.md` | `observability.md`, `observability-metrics.md`, `observability-tracing.md`, `observability-probes.md` | `kora-java-guide-observability-app` | `kora-java-telemetry`, `kora-java-metrics-micrometer` |
| Logging | `logging.md` | `observability.md` | `kora-java-guide-observability-app` | `kora-java-logging-logback` |
| Cache | `cache-caffeine.md`, `cache-redis.md` | `cache.md`, `cache-multi-level.md` | `kora-java-guide-cache-app`, `kora-java-guide-cache-multi-level-app` | `kora-java-cache-caffeine`, `kora-java-cache-redis` |
| Resilience | `resilient.md` | `resilient.md` | `kora-java-guide-resilient-app` | `kora-java-resilient` |
| Scheduling | `scheduling.md` | — | — | `kora-java-scheduling-jdk`, `kora-java-scheduling-quartz` |
| S3 | `s3.md` | `s3.md` | `kora-java-guide-s3-app` | `kora-java-s3-client-aws`, `kora-java-s3-client-minio` |
| MapStruct | `mapper.md` | — | — | `kora-java-mapper-mapstruct` |
| Testing | — | `testing-junit.md`, `testing-integration.md`, `testing-black-box.md` | `kora-java-guide-testing-junit-app`, `kora-java-guide-testing-integration-app`, `kora-java-guide-testing-black-box-app` | — |

**Kotlin equivalents:** All `kora-java-*` apps have Kotlin counterparts — replace `java` → `kotlin` in the name (e.g., `kora-kotlin-guide-http-server-app`, `kora-kotlin-http-server`).

**Paths:** Docs: `.kora-agent/kora-docs/mkdocs/docs/en/documentation/<module>.md` | Guides: `.kora-agent/kora-docs/mkdocs/docs/en/guides/<guide>.md` | Examples apps: `.kora-agent/kora-examples/examples/...` | Guides apps: `.kora-agent/kora-examples/guides/...`

### Limitations

**Not covered** (narrow use cases — read docs directly):
- R2DBC / Vert.x drivers, Camunda (BPMN/REST, Zeebe), GraalVM native-image

**Database drivers:** This meta-skill covers **JDBC** as canonical path. Kora also provides `database-r2dbc` and `database-vertx` — but **Kora maintainers do not recommend them**. Start with **JDBC + Hikari**. Deviate only with hard requirement and prod-experience sign-off.

### Source Priority

1. **Sub-skills** — concentrated expertise with templates and scripts
2. **Reference documents** inside each sub-skill (`references/`)
3. **Kora documentation or guides** — `.kora-agent/kora-docs/docs/en/documentation/<module>.md` or `.kora-agent/kora-docs/mkdocs/docs/en/guides/<guide>.md`
4. **Examples** — `.kora-agent/kora-examples/examples/...` or `.kora-agent/kora-examples/guides/...`
5. **Changelog** — https://raw.githubusercontent.com/kora-projects/kora-docs/refs/heads/master/mkdocs/docs/en/changelog/changelog.md

**Discrepancy:** Trust the source and update the skill.

---

## Continuous Improvement Journal

See **CORE RULE #3** (line 120) for full journal requirements.

**Quick reference:**
- **When:** After discovering Kora incorrect usage (self-realized or user-pointed)
- **Where:** `~/.kora-journal/<project>/<module>/<YYYY-MM-DD>_slug.md`
- **Format:** Separate Markdown file per entry
- **NOT for:** Project business logic, domain rules, non-Kora issues

```bash
# Add journal entry
python kora-journal/scripts/kora_journal.py add "Title" \
  --context "..." --problem "..." --solution "..." --files "..."
```

**Docs:** [`../kora-journal/SKILL.md`](../kora-journal/SKILL.md)
