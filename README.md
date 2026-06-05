# Kora Skills для Claude Code

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://www.apache.org/licenses/LICENSE-2.0)
[![Java](https://img.shields.io/badge/Java-17+-blue)](https://www.oracle.com/java/)
[![Kotlin](https://img.shields.io/badge/Kotlin-1.7+-purple)](https://kotlinlang.org/)
[![Kora](https://img.shields.io/badge/Kora-1.2.15+-green)](https://github.com/kora-projects/kora)
[![Validate Skills](https://github.com/kora-projects/kora-skills/actions/workflows/validate.yml/badge.svg)](https://github.com/kora-projects/kora-skills/actions/workflows/validate.yml)

> **[🇬🇧 English](README.en.md)**

Набор скиллов для Claude Code для работы с [Kora framework](https://github.com/kora-projects/kora) — компиляционная внедрение зависимостей для Java/Kotlin микросервисов.

## О фреймворке Kora

Kora — это серверный фреймворк для Java/Kotlin, ориентированный на облачные приложения и достигающий высокой производительности за счёт:

| Принцип | Преимущество |
|---------|--------------|
| **Нет рефлексии во время выполнения** | Вся работа выполняется на этапе компиляции |
| **Нет динамических прокси** | Аспекты применяются на этапе компиляции |
| **Нет генерации байт-кода** | Генерация исходного кода через аннотационные процессоры / KSP |
| **Компиляционное внедрение зависимостей** | Контейнер зависимостей собирается при компиляции |
| **Виртуальные потоки** | Эффективный блокирующий ввод-вывод с Project Loom (Java 21+) |

### 4 столпа Kora

**Производительность** — Kora генерирует высокопроизводительный код на этапе компиляции:
- Нет API рефлексии во время выполнения
- Нет динамических прокси
- Тонкозернистые абстракции
- Аспекты без потерь производительности
- Только самые эффективные реализации интеграций

**Эффективность** — Низкое потребление ресурсов:
- Время запуска: 50–100 мс
- Память в простое: ~50 МБ
- Эффективное горизонтальное масштабирование
- Максимальная утилизация ресурсов кластера

**Прозрачность** — Предсказуемое поведение:
- Генерируемый код читается человеком
- Нет эффекта «чёрного ящика»
- Понятные абстракции
- Полный контроль над поведением

**Простота** — Лёгкость разработки:
- Одно лучшее решение для каждой задачи
- Знакомые высокоуровневые абстракции
- Нет сложных конструкций или избыточных абстракций
- Быстрое введение новых разработчиков в проект

### Готовые модули

Kora предоставляет готовые модули для быстрой разработки:

| Категория | Модули |
|-----------|--------|
| **HTTP** | HTTP-сервер (Undertow), HTTP-клиенты (JDK, OkHttp) |
| **Базы данных** | JDBC, Cassandra, R2DBC, Vert.x, Flyway, Liquibase |
| **Обмен сообщениями** | Kafka-продюсеры/консьюмеры, gRPC-сервер/клиент |
| **Хранение** | S3-клиент (AWS S3, MinIO, Yandex Cloud) |
| **Отказоустойчивость** | CircuitBreaker, Retry, Timeout, Fallback |
| **Кэширование** | Caffeine, Redis с аспектами |
| **Планировщик** | JDK Scheduling, Quartz |
| **Наблюдаемость** | Трейсинг (OpenTelemetry), метрики (Micrometer), логирование |
| **Контракт сначала** | OpenAPI codegen (сервер/клиент), Swagger UI |
| **Рабочие процессы** | Camunda 7 BPMN/REST, Camunda 8 worker |
| **Тестирование** | JUnit5, Testcontainers, Mockito |

### Производительность

Kora показывает отличные результаты в независимых бенчмарках:

- **TechEmpower Benchmarks** — топ позиции в категории Fortune
- **Время запуска** — 50–100 мс для типичного микросервиса
- **Потребление памяти** — ~50 МБ в простое против 200–300 МБ у Spring Boot

## Быстрый старт

### Вариант 1: Установка в одну команду

```bash
curl -fsSL https://raw.githubusercontent.com/kora-projects/kora-skills/main/skills/kora/install.sh | bash
```

### Вариант 2: Клонирование и установка

```bash
git clone https://github.com/kora-projects/kora-skills.git
cd kora-skills/skills/kora && ./install.sh
```

## Доступные команды

После установки в Claude Code CLI становятся доступны:

| Команда | Описание |
|---------|----------|
| `/kora` | Главный мета-скилл: 10 принципов Kora, навигация, руководство по запуску |
| `/kora-mega` | **Универсальный скилл**: все 14 модулей в одном файле (альтернатива отдельным скиллам) |
| `/kora-bootstrap` | Каркас проекта, настройка внедрения зависимостей, конфиги HOCON/YAML |
| `/kora-database` | JDBC/Cassandra репозитории, `@Query`, миграции |
| `/kora-http-server` | REST-контроллеры с `@HttpController`, маршрутизация |
| `/kora-http-client` | Декларативные HTTP-клиенты, перехватчики |
| `/kora-openapi` | OpenAPI codegen (сервер/клиент), Swagger UI, валидация |
| `/kora-aop` | Валидация (`@Valid`), логирование (`@Log`), отказоустойчивость (`@CircuitBreaker`, `@Retry`), кэширование (`@Cacheable`), планировщик |
| `/kora-kafka` | Kafka-продюсеры, консьюмеры, batch-обработчики |
| `/kora-telemetry` | Метрики (Micrometer), трейсинг (OpenTelemetry) |
| `/kora-grpc` | gRPC-сервер/клиент, protobuf, перехватчики |
| `/kora-s3` | Объектное хранилище S3 (AWS S3, MinIO) |
| `/kora-testing` | `@KoraAppTest`, Testcontainers, Mockito, black-box тесты |
| `/kora-mapstruct` | Маппинг DTO ↔ Entity через MapStruct |
| `/kora-json` | JSON-сериализация с `@Json`, sealed-интерфейсы |
| `/kora-journal` | Журнал непрерывных улучшений |

## Документация

Подробная документация: [skills/kora/README.md](skills/kora/README.md)

Дополнительные ресурсы:
- [Документация Kora Framework](https://kora-projects.github.io/kora-docs/ru/)
- [Примеры проектов](https://github.com/kora-projects/kora-examples)
- [Журнал изменений Kora](https://kora-projects.github.io/kora-docs/ru/changelog/changelog/)

## Требования

| Компонент | Версия | Назначение |
|-----------|--------|------------|
| Java | 17+ (рекомендуется: 25) | Основной язык разработки |
| Kotlin | 1.7+ (JVM 17) | Для Kotlin-проектов |
| Gradle | 7+ | Система сборки (обязательно для инкрементальной обработки аннотаций) |
| Claude Code CLI | последняя | Для использования скиллов |

### Почему Gradle (а не Maven)?

Kora **рекомендует Gradle**, потому что:
- Оптимальная поддержка процессоров аннотаций (Java) и KSP (Kotlin)
- Инкрементальная сборка — значительно быстрее
- Многопроходная обработка аннотаций — критично для генерации кода Kora
- Лучшая интеграция с Kora BOM

Maven технически возможен, но значительно медленнее.

## Для кого это

- **Java/Kotlin-разработчики**, начинающие работу с Kora
- **Архитекторы**, оценивающие фреймворки с компиляционным внедрением зависимостей
- **Команды**, мигрирующие со Spring на Kora
- **Технические лидеры**, создающие стандарты разработки микросервисов

## Почему Kora для AI-агентов

Kora **идеально подходит** для AI-агентов и LLM-разработки:

| Преимущество | Почему это важно для AI |
|--------------|-------------------------|
| **Быстрый старт (50–100 мс)** | Агенты запускаются и останавливаются мгновенно |
| **Низкое потребление памяти (~50 МБ)** | В 6 раз больше агентов на том же оборудовании по сравнению с Spring Boot |
| **Компиляционное внедрение зависимостей** | Нет неожиданностей во время выполнения — предсказуемое поведение |
| **Читаемый код** | AI понимает, модифицирует и расширяет сгенерированный код |
| **Нет рефлексии/прокси** | Чистые трассировки стека, прозрачное поведение |
| **Виртуальные потоки** | Тысячи конкурентных задач агентов выполняются эффективно |

## Вклад в проект

1. Форкните репозиторий
2. Создайте ветку (`git checkout -b feature/amazing-skill`)
3. Зафиксируйте изменения (`git commit -m "Add amazing skill"`)
4. Отправьте в репозиторий (`git push origin feature/amazing-skill`)
5. Создайте Pull Request

## Лицензия

Лицензия Apache 2.0 — см. [LICENSE](LICENSE)

## Поддержка

- **Задачи:** [GitHub Issues](https://github.com/kora-projects/kora-skills/issues)
- **Обсуждения:** [GitHub Discussions](https://github.com/kora-projects/kora-skills/discussions)
- **Документация:** [kora-projects.github.io/kora-docs/ru](https://kora-projects.github.io/kora-docs/ru/)
