---
name: kora-config-yaml
description: "YAML configuration for Kora applications via the config-yaml artifact and YamlConfigModule. Binds application.yaml sections to type-safe interfaces with @ConfigSource and reusable shapes with @ConfigValueExtractor. Covers environment-variable substitution (${VAR}, ${?VAR}, ${VAR:default}), self-references, @Nullable optional values, default method bodies, and selecting files with config.resource/config.file. Use when a Kora service must read configuration from YAML instead of HOCON, when wiring @ConfigSource/@ConfigValueExtractor over an application.yaml, or when debugging unresolved YAML substitutions at startup."
---

# Kora Config YAML

YAML configuration for Kora, parsed by SnakeYAML and bound to type-safe Java/Kotlin
interfaces. HOCON is the recommended default for new Kora projects; use YAML when a
project requires it. The binding API (`@ConfigSource`, `@ConfigValueExtractor`,
`@Nullable`, `default` methods, env substitution) is identical for both formats —
only the file syntax differs.

## Quick Start

### 1. Dependency (`build.gradle`)

All Kora artifacts inherit their version from the `kora-parent` BOM; never pin a
version on an individual `ru.tinkoff.kora:*` dependency. The annotation processor is
mandatory — `@ConfigSource` generates a `*ConfigValueExtractor` at compile time and
nothing is bound without it.

```groovy
dependencies {
    koraBom platform("ru.tinkoff.kora:kora-parent:1.2.17")
    annotationProcessor "ru.tinkoff.kora:annotation-processors"

    implementation "ru.tinkoff.kora:config-yaml"
    implementation "ru.tinkoff.kora:logging-logback"
}
```

Kotlin uses KSP instead: `ksp "ru.tinkoff.kora:symbol-processors"`.

### 2. Enable the module

```java
import ru.tinkoff.kora.application.graph.KoraApplication;
import ru.tinkoff.kora.common.KoraApp;
import ru.tinkoff.kora.config.yaml.YamlConfigModule;
import ru.tinkoff.kora.logging.logback.LogbackModule;

@KoraApp
public interface Application extends YamlConfigModule, LogbackModule {

    static void main(String[] args) {
        KoraApplication.run(ApplicationGraph::graph);
    }
}
```

### 3. Config file (`src/main/resources/application.yaml`)

```yaml
app:
    name: ${APP_NAME:Task Management App}   # default if APP_NAME unset
    version: ${APP_VERSION}                  # required, fails fast if missing
    environment: "development"
```

### 4. Typed interface

`@ConfigSource("app")` registers the bound `AppConfig` as a graph component that any
constructor can request.

```java
import ru.tinkoff.kora.config.common.annotation.ConfigSource;

@ConfigSource("app")
public interface AppConfig {

    String name();

    String version();

    String environment();
}
```

### 5. Inject it

Configuration is a normal graph dependency — request it via the constructor.

```java
import ru.tinkoff.kora.common.Component;

@Component
public final class GreetingService {

    private final AppConfig config;

    public GreetingService(AppConfig config) {
        this.config = config;
    }
}
```

## What's in this skill

| File | Purpose |
|------|---------|
| [references/yaml-config-reference.md](references/yaml-config-reference.md) | YAML syntax, supported value types, substitution rules, file resolution, optional/default values, troubleshooting |
| [assets/README.md](assets/README.md) | Copy-paste `application.yaml` and `@ConfigSource` interface templates |

## When to use vs not

| Use YAML config when | Use HOCON ([kora-config-hocon](../kora-config-hocon/SKILL.md)) instead when |
|----------------------|-----------------------------------------------------------------------------|
| The project mandates YAML | Starting a new Kora service with no format constraint |
| Existing `application.yaml` files must be kept | You want string concatenation and the richer HOCON merge model |

Both formats use the same `@ConfigSource`/`@ConfigValueExtractor` API; switching is
a dependency swap (`config-yaml` ↔ `config-hocon`) plus the module interface.

## Core patterns

### Two binding styles

| Annotation | Use for | Behavior |
|------------|---------|----------|
| `@ConfigSource("path")` | One fixed section bound to a graph component | Auto-registers a component for that exact path |
| `@ConfigValueExtractor` | A reusable shape extracted from several paths | Generates an extractor; you call `extractor.extract(config.get("..."))` in a factory |

### Environment-variable substitution

Three forms, all resolved by Kora before binding:

```yaml
foo:
    valueRequired: ${ENV_VALUE_REQUIRED}            # required — startup fails if unset
    valueOptional: ${?ENV_VALUE_OPTIONAL}           # optional — key is omitted if unset
    valueDefault: ${ENV_VALUE_DEFAULT:someDefault}  # default literal used if unset
    valueRef: ${foo.valueRequired}-suffix           # reference another config value
```

`${?VAR}` requires a `@Nullable` return type because the value may be absent.

### Optional and default values (no `@DefaultValue` annotation exists)

Kora has no defaulting annotation. Express optional and default values in code:

```java
import jakarta.annotation.Nullable;

@ConfigSource("app")
public interface AppConfig {

    String name();                 // required

    @Nullable
    String description();          // optional — null when missing (use with ${?VAR})

    default int retries() {        // default value via method body
        return 3;
    }
}
```

Any `@Nullable` (`jakarta`, `javax`, JetBrains) works. In Kotlin, mark the return
type nullable (`fun description(): String?`) and use a default method body for
defaults.

### Nested objects via @ConfigValueExtractor

Nested config types are NOT nested `@ConfigSource` interfaces — the inner shape is
annotated `@ConfigValueExtractor` and exposed as a method on the parent:

```java
import ru.tinkoff.kora.config.common.annotation.ConfigSource;
import ru.tinkoff.kora.config.common.annotation.ConfigValueExtractor;
import java.time.Duration;

@ConfigSource("app")
public interface AppConfig {

    String name();

    PoolConfig pool();   // nested object

    @ConfigValueExtractor
    interface PoolConfig {

        int maxSize();

        Duration connectionTimeout();
    }
}
```

```yaml
app:
    name: "my-service"
    pool:
        maxSize: 20
        connectionTimeout: "30s"   # Duration parses ISO-like strings
```

### Reusing one shape under multiple paths

When the same shape appears more than once (e.g. two clients), bind it with
`@ConfigValueExtractor` and produce tagged instances from factory methods on the
`@KoraApp` interface. See [references/yaml-config-reference.md](references/yaml-config-reference.md#reusing-one-shape-under-multiple-paths)
for the full `@Tag` + `ConfigValueExtractor.extract(config.get(...))` pattern.

### Supported value types

Kora binds YAML to `String`, primitives and boxed numbers, `BigInteger`,
`BigDecimal`, `boolean`, `UUID`, `Pattern`, enums, `LocalDate`/`LocalTime`/
`LocalDateTime`/`OffsetTime`/`OffsetDateTime`, `Duration`, `Period`,
`List`/`Set`/`Map<String,?>`, `Properties`, and nested
`@ConfigValueExtractor` types (including lists of them). Full table in the
[reference](references/yaml-config-reference.md#supported-value-types).

## Selecting the config file

Kora merges all `reference.yaml` files (library defaults), then overlays the
application file. The application file is resolved in priority order:

1. `config.resource` system property — a file on the classpath (`resources/`)
2. `config.file` system property — a file on the filesystem
3. `application.yaml` on the classpath
4. an empty config if none of the above exists

There is no `config.environment` profile mechanism. For per-environment files,
create a complete alternative such as `application-prod.yaml` and select it
explicitly:

```bash
./gradlew run -Dconfig.resource=application-prod.yaml
```

The alternative file must be self-contained (it replaces, not layers over,
`application.yaml`).

## Common pitfalls

| Symptom | Cause / fix |
|---------|-------------|
| Startup fails: unresolved substitution | A `${VAR}` (required form) has no value. Provide the env var/system property, or switch to `${VAR:default}` / `${?VAR}` |
| `@DefaultValue` does not compile | That annotation does not exist in Kora — use a `default` method body |
| Nested `@ConfigSource` with relative path does nothing | Nested types use `@ConfigValueExtractor`, not a second `@ConfigSource` |
| YAML parse error | YAML is indentation-sensitive; use spaces only (no tabs), and quote values containing `:` or `#` |
| Optional value throws on missing key | Add `@Nullable` to the method (Kotlin: nullable return) and pair with `${?VAR}` |
| Config component "not found" in the graph | Annotation processor missing, or `@KoraApp` does not `extend YamlConfigModule` |
| Both `config-yaml` and `config-hocon` on the classpath | Use exactly one config format module |

## Related skills

- [kora-config-hocon](../kora-config-hocon/SKILL.md) — HOCON format (recommended default)
- [kora-di-compile](../kora-di-compile/SKILL.md) — how config components join the graph

## Source of truth

- Documentation: [.kora-agent/kora-docs/mkdocs/docs/en/documentation/config.md](../../.kora-agent/kora-docs/mkdocs/docs/en/documentation/config.md)
- Guide: [.kora-agent/kora-docs/mkdocs/docs/en/guides/config-yaml.md](../../.kora-agent/kora-docs/mkdocs/docs/en/guides/config-yaml.md)
- Example: `.kora-agent/kora-examples/examples/java/kora-java-config-yaml`
- Guide app: `.kora-agent/kora-examples/guides/java/kora-java-guide-config-yaml-app`
