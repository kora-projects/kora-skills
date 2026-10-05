# Kora Skills

AI coding agent skills for Kora Framework development.

> Русская версия: [README.ru.md](README.ru.md)

## What Is This?

This repository ships skill packages for **Kora Framework**. There are two, one per framework line,
and they are installed and versioned independently:

| Package                      | Framework Version | Group              | Use it when                                  |
|------------------------------|-------------------|--------------------|----------------------------------------------|
| [`kora-v2`](plugins/kora-v2) | Kora 2.x          | `io.koraframework` | New services, and any project already on 2.x |
| [`kora-v1`](plugins/kora-v1) | Kora 1.x          | `ru.tinkoff.kora`  | Existing services still on 1.x               |

They can be installed side by side. Sub-skills are namespaced by plugin
(`kora-v2:kora-http-server` vs `kora-v1:kora-http-server`), so nothing collides.

## Quick Start

```bash
git clone <repository-url> kora-skills
cd kora-skills
./plugins/kora-v2/install.sh     # Kora 2.x
./plugins/kora-v1/install.sh     # Kora 1.x
```

This is the recommended universal path for agents: clone the repo, run the installer for the line
you need, restart the target coding agent.

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
4. Install the `kora-v2` plugin (or `kora-v1`, or both).
5. Restart or reload plugins.

If the plugin UI is unavailable, use the shell installer:

```bash
./plugins/kora-v2/install.sh
```

### OpenAI Codex

Codex uses a separate repo-local marketplace manifest:

```text
.agents/plugins/marketplace.json
```

From the repository root, add this repository marketplace and install the package you need:

```bash
codex plugin marketplace add .
codex plugin add kora-v2@kora-skills
codex plugin add kora-v1@kora-skills   # only if you also maintain 1.x services
```

If Codex CLI plugin commands are unavailable in your build, use the shell installer:

```bash
./plugins/kora-v2/install.sh
```

### Local Skill Directories

The installer targets these local skill locations (`<pkg>` is `kora-v2` or `kora-v1`):

| Agent                 | Target                       |
|-----------------------|------------------------------|
| Claude Code           | `~/.claude/skills/<pkg>`     |
| OpenAI Codex          | `~/.agents/skills/<pkg>`     |
| Pi Coding Agent       | `~/.pi/skills/<pkg>`         |
| OMP                   | `~/.omp/skills/<pkg>`        |
| Cursor                | `~/.cursor/skills/<pkg>`     |
| OpenClaude / OpenClaw | `~/.openclaude/skills/<pkg>` |

Manual fallback for any SKILL.md-compatible agent:

```bash
mkdir -p ~/.local/share/skills/kora-v2
cp -r plugins/kora-v2/SKILL.md plugins/kora-v2/references plugins/kora-v2/skills \
      ~/.local/share/skills/kora-v2/
```

When a package is published to a skills registry:

```bash
npx skills add kora-projects/kora-v2
```

After installation, restart your AI coding agent and ask:

```text
Help me create a Kora microservice with HTTP endpoints.
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
    marketplace.json          # lists both plugins
  .agents/
    plugins/
      marketplace.json        # Codex; lists both plugins
  scripts/
    version.py                # per-plugin version sync (see scripts/README.md)
  plugins/
    kora-v2/                  # Kora 2.x package
      SKILL.md
      skill.json
      install.sh
      README.md
      README.ru.md
      .claude-plugin/plugin.json
      .codex-plugin/plugin.json
      references/
        kora-docs-map.md
      skills/
        kora-starter/
        kora-di-compile/
        ...
    kora-v1/                  # Kora 1.x package, same layout
```

## Instructions For AI Agents

If you are an AI coding agent reading this README and the user asks to install Kora skills:

1. Determine the framework line first. `ru.tinkoff.kora` in the project's build files → `kora-v1`.
   `io.koraframework` → `kora-v2`. Nothing to inspect (new project) → `kora-v2`. If it is genuinely
   ambiguous, ask; do not guess.
2. Prefer `./plugins/<pkg>/install.sh` from the repository root.
3. If shell execution is blocked, copy `plugins/<pkg>/SKILL.md`, `plugins/<pkg>/references/` and
   `plugins/<pkg>/skills/` into the agent-specific target directory from the table above.
4. For Claude Code or OpenClaude plugin installs, use `/plugin` when available and add this
   repository as the marketplace from `.claude-plugin/marketplace.json`.
5. For Codex plugin installs, use `.agents/plugins/marketplace.json`, then run
   `codex plugin marketplace add .` and `codex plugin add <pkg>@kora-skills`.
6. After installation, tell the user to restart or reload the target agent.
7. Do not rename an installed package, and do not install one over the other. `kora-v1` and
   `kora-v2` are separate directories for separate framework versions.

## Package Contents

`kora-v1` contains **39 domain skills** and `kora-v2` **40**, each plus one Codex meta-skill:

- Core: `kora-di-compile`, `kora-di-runtime`, `kora-config-hocon`, `kora-config-yaml`, `kora-json`
- Project setup: `kora-project-setup-java`, `kora-project-setup-kotlin`, `kora-project-dependencies`
- HTTP and OpenAPI: `kora-http-server`, `kora-http-server-auth`, `kora-http-client`, `kora-http-client-auth`,
  `kora-openapi-generator-server`, `kora-openapi-generator-client`, `kora-openapi-management`
- Data: `kora-database-jdbc`, `kora-database-cassandra`, `kora-database-migration`
- Messaging: `kora-kafka-producer`, `kora-kafka-consumer`
- gRPC and SOAP: `kora-grpc-server`, `kora-grpc-client`, `kora-soap-client`
- Telemetry: `kora-telemetry-tracing`, `kora-telemetry-metrics`, `kora-telemetry-logging`
- AOP: `kora-aop-caching`, `kora-aop-resilient`, `kora-aop-logging`, `kora-aop-scheduling-jdk`,
  `kora-aop-scheduling-quartz`, `kora-aop-scheduling-db` (`kora-v2` only), `kora-aop-validation`
- Testing: `kora-testing-junit-java`, `kora-testing-junit-kotlin`, `kora-testing-blackbox`
- Tools and learning: `kora-s3`, `kora-mapstruct`, `kora-journal`, `kora-teacher`
- Agent compatibility: `kora-starter`

The two packages share this skill *layout*, not their content — every skill is written against its
own framework line.

## Maintaining Versions

Each plugin carries its own version. Never hand-edit it; use the helper:

```bash
python scripts/version.py            # print every plugin version
python scripts/version.py check      # CI / pre-commit gate
python scripts/version.py bump patch kora-v2
```

`set` and `bump` require an explicit plugin name so one line is never bumped while you meant the
other. Details: [`scripts/README.md`](scripts/README.md).

## Supported Agents

The packages are prepared for agents and runtimes that understand `SKILL.md`-style skills or local
skill folders:

- Claude Code
- OpenAI Codex
- Pi Coding Agent
- OMP
- Cursor
- Gemini CLI
- OpenClaude / OpenClaw
- Other SKILL.md-compatible agents

## Documentation

| Resource               | Line | Link                                                  |
|------------------------|------|-------------------------------------------------------|
| Kora Framework docs    | 2.x  | https://koraframework.io/v2/en/                       |
| Kora Framework docs    | 1.x  | https://kora-projects.github.io/kora-docs             |
| Official examples      | 2.x  | https://github.com/kora-projects/kora-examples/tree/migration/2.0 |
| Official examples      | 1.x  | https://github.com/kora-projects/kora-examples        |
| Java template          | 1.x  | https://github.com/kora-projects/kora-java-template   |
| Kotlin template        | 1.x  | https://github.com/kora-projects/kora-kotlin-template |
| SKILL.md specification | —    | https://agentskills.io/specification                  |
