# kora-mega — Unified Kora Framework Skill

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://www.apache.org/licenses/LICENSE-2.0)
[![Java](https://img.shields.io/badge/Java-17+-blue)](https://www.oracle.com/java/)
[![Kotlin](https://img.shields.io/badge/Kotlin-1.7+-purple)](https://kotlinlang.org/)
[![Kora](https://img.shields.io/badge/Kora-1.2.15+-green)](https://github.com/kora-projects/kora)
[![Gradle](https://img.shields.io/badge/Gradle-7+-02303A)](https://gradle.org/)

A **unified mega-skill** combining all 14 Kora Framework sub-skills into one comprehensive guide for developing on the [Kora](https://github.com/kora-projects/kora) framework — a compile-time DI framework for Java/Kotlin backend development.

Kora is a cloud-oriented server-side framework that achieves high performance through:

- **No reflection at runtime** — all code generated at compile time
- **No dynamic proxies** — compile-time aspect weaving
- **No bytecode generation** — source code generation via annotation processors
- **Fine-grained abstractions** — simple, transparent APIs
- **Virtual threads support** — efficient blocking I/O

---

## 🚀 Quick Start

### Installation (choose one)

#### Option 1: Git clone + install script

```bash
# Clone the repository
git clone https://github.com/kora-projects/kora-skills.git
cd kora-skills/kora-mega

# Run install script
./install.sh
```

#### Option 2: Direct installation from the internet

```bash
# One-line automatic installation
curl -fsSL https://raw.githubusercontent.com/kora-projects/kora-skills/main/kora-mega/install.sh | bash
```

#### Option 3: Manual copy

```bash
# Copy kora-mega directory to ~/.claude/
cp -r kora-mega ~/.claude/skills/
```

### Usage

After installation, the following command becomes available in Claude Code CLI:

| Command       | Description                                                                                             |
|---------------|---------------------------------------------------------------------------------------------------------|
| `/kora-mega`  | **Unified skill**: all 14 Kora modules in one file — bootstrap, HTTP, database, Kafka, gRPC, S3, and more |

---

## 📦 Structure

```
kora-mega/
├── skill.json            # Manifest (dxt_version 1.0.0)
├── SKILL.md              # Unified mega-skill: all 14 modules in one file
├── README.md             # This file
├── install.sh            # Install script
├── assets/               # Code templates (all modules)
├── scripts/              # Python automation scripts
├── references/           # In-depth documentation (all modules)
└── evals/                # Evaluation scenarios (all modules)
```

**SKILL.md Contents:**

| #  | Module | Description |
|----|--------|-------------|
| 1  | Bootstrap | Project scaffolding, DI container, config, lifecycle |
| 2  | JSON | DTOs, sealed discriminators, custom (de)serialization |
| 3  | HTTP Server | Controllers, routes, request/response, error mapping |
| 4  | HTTP Client | Declarative `@HttpClient`, interceptors |
| 5  | OpenAPI | Codegen (server/client), Swagger UI, Rapidoc |
| 6  | AOP | Validation, logging, resilience, scheduling, caching |
| 7  | Kafka | Producers/consumers, batch listeners, transactions |
| 8  | Telemetry | Metrics, tracing, structured logging |
| 9  | Database | JDBC repositories, `@Query`, migrations |
| 10 | gRPC | Server handlers + client stubs |
| 11 | S3 | Object storage: AWS, MinIO, Yandex |
| 12 | Testing | `@KoraAppTest`, Testcontainers, black-box tests |
| 13 | MapStruct | DTO ↔ entity mappers |
| 14 | Journal | Continuous improvement journal |

---

## 🎯 Who Is This For

- **Java/Kotlin developers** who prefer a single comprehensive skill over 14 separate ones
- **Teams** wanting a unified reference for all Kora modules
- **Developers** working on multi-module microservices
- **Tech leads** building comprehensive development standards

---

## 🔧 Requirements

| Component       | Version               | Purpose                                                             |
|-----------------|-----------------------|---------------------------------------------------------------------|
| Java            | 17+ (recommended: 25) | Primary development language                                        |
| Kotlin          | 1.7+ (JVM 21)         | For Kotlin projects                                                 |
| Gradle          | 7+                    | Project build tool (required for incremental annotation processing) |
| Claude Code CLI | latest                | To use the skills                                                   |

### Why Gradle (not Maven)?

Kora **recommends Gradle** because:

- Optimal annotation processor support (Java) and KSP (Kotlin)
- Incremental build support — significantly faster builds
- Multi-round annotation processing — critical for Kora code generation
- Better integration with the Kora BOM

Maven is technically possible but significantly slower.

---

## 📖 Documentation

| Resource           | Link                                                                                                       |
|--------------------|------------------------------------------------------------------------------------------------------------|
| Kora Documentation | [kora-docs](https://github.com/kora-projects/kora-docs)                                                    |
| Example Projects   | [kora-examples](https://github.com/kora-projects/kora-examples)                                            |
| Kora Changelog     | [What's New](https://github.com/kora-projects/kora-docs/blob/master/mkdocs/docs/en/changelog/changelog.md) |
| Kora on GitHub     | [kora-projects/kora](https://github.com/kora-projects/kora)                                                |
| Java Template      | [kora-java-template](https://github.com/kora-projects/kora-java-template)                                  |
| Kotlin Template    | [kora-kotlin-template](https://github.com/kora-projects/kora-kotlin-template)                              |

---

## 🤖 Why Kora for AI Agents

Kora is **uniquely suited** for AI agent and LLM-based development:

| Benefit | Why It Matters for AI Agents |
|---------|-----------------------------|
| **Fast startup (50-100ms)** | Agents spin up/down instantly, reducing latency for on-demand tool execution |
| **Low memory (50MB idle)** | Run 6x more agents on the same hardware vs Spring Boot |
| **Compile-time DI** | No runtime surprises — agents behave predictably, easier to debug |
| **Readable generated code** | AI can understand, modify, and extend generated code safely |
| **No reflection/proxies** | Clean stack traces, transparent behavior for AI analysis |
| **Virtual threads** | Handle thousands of concurrent agent tasks efficiently |

---

## 🏗️ Kora Architectural Principles

### Core Principles

1. **Compile-time first** — all magic happens at compile time via annotation processors (Java) or KSP (Kotlin)
2. **No reflection** — zero runtime reflection overhead
3. **No dynamic proxies** — compile-time aspect weaving
4. **No bytecode generation** — source code generation only
5. **Fine-grained abstractions** — simple, composable APIs
6. **Free aspects** — AOP without performance penalty
7. **Most efficient implementations** — best-in-class integrations
8. **Transparency** — generated code is human-readable

### Key Features

| Feature                         | Description                                              |
|---------------------------------|----------------------------------------------------------|
| **Dependency Injection**        | Compile-time DI with `@KoraApp`, `@Component`, `@Module` |
| **Aspect-Oriented Programming** | Compile-time AOP via annotations                         |
| **Observability**               | OpenTelemetry metrics, tracing, logging out of the box   |
| **Virtual Threads**             | Full support for Java 21+ virtual threads                |
| **GraalVM Native**              | Compatible with GraalVM native image generation          |
| **Contract-First**              | OpenAPI-driven development with code generation          |

---

## 📦 Kora Modules

Kora provides a comprehensive set of modules:

### Core Modules

- `annotation-processors` / `symbol-processors` — compile-time code generation
- `json` — JSON serialization with `@Json`
- `config-hocon` / `config-yaml` — typed configuration
- `logging-logback` — logging integration

### HTTP

- `http-server-undertow` — embedded HTTP server
- `http-client-jdk` — JDK HTTP client
- `http-client-okhttp` — OkHttp client

### Databases

- `database-jdbc` — JDBC repositories with `@Query`
- `database-cassandra` — Cassandra repositories
- `database-r2dbc` — R2DBC (reactive)
- `database-vertx` — Vert.x (reactive)

### Messaging

- `kafka` — Kafka producers and consumers
- `grpc-server` / `grpc-client` — gRPC integration

### Integrations

- `openapi-codegen` — OpenAPI-driven code generation
- `s3-client` — AWS S3 compatible storage

### Resilience & Performance

- `resilient` — Circuit breaker, retry, timeout, fallback
- `cache-caffeine` / `cache-redis` — caching with AOP
- `scheduling-jdk` / `scheduling-quartz` — background job scheduling
- `validation` — Bean validation with `@Valid`

### Observability

- `telemetry-opentelemetry` — OpenTelemetry integration
- `metrics-micrometer` — Micrometer metrics

### Testing

- `junit5` — JUnit 5 extension
- `testcontainers` — Testcontainers integration

---

## 📦 Versioning

This package follows [SemVer](https://semver.org/):

```json
{
    "dxt_version": "1.0.0",
    "version": "1.0.0"
}
```

| Type      | When it changes                             |
|-----------|---------------------------------------------|
| **MAJOR** | Breaking changes in skill API or structure  |
| **MINOR** | New skills, features (backwards compatible) |
| **PATCH** | Bug fixes, documentation clarifications     |

**Kora Version:** 1.2.15+ (current at release time)

---

## 🤝 Contributing

1. Fork the repository
2. Create a branch (`git checkout -b feature/amazing-skill`)
3. Commit changes (`git commit -m "Add amazing skill"`)
4. Push (`git push origin feature/amazing-skill`)
5. Open a Pull Request

---

## 🔗 Distribution

### For Team Development

```bash
# Option 1: Git repo + install script
git clone https://github.com/your-org/kora-skills.git
cd kora-skills/kora-mega && ./install.sh

# Option 2: npx skills (via skills.sh registry)
npx skills add your-org/kora-mega
```

### Publishing to skills.sh Registry

```bash
# Requires skills.sh account
npx skills publish ./kora-mega
```

---

## 📝 License

Apache 2.0 License — see [LICENSE](LICENSE)

---

## 📞 Support

- **Issues:** [GitHub Issues](https://github.com/kora-projects/kora-skills/issues)
- **Discussions:** [GitHub Discussions](https://github.com/kora-projects/kora-skills/discussions)
- **Documentation:** [kora-docs](https://github.com/kora-projects/kora-docs/tree/master/mkdocs/docs/en/documentation)
