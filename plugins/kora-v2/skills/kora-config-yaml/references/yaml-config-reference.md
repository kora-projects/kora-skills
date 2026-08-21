# YAML Configuration Reference

Detailed reference for YAML configuration in Kora: `config-yaml` artifact,
`YamlConfigModule`, parsed by SnakeYAML and bound to type-safe interfaces with
`@ConfigSource` / `@ConfigValueExtractor`.

> HOCON is the recommended default format for new Kora projects. The binding API
> is identical; only the file syntax differs. See
> [kora-config-hocon](../../kora-config-hocon/SKILL.md).

## Contents

- [YAML syntax](#yaml-syntax)
- [Environment-variable substitution](#environment-variable-substitution)
- [Supported value types](#supported-value-types)
- [Binding styles: @ConfigSource vs @ConfigValueExtractor](#binding-styles)
- [Optional and default values](#optional-and-default-values)
- [Reusing one shape under multiple paths](#reusing-one-shape-under-multiple-paths)
- [File resolution and per-environment files](#file-resolution-and-per-environment-files)
- [Common pitfalls](#common-pitfalls)
- [Related](#related)

## YAML syntax

### Strings

```yaml
quoted: "my-app"
path: "/var/log/app.log"
unquoted: my-app

# multi-line, preserves line breaks
description: |
    Line 1
    Line 2

# folded, becomes a single line
summary: >
    This becomes
    one line
```

Quote any value containing `:` or `#`, otherwise YAML misreads it
(`url: "jdbc:postgresql://host/db"`, `password: "#secret"`).

### Numbers, booleans, null

```yaml
port: 8080
ratio: 0.75
enabled: true
value: null
```

### Objects and arrays

```yaml
server:
    host: localhost
    port: 8080
    ssl:
        enabled: true

hosts:                 # block style
    - host1
    - host2
ports: [8080, 8081]    # flow style
```

## Environment-variable substitution

Kora resolves substitutions before binding the file to interfaces.

```yaml
foo:
    valueRequired: ${ENV_VALUE_REQUIRED}            # required: startup fails if unset
    valueOptional: ${?ENV_VALUE_OPTIONAL}           # optional: key omitted if unset
    valueDefault: ${ENV_VALUE_DEFAULT:someDefault}  # literal default if unset
    valueRef: ${foo.valueRequired}-${foo.valueDefault}  # reference other config values
```

| Form | Meaning | Interface return type |
|------|---------|-----------------------|
| `${VAR}` | Required; resolution fails fast if the variable is missing | non-null |
| `${?VAR}` | Optional; the key is dropped when the variable is missing | `@Nullable` |
| `${VAR:default}` | Use the variable when set, otherwise the literal default | non-null |
| `${other.config.path}` | Self-reference to another resolved config value | matches target |

Self-references support inline composition, e.g.
`${foo.valueRequired}Other${foo.valueDefault}` builds one string from several parts.

## Supported value types

Kora binds YAML values to these types via the generated extractor:

| Category | Types |
|----------|-------|
| Text / scalars | `String`, `boolean`, `int`, `long`, `double`, `BigInteger`, `BigDecimal` |
| Identifiers / patterns | `UUID`, `Pattern`, enums |
| Date / time | `LocalDate`, `LocalTime`, `LocalDateTime`, `OffsetTime`, `OffsetDateTime`, `Duration`, `Period` |
| Collections | `List<T>`, `Set<T>`, `Map<String, ?>`, `Properties` |
| Nested objects | `@ConfigValueExtractor` interface, and `List<NestedConfig>` |

`Duration` accepts strings such as `"250s"`; `Period` accepts an int (`1`) or a
string (`"1d"`). A string list may be written either as an array
(`["v1", "v2"]`) or as a comma-separated string (`"v1,v2"`).

Example covering the full surface (adapted from
`.kora-agent/kora-examples/examples/java/kora-java-config-yaml`):

```yaml
foo:
    valueEnvRequired: ${ENV_VALUE_REQUIRED}
    valueEnvOptional: ${?ENV_VALUE_OPTIONAL}
    valueEnvDefault: ${ENV_VALUE_DEFAULT:someDefaultValue}
    valueString: "SomeString"
    valueRef: ${foo.valueString}Other${foo.valueString}
    valueUuid: "20684ccb-81f8-4fac-8ec0-297b08ff993d"
    valueDuration: "250s"
    valuePeriodAsString: "1d"
    valueListAsString: "v1,v2"
    valueListAsArray: ["v1", "v2"]
    valueMap:
        k1: "v1"
        k2: "v2"
    bar:
        someBarString: "someString"
        baz:
            someBazString: "someString"
    bars:
        - someBarString: "someString1"
          baz:
              someBazString: "someString1"
```

```java
import jakarta.annotation.Nullable;
import java.time.Duration;
import java.time.Period;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import ru.tinkoff.kora.config.common.annotation.ConfigSource;
import ru.tinkoff.kora.config.common.annotation.ConfigValueExtractor;

@ConfigSource("foo")
public interface FooConfig {

    String valueEnvRequired();

    @Nullable
    String valueEnvOptional();

    String valueEnvDefault();

    String valueString();

    String valueRef();

    UUID valueUuid();

    Duration valueDuration();

    Period valuePeriodAsString();

    List<String> valueListAsString();

    List<String> valueListAsArray();

    Map<String, String> valueMap();

    BarConfig bar();

    List<BarConfig> bars();

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

## Binding styles

| Annotation | Use for | How it binds |
|------------|---------|--------------|
| `@ConfigSource("path")` | One fixed section that becomes a graph component | Auto-registers a component bound to that exact path |
| `@ConfigValueExtractor` | A reusable shape used at multiple paths or nested inside another config | Generates an extractor; for top-level reuse you call `extractor.extract(config.get("path"))` inside a factory method |

`@ConfigSource("app")`:

```java
@ConfigSource("app")
public interface AppConfig {
    String name();
    String version();
    String environment();
}
```

```yaml
app:
    name: "my-app"
    version: "1.0.0"
    environment: "development"
```

## Optional and default values

Kora has no `@DefaultValue` annotation. Express optional/default values in code:

```java
import jakarta.annotation.Nullable;
import ru.tinkoff.kora.config.common.annotation.ConfigSource;

@ConfigSource("services.foo")
public interface FooServiceConfig {

    String bar();              // required

    @Nullable
    String note();             // optional, pairs with ${?VAR}; null when missing

    default int baz() {        // default via method body
        return 42;
    }
}
```

Any `@Nullable` annotation works (`jakarta.annotation.Nullable`,
`javax.annotation.Nullable`, `org.jetbrains.annotations.Nullable`). In Kotlin use a
nullable return type (`fun note(): String?`) and a default method body for defaults.

## Reusing one shape under multiple paths

When the same config structure appears at several paths, declare it once with
`@ConfigValueExtractor` and produce distinct tagged instances from factory methods
on the `@KoraApp` interface (pattern from
`.kora-agent/kora-examples/guides/java/kora-java-guide-config-yaml-app`).

```yaml
commonLib:
    endpoint: "https://integration.local/api"
    requestTimeout: "5s"

libs:
    lib1:
        endpoint: ${commonLib.endpoint}
        requestTimeout: ${commonLib.requestTimeout}
    lib2:
        endpoint: "https://integration-2.local/api"
        requestTimeout: ${commonLib.requestTimeout}
```

```java
import java.time.Duration;
import ru.tinkoff.kora.config.common.annotation.ConfigValueExtractor;

@ConfigValueExtractor
public interface LibConfig {
    String endpoint();
    Duration requestTimeout();
}
```

```java
import ru.tinkoff.kora.common.KoraApp;
import ru.tinkoff.kora.common.Tag;
import ru.tinkoff.kora.config.common.Config;
import ru.tinkoff.kora.config.common.extractor.ConfigValueExtractor;
import ru.tinkoff.kora.config.yaml.YamlConfigModule;
import ru.tinkoff.kora.logging.logback.LogbackModule;

@KoraApp
public interface Application extends YamlConfigModule, LogbackModule {

    final class Lib1Tag {
        private Lib1Tag() {}
    }

    final class Lib2Tag {
        private Lib2Tag() {}
    }

    @Tag(Lib1Tag.class)
    default LibConfig lib1Config(Config config, ConfigValueExtractor<LibConfig> extractor) {
        return extractor.extract(config.get("libs.lib1"));
    }

    @Tag(Lib2Tag.class)
    default LibConfig lib2Config(Config config, ConfigValueExtractor<LibConfig> extractor) {
        return extractor.extract(config.get("libs.lib2"));
    }
}
```

Consumers select the instance with the matching `@Tag`:

```java
public ConfigRunner(
        @Tag(Application.Lib1Tag.class) LibConfig lib1,
        @Tag(Application.Lib2Tag.class) LibConfig lib2) { /* ... */ }
```

`Config` is `ru.tinkoff.kora.config.common.Config`; the injected extractor is
`ru.tinkoff.kora.config.common.extractor.ConfigValueExtractor<T>`.

## File resolution and per-environment files

Kora merges all `reference.yaml` files (library defaults) first, then overlays the
application file. The application file is chosen in priority order:

1. `config.resource` system property — file from the classpath (`resources/`)
2. `config.file` system property — file from the filesystem
3. `application.yaml` from the classpath
4. an empty configuration if none of the above is present

There is no `config.environment` / profile mechanism. For per-environment setups,
create a complete alternative file (it replaces, not layers over, `application.yaml`)
and select it explicitly:

```yaml title="application-prod.yaml"
app:
    name: ${APP_NAME:Task Management App}
    version: ${APP_VERSION}
    environment: "production"
```

```bash
./gradlew run -Dconfig.resource=application-prod.yaml
```

## Common pitfalls

| Symptom | Cause / fix |
|---------|-------------|
| Startup fails with an unresolved substitution | A required `${VAR}` has no value — set it, or switch to `${VAR:default}` / `${?VAR}` |
| `@DefaultValue` does not compile | The annotation does not exist; use a `default` method body |
| Indentation / parse error | Use spaces only (no tabs); keep consistent 2-space indentation |
| Value containing `:` or `#` parses wrong | Quote it: `url: "jdbc:postgresql://..."`, `password: "#secret"` |
| Optional value throws on missing key | Add `@Nullable` and use `${?VAR}` |
| Config component not found in the graph | Annotation processor missing, or `@KoraApp` does not `extend YamlConfigModule` |
| Nested `@ConfigSource` with relative path is ignored | Nested types use `@ConfigValueExtractor`, exposed as a parent method |

## Related

- [SKILL.md](../SKILL.md) — overview and quick start
- [assets/README.md](../assets/README.md) — copy-paste templates
- [kora-config-hocon](../../kora-config-hocon/SKILL.md) — HOCON format (recommended default)
- Source doc: `.kora-agent/kora-docs/mkdocs/docs/en/documentation/config.md`
