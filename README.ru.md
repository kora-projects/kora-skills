# Kora Skills

Скиллы для AI coding agents, которые помогают разрабатывать приложения на Kora Framework.

> English version: [README.md](README.md)

## Что Это?

Репозиторий содержит пакеты скиллов для **Kora Framework**. Текущий пакет называется `kora-v1` и предназначен для линейки Kora 1.x.

Имя `kora-v1` выбрано специально: когда для Kora 2.x понадобится отдельный пакет, его можно будет добавить рядом как `kora-v2`. Алиасы `kora-1x` и `kora-1.x` оставлены в метаданных для поиска и совместимости.

## Быстрый Старт

```bash
git clone <repository-url> kora-skills
cd kora-skills
./kora-v1/install.sh
```

Это рекомендуемый универсальный путь для агентов: клонировать репозиторий, запустить установщик, перезапустить целевой coding agent.

## Установка Через UI Агентов

### Claude Code / OpenClaude

Этот репозиторий является Claude-compatible plugin marketplace. Marketplace manifest:

```text
.claude-plugin/marketplace.json
```

Если текущая версия Claude Code или OpenClaude поддерживает plugins:

1. Откройте Claude Code.
2. Выполните `/plugin`.
3. Добавьте этот репозиторий как plugin marketplace.
4. Установите plugin `kora-v1`.
5. Перезапустите agent или reload plugins.

Если plugin UI недоступен, используйте shell installer:

```bash
./kora-v1/install.sh
```

### OpenAI Codex

Codex использует отдельный repo-local marketplace manifest:

```text
.agents/plugins/marketplace.json
```

Из корня репозитория добавьте marketplace и установите `kora-v1`:

```bash
codex plugin marketplace add .
codex plugin add kora-v1@kora-skills
```

Если Codex CLI plugin commands недоступны в вашей версии, используйте shell installer:

```bash
./kora-v1/install.sh
```

### Локальные Директории Скиллов

Установщик пишет пакет в эти локальные директории:

| Агент | Target |
| --- | --- |
| Claude Code | `~/.claude/skills/kora-v1` |
| OpenAI Codex | `~/.agents/skills/kora-v1` |
| Pi Coding Agent | `~/.pi/skills/kora-v1` |
| OMP | `~/.omp/skills/kora-v1` |
| Cursor | `~/.cursor/skills/kora-v1` |
| OpenClaude / OpenClaw | `~/.openclaude/skills/kora-v1` |

Ручной fallback для любого SKILL.md-compatible agent:

```bash
mkdir -p ~/.local/share/skills/kora-v1
cp -r kora-v1/SKILL.md kora-v1/skills ~/.local/share/skills/kora-v1/
```

Когда пакет будет опубликован в skills registry:

```bash
npx skills add kora-projects/kora-v1
```

После установки перезапустите AI coding agent и задайте вопрос:

```text
Help me create a Kora 1.x microservice with HTTP endpoints.
Add a JDBC repository to this Kora service.
Create a Kora SOAP/WSDL client.
Debug this Kora DI graph error.
```

## Структура Репозитория

```text
kora-skills/
  README.md
  README.ru.md
  .claude-plugin/
    marketplace.json
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
    plugins/
      kora-v1 -> ../kora-v1
    skills/
      kora-codex-metaskill/
      kora-di-compile/
      ...
```

## Инструкции Для AI Agents

Если вы AI coding agent, читаете этот README и пользователь просит установить Kora skills:

1. Сначала используйте `./kora-v1/install.sh` из корня репозитория.
2. Если shell execution заблокирован, скопируйте `kora-v1/SKILL.md` и `kora-v1/skills/` в agent-specific target directory из таблицы выше.
3. Для Claude Code или OpenClaude plugin install используйте `/plugin`, если команда доступна, и добавляйте этот репозиторий как marketplace из `.claude-plugin/marketplace.json`.
4. Для Codex plugin install используйте `.agents/plugins/marketplace.json`, затем выполните `codex plugin marketplace add .` и `codex plugin add kora-v1@kora-skills`.
5. После установки попросите пользователя перезапустить или reload целевого агента.
6. Не переименовывайте установленный skill. Имя директории и skill name должны остаться `kora-v1`.

## Состав Пакета

`kora-v1` содержит **39 доменных скиллов и один Codex meta-skill**:

- Core: `kora-di-compile`, `kora-di-runtime`, `kora-config-hocon`, `kora-config-yaml`, `kora-json`
- Project setup: `kora-project-setup-java`, `kora-project-setup-kotlin`, `kora-project-dependencies`
- HTTP и OpenAPI: `kora-http-server`, `kora-http-server-auth`, `kora-http-client`, `kora-http-client-auth`, `kora-openapi-generator-server`, `kora-openapi-generator-client`, `kora-openapi-management`
- Data: `kora-database-jdbc`, `kora-database-cassandra`, `kora-database-migration`
- Messaging: `kora-kafka-producer`, `kora-kafka-consumer`
- gRPC и SOAP: `kora-grpc-server`, `kora-grpc-client`, `kora-soap-client`
- Telemetry: `kora-telemetry-tracing`, `kora-telemetry-metrics`, `kora-telemetry-logging`
- AOP: `kora-aop-caching`, `kora-aop-resilient`, `kora-aop-logging`, `kora-aop-scheduling-jdk`, `kora-aop-scheduling-quartz`, `kora-aop-validation`
- Testing: `kora-testing-junit-java`, `kora-testing-junit-kotlin`, `kora-testing-blackbox`
- Tools и обучение: `kora-s3`, `kora-mapstruct`, `kora-journal`, `kora-teacher`
- Agent compatibility: `kora-codex-metaskill`

## Поддерживаемые Агенты

Пакет подготовлен для агентов и сред, которые понимают `SKILL.md` или локальные директории скиллов:

- Claude Code
- OpenAI Codex
- Pi Coding Agent
- OMP
- Cursor
- Gemini CLI
- OpenClaude / OpenClaw
- Другие SKILL.md-compatible agents

## Документация

| Ресурс | Ссылка |
| --- | --- |
| Kora Framework docs | https://kora-projects.github.io/kora-docs |
| Official examples | https://github.com/kora-projects/kora-examples |
| Java template | https://github.com/kora-projects/kora-java-template |
| Kotlin template | https://github.com/kora-projects/kora-kotlin-template |
| SKILL.md specification | https://agentskills.io/specification |
