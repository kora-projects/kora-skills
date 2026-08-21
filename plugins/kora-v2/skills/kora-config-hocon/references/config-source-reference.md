# @ConfigSource and @ConfigValueExtractor Reference

Mapping HOCON (or YAML) sections into type-safe Kora config interfaces.

## Contents

- [Two mapping annotations](#two-mapping-annotations)
- [@ConfigSource: application config](#configsource-application-config)
- [@ConfigValueExtractor: reusable and library config](#configvalueextractor-reusable-and-library-config)
- [Reusing one shape at multiple paths with @Tag](#reusing-one-shape-at-multiple-paths-with-tag)
- [Required, optional, and default values](#required-optional-and-default-values)
- [Injecting the raw Config](#injecting-the-raw-config)

---

## Two mapping annotations

Both live in `ru.tinkoff.kora.config.common.annotation`.

- `@ConfigSource("path")` — binds a **fixed** config path and registers the resulting interface as a graph component. Inject it directly into constructors.
- `@ConfigValueExtractor` — generates a `ConfigValueExtractor<T>` for a **reusable** shape. It does not bind a path and is not a component on its own; you (or a library module) decide which path to extract it from. Also the required annotation for nested object types.

---

## @ConfigSource: application config

For one stable section that a component reads directly.

```java
package com.example.app;

import ru.tinkoff.kora.config.common.annotation.ConfigSource;

@ConfigSource("services.foo")
public interface FooServiceConfig {

    String bar();

    int baz();
}
```

```hocon
services {
  foo {
    bar = "SomeValue"
    baz = 10
  }
}
```

Inject it:

```java
import ru.tinkoff.kora.common.Component;

@Component
public final class FooService {

    private final FooServiceConfig config;

    public FooService(FooServiceConfig config) {
        this.config = config;
    }
}
```

### Nested objects use @ConfigValueExtractor

A nested interface representing a sub-object (or a list element) is annotated with `@ConfigValueExtractor`, never `@ConfigSource`. Only the outer, path-bound interface carries `@ConfigSource`.

```java
@ConfigSource("foo")
public interface FooConfig {

    String someString();

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

---

## @ConfigValueExtractor: reusable and library config

When the same structure appears at several paths, or a library wants to expose its own config without owning the path, declare the shape once with `@ConfigValueExtractor`.

```java
package com.example.app;

import java.time.Duration;
import ru.tinkoff.kora.config.common.annotation.ConfigValueExtractor;

@ConfigValueExtractor
public interface LibConfig {

    String endpoint();

    Duration requestTimeout();
}
```

A library provides its config by extracting from a known path in a module factory:

```java
import ru.tinkoff.kora.config.common.Config;
import ru.tinkoff.kora.config.common.extractor.ConfigValueExtractor;

public interface FooLibraryModule {

    default LibConfig fooLibraryConfig(Config config,
                                       ConfigValueExtractor<LibConfig> extractor) {
        return extractor.extract(config.get("library.foo"));
    }
}
```

`Config` is `ru.tinkoff.kora.config.common.Config`; the extractor is `ru.tinkoff.kora.config.common.extractor.ConfigValueExtractor<T>` — generated automatically for any `@ConfigValueExtractor` type.

---

## Reusing one shape at multiple paths with @Tag

To get two distinct instances of the same `@ConfigValueExtractor` type from two config branches, define `@Tag` marker classes and a factory method per branch on `@KoraApp`.

```java
package com.example.app;

import ru.tinkoff.kora.application.graph.KoraApplication;
import ru.tinkoff.kora.common.KoraApp;
import ru.tinkoff.kora.common.Tag;
import ru.tinkoff.kora.config.common.Config;
import ru.tinkoff.kora.config.common.extractor.ConfigValueExtractor;
import ru.tinkoff.kora.config.hocon.HoconConfigModule;
import ru.tinkoff.kora.logging.logback.LogbackModule;

@KoraApp
public interface Application extends HoconConfigModule, LogbackModule {

    final class Lib1Tag { private Lib1Tag() {} }
    final class Lib2Tag { private Lib2Tag() {} }

    @Tag(Lib1Tag.class)
    default LibConfig lib1Config(Config config, ConfigValueExtractor<LibConfig> extractor) {
        return extractor.extract(config.get("libs.lib1"));
    }

    @Tag(Lib2Tag.class)
    default LibConfig lib2Config(Config config, ConfigValueExtractor<LibConfig> extractor) {
        return extractor.extract(config.get("libs.lib2"));
    }

    static void main(String[] args) {
        KoraApplication.run(ApplicationGraph::graph);
    }
}
```

Consume the tagged instances:

```java
import ru.tinkoff.kora.common.Component;
import ru.tinkoff.kora.common.Tag;

@Component
public final class IntegrationService {

    public IntegrationService(
        @Tag(Application.Lib1Tag.class) LibConfig lib1,
        @Tag(Application.Lib2Tag.class) LibConfig lib2
    ) { /* ... */ }
}
```

HOCON lets you keep the two branches DRY by sharing one object and overriding a single field:

```hocon
common-lib = {
  endpoint = "https://integration.local/api"
  requestTimeout = 5s
}

libs.lib1 = ${common-lib}
libs.lib2 = ${common-lib}
libs.lib2.endpoint = "https://integration-2.local/api"
```

---

## Required, optional, and default values

Every method is **required** by default; a missing value aborts the graph build at startup. Kora has no `@DefaultValue` annotation — use a `default` method.

```java
@ConfigSource("services.foo")
public interface FooServiceConfig {

    String bar();                 // required

    @Nullable
    String optionalBar();         // optional → null if absent

    default int baz() {           // default if absent
        return 42;
    }
}
```

Any `@Nullable` works (`jakarta.annotation.Nullable`, `javax.annotation.Nullable`, `org.jetbrains.annotations.Nullable`). In Kotlin, a nullable return type marks optional and a method body provides a default:

```kotlin
@ConfigSource("services.foo")
interface FooServiceConfig {
    fun bar(): String
    fun optionalBar(): String?
    fun baz(): Int = 42
}
```

There is no auto-invoked validation hook. Validate by reading the config in a consuming component and throwing on invalid input.

---

## Injecting the raw Config

You may inject `ru.tinkoff.kora.config.common.Config` for a generic view of the merged configuration (file + environment variables + system properties). Tags scope it to one layer:

| Tag | Layer |
|---|---|
| (none) | file + env vars + system properties |
| `@Environment` | environment variables only |
| `@SystemProperties` | system properties only |
| `@ApplicationConfig` | config file only |

```java
import ru.tinkoff.kora.config.common.Config;
import ru.tinkoff.kora.common.Component;
import ru.tinkoff.kora.config.common.annotation.Environment;

@Component
public final class FooService {
    public FooService(@Environment Config config) { /* ... */ }
}
```

Prefer typed `@ConfigSource` interfaces: depending on the raw `Config` causes every dependent component to refresh whenever the config changes.

---

## Related

- [SKILL.md](../SKILL.md) — overview and quick start
- [hocon-syntax-reference.md](hocon-syntax-reference.md) — HOCON syntax and supported types
