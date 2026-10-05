# Core Modules Reference

The Kora 2.0 modules almost every service needs: configuration, JSON, and logging — plus the minimal
build and `@KoraApp` that tie them together.

## Contents

- [Required modules](#required-modules)
- [Configuration modules](#configuration-modules)
- [Config sections that changed in 2.0](#config-sections-that-changed-in-20)
- [Logging](#logging)
- [JSON](#json)
- [Minimal build](#minimal-build)
- [Application interface](#application-interface)

---

## Required modules

| Artifact | Module interface | When |
|---|---|---|
| `io.koraframework:config-hocon` | `HoconConfigModule` | Always (or `config-yaml`) |
| `io.koraframework:json-common` | `JsonModule` | DTOs, HTTP, Kafka |
| `io.koraframework:logging-logback` | `LogbackModule` | Always |

The artifact for JSON is `json-common`; `json-module` does not exist in 2.0.

---

## Configuration modules

### HOCON (recommended)

```groovy
implementation "io.koraframework:config-hocon"
```

`src/main/resources/application.conf` — keys are not prefixed with `kora.`; each module reads its own
top-level section:

```hocon
httpServer {
  port = 8080
  telemetry.logging.enabled = true
  telemetry.metrics.enabled = true
}

httpServer.system {
  port = 8085
}

jdbc {
  jdbcUrl = ${POSTGRES_JDBC_URL}
  username = ${POSTGRES_USER}
  password = ${POSTGRES_PASS}
  maxPoolSize = 10
}

logging.levels {
  "root" = "WARN"
  "io.koraframework" = "INFO"
}
```

Substitution:

- Required: `jdbcUrl = ${POSTGRES_JDBC_URL}` — startup fails if the variable is unset.
- Optional: `password = ${?DB_PASS}` — the key is left absent when unset.
- Literal default with an optional override — declare the value, then the optional substitution on
  the next line:

  ```hocon
  maxPoolSize = 10
  maxPoolSize = ${?DB_MAX_POOL}
  ```

### YAML (alternative)

```groovy
implementation "io.koraframework:config-yaml"
```

`src/main/resources/application.yaml`:

```yaml
httpServer:
  port: 8080
  system:
    port: 8085
  telemetry:
    logging:
      enabled: true

jdbc:
  jdbcUrl: ${POSTGRES_JDBC_URL}
  username: ${POSTGRES_USER}
  password: ${?DB_PASS}
  maxPoolSize: ${DB_MAX_POOL:10}
```

YAML substitution: `${VAR}` required, `${?VAR}` optional, `${VAR:default}` with a default. Note the
default form has **no** `?`.

Pick one format. Typed config is declared with `@ConfigSource("path")` interfaces — see
[`kora-config-hocon`](../../kora-config-hocon/SKILL.md).

---

## Config sections that changed in 2.0

These rename silently: the build stays green and the failure appears at startup.

| 1.x key | 2.0 key | What a stale key does |
|---|---|---|
| `httpServer.publicApiHttpPort` | `httpServer.port` | Ignored — the public server starts on the `8080` default |
| `httpServer.privateApiHttpPort` | `httpServer.system.port` | Ignored. `SystemHttpServerConfig` **overrides** `port()` to `8085`, so the system server starts on `8085` — not on the port you configured |
| `httpServer.privateApiHttpReadinessPath` / `…LivenessPath` / `…MetricsPath` | `httpServer.system.readinessPath` / `livenessPath` / `metricsPath` | Defaults `/system/readiness`, `/system/liveness`, `/metrics` are used instead |
| `db { … }` | `jdbc { … }` | `ConfigValueException: Config expected value, but got null at path: 'ROOT.jdbc.username'` |
| `openapi.management.file` | `openapi.management.files` (a list) | The endpoint serves an empty spec |

**Why the port rows are the dangerous ones.** Kora does not reject unrecognised config keys — no
schema check exists in `config-common` or `config-hocon`, so a key nothing declares is simply never
read. A 1.x config carrying `publicApiHttpPort = 8081` / `privateApiHttpPort = 8086` therefore
produces **no error at all**: both keys are ignored, and each server falls back to its own default —
`HttpServerConfig.port()` = `8080` for the public server, and `SystemHttpServerConfig.port()`, which
**overrides** the inherited default, = `8085` for the system server. The service starts green on
`8080`/`8085` while probes, the Prometheus scrape and the load balancer are all pointed at
`8081`/`8086` and hit nothing.

Guidance claiming the system server falls back to `8080` and collides with the public one describes a
pre-release build; that default was fixed before the first release candidate. `Address already in use` happens only in
the narrower case where the *new* keys genuinely point two servers at one port.

Telemetry defaults also changed: `telemetry.metrics.enabled` and `telemetry.logging.enabled` default
to **`false`** in 2.0 (`telemetry.tracing.enabled` defaults to `true`). Adding `micrometer-module`
alone produces no `http_server_*` / `db_*` metrics — enable them per component.

HOCON embedded in test sources counts too: `KoraConfigModification.ofString("""…""")` blocks carry
the same keys and are missed by scanners that only look at `.conf` / `.yaml` files.

---

## Logging

```groovy
implementation "io.koraframework:logging-logback"
```

```java
@KoraApp
public interface Application extends LogbackModule { }
```

Logger names moved with the packages — `logging.levels` entries keyed on `ru.tinkoff.kora` no longer
match anything. Use `io.koraframework`.

---

## JSON

```groovy
implementation "io.koraframework:json-common"
```

`@Json` triggers compile-time generation of a reader and a writer:

```java
import org.jspecify.annotations.Nullable;
import io.koraframework.json.common.annotation.Json;

@Json
public record UserDto(
    String id,
    String name,
    String email,
    @Nullable String phone
) {}
```

Java nullability is JSpecify (`org.jspecify.annotations.Nullable`), which is a **type-use**
annotation — position matters (`List<@Nullable String>`, `String @Nullable []`). Kotlin expresses
nullability in the type (`String?`) and must not carry the Java annotations.

Sealed type with a discriminator:

```java
import io.koraframework.json.common.annotation.Json;
import io.koraframework.json.common.annotation.JsonDiscriminatorField;
import io.koraframework.json.common.annotation.JsonDiscriminatorValue;

@Json
@JsonDiscriminatorField("type")
public sealed interface PaymentResult {

    @JsonDiscriminatorValue("success")
    record Success(String id) implements PaymentResult {}

    @JsonDiscriminatorValue("error")
    record Error(String code, String message) implements PaymentResult {}
}
```

Two 2.0 changes that bite:

- The `*Unchecked` methods are gone and the plain ones no longer declare checked exceptions —
  `toStringUnchecked` → `toString`, `toByteArrayUnchecked` → `toByteArray`, `readUnchecked` → `read`.
  In Java a `try/catch (IOException)` around `toByteArray` becomes a compile error.
- `JsonReader<T>.read(data)` returns **nullable**; in Kotlin wrap it in `requireNotNull(...)`.

---

## Minimal build

### Java (build.gradle)

```groovy
plugins {
    id "java"
    id "application"
}

repositories {
    mavenCentral()
}

java {
    toolchain {
        languageVersion = JavaLanguageVersion.of(25)
        vendor = JvmVendorSpec.ADOPTIUM
    }
}

configurations {
    koraBom
    annotationProcessor.extendsFrom(koraBom)
    compileOnly.extendsFrom(koraBom)
    implementation.extendsFrom(koraBom)
}

dependencies {
    koraBom platform("io.koraframework:kora-bom:$koraVersion")
    annotationProcessor "io.koraframework:annotation-processors"

    implementation "io.koraframework:logging-logback"
    implementation "io.koraframework:config-hocon"
    implementation "io.koraframework:json-common"
}
```

### Kotlin (build.gradle.kts)

```kotlin
plugins {
    id("application")
    kotlin("jvm") version "2.4.20"
    id("com.google.devtools.ksp") version "2.3.12"
}

repositories {
    mavenCentral()
}

dependencies {
    implementation(platform("io.koraframework:kora-bom:${property("koraVersion")}"))
    ksp("io.koraframework:symbol-processors:${property("koraVersion")}")

    implementation("io.koraframework:logging-logback")
    implementation("io.koraframework:config-hocon")
    implementation("io.koraframework:json-common")
}

kotlin {
    jvmToolchain(25)
}
```

---

## Application interface

The `@KoraApp` interface lists capabilities by extending `*Module` interfaces. `@KoraApp` comes from
`io.koraframework.common.annotation` and the runner from `io.koraframework.application.graph`. The
processor generates `ApplicationGraph`.

```java
import io.koraframework.application.graph.KoraApplication;
import io.koraframework.common.annotation.KoraApp;
import io.koraframework.config.hocon.HoconConfigModule;
import io.koraframework.json.common.JsonModule;
import io.koraframework.logging.logback.LogbackModule;

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

```kotlin
import io.koraframework.application.graph.KoraApplication
import io.koraframework.common.annotation.KoraApp
import io.koraframework.config.hocon.HoconConfigModule
import io.koraframework.json.common.JsonModule
import io.koraframework.logging.logback.LogbackModule

@KoraApp
interface Application : HoconConfigModule, JsonModule, LogbackModule

fun main() {
    KoraApplication.run { ApplicationGraph.graph() }
}
```

Typed config injected as a component:

```java
import org.jspecify.annotations.Nullable;
import io.koraframework.config.common.annotation.ConfigSource;

@ConfigSource("app")
public interface AppConfig {
    String name();
    @Nullable String description();
    default int timeout() { return 30; }
}
```

`@ConfigSource` kept its name in 2.0. Its sibling for reusable/library config was renamed:
`@ConfigValueExtractor` → **`@ConfigMapper`**.

---

## See Also

- [SKILL.md](../SKILL.md) — quick start, module picking
- [artifact-catalog.md](artifact-catalog.md) — every published artifact
- [bom-usage-reference.md](bom-usage-reference.md) — BOM setup
- [annotation-processors-reference.md](annotation-processors-reference.md) — processors / KSP setup
- [`kora-config-hocon/SKILL.md`](../../kora-config-hocon/SKILL.md) — typed `@ConfigSource` config
- [`kora-http-server/SKILL.md`](../../kora-http-server/SKILL.md), [`kora-database-jdbc/SKILL.md`](../../kora-database-jdbc/SKILL.md), [`kora-kafka-producer/SKILL.md`](../../kora-kafka-producer/SKILL.md)
