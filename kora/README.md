# kora — Claude Code Skills for Kora Framework

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://www.apache.org/licenses/LICENSE-2.0)
[![Java](https://img.shields.io/badge/Java-17+-blue)](https://www.oracle.com/java/)
[![Kotlin](https://img.shields.io/badge/Kotlin-1.7+-purple)](https://kotlinlang.org/)
[![Kora](https://img.shields.io/badge/Kora-1.2.15+-green)](https://github.com/kora-projects/kora)
[![Gradle](https://img.shields.io/badge/Gradle-7+-02303A)](https://gradle.org/)

A collection of **14 specialized Claude skills** for developing on the [Kora](https://github.com/kora-projects/kora) framework — a compile-time DI framework for Java/Kotlin backend development.

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
cd kora-skills/skills/kora

# Run install script
./install.sh
```

#### Option 2: Direct installation from the internet

```bash
# One-line automatic installation
curl -fsSL https://raw.githubusercontent.com/kora-projects/kora-skills/main/skills/kora/install.sh | bash
```

#### Option 3: Manual copy

```bash
# Copy skills directory to ~/.claude/
cp -r kora ~/.claude/skills/
```

### Usage

After installation, the following commands become available in Claude Code CLI:

| Command             | Description                                                                                                           |
|---------------------|-----------------------------------------------------------------------------------------------------------------------|
| `/kora`             | Main meta-skill: 10 Kora principles, navigation, bootstrap guidance                                                   |
| `/kora-bootstrap`   | Scaffold new project, configure DI, HOCON/YAML config                                                                 |
| `/kora-database`    | JDBC/Cassandra repositories, `@Query`, migrations, Flyway/Liquibase                                                   |
| `/kora-http-server` | REST controllers with `@HttpController`, routing, interceptors                                                        |
| `/kora-http-client` | Declarative HTTP clients, interceptors, error handling                                                                |
| `/kora-openapi`     | OpenAPI codegen (server/client), Swagger UI, validation                                                               |
| `/kora-aop`         | Validation (`@Valid`), logging (`@Log`), resilience (`@CircuitBreaker`, `@Retry`), caching (`@Cacheable`), scheduling |
| `/kora-kafka`       | Kafka producers, consumers, batch listeners, transactions                                                             |
| `/kora-telemetry`   | Metrics (Micrometer), tracing (OpenTelemetry), logging                                                                |
| `/kora-grpc`        | gRPC server/client, protobuf, interceptors                                                                            |
| `/kora-s3`          | S3 object storage (AWS S3, MinIO, Yandex Cloud)                                                                       |
| `/kora-testing`     | `@KoraAppTest`, Testcontainers, Mockito, black-box tests                                                              |
| `/kora-mapstruct`   | DTO ↔ Entity mapping with MapStruct                                                                                   |
| `/kora-json`        | JSON serialization with `@Json`, sealed interfaces, custom serializers                                                |
| `/kora-journal`     | Continuous improvement journal for team learning                                                                      |

---

## 📦 Structure

```
kora/
├── skill.json            # Manifest (dxt_version 1.0.0)
├── SKILL.md              # Meta-skill: 10 Kora principles, navigation
├── README.md             # This file
├── CHANGELOG.md          # Version history
├── install.sh            # Install script
├── .gitignore            # Git ignore
├── kora-bootstrap/       # Scaffolding + DI + Config
│   ├── SKILL.md          # Workflow, decision patterns
│   ├── assets/           # File templates (.java, .kt, .gradle, .conf)
│   ├── scripts/          # Python automation scripts
│   └── references/       # In-depth documentation
├── kora-database/        # JDBC, Cassandra, R2DBC, Vert.x
├── kora-http-server/     # HTTP server (Undertow)
├── kora-http-client/     # HTTP clients (JDK, OkHttp)
├── kora-openapi/         # OpenAPI generator
├── kora-aop/             # AOP: validation, logging, resilience, cache, scheduling
├── kora-kafka/           # Kafka
├── kora-telemetry/       # Observability (OpenTelemetry, Micrometer)
├── kora-grpc/            # gRPC
├── kora-s3/              # S3
├── kora-testing/         # Testing (JUnit5, Testcontainers)
├── kora-mapstruct/       # MapStruct mappers
├── kora-json/            # JSON serialization
└── kora-journal/         # Journal
```

Each sub-skill contains:

- **SKILL.md** — workflow, decision patterns, checklists, pro triggers
- **assets/** — ready-to-use file templates for Java and Kotlin
- **scripts/** — Python automation scripts for code generation
- **references/** — in-depth documentation and links

---

## 🎯 Who Is This For

- **Java/Kotlin developers** starting with Kora
- **Architects** evaluating compile-time DI frameworks
- **Teams** migrating from Spring to Kora
- **Tech leads** building microservice development standards

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
| **GraalVM native** | Ultra-fast cold starts for serverless agent deployments |

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
- `database-migration` — Flyway and Liquibase support

### Messaging

- `kafka` — Kafka producers and consumers
- `grpc-server` / `grpc-client` — gRPC integration

### Integrations

- `openapi-codegen` — OpenAPI-driven code generation
- `s3-client` — AWS S3 compatible storage
- `camunda7-bpmn` / `camunda7-rest` / `camunda8-worker` — Camunda workflow engine

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

### Adding a New Sub-Skill

```bash
cd skills/kora
mkdir kora-newfeature
# Create SKILL.md, assets/, scripts/, references/
# Follow the standard in SKILL-AUTHORING-STANDARD.md
```

---

## 🔗 Distribution

### For Team Development

```bash
# Option 1: Git repo + install script
git clone https://github.com/your-org/kora-skills.git
cd kora-skills && ./install.sh

# Option 2: npx skills (via skills.sh registry)
npx skills add your-org/kora-skills
```

### Publishing to skills.sh Registry

```bash
# Requires skills.sh account
npx skills publish ./skills/kora
```

---

## 📝 License

Apache 2.0 License — see [LICENSE](LICENSE)

---

## 📞 Support

- **Issues:** [GitHub Issues](https://github.com/kora-projects/kora-skills/issues)
- **Discussions:** [GitHub Discussions](https://github.com/kora-projects/kora-skills/discussions)
- **Documentation:** [kora-docs](https://github.com/kora-projects/kora-docs/tree/master/mkdocs/docs/en/documentation)
