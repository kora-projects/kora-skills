---
name: kora-config-hocon
description: "HOCON typed configuration in Kora 2.0 — @ConfigSource and @ConfigMapper interfaces bound to application.conf by HoconConfigModule (io.koraframework:config-hocon), custom ConfigValueMapper with @Mapping, env substitution, and the @ApplicationConfig/@EnvironmentConfig/@SystemPropertiesConfig layer tags. Use when adding typed config to a Kora service, porting @ConfigValueExtractor from Kora 1.x, or debugging \"Config expected value, but got null at path\"."
license: Apache-2.0
metadata:
  kora-version: "2.x"
---

# Kora Config HOCON

> **Kora sub-skill — obey the [kora-v2 meta rules](../../SKILL.md) on every task:** **R0** ground the workspace on Kora 2.0 refs before starting (framework source at tag `2.0.0.RC2` + `kora-examples` at `migration/2.0` + Kora 2.0 docs at koraframework.io/v2, which trail the source; 1.x `kora-docs` pages are never an authority) · **R1** read this sub-skill before writing code · **R2** Kora 2.0 APIs only — no Spring/Micronaut/Quarkus, no Kora 1.x APIs, no invented annotations or config keys · **R3** journal any incorrect Kora usage. Add comments/Javadoc only if asked.

| | |
|---|---|
| **Artifact** | `io.koraframework:config-hocon` (BOM `io.koraframework:kora-bom`) |
| **Module** | `HoconConfigModule` — `io.koraframework.config.hocon` |
| **Annotations** | `io.koraframework.config.common.annotation` — `@ConfigSource`, `@ConfigMapper`, `@ApplicationConfig`, `@EnvironmentConfig`, `@SystemPropertiesConfig` |
| **Runtime types** | `io.koraframework.config.common.{Config, ConfigValue, ConfigValuePath}`, `…config.common.mapper.ConfigValueMapper<T>`, `…config.common.exception.ConfigValueException` |

HOCON is the recommended config format for Kora. `config-hocon` maps `application.conf` into
type-safe interfaces **at compile time**: declare an interface, annotate it, inject it through a
constructor. No field injection and no runtime reflection — the annotation processor (Java) or KSP
(Kotlin) generates the mapper.

---

## Renamed in 2.0 — check this before touching ported 1.x code

| Kora 1.x | Kora 2.0 |
|---|---|
| `@ru.tinkoff.kora.config.common.annotation.ConfigValueExtractor` | **`@io.koraframework.config.common.annotation.ConfigMapper`** |
| `ru.tinkoff.kora.config.common.extractor.ConfigValueExtractor<T>` (runtime) | **`io.koraframework.config.common.mapper.ConfigValueMapper<T>`** |
| `extractor.extract(value)` | **`mapper.map(value)`** (`@Nullable`) / **`mapper.mapOrThrow(value)`** (throws) |
| `extractor.map(function)` (composition) | **`mapper.andThen(function)`** |
| package `config.common.extractor` | **removed** — no such package in 2.0 |
| `@Environment` | **`@EnvironmentConfig`** |
| `@SystemProperties` | **`@SystemPropertiesConfig`** |
| `@ApplicationConfig` | unchanged (same simple name, new package) |
| `ru.tinkoff.kora.common.util.Size` | `io.koraframework.common.util.Size` |
| `@ConfigSource("path")` | unchanged (same name and semantics, new package) |
| `ru.tinkoff.kora:config-hocon` | `io.koraframework:config-hocon` |

### The `ConfigMapper` / `ConfigValueMapper` trap

Two different things nearly collided on one name. In 2.0 they are distinct and must never be mixed:

- **`@ConfigMapper`** is an **annotation** on a config interface/record/class. It has no type
  parameter. Package `io.koraframework.config.common.annotation`.
- **`ConfigValueMapper<T>`** is the **runtime extraction contract** you inject, implement, or point
  `@Mapping` at. Package `io.koraframework.config.common.mapper`.

A migrated file that reads `ConfigMapper<LibConfig>` is broken — the annotation is not generic.
This happens because the automated rename pipeline renames `ConfigValueExtractor` → `ConfigMapper`
in both roles and only a second pass corrects the runtime one. Fix the type, not the import.

---

## Quick start

### 1. Dependencies

Kora 2.0 is published on Maven Central. Put `koraVersion=2.0.0.RC2` in `gradle.properties` and
resolve from `mavenCentral()` — no snapshot repository is involved.

Java (`build.gradle`):

```groovy
repositories { mavenCentral() }

configurations {
    koraBom
    annotationProcessor.extendsFrom(koraBom)
    compileOnly.extendsFrom(koraBom)
    implementation.extendsFrom(koraBom)
    testImplementation.extendsFrom(koraBom)
    testAnnotationProcessor.extendsFrom(koraBom)
}

dependencies {
    koraBom platform("io.koraframework:kora-bom:$koraVersion")

    // MANDATORY — without the annotation processor nothing is generated
    annotationProcessor "io.koraframework:annotation-processors"

    implementation "io.koraframework:config-hocon"
    implementation "io.koraframework:logging-logback"
}
```

Kotlin (`build.gradle.kts`):

```kotlin
plugins {
    id("org.jetbrains.kotlin.jvm")
    id("com.google.devtools.ksp")
}

repositories { mavenCentral() }

dependencies {
    implementation(platform("io.koraframework:kora-bom:${property("koraVersion")}"))
    ksp("io.koraframework:symbol-processors:${property("koraVersion")}")

    implementation("io.koraframework:config-hocon")
    implementation("io.koraframework:logging-logback")
}
```

Kora 2.0 targets a **JDK 25** toolchain. Every `io.koraframework:*` artifact takes its version from
the `kora-bom` platform — never pin one individually. The `ksp` configuration is the exception: it
does not inherit the platform, so it carries the version explicitly. There is no `kora-parent` BOM
in 2.0. `2.0.0-SNAPSHOT` is the development line on `master` and needs its own snapshot repository;
do not put it in a project unless that is deliberately what you want.

### 2. Enable the module on `@KoraApp`

```java
package com.example.app;

import io.koraframework.application.graph.KoraApplication;
import io.koraframework.common.annotation.KoraApp;
import io.koraframework.config.hocon.HoconConfigModule;
import io.koraframework.logging.logback.LogbackModule;

@KoraApp
public interface Application extends
        HoconConfigModule,
        LogbackModule {

    static void main(String[] args) {
        KoraApplication.run(ApplicationGraph::graph);
    }
}
```

```kotlin
@KoraApp
interface Application : HoconConfigModule, LogbackModule

fun main() {
    KoraApplication.run { ApplicationGraph.graph() }
}
```

### 3. Config file `src/main/resources/application.conf`

```hocon
app {
  name = "Task Management App"
  name = ${?APP_NAME}          # optional override: applied only if APP_NAME is set
  version = ${APP_VERSION}     # required: startup fails if APP_VERSION is missing
  environment = "development"
}
```

### 4. Typed config interface with `@ConfigSource`

```java
package com.example.app;

import io.koraframework.config.common.annotation.ConfigSource;

@ConfigSource("app")
public interface AppConfig {

    String name();

    String version();

    String environment();
}
```

```kotlin
@ConfigSource("app")
interface AppConfig {
    fun name(): String
    fun version(): String
    fun environment(): String
}
```

The processor generates two types next to `AppConfig`: `$AppConfig_ConfigValueMapper`
(the `ConfigValueMapper<AppConfig>` — the leading `$` is part of the generated name) and
`AppConfigModule`, a `@Module` whose single method is
`mapper.mapOrThrow(config.get("app"))`. **`@Module` interfaces generated in the same compilation
are discovered automatically** — do not add `AppConfigModule` to the `@KoraApp` `extends` list.
(A config interface compiled in a *different* Gradle module is a different story; see
[Config in a library module](#config-in-a-library-gradle-module).)

### 5. Inject it through the constructor

```java
import io.koraframework.common.annotation.Component;

@Component
public final class AppService {

    private final AppConfig config;

    public AppService(AppConfig config) {
        this.config = config;
    }

    public String describe() {
        return config.name() + " v" + config.version();
    }
}
```

---

## `@ConfigSource` vs `@ConfigMapper`

Both live in `io.koraframework.config.common.annotation`. Pick by who owns the config path.

| | `@ConfigSource("path")` | `@ConfigMapper` |
|---|---|---|
| **Binds a fixed config path** | Yes — `path` is hard-coded | No — the caller chooses the path |
| **Registered as a graph component** | Yes (via the generated `*Module`) — inject directly | No — it only generates a `ConfigValueMapper<T>` |
| **Use for** | one stable application section | a reusable shape mapped at several paths, or library config |
| **Use as a nested type** | No | Yes — nested objects and list element types |
| **Extra attribute** | — | `mapNullAsEmptyObject` (default `true`) |

Rule of thumb: a top-level interface that owns one stable section → `@ConfigSource`. A shape reused
at several paths, or a nested object / list element type → `@ConfigMapper`.

The framework's own config types are declared with `@ConfigMapper` (`HttpServerConfig`,
`TelemetryConfig`, …), which is exactly why they can be mounted under many different paths.

### Nested objects use `@ConfigMapper`

```java
@ConfigSource("foo")
public interface FooConfig {

    String someString();

    BarConfig bar();          // mapped sub-object
    List<BarConfig> bars();   // mapped list of sub-objects

    @ConfigMapper
    interface BarConfig {
        String someBarString();
        BazConfig baz();

        @ConfigMapper
        interface BazConfig {
            String someBazString();
        }
    }
}
```

```hocon
foo {
  someString = "value"
  bar = { someBarString = "s", baz.someBazString = "s" }
  bars = [
    { someBarString = "s1", baz.someBazString = "s1" },
    { someBarString = "s2", baz.someBazString = "s2" }
  ]
}
```

`mapNullAsEmptyObject = true` (the default) means an absent section is mapped as an **empty
object**, so a shape whose fields are all optional or defaulted still yields an instance. Set
`@ConfigMapper(mapNullAsEmptyObject = false)` when an absent section must map to `null` instead.

See [references/config-source-reference.md](references/config-source-reference.md) for the
reusable-shape pattern (one `@ConfigMapper` type bound at two paths via `@Tag`).

---

## Required, optional, and default values

Every config method is **required** by default — a missing value aborts the graph build at startup.
There is no `@DefaultValue` annotation in Kora; a default is a method with a body.

```java
import org.jspecify.annotations.Nullable;

@ConfigSource("services.foo")
public interface FooServiceConfig {

    String bar();                 // required — fails fast if absent

    @Nullable
    String optionalBar();         // optional — null if absent

    default int baz() {           // default when absent
        return 42;
    }
}
```

```kotlin
@ConfigSource("services.foo")
interface FooServiceConfig {
    fun bar(): String
    fun optionalBar(): String?
    fun baz(): Int = 42
}
```

- **Required:** a plain abstract method. A missing value throws
  `ConfigValueException: Config expected value, but got null at path: 'ROOT.services.foo.bar' for origin '…'`.
- **Optional (Java):** `org.jspecify.annotations.Nullable`. It is a **type-use** annotation, so it
  goes on the return *type* (`@Nullable String optionalBar();`). Do not carry
  `jakarta`/`javax`/`org.jetbrains` nullability annotations into new 2.0 code.
- **Optional (Kotlin):** a nullable return type (`String?`). Never `@field:Nullable`.
- **Default:** `default` method (Java) / method or property with a body (Kotlin). Kotlin data-class
  config also honours constructor default parameter values.
- `Optional<T>` is supported as a field type and yields `Optional.empty()` when absent.

Interfaces, Java `record`s, Kotlin `data class`es and JavaBean-style classes with a public no-arg
constructor plus `equals`/`hashCode` are all valid config targets.

### Validating config with `@Valid`

Adding `io.koraframework.validation.common.annotation.Valid` to a `@ConfigSource` /
`@ConfigMapper` type makes the generated mapper take a `Validator<T>` and call
`validateAndThrow(...)` right after parsing, so an invalid value fails at graph build. It requires
the validation module and processor — see [kora-aop-validation](../kora-aop-validation/SKILL.md).

---

## Relaxed key names

A field is looked up under its declared name first, then under kebab-case and snake_case variants
derived from it. `relaxedKey()` matches `relaxedKey`, `relaxed-key` **and** `relaxed_key` in HOCON.
This is a lookup fallback, not a rename: the declared name always wins when both are present.

---

## Environment variable substitution

Substitution is a HOCON feature, resolved before mapping. It is unchanged in 2.0.

```hocon
app {
  required    = ${APP_URL}     # required: missing var → startup fails
  optional    = ${?APP_URL}    # optional: key is omitted when the var is unset
  withDefault = 8080           # default-then-override pattern:
  withDefault = ${?APP_PORT}   #   keeps 8080 unless APP_PORT is set
}
```

`${VAR}` and `${?VAR}` are the **only** two forms — HOCON has no inline default. A default is the
double assignment above: literal first, `${?VAR}` second, so the literal survives when the variable
is unset and the override wins when it is set. Externalize every credential and host this way.

`${VAR:default}` does **not** work in a `.conf` — typesafe-config resolves HOCON substitutions
before Kora's own resolver runs, and `:` is not part of a HOCON substitution. It works in YAML,
which reaches Kora's resolver directly, so a config ported from `.yaml` must have every
`${VAR:default}` rewritten as a double assignment. Shell-style `${VAR:-default}` works in neither.

See [references/hocon-syntax-reference.md](references/hocon-syntax-reference.md) for value
references, concatenation and includes.

---

## Supported value types

Mapped out of the box:

- `boolean`, `int`, `long`, `double`, `float` and their boxed forms, `double[]`
- `String`, `BigInteger`, `BigDecimal`, `UUID`, `Pattern`, `Properties`
- `Duration` (`"250s"`), `Duration[]`, `Period` (`"1d"` or `1`), `LocalDate`, `LocalTime`,
  `LocalDateTime`, `OffsetTime`, `OffsetDateTime`
- `io.koraframework.common.util.Size` — byte sizes like `1Mb` (SI) / `1Mib` (binary); a bare number
  is bytes. There is no `DataSize` type in Kora.
- any `enum`, matched by `toString()`
- `List<T>`, `Set<T>`, `Map<K,V>`, `Optional<T>`, `io.koraframework.common.Either<A,B>`
- nested objects and lists of objects via `@ConfigMapper`

A list or set may be written as an array `["v1","v2"]` or a comma string `"v1,v2"`. Full table in
[references/hocon-syntax-reference.md](references/hocon-syntax-reference.md).

### Mapping an unsupported type

Implement `ConfigValueMapper<T>`, register it as a `@Component`, and point the config method at it
with `io.koraframework.common.annotation.Mapping`:

```java
import io.koraframework.common.annotation.Component;
import io.koraframework.config.common.ConfigValue;
import io.koraframework.config.common.mapper.ConfigValueMapper;

@Component
public final class TokenConfigValueMapper implements ConfigValueMapper<Token> {

    @Override
    public Token map(ConfigValue<?> value) {
        if (value instanceof ConfigValue.NullValue) return null;
        var raw = value.asString();
        if (!raw.startsWith("Bearer ")) throw new IllegalArgumentException("Token must start with 'Bearer '");
        return new Token(raw.substring("Bearer ".length()));
    }
}
```

```java
@Mapping(TokenConfigValueMapper.class)
Token apiToken();
```

`map` returns `@Nullable`; `mapOrThrow` is the non-null wrapper that raises
`ConfigValueException.missingValueAfterParse`. Return `null` from `map` only for a `NullValue`
input — a non-nullable config method converts that `null` into a startup failure anyway.

---

## Injecting the raw `Config`

For a generic view over the whole configuration, inject `io.koraframework.config.common.Config`.
The resolved config merges environment variables, system properties and the config file; the tag
selects a single layer.

| Tag | What you get |
|---|---|
| (no tag) | Full config: env vars + system properties + config file |
| `@EnvironmentConfig` | Environment variables only |
| `@SystemPropertiesConfig` | System properties only |
| `@ApplicationConfig` | Config file only |

```java
import io.koraframework.common.annotation.Component;
import io.koraframework.config.common.Config;
import io.koraframework.config.common.annotation.EnvironmentConfig;

@Component
public final class FooService {
    public FooService(@EnvironmentConfig Config config) { /* ... */ }
}
```

Prefer typed `@ConfigSource` interfaces: depending on the raw `Config` makes every config change
refresh every component that depends on it.

---

## Config file resolution and the watcher

`HoconConfigModule` picks the application config origin like this:

1. `config.resource` system property — a file on the classpath
2. `config.file` system property — a filesystem path
3. neither set → `application.conf` from the classpath
4. the named resource does not exist → an empty config

Setting **both** `config.resource` and `config.file` is an error:
`Application config source is ambiguous: both 'config.file'=… and 'config.resource'=… are set`.
This is the mechanism for per-environment files — there is no `config.environment` profile switch.

```bash
java -Dconfig.resource=application-prod.conf -jar app.jar
java -Dconfig.file=/etc/app/application.conf -jar app.jar
```

Library `reference.conf` files are merged as a fallback, JVM `-D` overrides win over the file, and
the result is resolved once.

Kora watches the config file, plus every file it pulls in through a filesystem `include`, on a
virtual thread polling once a second, and refreshes the affected part of the graph only when a
tracked file's modification time or symlink target changed, or an included file was added or
removed (classpath and URL includes are not watched). Disable it with the `KORA_CONFIG_WATCHER_ENABLED` env var or
the `kora.config.watcher.enabled` system property set to `false`.

---

## Framework config keys that changed in 2.0

Writing `application.conf` is this skill's job, so these renames are yours to get right. All three
compile green and fail — or silently do nothing — at runtime.

```hocon
httpServer {                         # public server, module UndertowPublicHttpServerModule
  port = 8080                        # 1.x: publicApiHttpPort          (default 8080)
  telemetry.logging.enabled = true   # default false in 2.0
  telemetry.metrics.enabled = true   # default false in 2.0

  system {                           # system server, path httpServer.system
    port = 8085                      # 1.x: privateApiHttpPort         (default 8085)
    readinessPath = "/system/readiness"   # 1.x: privateApiHttpReadinessPath
    livenessPath  = "/system/liveness"    # 1.x: privateApiHttpLivenessPath
    metricsPath   = "/metrics"            # 1.x: privateApiHttpMetricsPath
  }
}

jdbc {                               # 1.x: db { … }
  jdbcUrl = ${POSTGRES_JDBC_URL}
  username = ${POSTGRES_USER}
  password = ${POSTGRES_PASS}
  telemetry.metrics.enabled = true
}
```

- **Ports.** The system server moved into its own `httpServer.system` section. The 1.x flat keys are
  not read any more, and an unknown HOCON key is ignored **without a warning**, so every server
  silently falls back to its default: `HttpServerConfig.port()` = `8080`,
  `SystemHttpServerConfig.port()` = `8085` (it overrides the inherited value), together with
  `readinessPath = /system/readiness`, `livenessPath = /system/liveness`, `metricsPath = /metrics`.
  A 1.x config that used non-default ports therefore starts cleanly on the wrong ports — probes and
  load balancers hit nothing — and a config whose two stale keys mapped onto one port fails with
  `Address already in use`. Neither failure names the stale key.
- **`db` → `jdbc`.** `JdbcDatabaseModule` wires the section name `jdbc`. A leftover `db` block
  produces `ConfigValueException: Config expected value, but got null at path: 'ROOT.jdbc.username'`
  — an error that names a section your file does not even contain.
- **Telemetry defaults flipped.** `TelemetryConfig.MetricsConfig.enabled()` and
  `LoggingConfig.enabled()` both return `false` in 2.0 (`tracing.enabled` stays `true`, except on
  the system server where it is `false`). Component metrics and logs simply never appear. Any
  config that is meant to demonstrate them must switch them on explicitly, per component.

---

## Config in tests

`io.koraframework.test.extension.junit5.KoraConfigModification` replaces the application config for
a `@KoraAppTest`, either from a resource file or from an inline HOCON block:

```java
@Override
public KoraConfigModification config() {
    return KoraConfigModification.ofResourceFile("application.conf")
        .withSystemProperty("APP_VERSION", "1.0.0-test");
}
```

`KoraConfigModification.ofString("""…""")` embeds HOCON **inside a Java/Kotlin source file**. Those
blocks carry the same keys as `application.conf` and are invisible to any scan that only looks at
`.conf`/`.yaml` — migrate and review them together with the resource files. See
[kora-testing-junit-java](../kora-testing-junit-java/SKILL.md) /
[kora-testing-junit-kotlin](../kora-testing-junit-kotlin/SKILL.md).

---

## Config in a library Gradle module

`@ConfigMapper` and `@ConfigSource` are compile-time annotations. A Gradle module that declares
config interfaces must run the processor **itself**:

- Java: `annotationProcessor "io.koraframework:annotation-processors"`
- Kotlin: the `com.google.devtools.ksp` plugin plus `ksp("io.koraframework:symbol-processors")`

Skip it and nothing is generated in the library. The consumer's build then fails on a *missing
generated `*Module`* — the error points at the application, not at the library that caused it.

Module auto-discovery only covers the compilation that produced the module. When `AppConfig` lives
in another Gradle module, the consuming `@KoraApp` must extend the generated `AppConfigModule`
explicitly (see [kora-di-compile](../kora-di-compile/SKILL.md) for multi-module wiring).

---

## Common pitfalls

| Symptom | Cause / fix |
|---|---|
| `Config expected value, but got null at path: 'ROOT.x.y'` | A non-`@Nullable`, non-default method has no value. Provide it, mark it `@Nullable`, or give it a default. Also fires when a whole section was renamed (`db` → `jdbc`). |
| `Config expected value with type 'StringValue' but received type '…'` | The HOCON value's shape does not match the declared return type. |
| `ConfigMapper<Foo>` does not compile | `@ConfigMapper` is the annotation; the generic runtime type is `ConfigValueMapper<Foo>` from `io.koraframework.config.common.mapper`. |
| `package io.koraframework.config.common.extractor does not exist` | That package was removed in 2.0. Mappers live in `…config.common.mapper`. |
| `cannot find symbol: method extract(…)` | `extract` → `map` (nullable) or `mapOrThrow` (throws). |
| Nested config type not generated | Nested object interfaces need `@ConfigMapper`, not `@ConfigSource`. |
| Nothing is generated at all | Missing `annotationProcessor "io.koraframework:annotation-processors"` (Java) / `ksp "io.koraframework:symbol-processors"` (Kotlin) — in *that* Gradle module. |
| `type annotation @Nullable is not expected here` | JSpecify `@Nullable` is type-use; place it on the return type. |
| Service listens on 8080/8085 instead of the configured ports, or dies with `Address already in use` | Stale `publicApiHttpPort` / `privateApiHttpPort` are ignored and the defaults apply. Use `httpServer.port` and `httpServer.system.port`. |
| Metrics endpoint answers 200 but shows no component metrics | `telemetry.metrics.enabled` defaults to `false` in 2.0; enable it per component. |
| `Application config source is ambiguous` | Both `config.resource` and `config.file` are set. Pick one. |
| Phantom `ru.tinkoff.kora` errors after a rename | Stale generated sources. Rebuild with `clean` and `--no-build-cache`; never edit `build/generated`. |
| Expected `@DefaultValue` / `DataSize` | Neither exists in Kora. Use a default method and `io.koraframework.common.util.Size`. |

---

## References & assets

| File | Purpose |
|---|---|
| [references/config-source-reference.md](references/config-source-reference.md) | `@ConfigSource` vs `@ConfigMapper`, reusable shapes with `@Tag`, library config factories, custom `ConfigValueMapper` |
| [references/hocon-syntax-reference.md](references/hocon-syntax-reference.md) | HOCON syntax, substitution, includes, full supported-type list, `Size` |
| [assets/application.conf.template](assets/application.conf.template) | Base HOCON config template with the 2.0 framework keys |
| [assets/AppConfig.java.template](assets/AppConfig.java.template) | Typed `@ConfigSource` interface template (Java) |
| [assets/AppConfig.kt.template](assets/AppConfig.kt.template) | Typed `@ConfigSource` interface template (Kotlin) |

## Related skills

- [kora-config-yaml](../kora-config-yaml/SKILL.md) — YAML alternative (`YamlConfigModule`)
- [kora-di-compile](../kora-di-compile/SKILL.md) — `@KoraApp`, `@Component`, modules, `@Tag`
- [kora-di-runtime](../kora-di-runtime/SKILL.md) — `@Root`, `Lifecycle`, graph refresh
- [kora-aop-validation](../kora-aop-validation/SKILL.md) — `@Valid` on config types
- [kora-telemetry-metrics](../kora-telemetry-metrics/SKILL.md) — the telemetry keys this skill writes

## Source of truth

Version-aligned authorities for Kora 2.0, highest first. The Kora 2.0 documentation
([Configuration](https://koraframework.io/v2/en/documentation/config/)) explains concepts but can
trail the framework — confirm every key, default and signature in the source below. The 1.x pages
(`ru.tinkoff.kora`) are never an authority for 2.0.

- Framework source, tag `2.0.0.RC2`:
  [config-common](https://github.com/kora-projects/kora/tree/2.0.0.RC2/config/config-common) ·
  [config-hocon](https://github.com/kora-projects/kora/tree/2.0.0.RC2/config/config-hocon)
- Migrated examples, branch `migration/2.0`:
  [kora-java-config-hocon](https://github.com/kora-projects/kora-examples/tree/migration/2.0/examples/java/kora-java-config-hocon) ·
  [kora-kotlin-config-hocon](https://github.com/kora-projects/kora-examples/tree/migration/2.0/examples/kotlin/kora-kotlin-config-hocon)
- Migrated guide apps, branch `migration/2.0`:
  [kora-java-guide-config-hocon-app](https://github.com/kora-projects/kora-examples/tree/migration/2.0/guides/java/kora-java-guide-config-hocon-app) ·
  [kora-kotlin-guide-config-hocon-app](https://github.com/kora-projects/kora-examples/tree/migration/2.0/guides/kotlin/kora-kotlin-guide-config-hocon-app)
