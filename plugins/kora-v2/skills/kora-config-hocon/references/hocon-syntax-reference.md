# HOCON Syntax & Supported Types Reference

HOCON (Human-Optimized Config Object Notation) is the recommended config format for Kora, loaded by
`HoconConfigModule` from `io.koraframework:config-hocon`. It is a superset of JSON with relaxed
syntax, comments, substitution and includes. HOCON syntax itself did not change in Kora 2.0 —
what changed are the Kora types and framework config keys below.

## Contents

- [Values](#values)
- [Objects, paths, and arrays](#objects-paths-and-arrays)
- [Comments](#comments)
- [Environment variable substitution](#environment-variable-substitution)
- [Value references and string concatenation](#value-references-and-string-concatenation)
- [Includes](#includes)
- [Relaxed key names](#relaxed-key-names)
- [Supported value types](#supported-value-types)
- [The `Size` type](#the-size-type)
- [Config file resolution and the watcher](#config-file-resolution-and-the-watcher)
- [Framework config keys that changed in 2.0](#framework-config-keys-that-changed-in-20)
- [Common pitfalls](#common-pitfalls)

---

## Values

```hocon
# Strings (quoted or, when free of spaces/special chars, unquoted)
name = "my-app"
path = /var/log/app.log
message = "Hello \"World\""

# Numbers
port = 8080
ratio = 0.75
large = 1.5e6

# Booleans and null
enabled = true
value = null
```

A `null` value is dropped while the config tree is built, so it reads back exactly like an absent
key: optional fields become `null`, defaulted fields fall back to their default, and required
fields fail the graph build.

## Objects, paths, and arrays

```hocon
# Brace object
server {
  host = localhost
  port = 8080
}

# JSON-style is also valid
server: { host: localhost, port: 8080 }

# Dotted path — equivalent to the nested object above
server.host = localhost
server.port = 8080

# Arrays: one per line or inline
hosts = ["host1", "host2", "host3"]
ports = [
  8080
  8081
]
```

## Comments

```hocon
# hash comment
// double-slash comment
```

---

## Environment variable substitution

Resolved before the config is mapped into interfaces.

```hocon
app {
  required    = ${APP_URL}     # required: startup fails if APP_URL is unset
  optional    = ${?APP_URL}    # optional: key is omitted if APP_URL is unset
  withDefault = 8080           # default-then-override:
  withDefault = ${?APP_PORT}   #   keeps 8080 unless APP_PORT is set
}
```

**HOCON has exactly two substitution forms: `${VAR}` and `${?VAR}`. There is no inline default.**

A default is expressed by assigning the key **twice** — the literal first, then `${?VAR}`. Because
`${?VAR}` is dropped when the variable is unset, the literal survives; when the variable is set, the
second assignment wins. Use it for every value that has a sane local default but must be overridable
at deployment time.

Order matters: the *last* assignment wins, so `withDefault = ${?APP_PORT}` must come **after** the
literal. Writing the literal second would make the environment override unreachable.

```hocon
# The default-then-override idiom, as used throughout the migrated examples
maximumSize = 1000
maximumSize = ${?CACHE_MAX_SIZE}

logging.levels {
  "root" = "WARN"
  "root" = ${?LOGGING_LEVEL_ROOT}
}
```

Two forms that do **not** work in HOCON:

| Form | Why not |
|---|---|
| `${VAR:default}` | Kora's own resolver does understand `:` as a default separator, and that is why this form works in **YAML**, which has no substitution logic of its own and reaches Kora's resolver directly. HOCON does not: `HoconConfigModule` hands the file to typesafe-config, which resolves `${…}` itself before Kora ever sees it, and `:` is not part of a HOCON substitution. Zero occurrences exist in any `.conf` in the upstream examples. |
| `${VAR:-default}` | Shell syntax. Not valid in either format. |

If you are porting a `.yaml` config to `.conf`, every `${VAR:default}` must be rewritten as a
double assignment.

Substitutions read from environment variables **and** JVM system properties, which is what lets
tests inject values with `KoraConfigModification.withSystemProperty("APP_VERSION", "1.0.0-test")`
against a config file that says `version = ${APP_VERSION}`.

---

## Value references and string concatenation

Substitutions can reference other parts of the same config, and adjacent values concatenate.

```hocon
foo {
  valueString = "SomeString"
  valueRef = ${foo.valueString}"Other"${foo.valueString}  # -> "SomeStringOtherSomeString"
}

domain   = "example.com"
base_url = "https://api."${domain}        # -> "https://api.example.com"
full_url = ${base_url}"/v1/users"         # -> "https://api.example.com/v1/users"
```

A whole object can be referenced and then partially overridden — the idiomatic way to configure two
instances of the same shape:

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

## Includes

```hocon
include "application"               # resolved as a classpath resource
include classpath("defaults.conf")  # explicit classpath resource
include file("/etc/app/overrides.conf")
```

A bare `include "application"` inside `application-prod.conf` pulls in `application.conf` from the
classpath, which is how a per-environment file layers on top of the base one:

```hocon
# application-prod.conf
include "application"

app {
  environment = "production"
}
```

Prefer `classpath("…")` or an absolute `file("…")` when the intent matters — a bare include is
resolved heuristically. The config watcher tracks **file** includes only; classpath resources and
URLs are not watched.

Library `reference.conf` files are merged as a fallback beneath the application config, and JVM
`-D` overrides are layered on top of everything before the tree is resolved.

---

## Relaxed key names

A config field is looked up by its declared name first, then by kebab-case and snake_case variants
derived from it:

| Declared field | HOCON keys that match |
|---|---|
| `relaxedKey()` | `relaxedKey`, `relaxed-key`, `relaxed_key` |
| `maxPoolSize()` | `maxPoolSize`, `max-pool-size`, `max_pool_size` |

The declared name always wins when several variants are present. This is a lookup fallback, not a
naming convention — write the camelCase form in new config files.

---

## Supported value types

`@ConfigSource` / `@ConfigMapper` map these out of the box:

- `boolean`/`Boolean`, `int`/`Integer`, `long`/`Long`, `float`/`Float`, `double`/`Double`,
  `BigInteger`, `BigDecimal`, `double[]`
- `String`, `UUID`, `Pattern`, `Properties`
- `Duration` (`"250s"`), `Duration[]`, `Period` (`"1d"` or a bare `1` meaning days)
- `LocalDate`, `LocalTime`, `LocalDateTime`, `OffsetTime`, `OffsetDateTime`
- `io.koraframework.common.util.Size`
- any `enum`, matched by its `toString()`
- `List<T>`, `Set<T>`, `Map<K,V>`, `Optional<T>`, `io.koraframework.common.Either<A,B>`
- `ConfigValue.ObjectValue` for a raw sub-tree
- nested objects and lists of objects via `@ConfigMapper`

Anything else needs a custom `ConfigValueMapper<T>` registered as a `@Component` and referenced
with `@Mapping` — see [config-source-reference.md](config-source-reference.md#custom-configvaluemapper-with-mapping).
There is no built-in mapper for `short`/`byte`/`char`.

### Examples

```java
import java.time.*;
import java.util.*;
import java.util.regex.Pattern;
import io.koraframework.common.util.Size;
import io.koraframework.config.common.annotation.ConfigSource;

@ConfigSource("foo")
public interface FooConfig {

    UUID valueUuid();
    Pattern valuePattern();
    Duration valueDuration();     // "250s"
    Period valuePeriodAsString(); // "1d"
    Period valuePeriodAsInt();    // 1
    Size maxUpload();             // "10Mb"

    List<String> valueListAsArray();   // ["v1", "v2"]
    List<String> valueListAsString();  // "v1,v2"
    Set<String> valueSet();
    Map<String, String> valueMap();
    Properties valueProperties();
}
```

```hocon
foo {
  valueUuid = "20684ccb-81f8-4fac-8ec0-297b08ff993d"
  valuePattern = ".*somePattern.*"
  valueDuration = "250s"
  valuePeriodAsString = "1d"
  valuePeriodAsInt = 1
  maxUpload = "10Mb"
  valueListAsArray = ["v1", "v2"]
  valueListAsString = "v1,v2"
  valueSet = ["v1", "v2"]
  valueMap = { k1 = "v1", k2 = "v2" }
  valueProperties = { k1 = "v1", k2 = "v2" }
}
```

A list or set may be written either as an array or as a comma-separated string — both map to the
same collection.

---

## The `Size` type

`io.koraframework.common.util.Size` (moved out of the config package in 2.0 — it is a core type
now) parses human-friendly byte sizes in both the decimal (SI) and binary standards. There is no
`DataSize` type in Kora.

Suffixes are matched case-insensitively against `B`, `KB`/`KiB`, `MB`/`MiB`, `GB`/`GiB`,
`TB`/`TiB`, `PB`/`PiB`, `EB`/`EiB`. The `i` is what selects the binary scale.

| HOCON value | Bytes |
|---|---|
| `"1Mb"` / `"1MB"` | 1,000,000 (decimal megabyte) |
| `"1Mib"` / `"1MiB"` | 1,048,576 (binary mebibyte) |
| `"1024b"` / `"1024B"` | 1,024 |
| `1024` (bare number) | 1,024 |

Only whole numbers are accepted: `"1.5Mb"` fails with
`Can't extract size number part from: 1.5Mb`, and an unknown suffix fails with
`Can't extract size type part from: …`. Write `"1536Kb"` instead.

`Size` exposes `toBytes()`, `type()`, `valueExact()`, `valueRounded()` and `to(Type)`. Two `Size`
values are equal when their byte counts are equal, regardless of the unit they were written in.

---

## Config file resolution and the watcher

`HoconConfigModule` selects the application config origin as follows:

1. `config.resource` system property — a file on the classpath
2. `config.file` system property — a filesystem path
3. neither set → `application.conf` from the classpath
4. the named resource cannot be found → an empty config (the application still starts, and every
   required config value then fails the graph build)

```bash
java -Dconfig.resource=application-prod.conf -jar app.jar
java -Dconfig.file=/etc/app/application.conf -jar app.jar
```

Setting **both** properties is rejected:
`Application config source is ambiguous: both 'config.file'='…' and 'config.resource'='…' are set;
remove one of these system properties`. There is no `config.environment` profile switch in Kora —
per-environment configuration is a file selection plus `include`.

Kora watches the config file, and every file it includes, on a virtual thread named
`config-reload`. Once a second it compares each tracked file's modification time and symlink
target; a graph refresh is triggered only when one of them changed, or when the refreshed config
adds or drops an included file — an idle config file never causes a refresh. The refresh rebuilds
only the components whose config value actually changed (see
[kora-di-runtime](../../kora-di-runtime/references/runtime-graph-api-reference.md#4-refresh)).
Disable the watcher by setting the `KORA_CONFIG_WATCHER_ENABLED` environment variable or the
`kora.config.watcher.enabled` system property to `false`.

---

## Framework config keys that changed in 2.0

These live in the same `application.conf` you are authoring, so they are part of this skill's
surface. All of them compile green and fail — or silently do nothing — at runtime.

| Kora 1.x key | Kora 2.0 key |
|---|---|
| `httpServer.publicApiHttpPort` | `httpServer.port` |
| `httpServer.privateApiHttpPort` | `httpServer.system.port` |
| `httpServer.privateApiHttpReadinessPath` | `httpServer.system.readinessPath` |
| `httpServer.privateApiHttpLivenessPath` | `httpServer.system.livenessPath` |
| `httpServer.privateApiHttpMetricsPath` | `httpServer.system.metricsPath` |
| `db { … }` | `jdbc { … }` |

```hocon
httpServer {
  port = 8080
  system.port = 8085
  telemetry.logging.enabled = true
  telemetry.metrics.enabled = true
}

jdbc {
  jdbcUrl = ${POSTGRES_JDBC_URL}
  username = ${POSTGRES_USER}
  password = ${POSTGRES_PASS}
  maxPoolSize = 10
  telemetry.metrics.enabled = true
}
```

- The 1.x flat port keys are not read in 2.0, and an unknown HOCON key is ignored without a warning,
  so each server silently falls back to its default: `HttpServerConfig.port()` = `8080` for the
  public server and `SystemHttpServerConfig.port()` = `8085` for the system server (it overrides the
  inherited value). Defaults for the system paths are `readinessPath = /system/readiness`,
  `livenessPath = /system/liveness`, `metricsPath = /metrics`. A 1.x config that used non-default
  ports therefore starts on the wrong ports with no error at all; one whose stale keys collapse onto
  a single port dies with `Address already in use`.
- `JdbcDatabaseModule` reads the section named `jdbc`. A leftover `db` block yields
  `ConfigValueException: Config expected value, but got null at path: 'ROOT.jdbc.username'` — an
  error naming a section the file does not contain.
- Telemetry defaults flipped: `metrics.enabled` and `logging.enabled` are **`false`** in 2.0
  (`tracing.enabled` stays `true`). Component metrics such as `http_server_*`, `http_client_*` and
  `db_*` never appear until each component's `telemetry.metrics.enabled` is set to `true`.

The same keys appear in HOCON embedded in test sources via
`KoraConfigModification.ofString("""…""")`. Those blocks need the same edits and are missed by any
scan that only looks at `.conf` and `.yaml` files.

---

## Common pitfalls

| Symptom | Fix |
|---|---|
| `Config expected value, but got null at path: 'ROOT.x.y'` | Required substitution or key is missing. Provide it, mark the field `@Nullable`, or give it a default. Check that the *section* was not renamed (`db` → `jdbc`). |
| `Config expected value with type 'StringValue' but received type 'ObjectValue'` | The HOCON shape does not match the declared return type. |
| `${VAR}` aborts startup | Required substitution with the variable unset. Use `${?VAR}` or the double-assign default. |
| `${VAR:default}` or `${VAR:-default}` in a `.conf` | HOCON has no inline default. Assign the key twice: literal first, `${?VAR}` second. The `:default` form works only in YAML. |
| Env override never applies | The literal was assigned *after* `${?VAR}`. Last assignment wins — put the literal first. |
| `Can't extract size number part from: 1.5Mb` | `Size` accepts whole numbers only. Use `1536Kb`. |
| `Application config source is ambiguous` | Both `config.resource` and `config.file` are set. Pick one. |
| Config not loaded at all | `application.conf` is missing from `src/main/resources/`, or a `config.resource` / `config.file` override points elsewhere. |
| Nested type not generated | The nested object type needs `@ConfigMapper`, not `@ConfigSource`. |
| Servers listen on 8080/8085 instead of the configured ports | Stale 1.x port keys are ignored and the defaults apply. Use `httpServer.port` and `httpServer.system.port`. |
| Metrics endpoint returns 200 but has no component metrics | `telemetry.metrics.enabled` defaults to `false` in 2.0. |

---

## Related

- [SKILL.md](../SKILL.md) — overview and quick start
- [config-source-reference.md](config-source-reference.md) — `@ConfigSource` vs `@ConfigMapper`,
  custom `ConfigValueMapper`, library modules, 1.x porting checklist
