# Kora Skills

AI coding agent skills for Kora Framework development.

> Russian version: [README.ru.md](README.ru.md)

## What Is This?

This repository ships skill packages for **Kora Framework**. The current package is `kora-v1`, built for the Kora 1.x line.

The `kora-v1` name is intentional: it leaves room for a future `kora-v2` package when Kora 2.x needs separate guidance, while `kora-1x` and `kora-1.x` remain searchable aliases in metadata.

## Quick Start

```bash
git clone <repository-url> kora-skills
cd kora-skills
./plugins/kora-v1/install.sh
```

This is the recommended universal path for agents: clone the repo, run the installer, restart the target coding agent.

## Install With Agent UIs

### Claude Code / OpenClaude

This repository is a Claude-compatible plugin marketplace. The marketplace manifest is:

```text
.claude-plugin/marketplace.json
```

If your Claude Code or OpenClaude build supports plugins:

1. Open Claude Code.
2. Run `/plugin`.
3. Add this repository as a plugin marketplace.
4. Install the `kora-v1` plugin.
5. Restart or reload plugins.

If the plugin UI is unavailable, use the shell installer:

```bash
./plugins/kora-v1/install.sh
```

### OpenAI Codex

Codex uses a separate repo-local marketplace manifest:

```text
.agents/plugins/marketplace.json
```

From the repository root, add this repository marketplace and install `kora-v1`:

```bash
codex plugin marketplace add .
codex plugin add kora-v1@kora-skills
```

If Codex CLI plugin commands are unavailable in your build, use the shell installer:

```bash
./plugins/kora-v1/install.sh
```

### Local Skill Directories

The installer targets these local skill locations:

| Agent | Target |
| --- | --- |
| Claude Code | `~/.claude/skills/kora-v1` |
| OpenAI Codex | `~/.agents/skills/kora-v1` |
| Pi Coding Agent | `~/.pi/skills/kora-v1` |
| OMP | `~/.omp/skills/kora-v1` |
| Cursor | `~/.cursor/skills/kora-v1` |
| OpenClaude / OpenClaw | `~/.openclaude/skills/kora-v1` |

Manual fallback for any SKILL.md-compatible agent:

```bash
mkdir -p ~/.local/share/skills/kora-v1
cp -r plugins/kora-v1/SKILL.md plugins/kora-v1/skills ~/.local/share/skills/kora-v1/
```

When the package is published to a skills registry:

```bash
npx skills add kora-projects/kora-v1
```

After installation, restart your AI coding agent and ask:

```text
Help me create a Kora 1.x microservice with HTTP endpoints.
Add a JDBC repository to this Kora service.
Create a Kora SOAP/WSDL client.
Debug this Kora DI graph error.
```

## Repository Layout

```text
kora-skills/
  README.md
  README.ru.md
  .claude-plugin/
    marketplace.json
  .agents/
    plugins/
      marketplace.json
  plugins/
    kora-v1/
    SKILL.md
    skill.json
    install.sh
    README.md
    README.ru.md
    .claude-plugin/
      plugin.json
    .codex-plugin/
      plugin.json
    skills/
      kora-core-master-meta-skill/
      kora-di-compile/
      ...
```

## Instructions For AI Agents

If you are an AI coding agent reading this README and the user asks to install Kora skills:

1. Prefer `./plugins/kora-v1/install.sh` from the repository root.
2. If shell execution is blocked, copy `plugins/kora-v1/SKILL.md` and `plugins/kora-v1/skills/` into the agent-specific target directory from the table above.
3. For Claude Code or OpenClaude plugin installs, use `/plugin` when available and add this repository as the marketplace from `.claude-plugin/marketplace.json`.
4. For Codex plugin installs, use `.agents/plugins/marketplace.json`, then run `codex plugin marketplace add .` and `codex plugin add kora-v1@kora-skills`.
5. After installation, tell the user to restart or reload the target agent.
6. Do not rename the installed skill. Keep `kora-v1` as the directory and skill name.

## Package Contents

`kora-v1` contains **39 domain skills plus one Codex meta-skill**:

- Core: `kora-di-compile`, `kora-di-runtime`, `kora-config-hocon`, `kora-config-yaml`, `kora-json`
- Project setup: `kora-project-setup-java`, `kora-project-setup-kotlin`, `kora-project-dependencies`
- HTTP and OpenAPI: `kora-http-server`, `kora-http-server-auth`, `kora-http-client`, `kora-http-client-auth`, `kora-openapi-generator-server`, `kora-openapi-generator-client`, `kora-openapi-management`
- Data: `kora-database-jdbc`, `kora-database-cassandra`, `kora-database-migration`
- Messaging: `kora-kafka-producer`, `kora-kafka-consumer`
- gRPC and SOAP: `kora-grpc-server`, `kora-grpc-client`, `kora-soap-client`
- Telemetry: `kora-telemetry-tracing`, `kora-telemetry-metrics`, `kora-telemetry-logging`
- AOP: `kora-aop-caching`, `kora-aop-resilient`, `kora-aop-logging`, `kora-aop-scheduling-jdk`, `kora-aop-scheduling-quartz`, `kora-aop-validation`
- Testing: `kora-testing-junit-java`, `kora-testing-junit-kotlin`, `kora-testing-blackbox`
- Tools and learning: `kora-s3`, `kora-mapstruct`, `kora-journal`, `kora-teacher`
- Agent compatibility: `kora-core-master-meta-skill`

## Supported Agents

The package is prepared for agents and runtimes that understand `SKILL.md`-style skills or local skill folders:

- Claude Code
- OpenAI Codex
- Pi Coding Agent
- OMP
- Cursor
- Gemini CLI
- OpenClaude / OpenClaw
- Other SKILL.md-compatible agents

## Documentation

| Resource | Link |
| --- | --- |
| Kora Framework docs | https://kora-projects.github.io/kora-docs |
| Official examples | https://github.com/kora-projects/kora-examples |
| Java template | https://github.com/kora-projects/kora-java-template |
| Kotlin template | https://github.com/kora-projects/kora-kotlin-template |
| SKILL.md specification | https://agentskills.io/specification |
