---
name: kora-config-yaml
description: "YAML typed config in Kora 2.0 — io.koraframework:config-yaml, YamlConfigModule, @ConfigSource / @ConfigMapper over application.yaml, ConfigValueMapper.mapOrThrow, ${VAR} substitution. Use when a service reads YAML config, when migrating @ConfigValueExtractor to @ConfigMapper, or when a YAML key silently has no effect. For application.conf see kora-config-hocon."
license: Apache-2.0
metadata:
  version: "0.1.0"
  kora-version: "2.x"
---

# Kora Config YAML

> **Kora sub-skill — obey the [kora-v2 meta rules](../../SKILL.md) on every task:** **R0** ground the workspace on Kora 2.0 refs before starting (framework source at tag `2.0.0.RC2` + `kora-examples` at `migration/2.0` + Kora 2.0 docs at koraframework.io/v2, which trail the source; 1.x `kora-docs` pages are never an authority) · **R1** read this sub-skill before writing code · **R2** Kora 2.0 APIs only — no Spring/Micronaut/Quarkus, no Kora 1.x APIs, no invented annotations or config keys · **R3** journal any incorrect Kora usage. Add comments/Javadoc only if asked.

| | |
|---|---|
| **Artifact** | `io.koraframework:config-yaml` |
| **Module** | `io.koraframework.config.yaml.YamlConfigModule` |
| **Annotations** | `io.koraframework.config.common.annotation.{ConfigSource, ConfigMapper}` |
| **Runtime mapper** | `io.koraframework.config.common.mapper.ConfigValueMapper<T>` — `map(value)` / `mapOrThrow(value)` |
| **Parser** | `org.snakeyaml:snakeyaml-engine` (YAML 1.2) |
| **Default file** | `application.yaml` on the classpath |

HOCON stays the default format for new Kora services; use YAML when the project requires it.
The binding API is shared — `config-common` holds the annotations, the value mappers and the
substitution resolver, so only the file syntax and the two YAML-only limits below differ.

## Renamed in 2.0

| Kora 1.x | Kora 2.0 |
|---|---|
| `ru.tinkoff.kora:config-yaml` | `io.koraframework:config-yaml` |
| `ru.tinkoff.kora.config.yaml.YamlConfigModule` | `io.koraframework.config.yaml.YamlConfigModule` |
| `@ConfigValueExtractor` | **`@ConfigMapper`** (`io.koraframework.config.common.annotation`) |
| `ConfigValueExtractor<T>` / `extract(value)` (package `config.common.extractor`) | **`ConfigValueMapper<T>`** / **`mapOrThrow(value)`** (package `config.common.mapper`; the whole `extractor` package is gone) |
| `map(Function)` — *composition* on the 1.x extractor | **`andThen(Function)`** — in 2.0 `map(value)` **is** the extraction method, so a mechanical `map` → `map` rename compiles and silently changes meaning |
| `ru.tinkoff.kora:kora-parent` | `io.koraframework:kora-bom` |
| `jakarta.annotation.Nullable` | `org.jspecify.annotations.Nullable` (Java) / `T?` (Kotlin) |

`@ConfigSource` keeps its name, its single `String value()` path and its semantics: the processor
generates a `@Module` interface next to the annotated type, and every `@Module` compiled in the
same project joins the graph automatically — you never list it in `@KoraApp`. `@ConfigMapper` gained one attribute,
`mapNullAsEmptyObject()` (default `true`): an absent section is mapped as an empty object so a
type whose fields are all optional or defaulted still binds.

## Quick Start

### 1. Dependency

Versions come from the BOM — never pin a version on an individual `io.koraframework:*` artifact.
The current release is **`koraVersion=2.0.0.RC2`** from plain `mavenCentral()`; `2.0.0-SNAPSHOT` is
the development line and needs its own snapshot repository, so do not put it in a new project. The
processor is mandatory: without it `@ConfigSource` generates nothing and the graph has no config
component. Full build wiring lives in
[kora-project-setup-java](../kora-project-setup-java/SKILL.md) /
[kora-project-setup-kotlin](../kora-project-setup-kotlin/SKILL.md).

```groovy
dependencies {
    koraBom platform("io.koraframework:kora-bom:$koraVersion")
    annotationProcessor "io.koraframework:annotation-processors"

    implementation "io.koraframework:config-yaml"
    implementation "io.koraframework:logging-logback"
}
```

Kotlin uses KSP instead: `ksp("io.koraframework:symbol-processors:$koraVersion")`.

### 2. Enable the module

```java
import io.koraframework.application.graph.KoraApplication;
import io.koraframework.common.annotation.KoraApp;
import io.koraframework.config.yaml.YamlConfigModule;
import io.koraframework.logging.logback.LogbackModule;

@KoraApp
public interface Application extends YamlConfigModule, LogbackModule {

    static void main(String[] args) {
        KoraApplication.run(ApplicationGraph::graph);
    }
}
```

### 3. `src/main/resources/application.yaml`

```yaml
app:
  name: ${APP_NAME:Task Management App}   # literal default when APP_NAME is unset
  version: ${APP_VERSION}                 # required — startup fails if unset
  environment: "development"
```

### 4. Typed interface

```java
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

### 5. Inject it

Config is an ordinary graph dependency. A component that nothing else depends on must be `@Root`
or the graph prunes it.

```java
import io.koraframework.common.annotation.Component;
import io.koraframework.common.annotation.Root;

@Root
@Component
public final class GreetingService {

    private final AppConfig config;

    public GreetingService(AppConfig config) {
        this.config = config;
    }
}
```

## Two YAML-only rules

**1. There are no path expressions.** `YamlConfigFactory` stores every mapping key verbatim, while
lookups split the path on `.` and resolve one nesting level per segment. A dotted key is therefore
a key whose *name* contains a dot, and it matches nothing:

```yaml
httpServer:
  telemetry.metrics.enabled: true    # WRONG — key literally named "telemetry.metrics.enabled"
  telemetry:
    metrics:
      enabled: true                  # correct
```

Nothing fails: the section falls back to its defaults. HOCON expands `a.b = v` into nested objects,
so a `.conf` snippet copied into a `.yaml` file quietly stops working.

**2. An explicit `null` deletes the key.** Entries whose value is `null` are dropped while parsing,
so `note: null` behaves exactly like omitting `note` — a required method then fails with
`Config expected value, but got null at path: 'ROOT.app.note'`.

Values may only be objects, arrays, strings, numbers and booleans; an explicitly tagged node such
as `!!binary` raises `YAML config contains unsupported value type at path ...`.
Quote values that would otherwise be retyped: `version: "1.0"`, `url: "jdbc:postgresql://host/db"`.

Key lookup is relaxed: a method `relaxedKey()` matches `relaxedKey`, `relaxed-key` or
`relaxed_key`, in that order.

## Substitution

The resolver lives in `config-common` and runs over the merged tree, so `${VAR}`, `${?VAR}`,
config-path references, composition and escaping work the same in both formats. **The inline
default `${VAR:default}` is YAML-only** — see the note under the example.

```yaml
foo:
  valueRequired: ${ENV_VALUE_REQUIRED}            # required — startup fails if unset
  valueOptional: ${?ENV_VALUE_OPTIONAL}           # optional — resolves to null
  valueDefault: ${ENV_VALUE_DEFAULT:someDefault}  # literal default if unset
  valueRef: ${foo.valueRequired}-suffix           # reference another config path
```

`${VAR:default}` is a **capability YAML has and HOCON does not**. YAML ships no substitution logic
of its own, so the raw string reaches Kora's resolver, which understands the `:default` form. HOCON
is resolved by typesafe first, and `:` is not valid in an unquoted HOCON path expression, so the
form never survives to Kora's pass — in `.conf` you assign the key twice instead
(`key = fallback`, then `key = ${?VAR}`). Do not copy an inline default from YAML into HOCON, and
never write the shell form `${VAR:-default}`, which is invalid in both.

`${?VAR}` requires a `@Nullable` return type. The lookup namespace is the merged root, so a name
resolves against an environment variable, a system property or a config path alike. Precedence when
the same top-level key exists in more than one: **environment variable > system property >
application file**. System-property names are expanded on dots, so `-Dapp.name=Foo` overrides
`app.name` from the file; environment-variable names are flat and reach config only through an
explicit `${VAR}`.

Details — escaping with `\${`, composing several references into one string, resolution inside
`reference.yaml` — are in
[references/yaml-config-reference.md](references/yaml-config-reference.md#environment-variable-substitution).

## Optional and default values

Kora has no `@DefaultValue` annotation. Express both in the type:

```java
import org.jspecify.annotations.Nullable;

@ConfigSource("app")
public interface AppConfig {

    String name();                 // required

    @Nullable
    String description();          // optional — null when missing (pairs with ${?VAR})

    default int retries() {        // default value via method body
        return 3;
    }
}
```

```kotlin
@ConfigSource("app")
interface AppConfig {
    fun name(): String
    fun description(): String?     // optional
    fun retries(): Int = 3         // default — a non-abstract member
}
```

JSpecify `@Nullable` is a **type-use** annotation: it goes immediately before the type
(`List<@Nullable String>`, `Outer.@Nullable Inner`), and a wrong position is a compile error, not a
silent downgrade. In Kotlin nullability is the type — never carry the Java annotation over.

## Nested objects — `@ConfigMapper`

A nested shape is not a second `@ConfigSource`; annotate it `@ConfigMapper` and expose it as a
method on the parent.

```java
import io.koraframework.config.common.annotation.ConfigMapper;
import io.koraframework.config.common.annotation.ConfigSource;
import java.time.Duration;

@ConfigSource("app")
public interface AppConfig {

    String name();

    PoolConfig pool();

    @ConfigMapper
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
    connectionTimeout: "30s"
```

`List<PoolConfig>` binds a YAML sequence of such objects.

## Reusing one shape under several paths

Declare the shape once with `@ConfigMapper`, then build tagged instances from factory methods on
the `@KoraApp` interface — the `ConfigValueMapper<T>` is generated on demand by the processor.

```java
@Tag(Lib1Tag.class)
default LibConfig lib1Config(Config config, ConfigValueMapper<LibConfig> mapper) {
    return mapper.mapOrThrow(config.get("libs.lib1"));
}
```

`Config` is `io.koraframework.config.common.Config`. Full example, both languages, in
[references/yaml-config-reference.md](references/yaml-config-reference.md#reusing-one-shape-under-several-paths).

## Custom value types

Bind a type Kora does not know with `@Mapping` plus a `ConfigValueMapper<T>` registered as a
`@Component`; see the
[reference](references/yaml-config-reference.md#custom-value-types).

Built-in types: `String`, primitives and boxed numbers, `BigInteger`, `BigDecimal`, `boolean`,
`UUID`, `Pattern`, enums, `LocalDate`/`LocalTime`/`LocalDateTime`/`OffsetTime`/`OffsetDateTime`,
`Duration`, `Period`, `Size`, `List`/`Set`/`Map`, `Properties`, `Optional<T>`, `Either<A,B>`,
`double[]`, `Duration[]` and nested `@ConfigMapper` types. Full table in the
[reference](references/yaml-config-reference.md#supported-value-types).

## Selecting the config file

Kora merges every `reference.yaml` on the classpath (library defaults) and overlays the application
file:

1. `-Dconfig.resource=<name>` — a file on the classpath
2. `-Dconfig.file=<path>` — a file on the filesystem
3. `application.yaml` on the classpath, when neither property is set

Setting **both** properties is now a startup error (`Application config source is ambiguous`) — 2.0
no longer picks one silently. A `config.resource` that is not on the classpath yields an *empty*
configuration rather than an error, so a typo surfaces later as `Config expected value, but got
null`.

There is no profile mechanism. For per-environment setups write a complete alternative file — it
replaces `application.yaml`, it does not layer over it — and select it explicitly:

```bash
./gradlew run -Dconfig.resource=application-prod.yaml
```

A file-backed config is watched for changes and refreshes the graph; disable with
`-Dkora.config.watcher.enabled=false` or `KORA_CONFIG_WATCHER_ENABLED=false`.

## Config keys that moved in 2.0

Old keys are not rejected — an unknown YAML key is simply never read, so the compile is green and
the default applies.

Telemetry defaults are `logging.enabled = false`, `metrics.enabled = false`, `tracing.enabled = true`
— except under `httpServer.system`, whose `SystemHttpServerTracingConfig` overrides tracing to
`false` so probe traffic is not traced.

```yaml
httpServer:
  port: 8080                  # was publicApiHttpPort
  telemetry:
    logging:
      enabled: true           # 2.0 default is false
    metrics:
      enabled: true           # 2.0 default is false
  system:
    port: 8085                # was privateApiHttpPort
    readinessPath: "/system/readiness"   # was privateApiHttpReadinessPath
    livenessPath: "/system/liveness"     # was privateApiHttpLivenessPath
    metricsPath: "/metrics"              # was privateApiHttpMetricsPath

jdbc:                         # was db
  jdbcUrl: ${POSTGRES_JDBC_URL}
  username: ${POSTGRES_USER}
  password: ${POSTGRES_PASS}
```

The dangerous part is that **nothing fails**. A stale key is unrecognised, so each server simply
falls back to its own default — public `8080`, system `8085` — and a 1.x config that ran on custom
ports comes up green *on the wrong ports*, where probes and load balancers find nothing. You only
get `Address already in use` in the narrower case where a half-migrated config puts both servers on
one port. The rename is mandatory either way.

A stale `db:` section leaves the datasource empty —
`ConfigValueException: Config expected value, but got null at path: 'ROOT.jdbc.username'`.

## Common pitfalls

| Symptom | Cause / fix |
|---|---|
| A key you set has no effect, default used instead | Dotted key in YAML (`telemetry.metrics.enabled:`) — nest it, YAML has no path expressions |
| `cannot find symbol: ConfigValueExtractor` | Renamed to `@ConfigMapper`; the runtime contract is `ConfigValueMapper<T>` in `config.common.mapper` |
| `cannot find symbol: extract(...)` | `ConfigValueMapper` exposes `map(value)` (nullable) and `mapOrThrow(value)` |
| A migrated `.map(...)` compiles but returns the wrong thing | 1.x `map(Function)` was composition; in 2.0 that is `andThen(Function)` and `map(value)` is extraction |
| `${VAR:default}` copied into `application.conf` stops working | The inline default is YAML-only; in HOCON assign the key twice (`key = fallback`, `key = ${?VAR}`) |
| `Config reference '${VAR}' cannot be resolved at path ...` | Required substitution unset — provide it, or switch to `${VAR:default}` / `${?VAR}` |
| `Config expected value, but got null at path: 'ROOT.x.y'` | Key missing, spelled differently, set to `null`, or the whole file was not found — add `@Nullable`/a default, or check `config.resource` |
| `Application config source is ambiguous` | Both `config.file` and `config.resource` are set — remove one |
| `@DefaultValue` does not compile | No such annotation in Kora — use a method body |
| Nested `@ConfigSource` binds nothing | Nested types use `@ConfigMapper`, exposed as a parent method |
| `type annotation @Nullable is not expected here` | JSpecify is type-use — move it next to the type |
| Config component missing from the graph | Processor not wired (`annotation-processors` / `symbol-processors`), or `@KoraApp` does not extend `YamlConfigModule` |
| Both `config-yaml` and `config-hocon` on the classpath | Pick exactly one format module |
| `ru.tinkoff.kora` errors after renaming packages | Stale generated sources — `clean` + `--no-build-cache`, never edit `build/generated` |

## When to use YAML vs HOCON

| YAML | HOCON ([kora-config-hocon](../kora-config-hocon/SKILL.md)) |
|---|---|
| The project or platform mandates YAML | New service with no format constraint |
| Existing `application.yaml` files must be kept | You need path expressions (`a.b.c = v`) or `include` of other config files |
| You want inline defaults — `${VAR:default}` works here and nowhere else | You are happy assigning a key twice (`key = fallback`, `key = ${?VAR}`) to get the same effect |

Switching is a dependency swap (`config-yaml` ↔ `config-hocon`), the module interface, and
rewriting dotted keys into nesting. Everything else — annotations, mappers, substitution — is shared.

## Related skills

- [kora-config-hocon](../kora-config-hocon/SKILL.md) — HOCON format (default for new services)
- [kora-di-compile](../kora-di-compile/SKILL.md) — how config components join the graph
- [kora-project-dependencies](../kora-project-dependencies/SKILL.md) — artifact and BOM catalog

## Source of truth

Version-aligned material only — pinned to the tag and branch that match the published `2.0.0.RC2`
artifacts. Everything in this skill was verified against the framework source.

- Module source: <https://github.com/kora-projects/kora/tree/2.0.0.RC2/config/config-yaml>
- Shared binding/mapping/substitution: <https://github.com/kora-projects/kora/tree/2.0.0.RC2/config/config-common>
- Migrated examples (branch `migration/2.0`, **not** the repository default):
  <https://github.com/kora-projects/kora-examples/tree/migration/2.0/examples/java/kora-java-config-yaml>,
  `examples/kotlin/kora-kotlin-config-yaml`, `guides/java/kora-java-guide-config-yaml-app`

> The Kora 2.0 documentation ([Configuration](https://koraframework.io/v2/en/documentation/config/))
> explains concepts but can trail the framework — confirm every key, default and signature in the
> source above. The 1.x pages (`ru.tinkoff.kora` packages, `@ConfigValueExtractor`) are never an
> authority for a 2.0 question.
