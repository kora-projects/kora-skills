# Kora 2.0 Source, Docs & Example Map

Lookup table for level 5 of the R1 routing chain. Read this **only after** the relevant sub-skill
and its `references/` did not answer the question.

## Kora 2.0 documentation

Kora 2.0 is documented at [koraframework.io/v2/en](https://koraframework.io/v2/en/)
([ru](https://koraframework.io/v2/ru/)). The site is built from the `kora-docs` branch
`feature/kora-2.0`, directory `mkdocs/docs/v2/{en,ru}/`, which R0 clones to `.kora-agent/kora-docs-2.0/`.
It has two halves: `documentation/<module>.md` (reference per module) and `guides/*.md` (step-by-step
tutorials backed by the `kora-examples` guide apps).

The 2.0 docs are rewritten for `io.koraframework`, but they trail the framework: a page can still
describe behaviour that a later commit changed. Evidence order, highest first:

1. Framework source and tests — API names, config keys, defaults
2. Migrated example applications — working code
3. Kora 2.0 docs (`docs/v2`) — concepts, intent, recipes
4. Kora 1.x docs (`docs/v1`, `kora-projects.github.io/kora-docs`) — `ru.tinkoff.kora` vocabulary and
   background only, and only when you say so out loud

**Consequences:**

- A config key, default, class name or signature read in the docs is a hypothesis until the source
  confirms it. Docs and source disagree → the source wins.
- Never take an answer from a `docs/v1` page or from `kora-projects.github.io/kora-docs`: those pages
  are 1.x and look authoritative.
- A 2.0 feature missing from the docs is not evidence that it does not exist — check `settings.gradle`.

## Path templates

| Source | Path template | Ref |
|---|---|---|
| Framework source | `.kora-agent/kora-source-2.0/<area>/<module>/src/main/java/...` | tag `2.0.0.RC2` (or `master`) |
| Framework tests (behaviour, generated-code shape) | `.kora-agent/kora-source-2.0/<area>/<module>/src/test/...` | tag `2.0.0.RC2` (or `master`) |
| Version catalog (third-party versions) | `.kora-agent/kora-source-2.0/gradle/libs.versions.toml` | tag `2.0.0.RC2` (or `master`) |
| Artifact list | `.kora-agent/kora-source-2.0/settings.gradle` | tag `2.0.0.RC2` (or `master`) |
| Docs — module reference | `.kora-agent/kora-docs-2.0/mkdocs/docs/v2/en/documentation/<page>.md` | branch `feature/kora-2.0` |
| Docs — guides | `.kora-agent/kora-docs-2.0/mkdocs/docs/v2/en/guides/<page>.md` | branch `feature/kora-2.0` |
| Example apps | `.kora-agent/kora-examples-2.0/examples/java/<app>/` | branch `migration/2.0` |
| Guide apps | `.kora-agent/kora-examples-2.0/guides/java/<app>/` | branch `migration/2.0` |
| Migration corpus (1.x → 2.0) | `.kora-agent/kora-examples-2.0/migration/` | branch `migration/2.0` |

Russian docs: replace `/en/` with `/ru/`. Published page for `documentation/<page>.md`:
`https://koraframework.io/v2/en/documentation/<page>/`.

**Kotlin variants:** every `kora-java-*` app has a Kotlin twin — replace `java` with `kotlin`
(`kora-java-http-server` → `kora-kotlin-http-server`). The reference module the Java migration guide
was written against is `examples/java/kora-java-crud`; the Kotlin counterpart is
`examples/kotlin/kora-kotlin-crud`.

**Precedence inside level 5:** framework source outranks the examples, and the examples outrank the
docs. Framework **tests** are the best evidence for generated-code shape and for defaults that no
prose states.

## Module map

| Domain | Framework source | Docs v2 (`mkdocs/docs/v2/en/`) | Example apps | Guide apps |
|---|---|---|---|---|
| Bootstrap / DI | `core/common`, `core/application-graph`, `core/kora-app-annotation-processor`, `core/kora-app-symbol-processor` | `documentation/general.md`, `documentation/container.md`; `guides/getting-started.md`, `guides/dependency-injection*.md` | `kora-java-helloworld`, `kora-java-crud`, `kora-java-crud-submodule` | `kora-java-guide-getting-started-app`, `kora-java-guide-dependency-injection-introduction-app`, `kora-java-guide-dependency-injection/*` |
| Config | `config/config-common`, `config/config-hocon`, `config/config-yaml`, `config/config-annotation-processor`, `config/config-symbol-processor` | `documentation/config.md`; `guides/config-hocon.md`, `guides/config-yaml.md` | `kora-java-config-hocon`, `kora-java-config-yaml` | `kora-java-guide-config-hocon-app`, `kora-java-guide-config-yaml-app` |
| HTTP Server | `http/http-common`, `http/http-server-common`, `http/http-server-undertow`, `http/http-server-annotation-processor`, `http/http-server-symbol-processor` | `documentation/http-server.md`; `guides/http-server*.md` | `kora-java-http-server`, `kora-java-crud` | `kora-java-guide-http-server-app`, `kora-java-guide-http-server-advanced-app` |
| HTTP Client | `http/http-client-common`, `http/http-client-ok`, `http/http-client-jdk`, `http/http-client-apache`, `http/http-client-annotation-processor`, `http/http-client-symbol-processor` | `documentation/http-client.md`; `guides/http-client*.md` | `kora-java-http-client` | `kora-java-guide-http-client-app`, `kora-java-guide-http-client-advanced-app` |
| OpenAPI | `openapi/openapi-generator`, `openapi/openapi-management` | `documentation/openapi-codegen.md`, `documentation/openapi-management.md`; `guides/openapi-*.md` | `kora-java-openapi-generator-http-server`, `kora-java-openapi-generator-http-client`, `kora-java-crud` | `kora-java-guide-openapi-http-server-app`, `kora-java-guide-openapi-http-server-advanced-app`, `kora-java-guide-openapi-http-client-app` |
| Database JDBC | `database/database-common`, `database/database-jdbc`, `database/database-jdbc-postgres`, `database/database-annotation-processor`, `database/database-symbol-processor` | `documentation/database-common.md`, `documentation/database-jdbc.md`; `guides/database-jdbc*.md` | `kora-java-database-jdbc`, `kora-java-crud`, `kora-java-petclinic` | `kora-java-guide-database-jdbc-app`, `kora-java-guide-database-jdbc-advanced-app` |
| Database Cassandra | `database/database-cassandra` | `documentation/database-cassandra.md`; `guides/database-cassandra.md` | `kora-java-database-cassandra` | `kora-java-guide-database-cassandra-app` |
| Migrations | `database/database-flyway`, `database/database-liquibase` | `documentation/database-migration.md` | `kora-java-crud` (Flyway) | `kora-java-guide-database-jdbc-advanced-app` |
| gRPC | `grpc/grpc-server`, `grpc/grpc-client`, `grpc/grpc-client-annotation-processor`, `grpc/grpc-client-symbol-processor` | `documentation/grpc-server.md`, `documentation/grpc-client.md`; `guides/grpc-*.md` | `kora-java-grpc-server`, `kora-java-grpc-client` | `kora-java-guide-grpc-server-app`, `kora-java-guide-grpc-server-advanced-app`, `kora-java-guide-grpc-client-app`, `kora-java-guide-grpc-client-advanced-app` |
| Kafka | `kafka/kafka`, `kafka/kafka-annotation-processor`, `kafka/kafka-symbol-processor` | `documentation/kafka.md`; `guides/messaging-kafka.md` | `kora-java-kafka` | `kora-java-guide-messaging-kafka-app` |
| JSON | `json/json-common`, `json/jackson-module`, `json/json-annotation-processor`, `json/json-symbol-processor` | `documentation/json.md`; `guides/json.md` | `kora-java-json` | `kora-java-guide-json-app` |
| Validation | `validation/validation-common`, `validation/validation-module`, `validation/validation-annotation-processor`, `validation/validation-symbol-processor` | `documentation/validation.md`; `guides/validation.md` | `kora-java-validation` | `kora-java-guide-validation-app` |
| Telemetry — metrics | `telemetry/telemetry-common`, `telemetry/micrometer-common`, `telemetry/micrometer-module` | `documentation/metrics.md`; `guides/observability-metrics.md` | `kora-java-telemetry` | `kora-java-guide-observability-app` |
| Telemetry — tracing | `telemetry/opentelemetry-common`, `telemetry/opentelemetry-tracing`, `telemetry/opentelemetry-tracing-exporter-grpc`, `telemetry/opentelemetry-tracing-exporter-http` | `documentation/tracing.md`; `guides/observability-tracing.md` | `kora-java-telemetry` | `kora-java-guide-observability-app` |
| Logging | `logging/logging-common`, `logging/logging-logback`, `logging/logging-logback-json`, `logging/logging-annotation-processor`, `logging/logging-symbol-processor` | `documentation/logging-slf4j.md`, `documentation/logging-aspect.md` | `kora-java-telemetry` | `kora-java-guide-observability-app` |
| Cache | `cache/cache-common`, `cache/cache-caffeine`, `cache/cache-redis-common`, `cache/cache-redis-lettuce`, `cache/cache-annotation-processor`, `cache/cache-symbol-processor` | `documentation/cache.md`; `guides/cache*.md` | `kora-java-cache-caffeine`, `kora-java-cache-redis` | `kora-java-guide-cache-app`, `kora-java-guide-cache-multi-level-app` |
| Resilience | `resilient/resilient-kora`, `resilient/resilient-kora-distributed`, `resilient/resilient-kora-distributed-redis-lettuce`, `resilient/resilient-annotation-processor`, `resilient/resilient-symbol-processor` | `documentation/resilient.md`; `guides/resilient.md` | `kora-java-resilient`, `kora-java-crud` | `kora-java-guide-resilient-app` |
| Scheduling | `scheduling/scheduling-common`, `scheduling/scheduling-jdk`, `scheduling/scheduling-quartz`, `scheduling/scheduling-db-scheduler`, `scheduling/scheduling-annotation-processor`, `scheduling/scheduling-symbol-processor` | `documentation/scheduling.md` | `kora-java-scheduling-jdk`, `kora-java-scheduling-quartz` | — |
| S3 | `s3/s3-client-aws`, `experimental/s3-client-kora`, `experimental/s3-client-annotation-processor`, `experimental/s3-client-symbol-processor` | `documentation/s3-client.md`; `guides/s3.md` | `kora-java-s3-client-aws`, `kora-java-s3-client-kora` | `kora-java-guide-s3-app` |
| Mapping | `mapping/mapstruct-java-extension` (Java), `mapping/konvert-ksp-extension` (Kotlin) | `documentation/mapstruct.md` | `kora-java-crud` (MapStruct), `kora-kotlin-crud` (Konvert) | — |
| SOAP | `http/soap-client`, `http/soap-client-annotation-processor`, `http/soap-client-symbol-processor` | `documentation/soap-client.md` | `kora-java-soap-client` | — |
| Testing | `test/test-junit5` | `documentation/junit5.md`; `guides/testing-*.md` | every example's `src/test` | `kora-java-guide-testing-junit-app`, `kora-java-guide-testing-integration-app`, `kora-java-guide-testing-black-box-app` |

All three telemetry domains share one guide app — `kora-java-guide-observability-app`. The 2.0 docs
split it into `guides/observability.md`, `observability-metrics.md`, `observability-tracing.md` and
`observability-probes.md`, all backed by that one app.

No example or guide app exists yet for `database-jdbc-postgres`, `scheduling-db-scheduler`,
`resilient-kora-distributed*` or `logging-logback-json`. For those, the framework tests are the only
working code — read them before writing any.

## Removed in Kora 2.0 — do not look for them, do not recommend them

These are **gone**, not merely undocumented or discouraged. Any request that assumes them needs a
redesign conversation, not a workaround.

| 1.x feature | Status in 2.0 | Replacement |
|---|---|---|
| `database-r2dbc` | removed | synchronous `database-jdbc` on virtual threads |
| `database-vertx` | removed | synchronous `database-jdbc` on virtual threads |
| Reactive / `suspend` repository, controller and HTTP-client contracts | removed | synchronous contracts |
| `Context` | removed from the whole framework | rewrite the signature |
| `http-client-async` | removed | `http-client-jdk`, `http-client-ok`, `http-client-apache` |
| `s3-client-minio` | removed | `experimental:s3-client-kora`; any S3-compatible **server** (MinIO, RustFS, SeaweedFS, LocalStack) still works for tests |
| `json-module` | renamed | `json-common` |
| `cache-redis` | replaced | `cache-redis-lettuce` (plus transport-neutral `cache-redis-common`) |
| `kora-parent` | replaced | `kora-bom` |
| RapiDoc viewer | replaced | Scalar (`openapi.management.scalar`) |
| `java-reactive-*`, `kotlin-suspend-*`, `kotlin-reactive-*` OpenAPI modes | removed | `java-client`, `java-server`, `kotlin-client`, `kotlin-server` |

`kora-parent` and `cache-redis` still appear in the `io/koraframework/` directory listing on Maven
Central. Those are 1.x/alpha leftovers; neither is constrained by the `2.0.0.RC2` BOM. Directory
presence is not availability.

## Out of scope for this plugin

No sub-skill covers these. Read the framework source and the example apps directly, and say to the
user that you are working outside the plugin's vetted material.

| Area | Framework source | Example apps |
|---|---|---|
| Camunda 7 (BPMN / REST) | `experimental/camunda-engine-bpmn`, `experimental/camunda-rest-undertow` (docs: `documentation/camunda7-bpmn.md`, `documentation/camunda7-rest.md`) | `kora-java-camunda-engine` |
| Camunda 8 / Zeebe worker | `experimental/camunda-zeebe-worker`, `experimental/camunda-zeebe-worker-annotation-processor`, `experimental/camunda-zeebe-worker-symbol-processor` (docs: `documentation/camunda8-worker.md`) | `kora-java-camunda-zeebe-worker` |
| GraalVM native image | — (build configuration, not a Kora module; docs: `documentation/graalvm-native.md`) | `examples/graalvm/kora-java-graalvm-crud-jdbc`, `kora-java-graalvm-crud-cassandra`, `kora-java-graalvm-kafka` |
| JMS | `jms` | — |
| Netty tuning | `netty-common` (docs: `documentation/netty.md`) | — |
| Redis client (outside caching) | `redis/redis-lettuce` | `kora-java-cache-redis` |
| Probes / readiness | `core/common/.../liveness`, `core/common/.../readiness`, `http/http-server-common/.../system` (docs: `documentation/probes.md`, `guides/observability-probes.md`) | any example with `httpServer.system` configured |

**Driver guidance:** JDBC with HikariCP is the only relational path in Kora 2.0, and it is the
maintainer-recommended one. Virtual threads make blocking JDBC calls cheap, which is why the
reactive drivers were dropped rather than ported.
