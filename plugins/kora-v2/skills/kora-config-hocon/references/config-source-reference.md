# `@ConfigSource` and `@ConfigMapper` Reference

Mapping HOCON (or YAML) sections into type-safe Kora 2.0 config types.

## Contents

- [Three names you must keep apart](#three-names-you-must-keep-apart)
- [`@ConfigSource`: application config](#configsource-application-config)
- [`@ConfigMapper`: reusable and library config](#configmapper-reusable-and-library-config)
- [Reusing one shape at multiple paths with `@Tag`](#reusing-one-shape-at-multiple-paths-with-tag)
- [Supported config declarations](#supported-config-declarations)
- [Required, optional, and default values](#required-optional-and-default-values)
- [Custom `ConfigValueMapper` with `@Mapping`](#custom-configvaluemapper-with-mapping)
- [Validating config with `@Valid`](#validating-config-with-valid)
- [Injecting the raw `Config`](#injecting-the-raw-config)
- [Config in a library Gradle module](#config-in-a-library-gradle-module)
- [Porting a 1.x config module](#porting-a-1x-config-module)

---

## Three names you must keep apart

| Name | Kind | Package |
|---|---|---|
| `@ConfigSource("path")` | annotation, binds a fixed path | `io.koraframework.config.common.annotation` |
| `@ConfigMapper` | annotation, no path, **not generic** | `io.koraframework.config.common.annotation` |
| `ConfigValueMapper<T>` | runtime extraction contract | `io.koraframework.config.common.mapper` |

`@ConfigMapper` marks a type. `ConfigValueMapper<T>` is what the processor generates for that type
and what you inject, implement, or reference from `@Mapping`. Writing `ConfigMapper<T>` as a type
does not compile — it is the single most common breakage in code ported from Kora 1.x, where the
runtime contract was `ru.tinkoff.kora.config.common.extractor.ConfigValueExtractor<T>`.

`ConfigValueMapper<T>` has two extraction methods and one combinator:

```java
@Nullable T map(ConfigValue<?> value);          // null when the value is absent/null
        T mapOrThrow(ConfigValue<?> value);     // throws ConfigValueException.missingValueAfterParse
<U> ConfigValueMapper<U> andThen(Function<@Nullable T, U> function);
```

`mapOrThrow` is what the generated `@ConfigSource` module calls. `andThen` replaces the 1.x
combinator that was also called `map` — in 2.0 `map` extracts, it does not compose.

---

## `@ConfigSource`: application config

For one stable section that components read directly.

```java
package com.example.app;

import io.koraframework.config.common.annotation.ConfigSource;

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

```java
import io.koraframework.common.annotation.Component;

@Component
public final class FooService {

    private final FooServiceConfig config;

    public FooService(FooServiceConfig config) {
        this.config = config;
    }
}
```

### What gets generated

For `FooServiceConfig` the processor writes, in the same package:

| Generated type | Role |
|---|---|
| `$FooServiceConfig_ConfigValueMapper` | the `ConfigValueMapper<FooServiceConfig>` — the leading `$` is part of the generated name. It nests the `FooServiceConfig_Impl` record and, when any method has a default, a `FooServiceConfig_Defaults` holder |
| `FooServiceConfigModule` | a `@Module` with one method: `mapper.mapOrThrow(config.get("services.foo"))` |

`@Module` interfaces produced in the same compilation are picked up by `@KoraApp` automatically.
Do not list `FooServiceConfigModule` in the app's `extends` clause — do that only for config
compiled in another Gradle module.

A `@ConfigMapper` type generates only the `$*_ConfigValueMapper`; there is no `*Module` and no path.
A nested type carries its outer types in the prefix: `FooConfig.BarConfig` becomes
`$FooConfig_BarConfig_ConfigValueMapper`.

### Nested objects use `@ConfigMapper`

Only the outer, path-bound interface carries `@ConfigSource`.

```java
@ConfigSource("foo")
public interface FooConfig {

    String someString();

    BarConfig bar();
    List<BarConfig> bars();

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

---

## `@ConfigMapper`: reusable and library config

When the same structure appears at several paths, or a library exposes config without owning the
path, declare the shape once with `@ConfigMapper`.

```java
package com.example.app;

import java.time.Duration;
import io.koraframework.config.common.annotation.ConfigMapper;

@ConfigMapper
public interface LibConfig {

    String endpoint();

    Duration requestTimeout();
}
```

A library binds its own config by extracting from a known path in a module factory:

```java
import io.koraframework.config.common.Config;
import io.koraframework.config.common.mapper.ConfigValueMapper;

public interface FooLibraryModule {

    default LibConfig fooLibraryConfig(Config config, ConfigValueMapper<LibConfig> mapper) {
        return mapper.mapOrThrow(config.get("library.foo"));
    }
}
```

`ConfigValueMapper<LibConfig>` is resolved by the DI graph automatically for any type annotated
with `@ConfigMapper` or `@ConfigSource` — no explicit factory or registration is needed.

### `mapNullAsEmptyObject`

`@ConfigMapper` has one attribute, `mapNullAsEmptyObject`, default `true`:

- `true` — an absent section maps to an **empty object**, so a shape whose fields are all optional
  or defaulted still produces an instance. This is what makes framework config like
  `TelemetryConfig` work when nobody writes a `telemetry { … }` block.
- `false` — the mapper returns `null` for an absent section, so the caller can distinguish
  "not configured" from "configured with all defaults".

`@ConfigSource` types have no such switch; they always behave as `mapNullAsEmptyObject = true`.

---

## Reusing one shape at multiple paths with `@Tag`

Define `@Tag` marker classes and one factory method per branch on the `@KoraApp` interface.

```java
package com.example.app;

import io.koraframework.application.graph.KoraApplication;
import io.koraframework.common.annotation.KoraApp;
import io.koraframework.common.annotation.Tag;
import io.koraframework.config.common.Config;
import io.koraframework.config.common.mapper.ConfigValueMapper;
import io.koraframework.config.hocon.HoconConfigModule;
import io.koraframework.logging.logback.LogbackModule;

@KoraApp
public interface Application extends HoconConfigModule, LogbackModule {

    final class Lib1Tag { private Lib1Tag() {} }
    final class Lib2Tag { private Lib2Tag() {} }

    @Tag(Lib1Tag.class)
    default LibConfig lib1Config(Config config, ConfigValueMapper<LibConfig> mapper) {
        return mapper.mapOrThrow(config.get("libs.lib1"));
    }

    @Tag(Lib2Tag.class)
    default LibConfig lib2Config(Config config, ConfigValueMapper<LibConfig> mapper) {
        return mapper.mapOrThrow(config.get("libs.lib2"));
    }

    static void main(String[] args) {
        KoraApplication.run(ApplicationGraph::graph);
    }
}
```

```kotlin
@KoraApp
interface Application : HoconConfigModule, LogbackModule {

    class Lib1Tag private constructor()
    class Lib2Tag private constructor()

    @Tag(Lib1Tag::class)
    fun lib1Config(config: Config, mapper: ConfigValueMapper<LibConfig>): LibConfig =
        mapper.mapOrThrow(config.get("libs.lib1"))

    @Tag(Lib2Tag::class)
    fun lib2Config(config: Config, mapper: ConfigValueMapper<LibConfig>): LibConfig =
        mapper.mapOrThrow(config.get("libs.lib2"))
}

fun main() {
    KoraApplication.run(ApplicationGraph::graph)
}
```

Consume the tagged instances:

```java
import io.koraframework.common.annotation.Component;
import io.koraframework.common.annotation.Tag;

@Component
public final class IntegrationService {

    public IntegrationService(
        @Tag(Application.Lib1Tag.class) LibConfig lib1,
        @Tag(Application.Lib2Tag.class) LibConfig lib2
    ) { /* ... */ }
}
```

HOCON keeps the two branches DRY by sharing one object and overriding a single field:

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

## Supported config declarations

`@ConfigSource` / `@ConfigMapper` accept more than interfaces:

| Declaration | Rules |
|---|---|
| interface | abstract methods (and Kotlin `val` properties) are fields; a method with a body is a default; methods with parameters, `void`/`Unit` methods and generic methods must be `default`/non-abstract |
| Java `record` | every record component is a field; there are no defaults |
| Kotlin `data class` | every primary-constructor parameter is a field; a parameter default value is the field default |
| JavaBean-style class | needs a public no-arg constructor (or a constructor covering the fields), getters/setters, **and** `equals`/`hashCode` |

An abstract class is rejected: *"Config classes must be instantiable, but this class is abstract."*
A class without `equals`/`hashCode` is rejected too — the generated mapper compares parsed values
against defaults.

---

## Required, optional, and default values

Every field is **required** by default; a missing value aborts the graph build with
`ConfigValueException: Config expected value, but got null at path: '…'`. Kora has no
`@DefaultValue` annotation — a default is a method with a body.

```java
import org.jspecify.annotations.Nullable;

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

```kotlin
@ConfigSource("services.foo")
interface FooServiceConfig {
    fun bar(): String
    fun optionalBar(): String?
    fun baz(): Int = 42
}
```

- **Java nullability is JSpecify**, `org.jspecify.annotations.Nullable`, and it is a **type-use**
  annotation: it belongs on the return type. A wrong position produces
  `error: type annotation @org.jspecify.annotations.Nullable is not expected here`.
- **Kotlin nullability is the type** (`String?`). Do not carry Java nullability annotations into
  Kotlin sources; `@field:Nullable` is not a valid target.
- `Optional<T>` is a supported field type and becomes `Optional.empty()` when the value is absent.
- A primitive field can never be null: absent + no default means the generated mapper throws.

---

## Custom `ConfigValueMapper` with `@Mapping`

To map a type the framework does not know, implement `ConfigValueMapper<T>`, publish it as a
`@Component`, and reference it from the config method with
`io.koraframework.common.annotation.Mapping`.

```java
package com.example.app;

import io.koraframework.common.annotation.Component;
import io.koraframework.config.common.ConfigValue;
import io.koraframework.config.common.mapper.ConfigValueMapper;

public record Token(String value) {}

@Component
public final class TokenConfigValueMapper implements ConfigValueMapper<Token> {

    @Override
    public Token map(ConfigValue<?> value) {
        if (value instanceof ConfigValue.NullValue) return null;
        var raw = value.asString();
        if (!raw.startsWith("Bearer ")) {
            throw new IllegalArgumentException("Token must start with 'Bearer '");
        }
        return new Token(raw.substring("Bearer ".length()));
    }
}
```

```java
@ConfigSource("foo")
public interface FooConfig {

    @Mapping(TokenConfigValueMapper.class)
    Token apiToken();
}
```

```kotlin
@Component
class TokenConfigValueMapper : ConfigValueMapper<Token> {
    override fun map(value: ConfigValue<*>): Token? {
        if (value is ConfigValue.NullValue) return null
        val raw = value.asString()
        require(raw.startsWith("Bearer ")) { "Token must start with 'Bearer '" }
        return Token(raw.removePrefix("Bearer "))
    }
}
```

```hocon
foo.apiToken = "Bearer advanced-config-secret"
```

`ConfigValue<?>` is a sealed type: `NullValue`, `BooleanValue`, `StringValue`, `NumberValue`,
`ArrayValue`, `ObjectValue`. Convenience accessors `asString()`, `asNumber()`, `asBoolean()`,
`asArray()`, `asObject()` and `isNull()` throw `ConfigValueException.unexpectedValueType` on a
mismatch, which already carries the config path and origin — prefer them over manual casting.

A `ConfigValueMapper` declared without `@Mapping` and registered as a `@Component` becomes the
default mapper for its type everywhere.

---

## Validating config with `@Valid`

`io.koraframework.validation.common.annotation.Valid` on a `@ConfigSource` or `@ConfigMapper` type
makes the generated mapper accept a `Validator<T>` and call `validateAndThrow(...)` immediately
after parsing, so constraint violations fail the graph build instead of surfacing later.

It needs the validation module and its processor on the classpath — see
[kora-aop-validation](../../kora-aop-validation/SKILL.md).

---

## Injecting the raw `Config`

`io.koraframework.config.common.Config` gives a generic view of the merged configuration. Tags
scope it to one layer.

| Tag | Layer |
|---|---|
| (none) | environment variables + system properties + config file |
| `@EnvironmentConfig` | environment variables only |
| `@SystemPropertiesConfig` | system properties only |
| `@ApplicationConfig` | config file only |

```java
import io.koraframework.common.annotation.Component;
import io.koraframework.config.common.Config;
import io.koraframework.config.common.annotation.EnvironmentConfig;

@Component
public final class FooService {
    public FooService(@EnvironmentConfig Config config) { /* ... */ }
}
```

All three are `@Tag` meta-annotations, so `@EnvironmentConfig Config` is exactly
`@Tag(EnvironmentConfig.class) Config`. The 1.x names were `@Environment` and `@SystemProperties`;
both were renamed in 2.0.

`config.get("a.b.c")` returns a `ConfigValue<?>` — never null; an absent path yields a `NullValue`
that carries its origin, which is why config errors can name the file they came from.

Prefer typed `@ConfigSource` interfaces: depending on the raw `Config` makes every dependent
component refresh on any config change.

---

## Config in a library Gradle module

Config annotations are processed at compile time, in the module that declares them. A library
module that declares `@ConfigMapper` / `@ConfigSource` types must apply the processor itself:

```groovy
// Java library module (koraVersion=2.0.0.RC2 in gradle.properties, resolved from mavenCentral())
configurations {
    koraBom
    annotationProcessor.extendsFrom(koraBom)
    compileOnly.extendsFrom(koraBom)
    implementation.extendsFrom(koraBom)
    api.extendsFrom(koraBom)
}

dependencies {
    koraBom platform("io.koraframework:kora-bom:$koraVersion")
    annotationProcessor "io.koraframework:annotation-processors"
    api "io.koraframework:config-common"
}
```

```kotlin
// Kotlin library module
plugins {
    id("org.jetbrains.kotlin.jvm")
    id("com.google.devtools.ksp")
}

dependencies {
    api(platform("io.koraframework:kora-bom:${property("koraVersion")}"))
    ksp("io.koraframework:symbol-processors:${property("koraVersion")}")
    api("io.koraframework:config-common")
}
```

Without it the library compiles fine and generates nothing; the failure surfaces in the
**consumer** as a missing `*Module` or an unresolvable `ConfigValueMapper<T>`, which points at the
wrong module. In Kora 1.x such library modules often got away without a processor, so this is a
frequent post-migration surprise.

Because `@Module` auto-discovery only covers the current compilation, the consuming `@KoraApp`
must extend a `*Module` that was generated elsewhere:

```java
@KoraApp
public interface Application extends
        HoconConfigModule,
        LogbackModule,
        com.example.lib.LibAppConfigModule {   // generated in the library module
}
```

---

## Porting a 1.x config module

1. `ru.tinkoff.kora` → `io.koraframework` across imports.
2. `@ConfigValueExtractor` → `@ConfigMapper` (annotation, `…config.common.annotation`).
3. Runtime `ConfigValueExtractor<T>` → `ConfigValueMapper<T>` (`…config.common.mapper`). If an
   automated pass left `ConfigMapper<T>` as a *type*, that is the bug — fix the type name.
4. `extract(value)` → `map(value)` when a null result is acceptable, `mapOrThrow(value)` otherwise.
   A composing `extractor.map(fn)` becomes `mapper.andThen(fn)`.
5. `@Environment` → `@EnvironmentConfig`; `@SystemProperties` → `@SystemPropertiesConfig`;
   `@ApplicationConfig` keeps its name.
6. `Size` is `io.koraframework.common.util.Size`.
7. Java nullability annotations → JSpecify `org.jspecify.annotations.Nullable` on the return type;
   Kotlin → nullable return types, drop the annotations.
8. Rename framework config keys in every `.conf`/`.yaml` **and** in every
   `KoraConfigModification.ofString("""…""")` block: `httpServer.publicApiHttpPort` → `httpServer.port`,
   `httpServer.privateApiHttpPort` → `httpServer.system.port`, `db { … }` → `jdbc { … }`.
   A stale key is ignored silently and the component falls back to its default (`8080` for the
   public server, `8085` for the system server), so a green start proves nothing — check the ports
   the process actually listens on.
9. Re-enable telemetry explicitly where an example depends on it — `metrics.enabled` and
   `logging.enabled` both default to `false` in 2.0.
10. Rebuild with `clean` and `--no-build-cache` so stale `ru.tinkoff.kora` generated sources cannot
    produce phantom errors.

---

## Related

- [SKILL.md](../SKILL.md) — overview and quick start
- [hocon-syntax-reference.md](hocon-syntax-reference.md) — HOCON syntax and supported types
