# Kora 1.x Developer Skill

Kora Framework 1.x development skill package for AI coding agents.

[![Kora Version](https://img.shields.io/badge/kora-1.x-green.svg)](https://kora-projects.github.io/kora-docs)
[![Java](https://img.shields.io/badge/java-17%2B-orange.svg)](https://adoptium.net)
[![Kotlin](https://img.shields.io/badge/kotlin-1.9%2B-purple.svg)](https://kotlinlang.org)

> Russian version: [README.ru.md](README.ru.md)

## What It Does

`kora-v1` helps AI coding agents build and maintain Kora Framework 1.x services with correct Kora patterns:

- Compile-time DI with `@KoraApp`, `@Component`, `@Module`, tags, lifecycle, and graph debugging.
- HTTP server/client, authentication, OpenAPI server/client generation, and Swagger UI management.
- JDBC, Cassandra, Flyway/Liquibase migrations through the unified `kora-database-migration` skill.
- Kafka producer/consumer flows, gRPC server/client, and SOAP/WSDL client integration.
- Telemetry with OpenTelemetry tracing, Micrometer metrics, and structured logging.
- AOP features: caching, resilience, logging, scheduling, and validation.
- Testing with JUnit 5, `@KoraAppTest`, Testcontainers, and black-box test patterns.
- Project setup for Java/Kotlin Kora applications.

The package contains **39 domain skills plus one Codex meta-skill**.

## Installation

### Automatic Installer

```bash
cd plugins/kora-v1
./install.sh
```

The installer copies the package to every supported local skill directory it can find or create.

If you are installing from the repository root, run:

```bash
./plugins/kora-v1/install.sh
```

### Claude Code / OpenClaude Plugin UI

The repository root is a Claude-compatible plugin marketplace. The marketplace manifest is:

```text
.claude-plugin/marketplace.json
```

If your Claude Code or OpenClaude build supports plugins:

1. Run `/plugin` inside the agent.
2. Add this repository as a plugin marketplace.
3. Install `kora-v1`.
4. Restart or reload plugins.

The plugin manifest for this package is `plugins/kora-v1/.claude-plugin/plugin.json`.

### OpenAI Codex Marketplace

Codex uses its own repo-local marketplace manifest:

```text
.agents/plugins/marketplace.json
```

From the repository root:

```bash
codex plugin marketplace add .
codex plugin add kora-v1@kora-skills
```

If the Codex plugin commands are unavailable, use `./plugins/kora-v1/install.sh`.

### Manual Installation

```bash
# Claude Code
cp -r kora-v1 ~/.claude/skills/kora-v1

# OpenAI Codex
cp -r kora-v1 ~/.agents/skills/kora-v1

# Pi Coding Agent
cp -r kora-v1 ~/.pi/skills/kora-v1

# OMP
cp -r kora-v1 ~/.omp/skills/kora-v1

# Cursor
cp -r kora-v1 ~/.cursor/skills/kora-v1

# OpenClaude / OpenClaw
cp -r kora-v1 ~/.openclaude/skills/kora-v1
```

### Skills Registry

When published:

```bash
npx skills add kora-projects/kora-v1
```

## Instructions For AI Agents

If you are an AI coding agent reading this file and the user asks you to install this skill:

1. Run `./plugins/kora-v1/install.sh` from the repository root, or `./install.sh` from inside `plugins/kora-v1`.
2. If command execution is not available, copy `SKILL.md` and `skills/` into the target directory for the user's agent.
3. For Claude Code or OpenClaude plugin flow, use `/plugin`, add this repository as the marketplace from `.claude-plugin/marketplace.json`, then install `kora-v1`.
4. For Codex plugin flow, use `.agents/plugins/marketplace.json`, then run `codex plugin marketplace add .` and `codex plugin add kora-v1@kora-skills`.
5. Keep the installed directory name as `kora-v1`.
6. Ask the user to restart or reload their agent after installation.

## Usage

After installation, restart your AI coding agent and use natural language:

```text
Create a Kora 1.x HTTP service with Gradle.
Add a Kora JDBC repository with transactions.
Generate a SOAP/WSDL client for this service.
Debug this Kora DI compile error.
Teach me Kora from scratch.
```

Agents should activate `kora-v1` and then route to the relevant domain skill.

## Package Layout

```text
plugins/kora-v1/
  SKILL.md                  # Main Kora 1.x skill
  skill.json                # Generic skill metadata
  install.sh                # Multi-agent installer
  README.md
  README.ru.md
  .claude-plugin/
    plugin.json             # Claude Code plugin manifest
  .codex-plugin/
    plugin.json             # Codex plugin manifest
  skills/
    kora-core-master-meta-skill/   # Codex-visible copy of the root meta-skill
    kora-di-compile/
    kora-http-server/
    kora-database-jdbc/
    kora-soap-client/
    ...
```

`kora-core-master-meta-skill` exists because the Codex plugin manifest points at the `skills` directory. It lets Codex discover the same high-level routing instructions that live in the root `SKILL.md`.

## Skill Map

| Area | Skills |
| --- | --- |
| Core | `kora-di-compile`, `kora-di-runtime`, `kora-config-hocon`, `kora-config-yaml`, `kora-json` |
| Project setup | `kora-project-setup-java`, `kora-project-setup-kotlin`, `kora-project-dependencies` |
| HTTP and OpenAPI | `kora-http-server`, `kora-http-server-auth`, `kora-http-client`, `kora-http-client-auth`, `kora-openapi-generator-server`, `kora-openapi-generator-client`, `kora-openapi-management` |
| Data | `kora-database-jdbc`, `kora-database-cassandra`, `kora-database-migration` |
| Messaging | `kora-kafka-producer`, `kora-kafka-consumer` |
| gRPC and SOAP | `kora-grpc-server`, `kora-grpc-client`, `kora-soap-client` |
| Telemetry | `kora-telemetry-tracing`, `kora-telemetry-metrics`, `kora-telemetry-logging` |
| AOP | `kora-aop-caching`, `kora-aop-resilient`, `kora-aop-logging`, `kora-aop-scheduling-jdk`, `kora-aop-scheduling-quartz`, `kora-aop-validation` |
| Testing | `kora-testing-junit-java`, `kora-testing-junit-kotlin`, `kora-testing-blackbox` |
| Tools and learning | `kora-s3`, `kora-mapstruct`, `kora-journal`, `kora-teacher` |
| Agent compatibility | `kora-core-master-meta-skill` |

## Supported Agents

- Claude Code via `.claude-plugin/plugin.json` and `~/.claude/skills/kora-v1`
- OpenAI Codex via `.codex-plugin/plugin.json` and `~/.agents/skills/kora-v1`
- Pi Coding Agent via `~/.pi/skills/kora-v1`
- OMP via `~/.omp/skills/kora-v1`
- Cursor via `~/.cursor/skills/kora-v1`
- Gemini CLI and other SKILL.md-compatible agents
- OpenClaude / OpenClaw via `~/.openclaude/skills/kora-v1`

## Requirements

| Component | Version |
| --- | --- |
| Kora Framework | 1.x |
| Java | 17+ |
| Kotlin | 1.9+ |
| Gradle | 8+ |

## Documentation

| Resource | Link |
| --- | --- |
| Kora Documentation | https://kora-projects.github.io/kora-docs |
| Official Examples | https://github.com/kora-projects/kora-examples |
| Changelog | https://kora-projects.github.io/kora-docs/en/changelog/ |
| Java Template | https://github.com/kora-projects/kora-java-template |
| Kotlin Template | https://github.com/kora-projects/kora-kotlin-template |
