# Kora 1.x Developer Skill

Пакет скиллов для разработки на Kora Framework 1.x в AI coding agents.

[![Kora Version](https://img.shields.io/badge/kora-1.x-green.svg)](https://kora-projects.github.io/kora-docs)
[![Java](https://img.shields.io/badge/java-17%2B-orange.svg)](https://adoptium.net)
[![Kotlin](https://img.shields.io/badge/kotlin-1.9%2B-purple.svg)](https://kotlinlang.org)

> English version: [README.md](README.md)

## Что Делает Скилл

`kora-v1` помогает AI coding agents создавать и поддерживать сервисы на Kora Framework 1.x с корректными Kora patterns:

- Compile-time DI с `@KoraApp`, `@Component`, `@Module`, tags, lifecycle и диагностикой DI graph.
- HTTP server/client, authentication, OpenAPI server/client generation и Swagger UI management.
- JDBC, Cassandra, Flyway/Liquibase migrations через единый скилл `kora-database-migration`.
- Kafka producer/consumer flows, gRPC server/client и SOAP/WSDL client integration.
- Telemetry: OpenTelemetry tracing, Micrometer metrics и structured logging.
- AOP: caching, resilience, logging, scheduling и validation.
- Testing: JUnit 5, `@KoraAppTest`, Testcontainers и black-box test patterns.
- Project setup для Java/Kotlin приложений на Kora.

Пакет содержит **39 доменных скиллов и один Codex meta-skill**.

## Установка

### Автоматический Установщик

```bash
cd plugins/kora-v1
./install.sh
```

Установщик копирует пакет во все поддерживаемые локальные директории скиллов, которые может найти или создать.

Если установка запускается из корня репозитория:

```bash
./plugins/kora-v1/install.sh
```

### Claude Code / OpenClaude Plugin UI

Корень репозитория является Claude-compatible plugin marketplace. Marketplace manifest:

```text
.claude-plugin/marketplace.json
```

Если текущая версия Claude Code или OpenClaude поддерживает plugins:

1. Выполните `/plugin` внутри агента.
2. Добавьте этот репозиторий как plugin marketplace.
3. Установите `kora-v1`.
4. Перезапустите agent или reload plugins.

Plugin manifest этого пакета находится в `plugins/kora-v1/.claude-plugin/plugin.json`.

### OpenAI Codex Marketplace

Codex использует собственный repo-local marketplace manifest:

```text
.agents/plugins/marketplace.json
```

Из корня репозитория:

```bash
codex plugin marketplace add .
codex plugin add kora-v1@kora-skills
```

Если Codex plugin commands недоступны, используйте `./plugins/kora-v1/install.sh`.

### Ручная Установка

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

Когда пакет будет опубликован:

```bash
npx skills add kora-projects/kora-v1
```

## Инструкции Для AI Agents

Если вы AI coding agent, читаете этот файл и пользователь просит установить skill:

1. Запустите `./plugins/kora-v1/install.sh` из корня репозитория или `./install.sh` из директории `plugins/kora-v1`.
2. Если command execution недоступен, скопируйте `SKILL.md` и `skills/` в target directory для агента пользователя.
3. Для Claude Code или OpenClaude plugin flow используйте `/plugin`, добавьте этот репозиторий как marketplace из `.claude-plugin/marketplace.json`, затем установите `kora-v1`.
4. Для Codex plugin flow используйте `.agents/plugins/marketplace.json`, затем выполните `codex plugin marketplace add .` и `codex plugin add kora-v1@kora-skills`.
5. Оставьте имя installed directory как `kora-v1`.
6. Попросите пользователя перезапустить или reload агента после установки.

## Использование

После установки перезапустите AI coding agent и задайте задачу обычным текстом:

```text
Create a Kora 1.x HTTP service with Gradle.
Add a Kora JDBC repository with transactions.
Generate a SOAP/WSDL client for this service.
Debug this Kora DI compile error.
Teach me Kora from scratch.
```

Агент должен активировать `kora-v1`, а затем выбрать нужный доменный скилл.

## Структура Пакета

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

`kora-core-master-meta-skill` нужен потому, что Codex plugin manifest указывает на директорию `skills`. Эта копия позволяет Codex увидеть те же верхнеуровневые routing instructions, что находятся в корневом `SKILL.md`.

## Карта Скиллов

| Область | Скиллы |
| --- | --- |
| Core | `kora-di-compile`, `kora-di-runtime`, `kora-config-hocon`, `kora-config-yaml`, `kora-json` |
| Project setup | `kora-project-setup-java`, `kora-project-setup-kotlin`, `kora-project-dependencies` |
| HTTP и OpenAPI | `kora-http-server`, `kora-http-server-auth`, `kora-http-client`, `kora-http-client-auth`, `kora-openapi-generator-server`, `kora-openapi-generator-client`, `kora-openapi-management` |
| Data | `kora-database-jdbc`, `kora-database-cassandra`, `kora-database-migration` |
| Messaging | `kora-kafka-producer`, `kora-kafka-consumer` |
| gRPC и SOAP | `kora-grpc-server`, `kora-grpc-client`, `kora-soap-client` |
| Telemetry | `kora-telemetry-tracing`, `kora-telemetry-metrics`, `kora-telemetry-logging` |
| AOP | `kora-aop-caching`, `kora-aop-resilient`, `kora-aop-logging`, `kora-aop-scheduling-jdk`, `kora-aop-scheduling-quartz`, `kora-aop-validation` |
| Testing | `kora-testing-junit-java`, `kora-testing-junit-kotlin`, `kora-testing-blackbox` |
| Tools и обучение | `kora-s3`, `kora-mapstruct`, `kora-journal`, `kora-teacher` |
| Agent compatibility | `kora-core-master-meta-skill` |

## Поддерживаемые Агенты

- Claude Code через `.claude-plugin/plugin.json` и `~/.claude/skills/kora-v1`
- OpenAI Codex через `.codex-plugin/plugin.json` и `~/.agents/skills/kora-v1`
- Pi Coding Agent через `~/.pi/skills/kora-v1`
- OMP через `~/.omp/skills/kora-v1`
- Cursor через `~/.cursor/skills/kora-v1`
- Gemini CLI и другие SKILL.md-compatible agents
- OpenClaude / OpenClaw через `~/.openclaude/skills/kora-v1`

## Требования

| Компонент | Версия |
| --- | --- |
| Kora Framework | 1.x |
| Java | 17+ |
| Kotlin | 1.9+ |
| Gradle | 8+ |

## Документация

| Ресурс | Ссылка |
| --- | --- |
| Kora Documentation | https://kora-projects.github.io/kora-docs |
| Official Examples | https://github.com/kora-projects/kora-examples |
| Changelog | https://kora-projects.github.io/kora-docs/en/changelog/ |
| Java Template | https://github.com/kora-projects/kora-java-template |
| Kotlin Template | https://github.com/kora-projects/kora-kotlin-template |
