# Kora 2.x Developer Skill

Пакет скиллов для разработки на Kora Framework 2.x в AI coding agents.

[![Kora Version](https://img.shields.io/badge/kora-2.x-green.svg)](https://github.com/kora-projects/kora)
[![Java](https://img.shields.io/badge/java-25%2B-orange.svg)](https://adoptium.net)
[![Kotlin](https://img.shields.io/badge/kotlin-2.4-purple.svg)](https://kotlinlang.org)

> English version: [README.md](README.md)

## Что Делает Скилл

`kora-v2` помогает AI coding agents создавать и поддерживать сервисы на Kora Framework 2.x с корректными Kora patterns:

- Compile-time DI с `@KoraApp`, `@Component`, `@Module`, tags, lifecycle и диагностикой DI graph.
- HTTP server/client, authentication, OpenAPI server/client generation и управление спецификацией.
- JDBC (включая PostgreSQL-массивы, диапазоны, `interval`, `json`/`jsonb`), Cassandra, Flyway/Liquibase migrations через единый скилл `kora-database-migration`.
- Kafka producer/consumer flows, gRPC server/client и SOAP/WSDL client integration.
- Telemetry: OpenTelemetry tracing, Micrometer metrics, structured и JSON logging, маскирование секретов в telemetry-логах.
- AOP: caching, resilience (включая распределённые rate limiter и retry budget на Redis), logging, scheduling (JDK, Quartz, db-scheduler в базе данных) и validation.
- Testing: JUnit 5, `@KoraAppTest`, Testcontainers и black-box test patterns.
- Project setup для Java/Kotlin приложений на Kora.

Пакет содержит **40 доменных скиллов и один Codex meta-skill**.

## Установка

### Автоматический Установщик

```bash
cd plugins/kora-v2
./install.sh
```

Установщик копирует пакет во все поддерживаемые локальные директории скиллов, которые может найти или создать.

Если установка запускается из корня репозитория:

```bash
./plugins/kora-v2/install.sh
```

### Claude Code / OpenClaude Plugin UI

Корень репозитория является Claude-compatible plugin marketplace. Marketplace manifest:

```text
.claude-plugin/marketplace.json
```

Если текущая версия Claude Code или OpenClaude поддерживает plugins:

1. Выполните `/plugin` внутри агента.
2. Добавьте этот репозиторий как plugin marketplace.
3. Установите `kora-v2`.
4. Перезапустите agent или reload plugins.

Plugin manifest этого пакета находится в `plugins/kora-v2/.claude-plugin/plugin.json`.

`kora-v1` и `kora-v2` — разные плагины, их можно держать установленными одновременно: вложенные
скиллы неймспейсятся именем плагина (`kora-v2:kora-http-server`), поэтому конфликта нет.

### OpenAI Codex Marketplace

Codex использует собственный repo-local marketplace manifest:

```text
.agents/plugins/marketplace.json
```

Из корня репозитория:

```bash
codex plugin marketplace add .
codex plugin add kora-v2@kora-skills
```

Если plugin-команды Codex недоступны, используйте `./plugins/kora-v2/install.sh`.

### Ручная Установка

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

После публикации:

```bash
npx skills add kora-projects/kora-v2
```

## Инструкции Для AI Агентов

Если вы AI coding agent, читающий этот файл, и пользователь просит установить скилл:

1. Выполните `./plugins/kora-v2/install.sh` из корня репозитория или `./install.sh` внутри `plugins/kora-v2`.
2. Если выполнение команд недоступно, скопируйте `SKILL.md`, `references/` и `skills/` в целевую директорию агента
   пользователя.
3. Для Claude Code или OpenClaude используйте `/plugin`, добавьте репозиторий как marketplace из
   `.claude-plugin/marketplace.json`, затем установите `kora-v2`.
4. Для Codex используйте `.agents/plugins/marketplace.json`, затем `codex plugin marketplace add .` и
   `codex plugin add kora-v2@kora-skills`.
5. Сохраняйте имя установленной директории как `kora-v2`. Не перезаписывайте существующую установку `kora-v1` — это
   разные пакеты для разных версий фреймворка.
6. Попросите пользователя перезапустить или перезагрузить агента после установки.

## Использование

После установки перезапустите AI coding agent и используйте естественный язык:

```text
Создай HTTP-сервис на Kora 2.0 с Gradle.
Добавь Kora JDBC репозиторий с транзакциями.
Сгенерируй SOAP/WSDL клиент для этого сервиса.
Разбери эту ошибку Kora DI при компиляции.
Научи меня Kora с нуля.
```

Агент должен активировать `kora-v2` и затем маршрутизировать в нужный доменный скилл.

## Структура Пакета

```text
plugins/kora-v2/
  SKILL.md                  # Основной meta-skill Kora 2.x (маршрутизация и правила)
  skill.json                # Общие метаданные скилла
  install.sh                # Установщик для нескольких агентов
  README.md
  README.ru.md
  .claude-plugin/
    plugin.json             # Plugin manifest для Claude Code
  .codex-plugin/
    plugin.json             # Plugin manifest для Codex
  references/
    kora-docs-map.md        # Карта исходников фреймворка, документации 2.0 и примеров
  skills/
    kora-starter/           # Видимая для Codex копия корневого meta-skill
    kora-di-compile/
    kora-http-server/
    kora-database-jdbc/
    kora-soap-client/
    ...
```

`kora-starter` существует потому, что Codex plugin manifest указывает на директорию `skills`.
Он позволяет Codex обнаружить те же высокоуровневые инструкции маршрутизации, что лежат в корневом `SKILL.md`.

## Карта Скиллов

| Область                  | Скиллы                                                                                                                                                                                |
|--------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Core                     | `kora-di-compile`, `kora-di-runtime`, `kora-config-hocon`, `kora-config-yaml`, `kora-json`                                                                                            |
| Project setup            | `kora-project-setup-java`, `kora-project-setup-kotlin`, `kora-project-dependencies`                                                                                                   |
| HTTP и OpenAPI           | `kora-http-server`, `kora-http-server-auth`, `kora-http-client`, `kora-http-client-auth`, `kora-openapi-generator-server`, `kora-openapi-generator-client`, `kora-openapi-management` |
| Данные                   | `kora-database-jdbc`, `kora-database-cassandra`, `kora-database-migration`                                                                                                            |
| Messaging                | `kora-kafka-producer`, `kora-kafka-consumer`                                                                                                                                          |
| gRPC и SOAP              | `kora-grpc-server`, `kora-grpc-client`, `kora-soap-client`                                                                                                                            |
| Telemetry                | `kora-telemetry-tracing`, `kora-telemetry-metrics`, `kora-telemetry-logging`                                                                                                          |
| AOP                      | `kora-aop-caching`, `kora-aop-resilient`, `kora-aop-logging`, `kora-aop-scheduling-jdk`, `kora-aop-scheduling-quartz`, `kora-aop-scheduling-db`, `kora-aop-validation`                |
| Тестирование             | `kora-testing-junit-java`, `kora-testing-junit-kotlin`, `kora-testing-blackbox`                                                                                                       |
| Инструменты и обучение   | `kora-s3`, `kora-mapstruct`, `kora-journal`, `kora-teacher`                                                                                                                           |
| Совместимость с агентами | `kora-starter`                                                                                                                                                                        |

## Поддерживаемые Агенты

- Claude Code через `.claude-plugin/plugin.json` и `~/.claude/skills/kora-v2`
- OpenAI Codex через `.codex-plugin/plugin.json` и `~/.agents/skills/kora-v2`
- Pi Coding Agent через `~/.pi/skills/kora-v2`
- OMP через `~/.omp/skills/kora-v2`
- Cursor через `~/.cursor/skills/kora-v2`
- Gemini CLI и другие SKILL.md-совместимые агенты
- OpenClaude / OpenClaw через `~/.openclaude/skills/kora-v2`

## Требования

| Компонент      | Версия                                                                                                                         |
|----------------|--------------------------------------------------------------------------------------------------------------------------------|
| Kora Framework | 2.x — целевая версия `2.0.0.RC2` (синхронизировано с тегом `2.0.0.RC2`, `master` на `78351e1cf`)                                                  |
| Java           | 25+ (JDK, на котором запускается сам Gradle, тоже должен быть 25+, когда `openapi-generator` попадает в buildscript classpath) |
| Kotlin         | 2.4.20 с KSP 2.3.12                                                                                                            |
| Gradle         | 9+ (фреймворк фиксирует wrapper 9.7.1)                                                                                         |

## Источники

Документация Kora 2.0 опубликована на [koraframework.io/v2/ru](https://koraframework.io/v2/ru/). Она
может отставать от фреймворка, поэтому скиллы сверяют каждый ключ и значение по умолчанию с исходниками:
сначала исходники и тесты, затем мигрированные примеры, затем документация 2.0.
`kora-projects.github.io/kora-docs` и репозитории `kora-java-template` / `kora-kotlin-template`
по-прежнему описывают Kora **1.x** — их нельзя использовать как источник истины по API 2.x.

| Ресурс                                 | Ссылка                                                                      |
|----------------------------------------|-----------------------------------------------------------------------------|
| Исходники фреймворка (релиз)           | https://github.com/kora-projects/kora/tree/2.0.0.RC2                        |
| Исходники фреймворка (разработка)      | https://github.com/kora-projects/kora/tree/master                           |
| Документация Kora 2.0                  | https://koraframework.io/v2/ru/ (en: https://koraframework.io/v2/en/)       |
| Мигрированные примеры приложений       | https://github.com/kora-projects/kora-examples/tree/migration/2.0           |
| Корпус миграции 1.x → 2.0              | https://github.com/kora-projects/kora-examples/tree/migration/2.0/migration |
| Релизы                                 | https://github.com/kora-projects/kora/releases                              |
| Документация Kora 1.x (только как фон) | https://kora-projects.github.io/kora-docs                                   |
