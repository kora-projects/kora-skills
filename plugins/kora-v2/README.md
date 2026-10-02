# Kora 2.x Developer Skill

Kora Framework 2.x development skill package for AI coding agents.

[![Kora Version](https://img.shields.io/badge/kora-2.x-green.svg)](https://github.com/kora-projects/kora)
[![Java](https://img.shields.io/badge/java-25%2B-orange.svg)](https://adoptium.net)
[![Kotlin](https://img.shields.io/badge/kotlin-2.4-purple.svg)](https://kotlinlang.org)

> Русская версия: [README.ru.md](README.ru.md)

## What It Does

`kora-v2` helps AI coding agents build and maintain Kora Framework 2.x services with correct Kora patterns:

- Compile-time DI with `@KoraApp`, `@Component`, `@Module`, tags, lifecycle, and graph debugging.
- HTTP server/client, authentication, OpenAPI server/client generation, and spec management.
- JDBC (including PostgreSQL arrays, ranges, `interval`, `json`/`jsonb`), Cassandra, Flyway/Liquibase migrations through the unified `kora-database-migration` skill.
- Kafka producer/consumer flows, gRPC server/client, and SOAP/WSDL client integration.
- Telemetry with OpenTelemetry tracing, Micrometer metrics, structured and JSON logging, and masking of secrets in telemetry logs.
- AOP features: caching, resilience (including Redis-backed distributed rate limiting and retry budgets), logging, scheduling (JDK, Quartz, database-backed db-scheduler), and validation.
- Testing with JUnit 5, `@KoraAppTest`, Testcontainers, and black-box test patterns.
- Project setup for Java/Kotlin Kora applications.

The package contains **40 domain skills plus one Codex meta-skill**.

## Installation

### Automatic Installer

```bash
cd plugins/kora-v2
./install.sh
```

The installer copies the package to every supported local skill directory it can find or create.

If you are installing from the repository root, run:

```bash
./plugins/kora-v2/install.sh
```

### Claude Code / OpenClaude Plugin UI

The repository root is a Claude-compatible plugin marketplace. The marketplace manifest is:

```text
.claude-plugin/marketplace.json
```

If your Claude Code or OpenClaude build supports plugins:

1. Run `/plugin` inside the agent.
2. Add this repository as a plugin marketplace.
3. Install `kora-v2`.
4. Restart or reload plugins.

The plugin manifest for this package is `plugins/kora-v2/.claude-plugin/plugin.json`.

`kora-v1` and `kora-v2` are separate plugins and can be installed at the same time — their
sub-skills are namespaced by plugin (`kora-v2:kora-http-server`), so they do not collide.

### OpenAI Codex Marketplace

Codex uses its own repo-local marketplace manifest:

```text
.agents/plugins/marketplace.json
```

From the repository root:

```bash
codex plugin marketplace add .
codex plugin add kora-v2@kora-skills
```

If the Codex plugin commands are unavailable, use `./plugins/kora-v2/install.sh`.

### Manual Installation

```bash
# Claude Code
cp -r kora-v2 ~/.claude/skills/kora-v2

# OpenAI Codex
cp -r kora-v2 ~/.agents/skills/kora-v2

# Pi Coding Agent
cp -r kora-v2 ~/.pi/skills/kora-v2

# OMP
cp -r kora-v2 ~/.omp/skills/kora-v2

# Cursor
cp -r kora-v2 ~/.cursor/skills/kora-v2

# OpenClaude / OpenClaw
cp -r kora-v2 ~/.openclaude/skills/kora-v2
```

### Skills Registry

When published:

```bash
npx skills add kora-projects/kora-v2
```

## Instructions For AI Agents

If you are an AI coding agent reading this file and the user asks you to install this skill:

1. Run `./plugins/kora-v2/install.sh` from the repository root, or `./install.sh` from inside `plugins/kora-v2`.
2. If command execution is not available, copy `SKILL.md`, `references/` and `skills/` into the target directory for the
   user's agent.
3. For Claude Code or OpenClaude plugin flow, use `/plugin`, add this repository as the marketplace from
   `.claude-plugin/marketplace.json`, then install `kora-v2`.
4. For Codex plugin flow, use `.agents/plugins/marketplace.json`, then run `codex plugin marketplace add .` and
   `codex plugin add kora-v2@kora-skills`.
5. Keep the installed directory name as `kora-v2`. Do not overwrite an existing `kora-v1` installation — they are
   different packages for different framework versions.
6. Ask the user to restart or reload their agent after installation.

## Usage

After installation, restart your AI coding agent and use natural language:

```text
Create a Kora 2.0 HTTP service with Gradle.
Add a Kora JDBC repository with transactions.
Generate a SOAP/WSDL client for this service.
Debug this Kora DI compile error.
Teach me Kora from scratch.
```

Agents should activate `kora-v2` and then route to the relevant domain skill.

## Package Layout

```text
plugins/kora-v2/
  SKILL.md                  # Main Kora 2.x meta-skill (routing and rules)
  skill.json                # Generic skill metadata
  install.sh                # Multi-agent installer
  README.md
  README.ru.md
  .claude-plugin/
    plugin.json             # Claude Code plugin manifest
  .codex-plugin/
    plugin.json             # Codex plugin manifest
  references/
    kora-docs-map.md        # Framework-source, 2.0 docs and example-app map
  skills/
    kora-starter/           # Codex-visible copy of the root meta-skill
    kora-di-compile/
    kora-http-server/
    kora-database-jdbc/
    kora-soap-client/
    ...
```

`kora-starter` exists because the Codex plugin manifest points at the `skills` directory. It lets
Codex discover the same high-level routing instructions that live in the root `SKILL.md`.

## Skill Map

| Area                | Skills                                                                                                                                                                                |
|---------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Core                | `kora-di-compile`, `kora-di-runtime`, `kora-config-hocon`, `kora-config-yaml`, `kora-json`                                                                                            |
| Project setup       | `kora-project-setup-java`, `kora-project-setup-kotlin`, `kora-project-dependencies`                                                                                                   |
| HTTP and OpenAPI    | `kora-http-server`, `kora-http-server-auth`, `kora-http-client`, `kora-http-client-auth`, `kora-openapi-generator-server`, `kora-openapi-generator-client`, `kora-openapi-management` |
| Data                | `kora-database-jdbc`, `kora-database-cassandra`, `kora-database-migration`                                                                                                            |
| Messaging           | `kora-kafka-producer`, `kora-kafka-consumer`                                                                                                                                          |
| gRPC and SOAP       | `kora-grpc-server`, `kora-grpc-client`, `kora-soap-client`                                                                                                                            |
| Telemetry           | `kora-telemetry-tracing`, `kora-telemetry-metrics`, `kora-telemetry-logging`                                                                                                          |
| AOP                 | `kora-aop-caching`, `kora-aop-resilient`, `kora-aop-logging`, `kora-aop-scheduling-jdk`, `kora-aop-scheduling-quartz`, `kora-aop-scheduling-db`, `kora-aop-validation`                |
| Testing             | `kora-testing-junit-java`, `kora-testing-junit-kotlin`, `kora-testing-blackbox`                                                                                                       |
| Tools and learning  | `kora-s3`, `kora-mapstruct`, `kora-journal`, `kora-teacher`                                                                                                                           |
| Agent compatibility | `kora-starter`                                                                                                                                                                        |

## Supported Agents

- Claude Code via `.claude-plugin/plugin.json` and `~/.claude/skills/kora-v2`
- OpenAI Codex via `.codex-plugin/plugin.json` and `~/.agents/skills/kora-v2`
- Pi Coding Agent via `~/.pi/skills/kora-v2`
- OMP via `~/.omp/skills/kora-v2`
- Cursor via `~/.cursor/skills/kora-v2`
- Gemini CLI and other SKILL.md-compatible agents
- OpenClaude / OpenClaw via `~/.openclaude/skills/kora-v2`

## Requirements

| Component      | Version                                                                                                |
|----------------|--------------------------------------------------------------------------------------------------------|
| Kora Framework | 2.x — targets `2.0.0.RC2` (synced with the `2.0.0.RC2` tag, `master` at `78351e1cf`)                                        |
| Java           | 25+ (the JDK running Gradle must also be 25+ when `openapi-generator` is on the buildscript classpath) |
| Kotlin         | 2.4.20 with KSP 2.3.12                                                                                 |
| Gradle         | 9+ (the framework pins wrapper 9.7.1)                                                                  |

## Sources

Kora 2.0 is documented at [koraframework.io/v2/en](https://koraframework.io/v2/en/). The docs can
trail the framework, so the skills verify every key and default against the source: source and tests
first, then the migrated examples, then the 2.0 docs. `kora-projects.github.io/kora-docs` and the
`kora-java-template` / `kora-kotlin-template` repositories still describe Kora **1.x** — they must not
be used as an API authority for 2.x.

| Resource                                 | Link                                                                        |
|------------------------------------------|-----------------------------------------------------------------------------|
| Framework source (release)               | https://github.com/kora-projects/kora/tree/2.0.0.RC2                        |
| Framework source (development)           | https://github.com/kora-projects/kora/tree/master                           |
| Kora 2.0 documentation                   | https://koraframework.io/v2/en/ (ru: https://koraframework.io/v2/ru/)       |
| Migrated example applications            | https://github.com/kora-projects/kora-examples/tree/migration/2.0           |
| 1.x → 2.0 migration corpus               | https://github.com/kora-projects/kora-examples/tree/migration/2.0/migration |
| Releases                                 | https://github.com/kora-projects/kora/releases                              |
| Kora 1.x documentation (background only) | https://kora-projects.github.io/kora-docs                                   |
