# Kora Documentation & Example Map

Lookup table for step 5 of the routing procedure (external sources). Read this **only after**
the relevant sub-skill and its `references/` did not answer the question.

## Path templates

| Source | Path template |
|--------|---------------|
| Documentation | `.kora-agent/kora-docs/mkdocs/docs/en/documentation/<doc>.md` |
| Guides | `.kora-agent/kora-docs/mkdocs/docs/en/guides/<guide>.md` |
| Example apps | `.kora-agent/kora-examples/examples/<app>/` |
| Guide apps | `.kora-agent/kora-examples/guides/<app>/` |
| Changelog | https://raw.githubusercontent.com/kora-projects/kora-docs/refs/heads/master/mkdocs/docs/en/changelog/changelog.md |

**Kotlin variants:** every `kora-java-*` app has a Kotlin twin — replace `java` with `kotlin`
(`kora-java-http-server` → `kora-kotlin-http-server`).

## Module map

| Module | Docs | Guides | Guide apps | Example apps |
|--------|------|--------|------------|--------------|
| Bootstrap | `config.md`, `container.md`, `general.md` | `getting-started.md`, `dependency-injection.md`, `config-hocon.md`, `config-yaml.md` | `kora-java-guide-getting-started-app`, `kora-java-guide-dependency-injection-introduction-app`, `kora-java-guide-config-hocon-app`, `kora-java-guide-config-yaml-app` | `kora-java-helloworld`, `kora-java-config-hocon` |
| HTTP Server | `http-server.md` | `http-server.md`, `http-server-advanced.md` | `kora-java-guide-http-server-app`, `kora-java-guide-http-server-advanced-app` | `kora-java-http-server`, `kora-java-http-server-undertow` |
| HTTP Client | `http-client.md` | `http-client.md`, `http-client-advanced.md` | `kora-java-guide-http-client-app`, `kora-java-guide-http-client-advanced-app` | `kora-java-http-client`, `kora-java-http-client-apache` |
| OpenAPI | `openapi.md` | `openapi-http-server.md`, `openapi-http-server-advanced.md`, `openapi-http-client.md` | `kora-java-guide-openapi-http-server-app`, `kora-java-guide-openapi-http-server-advanced-app`, `kora-java-guide-openapi-http-client-app` | `kora-java-openapi-generator-http-server`, `kora-java-openapi-generator-http-client` |
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
| SOAP | `soap-client.md` | — | — | `kora-java-soap-client` |
| Testing | — | `testing-junit.md`, `testing-integration.md`, `testing-black-box.md` | `kora-java-guide-testing-junit-app`, `kora-java-guide-testing-integration-app`, `kora-java-guide-testing-black-box-app` | — |

## Out of scope for this plugin

No sub-skill covers these — read the documentation directly and verify against the changelog:

| Area | Doc |
|------|-----|
| R2DBC driver | `database-r2dbc.md` |
| Vert.x driver | `database-vertx.md` |
| Camunda 7 (BPMN / REST) | `camunda7-bpmn.md`, `camunda7-rest.md` |
| Camunda 8 (Zeebe worker) | `camunda8-worker.md` |
| GraalVM native image | `graalvm-native.md` |
| Netty tuning | `netty.md` |
| Probes / readiness | `probes.md` |

**Driver guidance:** JDBC + Hikari is the canonical, maintainer-recommended path. `database-r2dbc`
and `database-vertx` exist but are **not recommended by Kora maintainers**. Deviate only on a hard
requirement, and say so explicitly to the user.
