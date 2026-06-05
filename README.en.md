# Kora Skills for Claude Code

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://www.apache.org/licenses/LICENSE-2.0)
[![Java](https://img.shields.io/badge/Java-17+-blue)](https://www.oracle.com/java/)
[![Kotlin](https://img.shields.io/badge/Kotlin-1.7+-purple)](https://kotlinlang.org/)
[![Kora](https://img.shields.io/badge/Kora-1.2.15+-green)](https://github.com/kora-projects/kora)
[![Validate Skills](https://github.com/kora-projects/kora-skills/actions/workflows/validate.yml/badge.svg)](https://github.com/kora-projects/kora-skills/actions/workflows/validate.yml)

> **[🇷🇺 Русский](README.md)**

Claude Code Skills for [Kora framework](https://github.com/kora-projects/kora) — compile-time DI for Java/Kotlin microservices.

## About Kora Framework

Kora is a cloud-oriented server-side framework for Java/Kotlin that achieves high performance through:

| Principle | Benefit |
|-----------|---------|
| **No reflection at runtime** | All magic happens at compile time |
| **No dynamic proxies** | Compile-time aspect weaving |
| **No bytecode generation** | Source code generation via annotation processors / KSP |
| **Compile-time DI** | Dependency container built at compile time |
| **Virtual threads** | Efficient blocking I/O with Project Loom (Java 21+) |
| **GraalVM Native** | Native image compatibility out of the box |

### 4 Pillars of Kora

**Performance** — Kora generates high-performance code at compile time:
- No Reflection API at runtime
- No dynamic proxies
- Fine-grained abstractions
- Free aspects without performance penalty
- Only the most efficient implementation of integrations

**Efficiency** — Low resource consumption:
- Startup time: 50-100ms
- Idle memory: ~50MB
- Efficient horizontal scaling
- Maximum cluster resource utilization

**Transparency** — Transparent behavior:
- Human-readable generated code
- No black box effect
- Clear abstractions
- Full control over behavior

**Simplicity** — Development simplicity:
- One best solution per problem
- Familiar high-level abstractions
- No complex designs or redundant abstractions
- Easy onboarding for new developers

### Out of the Box

Kora provides ready-to-use modules for rapid development:

| Category | Modules |
|----------|---------|
| **HTTP** | HTTP server (Undertow), HTTP clients (JDK, OkHttp) |
| **Database** | JDBC, Cassandra, R2DBC, Vert.x, Flyway, Liquibase |
| **Messaging** | Kafka producers/consumers, gRPC server/client |
| **Storage** | S3 client (AWS S3, MinIO, Yandex Cloud) |
| **Resilience** | CircuitBreaker, Retry, Timeout, Fallback |
| **Caching** | Caffeine, Redis with AOP |
| **Scheduling** | JDK scheduling, Quartz |
| **Observability** | OpenTelemetry tracing, Micrometer metrics, logging |
| **Contract-First** | OpenAPI codegen (server/client), Swagger UI |
| **Workflow** | Camunda 7 BPMN/REST, Camunda 8 worker |
| **Testing** | JUnit5 extension, Testcontainers, Mockito |

### Performance

Kora demonstrates excellent results in independent benchmarks:

- **TechEmpower Benchmarks** — top positions in Fortune category
- **Startup time** — 50-100ms for typical microservice
- **Memory footprint** — ~50MB idle vs 200-300MB for Spring Boot

## Quick Start

### Option 1: One-line installation

```bash
curl -fsSL https://raw.githubusercontent.com/kora-projects/kora-skills/main/skills/kora/install.sh | bash
```

### Option 2: Clone and install

```bash
git clone https://github.com/kora-projects/kora-skills.git
cd kora-skills/skills/kora && ./install.sh
```

## Available Commands

After installation, these commands become available in Claude Code CLI:

| Command | Description |
|---------|-------------|
| `/kora` | Main meta-skill: 10 Kora principles, navigation, bootstrap guidance |
| `/kora-mega` | **Universal skill**: all 14 modules in one file (alternative to individual skills) |
| `/kora-bootstrap` | Scaffold new project, configure DI, HOCON/YAML config |
| `/kora-database` | JDBC/Cassandra repositories, `@Query`, migrations |
| `/kora-http-server` | REST controllers with `@HttpController`, routing, interceptors |
| `/kora-http-client` | Declarative HTTP clients, interceptors, error handling |
| `/kora-openapi` | OpenAPI codegen (server/client), Swagger UI, validation |
| `/kora-aop` | Validation (`@Valid`), logging (`@Log`), resilience (`@CircuitBreaker`, `@Retry`), caching (`@Cacheable`), scheduling |
| `/kora-kafka` | Kafka producers, consumers, batch listeners, transactions |
| `/kora-telemetry` | Metrics (Micrometer), tracing (OpenTelemetry), logging |
| `/kora-grpc` | gRPC server/client, protobuf, interceptors |
| `/kora-s3` | S3 object storage (AWS S3, MinIO) |
| `/kora-testing` | `@KoraAppTest`, Testcontainers, Mockito, black-box tests |
| `/kora-mapstruct` | DTO ↔ Entity mapping with MapStruct |
| `/kora-json` | JSON serialization with `@Json`, sealed interfaces |
| `/kora-journal` | Continuous improvement journal |

## Documentation

See [skills/kora/README.md](skills/kora/README.md) for detailed documentation.

Additional resources:
- [Kora Framework Documentation](https://kora-projects.github.io/kora-docs/en/)
- [Example Projects](https://github.com/kora-projects/kora-examples)
- [Kora Changelog](https://kora-projects.github.io/kora-docs/en/changelog/changelog/)

## Requirements

| Component | Version | Purpose |
|-----------|---------|---------|
| Java | 17+ (recommended: 25) | Primary development language |
| Kotlin | 1.7+ (JVM 17) | For Kotlin projects |
| Gradle | 7+ | Build tool (required for incremental annotation processing) |
| Claude Code CLI | latest | To use the skills |

### Why Gradle (not Maven)?

Kora **recommends Gradle** because:
- Optimal annotation processor support (Java) and KSP (Kotlin)
- Incremental build support — significantly faster builds
- Multi-round annotation processing — critical for Kora code generation
- Better integration with the Kora BOM

Maven is technically possible but significantly slower.

## Who Is This For

- **Java/Kotlin developers** starting with Kora
- **Architects** evaluating compile-time DI frameworks
- **Teams** migrating from Spring to Kora
- **Tech leads** building microservice development standards

## Why Kora for AI Agents

Kora is **uniquely suited** for AI agent and LLM-based development:

| Benefit | Why It Matters for AI Agents |
|---------|---------------------------|
| **Fast startup (50-100ms)** | Agents spin up/down instantly, reducing latency |
| **Low memory (~50MB idle)** | Run 6x more agents on same hardware vs Spring Boot |
| **Compile-time DI** | No runtime surprises — predictable behavior |
| **Readable generated code** | AI can understand, modify, and extend generated code safely |
| **No reflection/proxies** | Clean stack traces, transparent behavior for AI analysis |
| **Virtual threads** | Handle thousands of concurrent agent tasks efficiently |

## License

Apache 2.0 License — see [LICENSE](LICENSE)

## Support

- **Issues:** [GitHub Issues](https://github.com/kora-projects/kora-skills/issues)
- **Discussions:** [GitHub Discussions](https://github.com/kora-projects/kora-skills/discussions)
- **Documentation:** [kora-projects.github.io/kora-docs/en](https://kora-projects.github.io/kora-docs/en/)
