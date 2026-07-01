---
name: kora-config-hocon
description: "HOCON configuration in Kora services via the config-hocon module and HoconConfigModule. Maps application.conf into type-safe interfaces with @ConfigSource (application config) and @ConfigValueExtractor (reusable/library config). Covers required vs @Nullable vs default-method values, environment substitution (${VAR}, ${?VAR}, default = ${?VAR} override), supported types (Duration, Period, Size, UUID, List/Set/Map, nested objects), injecting the raw Config with @Environment/@SystemProperties/@ApplicationConfig tags, and the config file watcher. Use when adding typed config to a Kora app, choosing @ConfigSource vs @ConfigValueExtractor, wiring credentials through env vars, or debugging \"config value not found\" graph build failures."
---

# Kora Config HOCON

**Artifact:** `ru.tinkoff.kora:config-hocon` | **Module:** `HoconConfigModule` | **Annotations package:** `ru.tinkoff.kora.config.common.annotation`

HOCON is the recommended config format for Kora. The `config-hocon` module maps `application.conf` into type-safe interfaces at compile time. Define a config interface, annotate it, and inject it as an ordinary graph dependency through the constructor. There is no field injection and no runtime reflection — the annotation processor generates the extractor.

## Quick Start

### 1. Dependencies (`build.gradle`)

```groovy
dependencies {
    koraBom platform("ru.tinkoff.kora:kora-parent:1.2.17")

    // MANDATORY — without the annotation processor nothing is generated
    annotationProcessor "ru.tinkoff.kora:annotation-processors"

    implementation "ru.tinkoff.kora:config-hocon"
    implementation "ru.tinkoff.kora:logging-logback"
}
```

Kotlin uses `ksp "ru.tinkoff.kora:symbol-processors"` instead of `annotationProcessor`. All `ru.tinkoff.kora:*` artifacts inherit their version from the `kora-parent` BOM — never version them individually.

### 2. Enable the module on `@KoraApp`

```java
package com.example.app;

import ru.tinkoff.kora.application.graph.KoraApplication;
import ru.tinkoff.kora.common.KoraApp;
import ru.tinkoff.kora.config.hocon.HoconConfigModule;
import ru.tinkoff.kora.logging.logback.LogbackModule;

@KoraApp
public interface Application extends
        HoconConfigModule,
        LogbackModule {

    static void main(String[] args) {
        KoraApplication.run(ApplicationGraph::graph);
    }
}
```

### 3. Config file `src/main/resources/application.conf`

```hocon
app {
  name = "Task Management App"
  name = ${?APP_NAME}          # optional override: only applied if APP_NAME is set
  version = ${APP_VERSION}     # required: startup fails if APP_VERSION is missing
  environment = "development"
}
```

### 4. Typed config interface with `@ConfigSource`

```java
package com.example.app;

import ru.tinkoff.kora.config.common.annotation.ConfigSource;

@ConfigSource("app")
public interface AppConfig {

    String name();

    String version();

    String environment();
}
```

`@ConfigSource("app")` binds the `app` section and registers `AppConfig` as a graph component.

### 5. Inject the config through the constructor

```java
package com.example.app;

import ru.tinkoff.kora.common.Component;

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

## `@ConfigSource` vs `@ConfigValueExtractor`

These are the two mapping styles. Pick by ownership of the config path.

| | `@ConfigSource("path")` | `@ConfigValueExtractor` |
|---|---|---|
| **Binds a fixed config path** | Yes — `path` is hard-coded | No — the path is chosen at extraction time |
| **Registered as a graph component** | Yes, inject directly | No, it only generates a `ConfigValueExtractor<T>` |
| **Use for** | one stable application section | a reusable shape mapped to several paths / library config |
| **Use as a nested type** | No | Yes — nested objects inside a config interface |

Rule of thumb: top-level config interface that maps one stable section → `@ConfigSource`. A shape reused at multiple paths, or a nested object/list element type → `@ConfigValueExtractor`.

### Nested objects must use `@ConfigValueExtractor`

A nested interface that represents a sub-object (or list element) is **not** annotated with `@ConfigSource` — it is annotated with `@ConfigValueExtractor`. Only the outer interface that owns a fixed path carries `@ConfigSource`.

```java
@ConfigSource("foo")
public interface FooConfig {

    String someString();

    BarConfig bar();          // mapped sub-object
    List<BarConfig> bars();   // mapped list of sub-objects

    @ConfigValueExtractor
    interface BarConfig {
        String someBarString();
        BazConfig baz();

        @ConfigValueExtractor
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

See [references/config-source-reference.md](references/config-source-reference.md) for the reusable-shape pattern (extracting one `@ConfigValueExtractor` type at two paths via `@Tag` and `ConfigValueExtractor.extract(config.get(path))`).

---

## Required, optional, and default values

By default **every** config method is required (NotNull) — a missing value fails the graph build at startup. There is no `@DefaultValue` annotation in Kora; defaults are expressed with a Java `default` method.

```java
@ConfigSource("services.foo")
public interface FooServiceConfig {

    String bar();                 // required — fails fast if absent

    @Nullable
    String optionalBar();         // optional — null if absent

    default int baz() {           // default value when absent
        return 42;
    }
}
```

- **Required:** plain method. Any missing value aborts startup with a clear error.
- **Optional:** annotate with any `@Nullable` (`jakarta.annotation.Nullable`, `javax.annotation.Nullable`, or `org.jetbrains.annotations.Nullable`). In Kotlin use a nullable return type (`fun bar(): String?`).
- **Default:** a `default` method (Java) / method with a body (Kotlin). Used only when the value is absent from the config.

There is no auto-invoked `validate()` hook. To validate values, do it in a component that consumes the config (e.g. in its constructor) and throw if invalid.

---

## Environment variable substitution

Substitution is a HOCON feature resolved before mapping. Three forms:

```hocon
app {
  required  = ${APP_URL}           # required: missing var → startup fails
  optional  = ${?APP_URL}          # optional: missing var → key is omitted
  withDefault = 8080               # default-then-override pattern:
  withDefault = ${?APP_PORT}       #   keeps 8080 unless APP_PORT is set
}
```

The idiomatic "default then optional override" pattern assigns the literal first, then re-assigns with `${?VAR}` so the literal survives when the variable is unset. Externalize every credential and host this way. See [references/hocon-syntax-reference.md](references/hocon-syntax-reference.md) for value references and string concatenation.

---

## Supported value types

`@ConfigSource` / `@ConfigValueExtractor` map a broad set of types out of the box, including:

- Primitives and boxed: `boolean`, `int`, `long`, `double`, `float`, `short`
- `String`, `BigInteger`, `BigDecimal`, `UUID`, `Pattern`, `Properties`
- Time: `Duration` (`"250s"`), `Period` (`"1d"` or `1`), `LocalDate`, `LocalTime`, `LocalDateTime`, `OffsetTime`, `OffsetDateTime`
- `Size` — byte sizes like `1Mb` (decimal) / `1Mib` (binary); a bare number means bytes
- Any `enum` (matched by `toString()`)
- `List<T>`, `Set<T>`, `Map<K,V>`, `Either<A,B>` of the above
- Nested objects via `@ConfigValueExtractor`

A list/set may be written as an array `["v1","v2"]` or a comma string `"v1,v2"`. For the full list see [references/hocon-syntax-reference.md](references/hocon-syntax-reference.md).

Note: the size type is `ru.tinkoff.kora.config.common.Size`. There is no `DataSize` type in Kora.

---

## Injecting the raw `Config`

For a generic abstraction over the whole config you may inject `ru.tinkoff.kora.config.common.Config`. The resolved config layers environment variables, system properties, and the config file. Tags select a single layer:

| Tag | What you get |
|---|---|
| (no tag) | Full config: file + env vars + system properties |
| `@Environment` | Environment variables only |
| `@SystemProperties` | System properties only |
| `@ApplicationConfig` | Config file only |

```java
@Component
public final class FooService {
    public FooService(@Environment Config config) { /* ... */ }
}
```

Prefer typed `@ConfigSource` interfaces over the raw `Config`: injecting `Config` directly means any config change refreshes every component that depends on it.

---

## Config file resolution and the watcher

`HoconConfigModule` loads, in priority order:

1. `config.resource` system property (a file on the classpath), if set
2. `config.file` system property (a filesystem path), if set
3. `application.conf` from `resources`, if present
4. an empty config otherwise

`reference.conf` files (library defaults) are merged first, then `application.conf` is overlaid. This is the mechanism for selecting per-environment config files — point `config.resource`/`config.file` at the variant you want; there is no `config.environment` profile switch.

```bash
java -Dconfig.resource=application-prod.conf -jar app.jar
java -Dconfig.file=/etc/app/application.conf -jar app.jar
```

Kora watches the config file and rebuilds the affected part of the graph on change. Disable it with the `KORA_CONFIG_WATCHER_ENABLED` env var or the `kora.config.watcher.enabled` system property.

---

## Common pitfalls

| Symptom | Cause / fix |
|---|---|
| Startup fails: required config value not found | A non-`@Nullable`, non-`default` method has no value. Provide it, or mark `@Nullable` / add a `default`. |
| Nested config type not generated | Nested object interfaces need `@ConfigValueExtractor`, not `@ConfigSource`. |
| `${VAR}` aborts startup | Required substitution and the env var is unset. Use `${?VAR}` for optional or a `default`-then-override. |
| Nothing is generated at all | Missing `annotationProcessor "ru.tinkoff.kora:annotation-processors"` (Java) / `ksp "ru.tinkoff.kora:symbol-processors"` (Kotlin). |
| Config not loaded | `application.conf` not in `src/main/resources/`, or a `config.resource`/`config.file` override points elsewhere. |
| Expected a `@DefaultValue` / `DataSize` | Neither exists in Kora. Use a `default` method and `Size`. |

---

## References & assets

| File | Purpose |
|---|---|
| [references/config-source-reference.md](references/config-source-reference.md) | `@ConfigSource` vs `@ConfigValueExtractor`, reusable shapes, library config factories |
| [references/hocon-syntax-reference.md](references/hocon-syntax-reference.md) | HOCON syntax, substitution, includes, full supported-type list |
| [assets/application.conf.template](assets/application.conf.template) | Base HOCON config template |
| [assets/AppConfig.java.template](assets/AppConfig.java.template) | Typed `@ConfigSource` interface template |

## Related skills

- [kora-config-yaml](../kora-config-yaml/SKILL.md) — YAML alternative (`YamlConfigModule`)
- [kora-di-compile](../kora-di-compile/SKILL.md) — compile-time DI: `@KoraApp`, `@Component`, modules, `@Tag`
- [kora-di-runtime](../kora-di-runtime/SKILL.md) — `@Root`, `Lifecycle`, runtime graph

## Source of truth

- Documentation: [config.md](../../.kora-agent/kora-docs/mkdocs/docs/en/documentation/config.md)
- Guide: [config-hocon.md](../../.kora-agent/kora-docs/mkdocs/docs/en/guides/config-hocon.md)
- Example: [kora-java-config-hocon](../../.kora-agent/kora-examples/examples/java/kora-java-config-hocon)
