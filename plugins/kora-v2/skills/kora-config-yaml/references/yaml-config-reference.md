# YAML Configuration Reference — Kora 2.0

Depth reference for the `io.koraframework:config-yaml` module: `YamlConfigModule`, YAML parsed by
`snakeyaml-engine` (YAML 1.2) into `io.koraframework.config.common.Config`, then bound to typed
interfaces by processor-generated `ConfigValueMapper`s.

> HOCON remains the default format for new services; see
> [kora-config-hocon](../../kora-config-hocon/SKILL.md). Annotations, value mappers and
> substitution are shared through `config-common` — only file syntax and the YAML-only limits
> below differ.

## Contents

- [YAML syntax and the two YAML-only limits](#yaml-syntax-and-the-two-yaml-only-limits)
- [Environment-variable substitution](#environment-variable-substitution)
- [Merge order and precedence](#merge-order-and-precedence)
- [Supported value types](#supported-value-types)
- [Binding styles: @ConfigSource vs @ConfigMapper](#binding-styles-configsource-vs-configmapper)
- [Optional and default values](#optional-and-default-values)
- [Reusing one shape under several paths](#reusing-one-shape-under-several-paths)
- [Custom value types](#custom-value-types)
- [File resolution, reference.yaml and the watcher](#file-resolution-referenceyaml-and-the-watcher)
- [Testing YAML config](#testing-yaml-config)
- [Migrating a 1.x YAML config](#migrating-a-1x-yaml-config)
- [Common pitfalls](#common-pitfalls)
- [Related](#related)

## YAML syntax and the two YAML-only limits

### Scalars, objects, arrays

```yaml
quoted: "my-app"
unquoted: my-app
port: 8080
ratio: 0.75
enabled: true

description: |          # literal block, keeps line breaks
  Line 1
  Line 2
summary: >              # folded block, becomes one line
  This becomes
  one line

server:
  host: localhost
  ssl:
    enabled: true

hosts:                  # block sequence
  - host1
  - host2
ports: [8080, 8081]     # flow sequence
```

Spaces only, never tabs. Quote any value containing `:` or `#`
(`url: "jdbc:postgresql://host/db"`, `password: "#secret"`) and any value YAML would retype
(`version: "1.0"` — unquoted it becomes the number `1.0`).

### Limit 1 — no path expressions

A mapping key is stored verbatim, while a config path is split on `.` and resolved one nesting
level per segment. A key containing a dot is a key *named* with a dot and matches no path:

```yaml
httpServer:
  telemetry.metrics.enabled: true   # WRONG — never read
  telemetry:
    metrics:
      enabled: true                 # correct
```

Nothing fails; the section keeps its defaults. HOCON expands `a.b = v` into nested objects, so
`.conf` snippets pasted into YAML quietly stop working. The exception is a value bound to
`Map<String, ?>` or `Properties` — there the dotted key *is* the map key and is meant to be flat
(`logging.levels`, Kafka `driverProperties`).

### Limit 2 — an explicit null deletes the key

Entries whose value is `null` are dropped during parsing, so

```yaml
app:
  note: null
```

is indistinguishable from omitting `note`. A required method then fails with
`Config expected value, but got null at path: 'ROOT.app.note'`. Use `@Nullable` (Kotlin: `String?`)
for a value that may be absent.

Only objects, arrays, strings, numbers and booleans are accepted. Any other YAML node raises
`YAML config contains unsupported value type at path '<path>': <class>, value '<value>'`.

### Relaxed key matching

A lookup tries the exact name first, then kebab-case, then snake_case. `relaxedKey()` therefore
binds `relaxedKey`, `relaxed-key` or `relaxed_key`. The conversion runs on the *method* name, so a
YAML key in another shape (`RELAXED_KEY`, `relaxedkey`) is not matched.

## Environment-variable substitution

Substitution is resolved by `config-common` after the environment, system properties and the
application file have been merged. The resolver is shared with HOCON, so `${VAR}`, `${?VAR}`,
config-path references, composition and escaping behave the same in both formats — but the two
backends do not feed the resolver the same input, and the inline-default form is YAML-only (see
below).

```yaml
foo:
  valueRequired: ${ENV_VALUE_REQUIRED}            # required: startup fails if unset
  valueOptional: ${?ENV_VALUE_OPTIONAL}           # optional: resolves to null
  valueDefault: ${ENV_VALUE_DEFAULT:someDefault}  # literal default if unset
  valueRef: ${foo.valueRequired}-${foo.valueDefault}
```

| Form | Meaning | Interface return type |
|---|---|---|
| `${NAME}` | Required. Unresolvable → `Config reference '${NAME}' cannot be resolved at path '<path>' …` | non-null |
| `${?NAME}` | Optional. Missing → null; inside a composed string the fragment is dropped | `@Nullable` / `T?` |
| `${NAME:default}` | **YAML-only.** Falls back to the literal after the first `:` (the default itself may contain `:`) | non-null |
| `${some.config.path}` | Reference to another resolved config value | matches the target |

Notes verified in `ConfigResolverUtils`:

- **One namespace.** A name is looked up in the merged root, so `${DATABASE_URL}` (env var),
  `${app.name}` (config path) and a system property all use the same syntax.
- **Composition.** Several references and literals concatenate into one string:
  `${foo.valueString}Other${foo.valueString}`. Only strings, numbers and resolved-to-null optionals
  may be embedded; an object or array reference raises an error.
- **Escaping.** `\${NOT_A_REF}` is left as literal text.
- **The inline default is a YAML capability, not a shared one.** YAML has no substitution logic of
  its own — `YamlConfigFactory` only maps snakeyaml nodes — so `${VAR:default}` reaches Kora's
  resolver as a plain string and is handled there. HOCON is resolved by typesafe first
  (`HoconConfigModule` ends with `.resolve(ConfigResolveOptions.defaults())`), and `:` is not valid
  in an unquoted HOCON path expression, so the form never survives to Kora's pass. The corpus bears
  this out: `${VAR:default}` appears only in `.yaml` files and never in a `.conf`. The HOCON idiom
  is a double assignment — `"root": "WARN"` then `"root": ${?LOGGING_LEVEL_ROOT}` — where the second
  line is dropped when the variable is unset. Never write the shell form `${VAR:-default}`; it is
  invalid in both formats.
- **Environment values are never re-resolved** — a `${...}` inside an environment variable's value
  stays literal. System-property values *are* resolved unless
  `KORA_SYSTEM_PROPERTIES_RESOLVE_ENABLED=false` / `-Dkora.system.properties.resolve.enabled=false`.

## Merge order and precedence

`ConfigModule` merges environment variables, then system properties, then the application config,
and resolves the result. When the same top-level key exists in more than one source:

**environment variable > system property > application file**

Environment-variable names are kept flat, so they influence config only through an explicit
`${VAR}`. System-property names are expanded on dots into a nested tree, so `-Dapp.name=Foo`
directly overrides `app.name` from the file — the closest thing 2.0 has to an ad-hoc override.

The whole merged `Config` can also be injected: plain `Config` for the merged view,
`@ApplicationConfig Config` for the file alone, `@EnvironmentConfig` / `@SystemPropertiesConfig`
for those sources (all in `io.koraframework.config.common.annotation`).

## Supported value types

| Category | Types |
|---|---|
| Text / scalars | `String`, `boolean`, `int`, `long`, `float`, `double`, `BigInteger`, `BigDecimal` |
| Identifiers / patterns | `UUID`, `Pattern`, enums |
| Date / time | `LocalDate`, `LocalTime`, `LocalDateTime`, `OffsetTime`, `OffsetDateTime`, `Duration`, `Period` |
| Sizes | `io.koraframework.common.util.Size` |
| Collections | `List<T>`, `Set<T>`, `Map<K, V>`, `Properties`, `double[]`, `Duration[]` |
| Wrappers | `Optional<T>`, `io.koraframework.common.Either<A, B>` |
| Nested objects | `@ConfigMapper` type, `List<NestedConfig>`, raw `ConfigValue.ObjectValue` |

Parsing rules worth knowing:

- **`Duration`** — a bare number is milliseconds (`250` → 250 ms). A string is parsed as ISO-8601
  first (`"PT4M10S"`), then HOCON-style (`"250s"`, `"5 minutes"`, `"1d"`); a unitless string is
  milliseconds. Unknown unit → `Could not parse time unit '<u>' (try ns, us, ms, s, m, h, d)`.
- **`Period`** — an int (`1`) or a string (`"1d"`).
- **`Size`** — a bare number is bytes; a string carries a unit, binary or SI
  (`"256MiB"`, `"10MB"`, `"1024B"`).
- **`List` / `Set`** — either a YAML sequence (`["v1", "v2"]`) or a comma-separated string
  (`"v1,v2"`, elements trimmed). An empty string yields an empty collection.
- **`Properties`** — an object; nested objects are flattened back into dotted property names.

Full-surface example, mirroring `examples/java/kora-java-config-yaml`:

```yaml
foo:
  valueEnvRequired: ${ENV_VALUE_REQUIRED}
  valueEnvOptional: ${?ENV_VALUE_OPTIONAL}
  valueEnvDefault: ${ENV_VALUE_DEFAULT:someDefaultValue}
  valueString: "SomeString"
  valueRef: ${foo.valueString}Other${foo.valueString}
  valueUuid: "20684ccb-81f8-4fac-8ec0-297b08ff993d"
  valuePattern: ".*somePattern.*"
  valueEnum: "ANY"
  valueLocalDate: "2020-10-10"
  valueOffsetDateTime: "2020-10-10T12:10:10+03:00"
  valuePeriodAsString: "1d"
  valueDuration: "250s"
  valueInt: 1
  valueBigDecimal: 5.1
  relaxed-key: "relaxed-name"
  valueBoolean: true
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
import io.koraframework.config.common.annotation.ConfigMapper;
import io.koraframework.config.common.annotation.ConfigSource;
import org.jspecify.annotations.Nullable;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.Duration;
import java.time.OffsetDateTime;
import java.time.Period;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.regex.Pattern;

@ConfigSource("foo")
public interface FooConfig {

    enum EnumValue { ANY, SOME }

    String valueEnvRequired();

    @Nullable
    String valueEnvOptional();

    String valueEnvDefault();

    String valueString();

    String valueRef();

    UUID valueUuid();

    Pattern valuePattern();

    EnumValue valueEnum();

    LocalDate valueLocalDate();

    OffsetDateTime valueOffsetDateTime();

    Period valuePeriodAsString();

    Duration valueDuration();

    int valueInt();

    BigDecimal valueBigDecimal();

    String relaxedKey();          // binds relaxed-key

    boolean valueBoolean();

    List<String> valueListAsString();

    List<String> valueListAsArray();

    Map<String, String> valueMap();

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

## Binding styles: @ConfigSource vs @ConfigMapper

| Annotation | Use for | How it binds |
|---|---|---|
| `@ConfigSource("path")` | One fixed section that becomes a graph component | The processor writes a `<Type>Module` `@Module` interface whose factory calls `mapper.mapOrThrow(config.get("path"))`. Every `@Module` compiled in the same project joins the graph, so nothing has to be listed in `@KoraApp`. A `@ConfigSource` shipped inside a *library* jar is not in your compilation — extend its generated module explicitly, or prefer `@ConfigMapper` for library config. |
| `@ConfigMapper` | A shape nested in another config, or reused at several paths, or shipped by a library | The processor generates a `ConfigValueMapper<T>`; inject it and call `map` / `mapOrThrow` yourself. |

Both accept an interface (the form the examples use, and the only one where a method body supplies
a default), a Java record or a Kotlin data class.

`@ConfigMapper` has one attribute, `mapNullAsEmptyObject()` (default `true`): an absent section is
mapped as an empty object, so a type whose every field is optional or defaulted still binds. Set it
to `false` to make an absent section produce `null` instead.

Adding `@Valid` (`io.koraframework.validation.common.annotation.Valid`) to a config type makes the
generated mapper call `validateAndThrow` on the bound instance, so constraint violations surface as
a binding failure at startup rather than later.

## Optional and default values

Kora has no `@DefaultValue` annotation.

```java
import io.koraframework.config.common.annotation.ConfigSource;
import org.jspecify.annotations.Nullable;

@ConfigSource("services.foo")
public interface FooServiceConfig {

    String bar();              // required

    @Nullable
    String note();             // optional — null when missing, pairs with ${?VAR}

    default int baz() {        // default via method body
        return 42;
    }
}
```

```kotlin
@ConfigSource("services.foo")
interface FooServiceConfig {
    fun bar(): String
    fun note(): String?        // optional
    fun baz(): Int = 42        // default — a non-abstract member
}
```

Nullability rules for 2.0:

- Java uses JSpecify `org.jspecify.annotations.Nullable`, which ships transitively with the core
  artifacts. It is a **type-use** annotation, so it binds to the type it precedes:
  `List<@Nullable String>`, `String @Nullable []`, `Outer.@Nullable Inner`. A wrong position is a
  compile error (`type annotation @org.jspecify.annotations.Nullable is not expected here`), not a
  silent downgrade.
- Kotlin expresses nullability in the type (`String?`). Never carry a Java nullability annotation
  into Kotlin.
- A primitive return type is never nullable; use the boxed type plus `@Nullable` if the key may be
  absent, or give it a default.

## Reusing one shape under several paths

Declare the shape once with `@ConfigMapper`, then produce tagged instances from factory methods on
the `@KoraApp` interface. The `ConfigValueMapper<LibConfig>` parameter is generated on demand by
the processor — you do not register it.

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
import io.koraframework.config.common.annotation.ConfigMapper;
import java.time.Duration;

@ConfigMapper
public interface LibConfig {

    String endpoint();

    Duration requestTimeout();
}
```

```java
import io.koraframework.application.graph.KoraApplication;
import io.koraframework.common.annotation.KoraApp;
import io.koraframework.common.annotation.Tag;
import io.koraframework.config.common.Config;
import io.koraframework.config.common.mapper.ConfigValueMapper;
import io.koraframework.config.yaml.YamlConfigModule;
import io.koraframework.logging.logback.LogbackModule;

@KoraApp
public interface Application extends YamlConfigModule, LogbackModule {

    final class Lib1Tag {}

    final class Lib2Tag {}

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
interface Application : YamlConfigModule, LogbackModule {

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

Consumers select an instance by tag:

```java
public ConfigRunner(
        AppConfig appConfig,
        @Tag(Application.Lib1Tag.class) LibConfig lib1,
        @Tag(Application.Lib2Tag.class) LibConfig lib2) { /* ... */ }
```

`mapOrThrow` fails with `Config expected value, but got null after parsing at path: '<path>'` when
the section maps to nothing; `map` returns null instead, for a genuinely optional section.

## Custom value types

Bind a type Kora does not know by pointing the config method at a `ConfigValueMapper<T>` with
`@Mapping` (`io.koraframework.common.annotation.Mapping`). The mapper must be a `@Component`.

```java
@ConfigSource("foo")
public interface FooConfig {

    @Mapping(TokenConfigValueMapper.class)
    Token apiToken();
}
```

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

```yaml
foo:
  apiToken: "Bearer advanced-config-secret"
```

In Kotlin the override signature is `fun map(value: ConfigValue<*>): Token?` — the parameter is
non-null (Kora contracts are `@NullMarked`) and the result is nullable. Declaring `Token` instead of
`Token?` fails with `'map' overrides nothing`, which does not mention nullability.

A `ConfigValueMapper<T>` declared as a `@Component` without `@Mapping` becomes the default mapper
for `T` everywhere.

## File resolution, reference.yaml and the watcher

`YamlConfigModule` first merges every `reference.yaml` found on the classpath (library defaults,
each resolved on its own), then overlays the application file:

1. `-Dconfig.resource=<name>` — a classpath resource
2. `-Dconfig.file=<path>` — a filesystem path
3. `application.yaml` from the classpath, when neither property is set

Behaviour to know:

- Setting **both** properties throws at startup:
  `Application config source is ambiguous: both 'config.file'='…' and 'config.resource'='…' are set`.
- A `config.resource` that is not on the classpath resolves to an **empty** configuration, not an
  error. The typo shows up later as `Config expected value, but got null at path: 'ROOT.…'`.
- A `reference.yaml` that cannot be resolved on its own fails with
  `Reference config '<origin>' cannot be resolved without external application config` — give
  library defaults an in-file default or make the reference optional.

There is no profile mechanism. For per-environment setups write a complete alternative file — it
*replaces* `application.yaml` rather than layering over it — and select it explicitly:

```yaml title="application-prod.yaml"
app:
  name: ${APP_NAME:Task Management App}
  version: ${APP_VERSION}
  environment: "production"
```

```bash
./gradlew run -Dconfig.resource=application-prod.yaml
```

A file-backed config (`config.file`, or a `config.resource` that resolves to a real file) is polled
once a second and refreshes the graph on change. Disable with
`-Dkora.config.watcher.enabled=false` or `KORA_CONFIG_WATCHER_ENABLED=false`.

## Testing YAML config

`test-junit5` loads the application's YAML and lets a test override values without touching the
file:

```java
@KoraAppTest(Application.class)
class ConfigAppTest implements KoraAppTestConfigModifier {

    @TestComponent
    private AppConfig appConfig;

    @Override
    public KoraConfigModification config() {
        return KoraConfigModification.ofResourceFile("application.yaml")
            .withSystemProperty("APP_VERSION", "1.0.0-test");
    }

    @Test
    void bindsTypedInterface() {
        assertEquals("1.0.0-test", this.appConfig.version());
    }
}
```

A tagged instance is injected the same way: `@TestComponent @Tag(Application.Lib1Tag.class)`.
See [kora-testing-junit-java](../../kora-testing-junit-java/SKILL.md) /
[kora-testing-junit-kotlin](../../kora-testing-junit-kotlin/SKILL.md).

## Migrating a 1.x YAML config

Code:

| 1.x | 2.0 |
|---|---|
| `ru.tinkoff.kora:config-yaml` | `io.koraframework:config-yaml` |
| `ru.tinkoff.kora.config.yaml.YamlConfigModule` | `io.koraframework.config.yaml.YamlConfigModule` |
| `ru.tinkoff.kora.config.common.annotation.ConfigSource` | `io.koraframework.config.common.annotation.ConfigSource` |
| `@ConfigValueExtractor` | `@ConfigMapper` |
| `ConfigValueExtractor<T>` (`config.common.extractor`) | `ConfigValueMapper<T>` (`config.common.mapper`) |
| `extractor.extract(config.get(path))` | `mapper.mapOrThrow(config.get(path))` |
| `map(Function)` (composition on the 1.x extractor) | `andThen(Function)` — in 2.0 `map(value)` is the *extraction* method |
| `jakarta.annotation.Nullable` | `org.jspecify.annotations.Nullable` |

File keys — none of these are rejected when stale, they are simply never read, so the build stays
green and the default silently applies:

| 1.x key | 2.0 key |
|---|---|
| `httpServer.publicApiHttpPort` | `httpServer.port` |
| `httpServer.privateApiHttpPort` | `httpServer.system.port` |
| `httpServer.privateApiHttpReadinessPath` | `httpServer.system.readinessPath` |
| `httpServer.privateApiHttpLivenessPath` | `httpServer.system.livenessPath` |
| `httpServer.privateApiHttpMetricsPath` | `httpServer.system.metricsPath` |
| `db:` (datasource section) | `jdbc:` |

```yaml
httpServer:
  port: 8080
  telemetry:
    logging:
      enabled: true       # 2.0 default is false
    metrics:
      enabled: true       # 2.0 default is false
  system:
    port: 8085

jdbc:
  jdbcUrl: ${POSTGRES_JDBC_URL}
  username: ${POSTGRES_USER}
  password: ${POSTGRES_PASS}
```

None of this fails loudly. A stale key is unrecognised and therefore never read, so each server
falls back to its own default — public `8080` (`HttpServerConfig.port()`), system `8085`
(`SystemHttpServerConfig.port()` overrides it). A 1.x config that ran on custom ports starts green
**on the wrong ports**, and readiness probes, metrics scrapers and load balancers quietly hit
nothing. `Address already in use` appears only in the narrower case where a half-migrated config
collapses both servers onto one port. Either way the rename is mandatory.

Leave the datasource section named `db` and every value stays unset:
`ConfigValueException: Config expected value, but got null at path: 'ROOT.jdbc.username'`.

Telemetry is opt-in per component in 2.0 — `metrics.enabled` and `logging.enabled` default to
`false`, `tracing.enabled` to `true`. Every component that reports telemetry carries the same
`telemetry.{logging,metrics,tracing}.enabled` block in its own section — `httpServer`,
`httpServer.system`, `jdbc`, each declarative HTTP client, each Kafka publisher and listener. An
example that claims to show metrics or request logging has to enable them explicitly.

One documented exception: under `httpServer.system` the nested `SystemHttpServerTracingConfig`
overrides `enabled()` to `false`, so the system server is **not** traced by default even though
tracing is on everywhere else. Readiness and liveness polling would otherwise flood the trace
backend.

## Common pitfalls

| Symptom | Cause / fix |
|---|---|
| A key has no effect and the default is used | Dotted key in YAML — nest it; YAML has no path expressions |
| `cannot find symbol: ConfigValueExtractor` | Renamed to `@ConfigMapper`; the runtime contract is `ConfigValueMapper<T>` |
| `cannot find symbol: extract(...)` | `ConfigValueMapper` exposes `map(value)` and `mapOrThrow(value)` |
| A migrated `.map(...)` compiles but behaves differently | 1.x `map(Function)` was composition; 2.0 spells that `andThen(Function)` and uses `map(value)` for extraction. Treat every 1.x `.map(` on a config extractor as suspect |
| `${VAR:default}` moved into a `.conf` no longer applies | The inline default is YAML-only; HOCON assigns the key twice instead |
| `Config reference '${VAR}' cannot be resolved at path '…'` | Required substitution unset — set it, or use `${VAR:default}` / `${?VAR}` |
| `Config expected value, but got null at path: 'ROOT.…'` | Key absent, spelled differently, set to `null`, or the file was not found |
| `Config expected value, but got null after parsing at path: '…'` | `mapOrThrow` on a section that maps to nothing — use `map` if it is optional |
| `Config expected value with type 'StringValue' but received type 'ObjectValue'` | Shape mismatch between the YAML node and the declared return type |
| `Application config source is ambiguous` | Both `config.file` and `config.resource` set — remove one |
| `YAML config contains unsupported value type at path '…'` | A YAML node that is not object/array/string/number/boolean — quote it |
| Indentation / parse error | Spaces only, consistent depth; no tabs |
| `@DefaultValue` does not compile | No such annotation — use a method body |
| Nested `@ConfigSource` binds nothing | Nested types use `@ConfigMapper`, exposed as a parent method |
| `type annotation @Nullable is not expected here` | JSpecify is type-use — move it next to the type |
| `'map' overrides nothing` (Kotlin) | `ConfigValueMapper.map` returns `T?`, its parameter is non-null |
| Config component missing from the graph | Processor not wired, or `@KoraApp` does not extend `YamlConfigModule` |
| Both `config-yaml` and `config-hocon` present | Pick exactly one format module |
| `ru.tinkoff.kora` errors after the rename | Stale generated sources — `clean` + `--no-build-cache`; never edit `build/generated` |

## Related

- [SKILL.md](../SKILL.md) — overview and quick start
- [kora-config-hocon](../../kora-config-hocon/SKILL.md) — HOCON format (default for new services)
- [kora-di-compile](../../kora-di-compile/SKILL.md) — how config components join the graph
- Module source: <https://github.com/kora-projects/kora/tree/2.0.0.RC2/config/config-yaml>
- Shared binding/mapping/substitution: <https://github.com/kora-projects/kora/tree/2.0.0.RC2/config/config-common>
- Migrated examples, branch `migration/2.0` (**not** the repository default branch, which is 1.x):
  <https://github.com/kora-projects/kora-examples/tree/migration/2.0/examples/java/kora-java-config-yaml>

> The Kora 2.0 documentation ([Configuration](https://koraframework.io/v2/en/documentation/config/))
> explains concepts but can trail the framework; the source links above are the authority for every
> statement in this reference. The 1.x pages (`ru.tinkoff.kora` packages, `@ConfigValueExtractor`)
> are background only.
