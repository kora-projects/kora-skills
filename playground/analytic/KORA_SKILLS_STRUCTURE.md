# План декомпозиции kora-skills

Цель документа: описать будущую структуру набора гранулированных skills для Kora Framework. На этой итерации мы не создаем сами skills, а фиксируем архитектуру, границы ответственности, список
источников и первые базовые сценарии.

Основная проблема текущего `kora-skill`: skills слишком крупные и местами смешивают несколько самостоятельных областей. Например, bootstrap одновременно затрагивает Gradle, `@KoraApp`, DI, config,
lifecycle и troubleshooting. Новая структура должна быть более атомарной: один skill отвечает за одну устойчивую область Kora, а `kora-core` становится навигационной и справочной основой по модулям,
зависимостям, ключевым аннотациям, интерфейсам и функциям.

## Источники правды

Каждый будущий skill должен явно ссылаться на локальную документацию и примеры:

- Документация модулей: `mkdocs/docs/en/documentation/`
- Пошаговые guides: `mkdocs/docs/en/guides/`
- Java examples: `examples/java/`
- Java guide apps: `guides/java/`
- Kotlin examples и guide apps использовать как дополнительный источник, но Java считать первым языком для базовых templates.

Правило для разработки skills: сначала читать документацию, потом пример, потом только формировать workflow, snippets, assets и validation checklist.

## Общие принципы новой структуры

1. Один skill должен иметь маленькую и понятную область применения.
2. `kora-core` не должен генерировать прикладной код. Он должен помогать выбрать нужный module/skill и давать компактную карту Kora.
3. Skills с кодогенерацией должны иметь `assets/` и, при необходимости, `scripts/`.
4. Skills без кодогенерации могут состоять из `SKILL.md` и `references/`.
5. Каждый skill должен содержать:
    - `name` и `description` с точными trigger-словами;
    - когда использовать skill;
    - когда не использовать skill и какой skill выбрать вместо него;
    - dependencies для Gradle Groovy и Kotlin DSL;
    - подключаемые Kora modules для `@KoraApp`;
    - основные аннотации, интерфейсы и классы;
    - минимальный working path;
    - common pitfalls;
    - validation commands.
6. Все snippets должны использовать импортированные классы, а не fully qualified names.
7. Для DAO/entity records всегда явно напоминать про `@Column` annotations, если skill работает с database repositories.
8. Для любого workflow указывать команду проверки: обычно `./gradlew clean classes`, затем `./gradlew test`.
9. Все будущие реальные skills, включая `SKILL.md`, `README.md`, `references/`, `assets/`, `scripts/` comments/docstrings и `evals/`, должны быть полностью на английском языке. Этот плановый документ
   остается на русском.
10. Skills нужно создавать не только по `documentation/`, но и по существующим guides из `mkdocs/docs/en/guides/`. Если guide описывает самостоятельный пользовательский сценарий, он должен либо получить отдельный skill, либо быть явно покрыт ближайшим тематическим skill.
11. Каждый subskill `SKILL.md` должен содержать только минимально необходимое описание для навигации и запуска workflow. Большинство подробной информации нужно гранулированно выносить в `references/`, а из `SKILL.md` делать явные переходы к нужным reference documents.
12. Для любой Kora-задачи обязательна иерархия чтения: сначала верхний `kora-core` meta-skill, затем релевантный subskill, затем reference-документы subskill, затем локальная внешняя документация и примеры.

Обязательная иерархия контекста:

```text
1. This meta-skill (navigation + architectural principles)
        ↓
2. Sub-skill for the relevant area (SKILL.md in its folder)
        ↓
3. Reference documents inside the sub-skill (references/)
        ↓
4. External documentation and examples (.kora-agent/)
```

`kora-core` должен enforce-ить эту иерархию для всего, что связано с Kora.

## Эталон структуры: kora-bootstrap

Текущий `kora-skill/skills/kora-bootstrap/SKILL.md` и вся директория `kora-skill/skills/kora-bootstrap` должны быть глубоко проанализированы перед созданием первого нового skill. Их нужно использовать как основу структуры каждого будущего subskill, но не как основу ширины ответственности. `kora-bootstrap` слишком широкий по предметной области, зато его упаковка, плотность `SKILL.md`, набор `assets/`, `scripts/`, `references/` и `evals/` являются хорошим базовым стандартом.

Текущая структура:

```text
kora-bootstrap/
  SKILL.md
  README.md
  assets/
    application.conf.template
    application.yaml.template
    Application.java.template
    Application.kt.template
    build.gradle.template
    build.gradle.kts.template
    gradle-wrapper.properties.template
    gradle.properties.template
    settings.gradle.template
  scripts/
    generate_project.py
    validate_gradle.py
  references/
    config-reference.md
    configuration-reference.md
    core-container-reference.md
    dependency-injection-reference.md
    gradle-setup-reference.md
    lifecycle-reference.md
    logging-reference.md
    multi-module-architecture.md
    tags-collections-reference.md
  evals/
    evals.json
```

Что в нем хорошо и должно быть повторено:

- `SKILL.md` начинается с frontmatter `name` и `description`, где есть triggers.
- `SKILL.md` работает как полноценный entry point: быстрый старт, основные концепции, decision rules, common pitfalls, assets, references, scripts.
- `SKILL.md` не ограничивается короткой памяткой: он дает агенту рабочий алгоритм, snippets, troubleshooting и validation path.
- `README.md` короткий и объясняет назначение skill для человека.
- `assets/` содержит готовые templates, а не только фрагменты текста.
- `scripts/` автоматизируют повторяемые операции и validation.
- `references/` держит глубокие материалы отдельно от основного `SKILL.md`.
- `evals/evals.json` фиксирует ожидаемые сценарии поведения skill.
- `assets/`, `scripts/`, `references/` и `evals/` синхронизированы с тем, что описано в `SKILL.md`, поэтому skill выглядит как законченный инструмент, а не как один markdown-файл.

Что нужно изменить в новой структуре:

- `kora-bootstrap` сейчас смешивает Gradle, DI, config, lifecycle, logging и multi-module architecture; в новой модели это должно быть разнесено по `kora-gradle`, `kora-app-bootstrap`,
  `kora-di-core`, `kora-di-advanced`, `kora-config-*`, `kora-logging-*`.
- `SKILL.md` будущего subskill должен быть меньше и точнее: только одна область, без превращения в общий справочник по Kora.
- `references/` должны быть привязаны к конкретной области subskill, а не дублировать соседние skills.
- `assets/` должны быть минимальными и предметными: templates только для этого skill.
- `scripts/` нужны только там, где есть реальная повторяемая механика генерации или проверки.

### Структурный вывод из анализа kora-bootstrap/SKILL.md

Каждый новый skill должен наследовать следующую форму:

- strong frontmatter: точное `name`, длинный `description`, triggers по annotations, module interfaces, Gradle artifacts и типовым задачам;
- opening purpose: зачем skill существует и когда он включается;
- "Read this first when" list: быстрый набор условий активации;
- quick start / minimal path: минимальные шаги от dependency до working code;
- core concepts: короткие объяснения ключевых Kora-механик;
- code snippets: Java-first, Kotlin where useful, только с imports;
- configuration snippets: HOCON/YAML/Gradle только если это относится к skill;
- decision rules: когда выбрать этот skill, а когда соседний;
- common pitfalls: compile-time graph errors, missing module interfaces, missing processors, wrong config, missing annotations;
- development workflow: `./gradlew clean classes`, `./gradlew test`, `./gradlew --stop` для locked clean;
- assets table: все templates, которые реально есть в `assets/`;
- references table: все files из `references/` с коротким назначением;
- scripts section: CLI usage для scripts, если они есть.

`kora-bootstrap/SKILL.md` также показывает важный принцип: основной `SKILL.md` должен быть достаточно полезным для быстрого старта, но не должен поглощать всю документацию. Все детальные справочники, длинные таблицы, расширенные варианты, edge cases, troubleshooting matrices и deep-dive examples нужно выносить в `references/`, чтобы агент читал их по необходимости.

## Обязательный контракт каждого subskill

Каждый будущий subskill должен быть упакован по одной схеме. Минимальная структура:

```text
kora-<area>/
  SKILL.md
  README.md
  references/
```

Полная структура для skills с генерацией, проверками и regression scenarios:

```text
kora-<area>/
  SKILL.md
  README.md
  assets/
  scripts/
  references/
  evals/
    evals.json
```

### SKILL.md

Обязательный язык: английский.

Назначение: основной entry point для агента. Он должен быть достаточно подробным, чтобы агент мог быстро выбрать workflow и начать работу, но должен содержать только минимально необходимое описание. Большая часть подробностей, длинных таблиц, вариантов, troubleshooting и deep dives должна быть вынесена в `references/`.

Каждый subskill `SKILL.md` обязан явно перенаправлять в свои reference documents: "For details, read `references/<file>.md`". Агент должен читать references тогда, когда задача выходит за рамки minimal path.

Обязательные элементы:

- frontmatter:
    - `name`;
    - `description`;
    - triggers внутри description;
- title;
- purpose;
- framework/module version assumptions, если важно;
- "Read this first when";
- "Do not use when" и ссылка на соседний skill;
- dependencies для Gradle Groovy и Kotlin DSL, если применимо;
- Kora modules/interfaces to extend in `@KoraApp`, если применимо;
- minimal working path;
- key annotations/interfaces/classes;
- common patterns;
- common pitfalls;
- validation commands;
- assets table;
- references table;
- scripts usage, если scripts есть.
- explicit reference routing: какой `references/*.md` читать для dependencies, annotations, configuration, advanced patterns, troubleshooting and testing.

### README.md

Обязательный язык: английский.

Назначение: короткая карточка skill для человека и marketplace/index.

Обязательные элементы:

- skill name and one-line purpose;
- when to use;
- key features;
- triggers;
- resources list: `SKILL.md`, `references/`, `assets/`, `scripts/`, `evals/` если есть.

### references/

Обязательный язык: английский.

Назначение: глубокая справка, которую агент читает только при необходимости.

Правила:

- один файл должен раскрывать один аспект;
- ссылки на локальные docs/guides/examples обязательны;
- для `kora-core` обязательно нужен `module-catalog.md` со всеми Kora modules из `mkdocs/docs/en/documentation/`, их Gradle dependencies, `@KoraApp` module interfaces, основными
  annotations/interfaces/classes, ссылками на docs/guides/examples и указанием целевого специализированного skill;
- references не должны дублировать весь `SKILL.md`;
- references должны быть достаточно автономными, чтобы агент мог углубиться без web search.

В `kora-core/references/module-catalog.md` должна быть основная разводящая таблица. Это главный router для агента: по dependency или module interface он должен понять, какой subskill открыть и какие
Kora API искать.

Обязательные колонки таблицы:

- Kora area / dependency;
- target subskill;
- `@KoraApp` module interface;
- main annotations/interfaces/classes;
- purpose tags;
- docs/guides/examples links.

Начальная версия таблицы должна покрывать все эти строки:

| Kora area / dependency                                | Target subskill                                                                              | `@KoraApp` module interface                                                                   | Main annotations/interfaces/classes                                                                                                                                                                                                                                              | Purpose tags                                                | Sources                                                                                            |
|-------------------------------------------------------|----------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-------------------------------------------------------------|----------------------------------------------------------------------------------------------------|
| Gradle base files: `build.gradle`, `build.gradle.kts`, `settings.gradle`, `gradle.properties` | `kora-gradle`                                                                                 | no runtime module; configures build before `@KoraApp` exists                                  | Gradle plugins, configurations, source sets, `application.mainClass`, wrapper files                                                                                                                                                                                              | gradle, build, project-setup, wrapper, source-sets          | `documentation/general.md`, `guides/getting-started.md`, `kora-bootstrap/references/gradle-setup-reference.md` |
| `ru.tinkoff.kora:kora-parent` BOM                    | `kora-gradle`                                                                                 | no runtime module                                                                             | `koraBom`, `platform(...)`, dependency version alignment                                                                                                                                                                                                                         | gradle, bom, dependency-management, versions                | `documentation/general.md`, `guides/getting-started.md`                                           |
| `ru.tinkoff.kora:annotation-processors`               | `kora-gradle`                                                                                 | no runtime module; enables generated graph/components                                          | `annotationProcessor`, `testAnnotationProcessor`, generated `ApplicationGraph`                                                                                                                                                                                                   | gradle, java, annotation-processing, generated-code         | `documentation/general.md`, `guides/getting-started.md`, `guides/dependency-injection.md`         |
| `ru.tinkoff.kora:symbol-processors`                   | `kora-gradle`                                                                                 | no runtime module; enables Kotlin generated graph/components                                   | KSP plugin, `ksp`, `kspTest`, generated KSP source dirs                                                                                                                                                                                                                          | gradle, kotlin, ksp, generated-code                         | `documentation/general.md`, `guides/getting-started.md`, `guides/dependency-injection.md`         |
| `ru.tinkoff.kora:common`                              | `kora-di-core`, `kora-di-advanced`                                                           | application-defined `@KoraApp`; app-defined `@Module` interfaces                              | `@KoraApp`, `@Component`, `@Module`, `@Root`, `@Tag`, `@DefaultComponent`, `@KoraSubmodule`, `All<T>`, `ValueOf<T>`, `Lifecycle`, `LifecycleWrapper`, `GraphInterceptor<T>`                                                                                                      | core, di, graph, lifecycle, tags, generated-code            | `documentation/general.md`, `documentation/container.md`, `guides/dependency-injection*.md`        |
| `ru.tinkoff.kora:config-common`                       | `kora-config-core`                                                                           | none by itself; used by config format modules                                                 | `@ConfigSource`, `@ConfigValueExtractor`, `Config`, `ConfigValue`, `@Environment`, `@SystemProperties`                                                                                                                                                                           | config, typed-config, extraction, graph-refresh             | `documentation/config.md`                                                                          |
| `ru.tinkoff.kora:config-hocon`                        | `kora-config-hocon`                                                                          | `HoconConfigModule`                                                                           | `@ConfigSource`, `@ConfigValueExtractor`, `application.conf`, `reference.conf`                                                                                                                                                                                                   | config, hocon, env-substitution, typed-config               | `documentation/config.md`, `guides/config-hocon.md`, `examples/java/kora-java-config-hocon`        |
| `ru.tinkoff.kora:config-yaml`                         | `kora-config-yaml`                                                                           | `YamlConfigModule`                                                                            | `@ConfigSource`, `@ConfigValueExtractor`, `application.yaml`                                                                                                                                                                                                                     | config, yaml, env-substitution, typed-config                | `documentation/config.md`, `guides/config-yaml.md`, `examples/java/kora-java-config-yaml`          |
| `ru.tinkoff.kora:json-module`                         | `kora-json`                                                                                  | `JsonModule`                                                                                  | `@Json`, `@JsonReader`, `@JsonWriter`, `@JsonField`, `@JsonSkip`, `@JsonInclude`, `@JsonDiscriminatorField`, `@JsonDiscriminatorValue`, `JsonReader<T>`, `JsonWriter<T>`, `JsonNullable<T>`                                                                                      | json, dto, serialization, http-body, polymorphism           | `documentation/json.md`, `guides/json.md`, `guides/java/kora-java-guide-json-app`                  |
| `ru.tinkoff.kora:jackson-module`                      | future `kora-json-jackson` or `kora-json-core` section                                       | `JacksonModule`                                                                               | Jackson mapper integration, custom mapper components                                                                                                                                                                                                                             | json, jackson, compatibility, external-libraries            | `documentation/json.md`                                                                            |
| `ru.tinkoff.kora:logging-logback`                     | `kora-logging-slf4j`                                                                         | `LogbackModule`                                                                               | `logback.xml`, SLF4J `Logger`, logging configuration                                                                                                                                                                                                                             | logging, logback, runtime-logs, startup                     | `documentation/logging-slf4j.md`                                                                   |
| `ru.tinkoff.kora:logging-common`                      | `kora-logging-aspect`                                                                        | `LoggingModule`                                                                               | `@Log`, logging aspect configuration                                                                                                                                                                                                                                             | logging, aop, method-logging, diagnostics                   | `documentation/logging-aspect.md`, `documentation/logging-slf4j.md`                                |
| `ru.tinkoff.kora:http-server-undertow`                | `kora-http-server-core`, `kora-http-server-advanced`                                         | `UndertowHttpServerModule`                                                                    | `@HttpController`, `@HttpRoute`, `HttpMethod`, `@Path`, `@Query`, `@Header`, `@Cookie`, `HttpServerResponse`, `HttpResponseEntity<T>`, `HttpServerResponseException`, `HttpServerInterceptor`, `HttpServerRequestMapper<T>`, `HttpServerResponseMapper<T>`, `UndertowConfigurer` | http, server, rest, controller, undertow, interceptors      | `documentation/http-server.md`, `guides/http-server*.md`, `examples/java/kora-java-http-server`    |
| `ru.tinkoff.kora:http-client-common`                  | `kora-http-client-core`, `kora-http-client-advanced`                                         | client implementation module still required                                                   | declarative HTTP client annotations, request/response mappers, interceptors                                                                                                                                                                                                      | http, client, declarative-client, mappers                   | `documentation/http-client.md`, `guides/http-client*.md`                                           |
| `ru.tinkoff.kora:http-client-ok`                      | `kora-http-client-core`, `kora-http-client-advanced`                                         | `OkHttpClientModule`                                                                          | OkHttp-backed declarative clients and client config                                                                                                                                                                                                                              | http, client, okhttp, blocking                              | `documentation/http-client.md`, `guides/http-client.md`                                            |
| `ru.tinkoff.kora:http-client-jdk`                     | `kora-http-client-core`, `kora-http-client-advanced`                                         | `JdkHttpClientModule`                                                                         | JDK-backed declarative clients and client config                                                                                                                                                                                                                                 | http, client, jdk, standard-library                         | `documentation/http-client.md`, `examples/java/kora-java-http-client`                              |
| `ru.tinkoff.kora:http-client-async`                   | `kora-http-client-advanced`                                                                  | `AsyncHttpClientModule`                                                                       | Async HTTP client integration                                                                                                                                                                                                                                                    | http, client, async                                         | `documentation/http-client.md`                                                                     |
| buildscript `ru.tinkoff.kora:openapi-generator`       | `kora-openapi-server`, `kora-openapi-client`                                                 | generated server/client still need HTTP modules                                               | OpenAPI generator Gradle tasks, generated delegates, generated clients                                                                                                                                                                                                           | openapi, codegen, contract-first, server, client            | `documentation/openapi-codegen.md`, `guides/openapi-http-*.md`                                     |
| `ru.tinkoff.kora:openapi-management`                  | `kora-openapi-management`                                                                    | `OpenApiManagementModule`                                                                     | OpenAPI/Swagger management endpoints and config                                                                                                                                                                                                                                  | openapi, swagger, management, docs-ui                       | `documentation/openapi-management.md`, `guides/openapi-http-server.md`                             |
| `ru.tinkoff.kora:validation-module`                   | `kora-validation`                                                                            | `ValidationModule`                                                                            | `@Validate`, `@Valid`, `@NotNull`, `@NotEmpty`, `@Pattern`, `@Range`, `@Size`, `@Validator`, generated validators                                                                                                                                                                | validation, aop, request-validation, business-rules         | `documentation/validation.md`, `guides/validation.md`, `examples/java/kora-java-validation`        |
| `ru.tinkoff.kora:database-jdbc`                       | `kora-database-jdbc`, `kora-database-jdbc-advanced`                                          | `JdbcDatabaseModule`                                                                          | `@Repository`, `@Query`, `@Column`, JDBC mappers, transactions                                                                                                                                                                                                                   | database, jdbc, sql, repository, transaction                | `documentation/database-jdbc.md`, `documentation/database-common.md`, `guides/database-jdbc*.md`   |
| `ru.tinkoff.kora:database-flyway`                     | `kora-database-migration`                                                                    | `FlywayJdbcDatabaseModule`                                                                    | Flyway migrations, migration config                                                                                                                                                                                                                                              | database, migration, flyway, schema                         | `documentation/database-migration.md`, `guides/database-jdbc-advanced.md`                          |
| `ru.tinkoff.kora:database-liquibase`                  | `kora-database-migration`                                                                    | `LiquibaseJdbcDatabaseModule`                                                                 | Liquibase migrations, changelog config                                                                                                                                                                                                                                           | database, migration, liquibase, schema                      | `documentation/database-migration.md`                                                              |
| `ru.tinkoff.kora:database-cassandra`                  | `kora-database-cassandra`                                                                    | `CassandraDatabaseModule`                                                                     | `@Repository`, `@Query`, Cassandra mappers                                                                                                                                                                                                                                       | database, cassandra, cql, repository                        | `documentation/database-cassandra.md`, `guides/database-cassandra.md`                              |
| `ru.tinkoff.kora:database-r2dbc`                      | no dedicated skill planned; docs-only entry in `kora-core`                                   | `R2dbcDatabaseModule`                                                                         | `@Repository`, `@Query`, R2DBC mappers                                                                                                                                                                                                                                           | database, r2dbc, reactive, repository, docs-only            | `documentation/database-r2dbc.md`, `examples/java/kora-java-database-r2dbc`                        |
| `ru.tinkoff.kora:database-vertx`                      | no dedicated skill planned; docs-only entry in `kora-core`                                   | `VertxDatabaseModule`                                                                         | `@Repository`, `@Query`, Vert.x SQL mappers                                                                                                                                                                                                                                      | database, vertx, async-sql, repository, docs-only           | `documentation/database-vertx.md`, `examples/java/kora-java-database-vertx`                        |
| `ru.tinkoff.kora:cache-caffeine`                      | `kora-cache-core`, `kora-cache-caffeine`                                                     | `CaffeineCacheModule`                                                                         | `@Cacheable`, `@CachePut`, `@CacheInvalidate`, cache interfaces, cache key mappers                                                                                                                                                                                               | cache, caffeine, local-cache, aop                           | `documentation/cache.md`, `guides/cache.md`, `examples/java/kora-java-cache-caffeine`              |
| `ru.tinkoff.kora:cache-redis`                         | `kora-cache-core`, `kora-cache-redis`                                                        | `RedisCacheModule`                                                                            | `@Cacheable`, `@CachePut`, `@CacheInvalidate`, Redis cache config                                                                                                                                                                                                                | cache, redis, distributed-cache, multi-level-cache          | `documentation/cache.md`, `guides/cache-multi-level.md`, `examples/java/kora-java-cache-redis`     |
| `ru.tinkoff.kora:resilient-kora`                      | `kora-resilient`                                                                             | `ResilientModule`                                                                             | `@CircuitBreaker`, `@Retry`, `@Timeout`, `@Fallback`, failure predicates                                                                                                                                                                                                         | resilient, fault-tolerance, retry, circuit-breaker, timeout | `documentation/resilient.md`, `guides/resilient.md`, `examples/java/kora-java-resilient`           |
| `ru.tinkoff.kora:micrometer-module`                   | `kora-metrics`                                                                               | `MetricsModule`                                                                               | Micrometer `MeterRegistry`, counters, timers, gauges, module telemetry                                                                                                                                                                                                           | metrics, micrometer, observability, prometheus              | `documentation/metrics.md`, `guides/observability-metrics.md`, `examples/java/kora-java-telemetry` |
| `ru.tinkoff.kora:opentelemetry-tracing-exporter-http` | `kora-tracing`                                                                               | `OpentelemetryHttpExporterModule`                                                             | OpenTelemetry tracing exporter, spans, trace config                                                                                                                                                                                                                              | tracing, opentelemetry, http-exporter, observability        | `documentation/tracing.md`, `guides/observability-tracing.md`                                      |
| `ru.tinkoff.kora:opentelemetry-tracing-exporter-grpc` | `kora-tracing`                                                                               | `OpentelemetryGrpcExporterModule`                                                             | OpenTelemetry tracing exporter, spans, trace config                                                                                                                                                                                                                              | tracing, opentelemetry, grpc-exporter, observability        | `documentation/tracing.md`, `examples/java/kora-java-telemetry`                                    |
| probes module from `probes.md`                        | `kora-probes`                                                                                | `ProbesModule` where applicable; verify exact dependency/module in docs before implementation | readiness/liveness probe interfaces, custom probes                                                                                                                                                                                                                               | probes, health, readiness, liveness, kubernetes             | `documentation/probes.md`, `guides/observability-probes.md`                                        |
| `ru.tinkoff.kora:kafka`                               | `kora-kafka`                                                                                 | `KafkaModule`                                                                                 | Kafka producer/consumer annotations and handlers, record mappers, telemetry                                                                                                                                                                                                      | kafka, messaging, producer, consumer, async                 | `documentation/kafka.md`, `guides/messaging-kafka.md`, `examples/java/kora-java-kafka`             |
| `ru.tinkoff.kora:grpc-server`                         | `kora-grpc-server`                                                                           | `GrpcServerModule`                                                                            | generated gRPC services, interceptors, protobuf service contracts                                                                                                                                                                                                                | grpc, server, protobuf, streaming                           | `documentation/grpc-server.md`, `guides/grpc-server*.md`, `examples/java/kora-java-grpc-server`    |
| `ru.tinkoff.kora:grpc-client`                         | `kora-grpc-client`                                                                           | `GrpcClientModule`                                                                            | generated gRPC clients, interceptors, metadata, stubs                                                                                                                                                                                                                            | grpc, client, protobuf, streaming                           | `documentation/grpc-client.md`, `guides/grpc-client*.md`, `examples/java/kora-java-grpc-client`    |
| S3 AWS client dependency from `s3-client.md`          | `kora-s3-client`                                                                             | `AwsS3ClientModule`                                                                           | `@S3.Client`, `@S3.Get`, `@S3.Put`, `@S3.Delete`, `@S3.List`, `S3Body`, S3 object models                                                                                                                                                                                         | s3, aws, object-storage, files                              | `documentation/s3-client.md`, `guides/s3.md`, `examples/java/kora-java-s3-client-aws`              |
| S3 MinIO client dependency from `s3-client.md`        | `kora-s3-client`                                                                             | `MinioS3ClientModule`                                                                         | `@S3.Client`, `@S3.Get`, `@S3.Put`, `@S3.Delete`, `@S3.List`, `S3Body`, S3 object models                                                                                                                                                                                         | s3, minio, object-storage, local-dev                        | `documentation/s3-client.md`, `guides/s3.md`, `examples/java/kora-java-s3-client-minio`            |
| `ru.tinkoff.kora:scheduling-jdk`                      | `kora-scheduling-jdk`                                                                        | `SchedulingJdkModule`                                                                         | scheduling annotations, fixed-rate/fixed-delay jobs                                                                                                                                                                                                                              | scheduling, jdk, jobs, background-tasks                     | `documentation/scheduling.md`, `examples/java/kora-java-scheduling-jdk`                            |
| `ru.tinkoff.kora:scheduling-quartz`                   | `kora-scheduling-quartz`                                                                     | `QuartzModule`                                                                                | scheduling annotations, Quartz triggers, cron jobs                                                                                                                                                                                                                               | scheduling, quartz, cron, persistent-jobs                   | `documentation/scheduling.md`, `examples/java/kora-java-scheduling-quartz`                         |
| `ru.tinkoff.kora:soap-client`                         | `kora-soap-client`                                                                           | `SoapClientModule`                                                                            | SOAP client interfaces, generated SOAP clients, XML mapping                                                                                                                                                                                                                      | soap, client, xml, legacy-integration                       | `documentation/soap-client.md`, `examples/java/kora-java-soap-client`                              |
| `ru.tinkoff.kora:test-junit5`                         | `kora-junit5`, `kora-testing-component`, `kora-testing-integration`, `kora-testing-blackbox` | test application graph modules; no production `@KoraApp` module                               | `@KoraAppTest`, `KoraJUnit5Extension`, graph modification/replacement APIs                                                                                                                                                                                                       | testing, junit5, component-test, integration-test           | `documentation/junit5.md`, `guides/testing-*.md`                                                   |
| container support from `container.md`                 | `kora-container`                                                                             | depends on app modules                                                                        | Dockerfile, `distTar`, runtime image layout, health checks                                                                                                                                                                                                                       | container, docker, deployment, runtime                      | `documentation/container.md`                                                                       |
| GraalVM support from `graalvm-native.md`              | no dedicated skill planned; docs-only entry in `kora-core`                                   | depends on app modules                                                                        | native-image config, reflection/resource configs when needed                                                                                                                                                                                                                     | graalvm, native-image, startup, deployment, docs-only       | `documentation/graalvm-native.md`, `examples/graalvm/`                                             |
| Camunda 7 BPMN dependency from `camunda7-bpmn.md`     | `kora-camunda7-bpmn`                                                                         | `CamundaEngineBpmnModule`                                                                     | BPMN engine components, process deployment/config                                                                                                                                                                                                                                | camunda7, bpmn, workflow, process-engine                    | `documentation/camunda7-bpmn.md`, `examples/java/kora-java-camunda-engine`                         |
| Camunda 7 REST dependency from `camunda7-rest.md`     | `kora-camunda7-rest`                                                                         | `CamundaRestUndertowModule`                                                                   | Camunda REST API on Undertow                                                                                                                                                                                                                                                     | camunda7, rest, workflow, management-api                    | `documentation/camunda7-rest.md`                                                                   |
| Camunda 8 worker dependency from `camunda8-worker.md` | `kora-camunda8-worker`                                                                       | `ZeebeWorkerModule`                                                                           | Zeebe workers, job handlers, worker config                                                                                                                                                                                                                                       | camunda8, zeebe, worker, workflow                           | `documentation/camunda8-worker.md`, `examples/java/kora-java-camunda-zeebe-worker`                 |

Если точная dependency или module interface неочевидны из routing table, агент обязан проверить соответствующий файл в `mkdocs/docs/en/documentation/` перед созданием реального skill. В таблице нельзя
оставлять догадки без пометки "verify in docs".

Примеры имен:

- `module-catalog.md`
- `module-reference.md`
- `configuration-reference.md`
- `annotations-reference.md`
- `troubleshooting-reference.md`
- `testing-reference.md`
- `advanced-patterns-reference.md`

### assets/

Обязательный язык: английский в comments/placeholders.

Назначение: готовые templates для файлов, которые skill часто создает.

Правила:

- имена templates должны быть конкретными: `Application.java.template`, `application.conf.template`, `Repository.java.template`;
- placeholders должны быть едиными: `${packageName}`, `${className}`, `${moduleName}`;
- templates должны компилироваться после замены placeholders;
- templates должны следовать Kora conventions и использовать imports вместо fully qualified names.

### scripts/

Обязательный язык: английский в CLI help, comments, docstrings and output.

Назначение: автоматизация генерации или проверки, когда copy/paste templates уже недостаточно.

Правила:

- каждый script должен иметь `--help`;
- script не должен делать destructive actions без явного флага;
- validation scripts должны возвращать non-zero exit code на ошибках;
- scripts должны работать с относительными путями проекта;
- scripts не должны зависеть от сети.

### evals/

Обязательный язык: английский.

Назначение: regression scenarios для проверки поведения skill.

Минимальный формат:

```json
{
    "skill_name": "kora-<area>",
    "evals": [
        {
            "id": 1,
            "name": "scenario-name",
            "prompt": "User-facing prompt in English",
            "expected_output": "Expected behavior summary",
            "files": [],
            "assertions": [
                {
                    "name": "has_required_concept",
                    "type": "code_contains",
                    "expected": "..."
                }
            ]
        }
    ]
}
```

Для первой версии каждого subskill достаточно 5-10 eval scenarios. Для крупных skills вроде `kora-database-jdbc` или `kora-openapi-server` нужно 15+ scenarios.

## Предлагаемое дерево skills

```text
kora-skills/
  skills/
    kora-core/
      SKILL.md
      references/
        module-catalog.md
        annotation-catalog.md
        dependency-catalog.md
        generated-code-debugging.md

    kora-gradle/
    kora-app-bootstrap/
    kora-di-core/
    kora-di-advanced/
    kora-config-core/
    kora-config-hocon/
    kora-config-yaml/
    kora-json-core/
    kora-http-server-core/
    kora-http-server-advanced/
    kora-http-client-core/
    kora-http-client-advanced/
    kora-openapi-server/
    kora-openapi-client/
    kora-openapi-management/
    kora-validation/
    kora-database-common/
    kora-database-jdbc/
    kora-database-jdbc-advanced/
    kora-database-cassandra/
    kora-database-migration/
    kora-cache-core/
    kora-cache-caffeine/
    kora-cache-redis/
    kora-resilient/
    kora-logging-slf4j/
    kora-logging-aspect/
    kora-metrics/
    kora-tracing/
    kora-probes/
    kora-observability-composition/
    kora-kafka/
    kora-grpc-server/
    kora-grpc-client/
    kora-s3-client/
    kora-scheduling-jdk/
    kora-scheduling-quartz/
    kora-soap-client/
    kora-mapstruct/
    kora-junit5/
    kora-testing-component/
    kora-testing-integration/
    kora-testing-blackbox/
    kora-container/
    kora-camunda7-bpmn/
    kora-camunda7-rest/
    kora-camunda8-worker/
```

На первой итерации стоит сделать не все сразу, а минимальный фундамент:

1. `kora-core`
2. `kora-gradle`
3. `kora-app-bootstrap`
4. `kora-di-core`
5. `kora-config-core`
6. `kora-config-hocon`
7. `kora-config-yaml`
8. `kora-json-core`
9. `kora-http-server-core`

Этого хватит, чтобы покрыть getting started, config guides, DI guide, JSON guide и первый HTTP server guide.

## kora-core

### Назначение

Главный навигационный и справочный skill. Он должен отвечать на вопросы:

- какой Kora module нужен для задачи;
- какую Gradle dependency добавить;
- какой `*Module` подключить в `@KoraApp`;
- какие аннотации, интерфейсы и классы являются ключевыми;
- какой специализированный skill вызвать дальше;
- где лежит документация и пример.

`kora-core` не должен подменять специализированные skills. Он должен жестко регламентировать использование подскиллов для всех задач: определить область, выбрать один или несколько target subskills,
указать документацию/guides/examples, а затем передать работу специализированному skill. Это основной разводящий meta-skill для всего Kora набора.

Ключевое правило `kora-core`: для любой конкретной реализации, настройки или troubleshooting он обязан маршрутизировать агента в подскилл. Исключение только для коротких навигационных ответов,
выбора dependency/module interface или составления карты модулей.

### Use when

- пользователь спрашивает про Kora в целом;
- нужно выбрать module/dependency;
- нужно понять, какой skill подходит;
- нужно объяснить compile-time DI, annotation processors, generated sources;
- нужно составить карту модулей приложения;
- задача еще не определена достаточно точно.
- нужно разложить пользовательский запрос на набор специализированных Kora skills.

### Do not use when

- уже ясно, что пользователь работает с HOCON, YAML, HTTP server, JDBC и т.п. Тогда использовать конкретный skill;
- нужно сгенерировать прикладной код. `kora-core` может указать следующий skill, но не должен быть codegen skill.

### Mandatory routing behavior

`kora-core/SKILL.md` должен прямо требовать следующий порядок:

1. Определить Kora area по словам пользователя, imports, annotations, Gradle dependencies, module interfaces или ошибкам компиляции.
2. Открыть `references/module-catalog.md`.
3. Найти target subskill по dependency/module interface/purpose tags.
4. Перед реализацией прочитать relevant docs/guides/examples:
    - `mkdocs/docs/en/documentation/<module>.md`;
    - `mkdocs/docs/en/guides/<scenario>.md`;
    - matching `examples/java/*` или `guides/java/*`.
5. Использовать специализированный subskill как основной источник workflow.
6. Вернуться в `kora-core` только если нужно выбрать следующий skill или сверить module/dependency map.

`kora-core` должен постоянно продвигать documentation-driven development: не угадывать Kora API, а проверять local docs/guides/examples перед изменениями.

### Mandatory repository preparation

`kora-core/SKILL.md` должен обязательно требовать подготовить repository context перед любой Kora-разработкой:

1. Проверить наличие локальных docs и examples, как указано в meta-skill:
    - `.kora-agent/kora-docs/` или согласованный локальный путь к `kora-docs`;
    - `.kora-agent/kora-examples/` или согласованный локальный путь к `kora-examples`;
    - в рамках этого репозитория основными локальными путями являются `mkdocs/docs/en/`, `examples/java/`, `guides/java/`.
2. Если docs/examples отсутствуют, meta-skill должен сначала дать шаги подготовки repo context и только потом продолжать проектирование или код.
3. Перед созданием/изменением кода агент обязан сослаться на конкретные docs/guides/examples, которые он использует.
4. Для каждого Kora workflow должен вестись journal, как указано в meta-skill: что делали, какие docs/examples использовали, какие решения приняли, какие проверки запускали, какие follow-up tasks остались.
5. Journal должен быть обязательной частью процесса для всех subskills, а не опциональной заметкой.

### Core principles

Из `mkdocs/docs/en/documentation/general.md`:

- Kora использует compile-time annotation processors.
- Runtime reflection не является основой фреймворка.
- Ошибки wiring должны ловиться на compile-time.
- Gradle является основным build system.
- BOM: `ru.tinkoff.kora:kora-parent`.
- Java: annotation processors.
- Kotlin: KSP / symbol processors.

### Build dependencies catalog

| Область               | Dependency                                                    | Processor / test dependency                                   | Kora module/interface                  |
|-----------------------|---------------------------------------------------------------|---------------------------------------------------------------|----------------------------------------|
| BOM                   | `ru.tinkoff.kora:kora-parent`                                 | -                                                             | -                                      |
| Java processors       | -                                                             | `ru.tinkoff.kora:annotation-processors`                       | -                                      |
| Kotlin processors     | -                                                             | `ru.tinkoff.kora:symbol-processors`                           | -                                      |
| Common DI             | `ru.tinkoff.kora:common`                                      | processors required                                           | `@KoraApp`, `@Component`, `@Module`    |
| HOCON config          | `ru.tinkoff.kora:config-hocon`                                | processors required for typed config                          | `HoconConfigModule`                    |
| YAML config           | `ru.tinkoff.kora:config-yaml`                                 | processors required for typed config                          | `YamlConfigModule`                     |
| Config common         | `ru.tinkoff.kora:config-common`                               | processors required for annotations                           | config annotations/extractors          |
| JSON                  | `ru.tinkoff.kora:json-module`                                 | included in common processors or JSON processor when isolated | `JsonModule`                           |
| Jackson JSON          | `ru.tinkoff.kora:jackson-module`                              | -                                                             | Jackson module integration             |
| Logging backend       | `ru.tinkoff.kora:logging-logback`                             | -                                                             | `LogbackModule`                        |
| Logging aspect        | `ru.tinkoff.kora:logging-common`                              | processors required                                           | `@Log`                                 |
| HTTP server           | `ru.tinkoff.kora:http-server-undertow`                        | processors required                                           | `UndertowHttpServerModule`             |
| HTTP client common    | `ru.tinkoff.kora:http-client-common`                          | processors required                                           | declarative clients common             |
| HTTP client OkHttp    | `ru.tinkoff.kora:http-client-ok`                              | processors required                                           | OkHttp client module                   |
| HTTP client JDK       | `ru.tinkoff.kora:http-client-jdk`                             | processors required                                           | JDK client module                      |
| HTTP client async     | `ru.tinkoff.kora:http-client-async`                           | processors required                                           | async client module                    |
| OpenAPI generator     | buildscript `ru.tinkoff.kora:openapi-generator`               | Gradle codegen task                                           | generated server/client                |
| OpenAPI management    | `ru.tinkoff.kora:openapi-management`                          | -                                                             | Swagger/OpenAPI management endpoints   |
| Validation            | `ru.tinkoff.kora:validation-module`                           | processors required                                           | `@Valid`, validators                   |
| JDBC                  | `ru.tinkoff.kora:database-jdbc`                               | processors required                                           | JDBC database module/repositories      |
| Flyway                | `ru.tinkoff.kora:database-flyway`                             | -                                                             | migration module                       |
| Liquibase             | `ru.tinkoff.kora:database-liquibase`                          | -                                                             | migration module                       |
| Cassandra             | `ru.tinkoff.kora:database-cassandra`                          | processors required                                           | Cassandra module/repositories          |
| Cache Caffeine        | `ru.tinkoff.kora:cache-caffeine`                              | processors required                                           | cache module                           |
| Cache Redis           | `ru.tinkoff.kora:cache-redis`                                 | processors required                                           | Redis cache module                     |
| Resilient             | `ru.tinkoff.kora:resilient-kora`                              | processors required                                           | circuit breaker/retry/timeout/fallback |
| Metrics               | `ru.tinkoff.kora:micrometer-module`                           | -                                                             | Micrometer module                      |
| Tracing HTTP exporter | `ru.tinkoff.kora:opentelemetry-tracing-exporter-http`         | -                                                             | OpenTelemetry tracing                  |
| Tracing gRPC exporter | `ru.tinkoff.kora:opentelemetry-tracing-exporter-grpc`         | -                                                             | OpenTelemetry tracing                  |
| Probes                | see `probes.md`                                               | -                                                             | readiness/liveness probes              |
| Kafka                 | `ru.tinkoff.kora:kafka`                                       | processors required                                           | Kafka consumers/producers              |
| gRPC server           | `ru.tinkoff.kora:grpc-server`                                 | processors required                                           | gRPC server module                     |
| gRPC client           | `ru.tinkoff.kora:grpc-client`                                 | processors required                                           | gRPC client module                     |
| S3                    | see `s3-client.md`; examples often pair with `http-client-ok` | -                                                             | S3 clients                             |
| Scheduling JDK        | `ru.tinkoff.kora:scheduling-jdk`                              | processors required                                           | scheduler module                       |
| Scheduling Quartz     | `ru.tinkoff.kora:scheduling-quartz`                           | processors required                                           | Quartz scheduler module                |
| SOAP client           | `ru.tinkoff.kora:soap-client`                                 | processors required                                           | SOAP client module                     |
| Testing               | `ru.tinkoff.kora:test-junit5`                                 | test processors                                               | `@KoraAppTest`                         |

### Annotation and interface catalog

Core DI:

- `@KoraApp`: root application graph.
- `KoraApplication.run(ApplicationGraph::graph)`: application startup.
- generated `ApplicationGraph`: compile-time graph implementation.
- `@Component`: graph-managed class.
- `@Module`: interface with factory methods.
- `@KoraSubmodule`: generated bridge for Gradle submodules.
- `@Root`: force creation of components with no consumers.
- `@Tag`: distinguish multiple components of the same type.
- `@DefaultComponent`: overridable default component.
- `All<T>` / `List<T>` with tags: collect multiple components.
- `ValueOf<T>`: indirect dependency that avoids cascading refresh/restart.
- `Lifecycle`: component init/release lifecycle.
- `LifecycleWrapper`: lifecycle wrapper for factory-created objects.
- `GraphInterceptor<T>`: lifecycle interception or component wrapping.
- `Wrapped<T>`: component plus lifecycle wrapper result.

Configuration:

- `@ConfigSource`: bind fixed config path to typed interface/record.
- `@ConfigValueExtractor`: reusable extractor for config fragments.
- `Config`: raw config tree.
- `ConfigValue`: typed config value model.
- `@Environment`: environment config source.
- `@SystemProperties`: system properties config source.
- `HoconConfigModule`: read `application.conf`.
- `YamlConfigModule`: read `application.yaml`.

JSON:

- `@Json`: generate reader and writer.
- `@JsonReader`: deserialize only.
- `@JsonWriter`: serialize only.
- `@JsonField`: field rename.
- `@JsonSkip`: skip field.
- `@JsonInclude`: include policy.
- `@JsonDiscriminatorField`: polymorphic discriminator field.
- `@JsonDiscriminatorValue`: polymorphic implementation value.
- `JsonReader<T>` / `JsonWriter<T>`: custom mappers.
- `JsonNullable<T>`: distinguish missing/null/value where supported.

HTTP server:

- `@HttpController`: route container.
- `@HttpRoute`: HTTP method/path mapping.
- `HttpMethod`: GET/POST/PUT/PATCH/DELETE/etc.
- `@Path`, `@Query`, `@Header`, `@Cookie`: request parameter sources.
- `HttpServerResponse`: raw response.
- `HttpResponseEntity<T>`: status/headers/body response.
- `HttpServerResponseException`: shortcut error response.
- `HttpServerInterceptor`: server interceptor.
- `HttpServerRequestMapper<T>` / `HttpServerResponseMapper<T>`: custom mapping.
- `UndertowHttpServerModule`: Undertow server integration.
- `UndertowConfigurer`: server customization.

Database:

- `@Repository`: repository declaration.
- `@Query`: SQL/CQL query method.
- `@Column`: explicit column mapping for records/entities.
- transaction annotations/interfaces: split by database-specific skills.

Observability:

- `@Log`: logging aspect.
- metrics interfaces/classes from Micrometer module.
- tracing integration from OpenTelemetry modules.
- readiness/liveness probe interfaces from probes docs.

### References for `kora-core`

- `mkdocs/docs/en/documentation/general.md`
- `mkdocs/docs/en/documentation/container.md`
- `mkdocs/docs/en/documentation/config.md`
- `mkdocs/docs/en/documentation/json.md`
- `mkdocs/docs/en/documentation/http-server.md`
- `mkdocs/docs/en/documentation/database-common.md`
- `mkdocs/docs/en/examples/kora-examples.md`
- `examples/java/README.md`

## kora-gradle

### Назначение

Отдельный детальный skill для Gradle setup базы Kora-приложения. Он должен описывать все основные секции Gradle build files, что именно использовать, зачем это нужно и как это настраивается в Java/Kotlin Kora projects на основе локальной документации, guides и examples.

Это не просто "добавить dependency" skill. `kora-gradle` должен быть основным источником по Gradle foundation для Kora: BOM, configurations, annotation processors, KSP, plugins, source sets, generated sources, application plugin, test processors, multi-module setup, Gradle Wrapper, validation commands and troubleshooting.

### Use when

- создается новый Kora project;
- нужно добавить Kora в существующий Gradle project;
- нужно понять обязательные секции `build.gradle`, `build.gradle.kts`, `settings.gradle`, `gradle.properties`;
- не генерируется `ApplicationGraph`;
- не работают annotation processors/KSP;
- нужно настроить test annotation processing.
- нужно настроить multi-module project или `@KoraSubmodule`;
- нужно собрать final artifact через `distTar`;
- `./gradlew clean` не удаляет директории из-за Gradle daemons/file locks.

### Sources

- `mkdocs/docs/en/documentation/general.md`
- `mkdocs/docs/en/documentation/container.md`
- `mkdocs/docs/en/guides/getting-started.md`
- `mkdocs/docs/en/guides/dependency-injection.md`
- `examples/java/kora-java-helloworld/build.gradle`
- `kora-skill/skills/kora-bootstrap/SKILL.md`
- `kora-skill/skills/kora-bootstrap/references/gradle-setup-reference.md`
- `kora-skill/skills/kora-bootstrap/assets/build.gradle.template`
- `kora-skill/skills/kora-bootstrap/assets/build.gradle.kts.template`
- `kora-skill/skills/kora-bootstrap/assets/settings.gradle.template`
- `kora-skill/skills/kora-bootstrap/assets/gradle.properties.template`

### Must cover

- Java `plugins`: `java`, `application`, optional module-specific plugins.
- Kotlin `plugins`: `kotlin("jvm")`, KSP plugin, `application`.
- BOM configuration: `koraBom platform("ru.tinkoff.kora:kora-parent:<version>")`.
- Gradle configurations: `annotationProcessor.extendsFrom(koraBom)`, `compileOnly.extendsFrom(koraBom)`, `implementation.extendsFrom(koraBom)`, `api.extendsFrom(koraBom)`, and test equivalents where needed.
- Java processors: `annotationProcessor "ru.tinkoff.kora:annotation-processors"`.
- Test processors: `testAnnotationProcessor "ru.tinkoff.kora:annotation-processors"` when tests build Kora graphs.
- Kotlin KSP: `ksp("ru.tinkoff.kora:symbol-processors")`, generated KSP source dirs and test KSP when needed.
- Java/Kotlin toolchain and compatibility settings from docs/guides.
- `application` plugin and correct `mainClass`: the `@KoraApp` interface, not generated `ApplicationGraph`.
- `settings.gradle` / `settings.gradle.kts` for single-module and multi-module projects.
- `gradle.properties`: Kora version, Gradle/JVM options, Kotlin/KSP settings where applicable.
- Gradle Wrapper setup and wrapper properties.
- `distTar` as final artifact build command.
- generated sources inspection:
    - Java: `build/generated/sources/annotationProcessor/`
    - Kotlin: `build/generated/ksp/`
- common Gradle troubleshooting:
    - missing BOM;
    - missing processors;
    - generated `ApplicationGraph` absent;
    - wrong `mainClass`;
    - locked clean fixed with `./gradlew --stop`;
    - dependency added but corresponding `@KoraApp` module interface not extended.

### Validation checklist

- `./gradlew clean classes`
- if tests use Kora graph: `./gradlew test`
- if clean fails because files are locked: run `./gradlew --stop`, then retry.

## kora-app-bootstrap

### Назначение

Skill для минимального runnable приложения: `@KoraApp`, `KoraApplication.run`, baseline modules, `application.conf` или `application.yaml`, logging backend.

### Use when

- нужно создать минимальное Kora service skeleton;
- нужно добавить entry point;
- нужно подключить framework modules в root graph;
- нужно понять почему приложение компилируется, но ничего не стартует.

### Boundaries

Этот skill не должен глубоко объяснять DI. Для graph patterns использовать `kora-di-core` и `kora-di-advanced`.

### Baseline Java application

Минимальный обычный HTTP-oriented baseline:

```java

@KoraApp
public interface Application extends
    HoconConfigModule,
    JsonModule,
    LogbackModule,
    UndertowHttpServerModule {

    static void main(String[] args) {
        KoraApplication.run(ApplicationGraph::graph);
    }
}
```

### Sources

- `mkdocs/docs/en/guides/getting-started.md`
- `examples/java/kora-java-helloworld/`
- `guides/java/kora-java-guide-getting-started-app/`

### Must cover

- explicit module inheritance;
- no classpath auto-discovery for external Kora modules;
- generated `ApplicationGraph`;
- `@Root` for lifecycle roots when applicable;
- `LogbackModule` as basic operational default.

## kora-di-core

### Назначение

Skill для compile-time dependency injection basics: components, modules, factories, constructor injection, root graph, tags, nullable dependencies.

### Use when

- пользователь добавляет service/repository/component;
- нужен factory method;
- есть несколько implementations одного interface;
- compile-time ошибка "dependency not found" или "ambiguous dependency";
- нужно объяснить, что именно попадет в graph.

### Sources

- `mkdocs/docs/en/documentation/container.md`
- `mkdocs/docs/en/guides/dependency-injection-introduction.md`
- `mkdocs/docs/en/guides/dependency-injection.md`
- `guides/java/kora-java-guide-dependency-injection/`

### Must cover

- `@Component` final class with constructor dependencies.
- `@Module` factory methods.
- factory methods directly on `@KoraApp`.
- `@Root` for components with no consumers.
- `@Tag` for multiple same-type components.
- optional dependencies via `@Nullable`.
- `All<T>` / list injection for multiple implementations.
- generated code inspection as first debugging tool.

### Out of scope

- lifecycle-heavy patterns: move to `kora-di-advanced`.
- config binding: move to `kora-config-core`.
- testing graph replacement: move to testing skills.

## kora-config-core

### Назначение

Shared config concepts independent of file format. Это базовый skill для `@ConfigSource`, `@ConfigValueExtractor`, raw `Config`, supported value types, environment/system property sources, and
injection patterns.

### Use when

- нужно спроектировать typed config contract;
- один config shape используется в нескольких местах;
- нужно выбрать между `@ConfigSource` и `@ConfigValueExtractor`;
- нужно объяснить config as graph dependency.

### Sources

- `mkdocs/docs/en/documentation/config.md`
- `mkdocs/docs/en/guides/config-hocon.md`
- `mkdocs/docs/en/guides/config-yaml.md`
- `examples/java/kora-java-config-hocon/`
- `examples/java/kora-java-config-yaml/`

### Must cover

- `@ConfigSource("path")` for stable app sections.
- `@ConfigValueExtractor` for reusable fragments.
- primitive/scalar values, lists, maps, nested objects, object lists.
- required vs optional config fields.
- Java `@Nullable` and Kotlin nullable types.
- config should be injected as typed dependency, not manually read from env in components.

## kora-config-hocon

### Назначение

Skill только для HOCON configuration. Он должен знать syntax, file resolution, substitutions, object reuse and Kora module wiring.

### Use when

- проект использует `application.conf`;
- нужно добавить `config-hocon`;
- нужно описать required/optional env substitutions;
- нужно переиспользовать HOCON object blocks;
- нужно debug resolved config.

### Dependencies and modules

Gradle:

```groovy
dependencies {
    implementation "ru.tinkoff.kora:config-hocon"
    implementation "ru.tinkoff.kora:logging-logback"
}
```

Application:

```java

@KoraApp
public interface Application extends
    HoconConfigModule,
    LogbackModule {
}
```

### Key HOCON concepts

- default app file: `application.conf`;
- library defaults: `reference.conf`;
- required env substitution: `${REQUIRED_ENV_VALUE}`;
- optional env substitution: `${?OPTIONAL_ENV_VALUE}`;
- default override style:
    - define value first;
    - then override with `${?ENV_VALUE}`;
- reference another config path: `${services.foo.bar}`;
- array can be array syntax or comma-separated string where supported;
- map/object/list-of-objects mapping to typed config.

### Skill assets to create later

- `assets/application.conf.template`
- `assets/AppConfig.java.template`
- `assets/AppConfig.kt.template`
- `assets/ReusableConfig.java.template`
- `assets/ReusableConfig.kt.template`
- optional script: validate presence of `HoconConfigModule` and `application.conf`.

### Validation checklist

- `./gradlew clean classes`
- run app with required env value set.
- verify logs include config loading/startup.

### Sources

- `mkdocs/docs/en/documentation/config.md`
- `mkdocs/docs/en/guides/config-hocon.md`
- `examples/java/kora-java-config-hocon/`

## kora-config-yaml

### Назначение

Skill только для YAML configuration. Он должен отличать YAML substitutions/defaults от HOCON и не смешивать syntax.

### Use when

- проект использует `application.yaml`;
- нужно добавить `config-yaml`;
- нужно описать required/defaulted env substitutions;
- нужно переиспользовать YAML object fragments;
- нужно debug YAML config extraction.

### Dependencies and modules

Gradle:

```groovy
dependencies {
    implementation "ru.tinkoff.kora:config-yaml"
    implementation "ru.tinkoff.kora:logging-logback"
}
```

Application:

```java

@KoraApp
public interface Application extends
    YamlConfigModule,
    LogbackModule {
}
```

### Key YAML concepts

- default app file: `application.yaml`;
- required env substitution: `${APP_VERSION}`;
- defaulted substitution: `${APP_NAME:Task Management App}`;
- optional style differs from HOCON and must be checked against Kora YAML docs before adding snippets;
- nested maps and lists map to typed interfaces/records;
- YAML examples should preserve indentation strictly.

### Skill assets to create later

- `assets/application.yaml.template`
- `assets/AppConfig.java.template`
- `assets/AppConfig.kt.template`
- `assets/ReusableConfig.java.template`
- `assets/ReusableConfig.kt.template`
- optional script: validate presence of `YamlConfigModule` and `application.yaml`.

### Validation checklist

- `./gradlew clean classes`
- run app with required env value set.
- verify resolved values from startup component or smoke test.

### Sources

- `mkdocs/docs/en/documentation/config.md`
- `mkdocs/docs/en/guides/config-yaml.md`
- `examples/java/kora-java-config-yaml/`

## kora-json-core

### Назначение

Skill для базовой JSON serialization/deserialization: DTO records/data classes, `@Json`, readers/writers, field mapping, nullable fields.

### Use when

- создаются HTTP request/response DTO;
- нужен JSON mapper для internal/external API;
- нужно добавить `json-module`;
- compile fails because JSON mapper is missing;
- нужно сделать custom `JsonReader`/`JsonWriter`.

### Dependencies and modules

Gradle:

```groovy
dependencies {
    implementation "ru.tinkoff.kora:json-module"
}
```

Application:

```java

@KoraApp
public interface Application extends JsonModule {
}
```

### Must cover

- `@Json` generates reader and writer.
- `@JsonReader` for input-only DTO.
- `@JsonWriter` for output-only DTO.
- `@JsonField` for wire name.
- `@JsonSkip` for ignored fields.
- `@JsonInclude` for null/empty policy.
- enum serialization requires `@Json`.
- custom mapper factories in modules.

### Sources

- `mkdocs/docs/en/documentation/json.md`
- `mkdocs/docs/en/guides/json.md`
- `examples/java/kora-java-validation/`
- `guides/java/kora-java-guide-json-app/`

## kora-http-server-core

### Назначение

Skill для code-first HTTP server basics: Undertow module, controllers, routes, path/query/header/cookie params, JSON request/response, basic errors.

### Use when

- нужно создать REST endpoint without OpenAPI contract;
- нужно объяснить `@HttpController` / `@HttpRoute`;
- нужно добавить `http-server-undertow`;
- нужно обработать request params/body;
- нужно вернуть JSON response or status error.

### Prefer another skill when

- есть OpenAPI specification: use `kora-openapi-server`;
- нужны interceptors/auth/error mappers/Undertow tuning: use `kora-http-server-advanced`;
- задача только про DTO JSON: use `kora-json-core`.

### Dependencies and modules

Gradle:

```groovy
dependencies {
    implementation "ru.tinkoff.kora:http-server-undertow"
    implementation "ru.tinkoff.kora:json-module"
    implementation "ru.tinkoff.kora:config-hocon"
    implementation "ru.tinkoff.kora:logging-logback"
}
```

Application:

```java

@KoraApp
public interface Application extends
    HoconConfigModule,
    JsonModule,
    LogbackModule,
    UndertowHttpServerModule {
}
```

### Must cover

- `@Component` + `@HttpController`.
- `@HttpRoute(method = HttpMethod.GET, path = "/...")`.
- `@Path`, `@Query`, `@Header`, `@Cookie`.
- `@Nullable` for optional params.
- `@Json` on method/request/response as required by Kora docs/examples.
- `HttpServerResponseException.of(status, message)`.
- `HttpServerResponse` for custom raw response.
- `HttpResponseEntity<T>` for status/headers/body.
- basic `application.conf` ports and logging.

### Sources

- `mkdocs/docs/en/documentation/http-server.md`
- `mkdocs/docs/en/guides/http-server.md`
- `mkdocs/docs/en/guides/getting-started.md`
- `examples/java/kora-java-http-server/`
- `guides/java/kora-java-guide-http-server-app/`

## Следующие skills после первой итерации

После проверки базовой структуры стоит детализировать следующие группы:

### HTTP/OpenAPI group

- `kora-http-server-advanced`: interceptors, exception handlers, custom mappers, Undertow config, auth patterns.
- `kora-http-client-core`: declarative clients, request/response mapping, client config.
- `kora-http-client-advanced`: interceptors, error handling, resilience composition.
- `kora-openapi-server`: generator config, delegates, generated routes, contract-first boundaries.
- `kora-openapi-client`: generated clients, validation, HTTP client integration.
- `kora-openapi-management`: Swagger/OpenAPI management endpoints.

### Database group

- `kora-database-common`: shared concepts, transactions, repository annotation catalog.
- `kora-database-jdbc`: `database-jdbc`, `@Repository`, `@Query`, `@Column`, mapping records.
- `kora-database-jdbc-advanced`: transactions, batch, generated queries, integration tests.
- `kora-database-migration`: Flyway and Liquibase.
- `kora-database-cassandra`

### Observability group

- `kora-logging-slf4j`
- `kora-logging-aspect`
- `kora-metrics`
- `kora-tracing`
- `kora-probes`
- `kora-observability-composition`

### Testing group

- `kora-junit5`: `@KoraAppTest`, graph modification basics.
- `kora-testing-component`: component-level tests.
- `kora-testing-integration`: Testcontainers, DB, HTTP app tests.
- `kora-testing-blackbox`: containerized app tests.

### Enterprise/integration group

- `kora-kafka`
- `kora-grpc-server`
- `kora-grpc-client`
- `kora-s3-client`
- `kora-cache-core`
- `kora-cache-caffeine`
- `kora-cache-redis`
- `kora-resilient`
- `kora-scheduling-jdk`
- `kora-scheduling-quartz`
- `kora-soap-client`
- `kora-mapstruct`
- `kora-container`
- `kora-camunda7-bpmn`
- `kora-camunda7-rest`
- `kora-camunda8-worker`

## Формат будущего SKILL.md

Каждый `SKILL.md` должен придерживаться единого шаблона:

```markdown
---
name: kora-...
description: ...
---

# Title

## Purpose

## Use When

## Do Not Use When

## Read First

## Dependencies

## Kora Modules

## Key Annotations and Interfaces

## Minimal Working Path

## Common Patterns

## Common Pitfalls

## Validation

## Assets

## References
```

Для больших skills допустимы отдельные `references/*.md`, но `SKILL.md` должен оставаться быстрым entry point, а не полной копией документации.

## Definition of done для каждого skill

- Есть точные triggers в frontmatter.
- Есть ссылки на docs/guides/examples.
- Есть Gradle dependencies.
- Есть Kora module/interface for `@KoraApp`.
- Есть key annotations/interfaces/classes.
- Есть короткий happy path.
- Есть pitfalls и compile-time troubleshooting.
- Есть validation checklist.
- Если skill генерирует файлы, есть assets/templates.
- Если skill меняет build/application graph, есть команда `./gradlew clean classes`.
