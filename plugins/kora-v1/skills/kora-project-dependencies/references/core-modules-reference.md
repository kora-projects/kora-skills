# Core Modules Reference

The Kora modules almost every service needs: configuration, JSON, and logging.

## Contents

- [Required modules](#required-modules)
- [Configuration modules](#configuration-modules)
- [Logging](#logging)
- [JSON module](#json-module)
- [Minimal build](#minimal-build)
- [Application interface](#application-interface)

---

## Required modules

| Artifact | Module interface | When |
|----------|------------------|------|
| `ru.tinkoff.kora:config-hocon` | `HoconConfigModule` | Always (or `config-yaml`) |
| `ru.tinkoff.kora:json-module` | `JsonModule` | DTOs, HTTP, Kafka |
| `ru.tinkoff.kora:logging-logback` | `LogbackModule` | Always |

---

## Configuration modules

### HOCON (recommended)

```groovy
implementation "ru.tinkoff.kora:config-hocon"
```

`src/main/resources/application.conf` — note that config keys are not prefixed with `kora.`; modules read their own top-level sections (for example `httpServer`, `db`):

```hocon
httpServer {
  publicApiHttpPort = 8080
  privateApiHttpPort = 8085
}

db {
  jdbcUrl = ${?DB_URL}
  username = ${?DB_USER}
  password = ${?DB_PASS}
}
```

### YAML (alternative)

```groovy
implementation "ru.tinkoff.kora:config-yaml"
```

`src/main/resources/application.yaml`:

```yaml
httpServer:
  publicApiHttpPort: 8080
  privateApiHttpPort: 8085

db:
  jdbcUrl: ${DB_URL}
  username: ${DB_USER}
  password: ${DB_PASS}
```

Pick one format. HOCON is preferred for substitution, includes, and richer structure. Typed config is declared with `@ConfigSource("path")` interfaces (see `kora-config-hocon`).

---

## Logging

```groovy
implementation "ru.tinkoff.kora:logging-logback"
```

```java
@KoraApp
public interface Application extends LogbackModule { }
```

---

## JSON module

```groovy
implementation "ru.tinkoff.kora:json-module"
```

DTO — `@Json` triggers generation of a reader and writer:

```java
import jakarta.annotation.Nullable;
import ru.tinkoff.kora.json.common.annotation.Json;

@Json
public record UserDto(
    String id,
    String name,
    String email,
    @Nullable String phone   // optional field
) {}
```

Sealed type with a discriminator (`@JsonDiscriminatorField` on the parent, `@JsonDiscriminatorValue` on each subtype):

```java
import ru.tinkoff.kora.json.common.annotation.Json;
import ru.tinkoff.kora.json.common.annotation.JsonDiscriminatorField;
import ru.tinkoff.kora.json.common.annotation.JsonDiscriminatorValue;

@Json
@JsonDiscriminatorField("type")
public sealed interface PaymentResult {

    @JsonDiscriminatorValue("success")
    record Success(String id) implements PaymentResult {}

    @JsonDiscriminatorValue("error")
    record Error(String code, String message) implements PaymentResult {}
}
```

---

## Minimal build

### Java (build.gradle)

```groovy
plugins {
    id "java"
    id "application"
}

java {
    toolchain {
        languageVersion = JavaLanguageVersion.of(21)
        vendor = JvmVendorSpec.ADOPTIUM
    }
}

configurations {
    koraBom
    annotationProcessor.extendsFrom(koraBom)
    implementation.extendsFrom(koraBom)
}

dependencies {
    koraBom platform("ru.tinkoff.kora:kora-parent:$koraVersion")
    annotationProcessor "ru.tinkoff.kora:annotation-processors"

    implementation "ru.tinkoff.kora:logging-logback"
    implementation "ru.tinkoff.kora:config-hocon"
    implementation "ru.tinkoff.kora:json-module"
}
```

### Kotlin (build.gradle.kts)

```kotlin
plugins {
    application
    kotlin("jvm") version "1.9.25"
    id("com.google.devtools.ksp") version "1.9.25-1.0.20"
}

val koraBom: Configuration by configurations.creating
configurations {
    ksp.get().extendsFrom(koraBom)
    implementation.get().extendsFrom(koraBom)
}

val koraVersion: String by project
dependencies {
    koraBom(platform("ru.tinkoff.kora:kora-parent:$koraVersion"))
    ksp("ru.tinkoff.kora:symbol-processors")

    implementation("ru.tinkoff.kora:logging-logback")
    implementation("ru.tinkoff.kora:config-hocon")
    implementation("ru.tinkoff.kora:json-module")
}

kotlin {
    jvmToolchain(21)
}
```

---

## Application interface

The `@KoraApp` interface lists capabilities by extending `*Module` interfaces. `@KoraApp` comes from `ru.tinkoff.kora.common` and the runner is `ru.tinkoff.kora.application.graph.KoraApplication`. The processor generates `ApplicationGraph`.

```java
import ru.tinkoff.kora.application.graph.KoraApplication;
import ru.tinkoff.kora.common.KoraApp;
import ru.tinkoff.kora.config.hocon.HoconConfigModule;
import ru.tinkoff.kora.json.module.JsonModule;
import ru.tinkoff.kora.logging.logback.LogbackModule;

@KoraApp
public interface Application extends
        HoconConfigModule,
        JsonModule,
        LogbackModule {

    static void main(String[] args) {
        KoraApplication.run(ApplicationGraph::graph);
    }
}
```

Typed config interface injected as a component:

```java
import jakarta.annotation.Nullable;
import ru.tinkoff.kora.config.common.annotation.ConfigSource;

@ConfigSource("app")
public interface AppConfig {
    String name();
    @Nullable String description();
    default int timeout() { return 30; }
}
```

---

## See Also

- [SKILL.md](../SKILL.md) — Quick start, module catalog
- [bom-usage-reference.md](bom-usage-reference.md) — BOM setup
- [annotation-processors-reference.md](annotation-processors-reference.md) — Processors / KSP setup
- [`kora-config-hocon/SKILL.md`](../../kora-config-hocon/SKILL.md) — typed `@ConfigSource` config
- [`kora-http-server/SKILL.md`](../../kora-http-server/SKILL.md), [`kora-database-jdbc/SKILL.md`](../../kora-database-jdbc/SKILL.md), [`kora-kafka-producer/SKILL.md`](../../kora-kafka-producer/SKILL.md)
