# Kora Journal - PetClinic

Журнал непрерывного улучшения для проекта PetClinic на Kora Framework.

---

## Записи

### [2026-06-05] Ошибка #1: BOM import в Gradle 9

**Контекст:**
Настройка проекта petclinic-kora с использованием Kora Framework 1.2.15 и Gradle 9.0.

**Проблема:**
Неправильный импорт BOM (Bill of Materials) для зависимостей Kora. Использовался синтаксис `koraBom platform()` который не поддерживается в Gradle 9, а также `enforcedPlatform()` без указания версии.

**Ошибка:**
```
Could not find method koraBom() for arguments [ru.tinkoff.kora:kora-parent:1.2.15]
```

**Решение:**
Использовать стандартный синтаксис Gradle для импорта BOM:
```groovy
dependencies {
    implementation platform("ru.tinkoff.kora:kora-parent:$koraVersion")
    
    // Зависимости без явной версии - берутся из BOM
    implementation "ru.tinkoff.kora:application"
    implementation "ru.tinkoff.kora:config"
}
```

**Файлы:**
- `build.gradle`

**Урок:**
- В Gradle 9+ использовать `platform()` для импорта BOM
- Не указывать версию для зависимостей, которые управляются BOM
- Для annotation processor указывать версию явно

---

### [2026-06-05] Ошибка #2: Имена артефактов Kora

**Контекст:**
После исправления BOM импорта, сборка не может найти артефакты Kora.

**Проблема:**
Неправильные имена артефактов Kora. Использовались имена типа `ru.tinkoff.kora:application`, но в Maven Central артефакты имеют префиксы.

**Ошибка:**
```
Could not find ru.tinkoff.kora:application:1.2.15
Searched in:
  - https://repo.maven.apache.org/maven2/ru/tinkoff/kora/application/1.2.15/application-1.2.15.pom
```

**Решение:**
Kora Framework использует следующую схему именования артефактов:
- `application-graph` - базовый модуль приложения
- `config-hocon` - конфигурация HOCON
- `http-server-undertow` - HTTP сервер
- `jdbc` - JDBC модуль
- `json-jackson` - JSON сериализация
- и т.д.

Полный список артефактов доступен по адресу:
https://repo.maven.apache.org/maven2/ru/tinkoff/kora/

**Файлы:**
- `build.gradle`

**Урок:**
- Проверять имена артефактов в Maven Central перед использованием
- Kora использует декомпозированные имена модулей (не `application`, а `application-graph`)

---

### [2026-06-05] Ошибка #3: Jackson JSR310 модуль

**Контекст:**
Настройка зависимостей для JSON сериализации.

**Проблема:**
Артефакт `jackson-jsr310` не существует как отдельный модуль.

**Ошибка:**
```
Could not find com.fasterxml.jackson.core:jackson-jsr310:2.17.1
```

**Решение:**
JSR310 модуль является частью `jackson-datatype-jsr310`:
```groovy
implementation "com.fasterxml.jackson.datatype:jackson-datatype-jsr310:2.17.1"
```

**Файлы:**
- `build.gradle`

**Урок:**
- Jackson использует разные groupId для datatype модулей
- `jackson-datatype-jsr310` для поддержки Java 8 Date/Time API

---

### [2026-06-05] Ошибка #4: Неправильные имена модулей Kora

**Контекст:**
После исправления схемы именования артефактов, сборка продолжает падать.

**Проблема:**
Некоторые модули Kora имеют другие имена:
- `probes` → не существует как отдельный артефакт
- `application` → `application-graph`
- `http-server` → `http-server-common` + `http-server-undertow`
- `openapi` → `openapi-management`
- `json` → `json-module` + `json-common`
- `jdbc` → `database-jdbc`
- `repository-jdbc` → часть `database-jdbc`
- `telemetry` → `telemetry-common`
- `metrics-micrometer` → не найден
- `tracing-opentelemetry` → `opentelemetry-module`

**Решение:**
Использовать правильные имена артефактов из Kora BOM:
```groovy
// Config
implementation "ru.tinkoff.kora:config-common"
implementation "ru.tinkoff.kora:config-hocon"

// HTTP Server
implementation "ru.tinkoff.kora:http-server-common"
implementation "ru.tinkoff.kora:http-server-undertow"

// OpenAPI
implementation "ru.tinkoff.kora:openapi-management"

// JSON
implementation "ru.tinkoff.kora:json-common"
implementation "ru.tinkoff.kora:json-module"

// Database
implementation "ru.tinkoff.kora:database-common"
implementation "ru.tinkoff.kora:database-jdbc"
implementation "ru.tinkoff.kora:database-flyway"

// Validation
implementation "ru.tinkoff.kora:validation-common"
implementation "ru.tinkoff.kora:validation-module"

// Resilient
implementation "ru.tinkoff.kora:resilient-kora"

// Telemetry
implementation "ru.tinkoff.kora:telemetry-common"
implementation "ru.tinkoff.kora:opentelemetry-module"
```

**Файлы:**
- `build.gradle`

**Урок:**
- Проверять имена модулей в BOM файле перед использованием
- Kora использует префиксы для всех модулей
- Некоторые модули могут быть объединены или переименованы

---

## Summary

| Дата | Ошибка | Статус |
|------|--------|--------|
| 2026-06-05 | BOM import в Gradle 9 | ✅ Resolved |
| 2026-06-05 | Имена артефактов Kora | 🔄 In Progress |
| 2026-06-05 | Jackson JSR310 модуль | ✅ Resolved |
