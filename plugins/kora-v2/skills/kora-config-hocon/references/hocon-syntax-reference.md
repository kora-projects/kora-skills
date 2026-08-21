# HOCON Syntax & Supported Types Reference

HOCON (Human-Optimized Config Object Notation) is the recommended config format for Kora, loaded by `HoconConfigModule` from the `ru.tinkoff.kora:config-hocon` module. It is a superset of JSON with relaxed syntax, comments, substitution, and includes.

## Contents

- [Values](#values)
- [Objects, paths, and arrays](#objects-paths-and-arrays)
- [Comments](#comments)
- [Environment variable substitution](#environment-variable-substitution)
- [Value references and string concatenation](#value-references-and-string-concatenation)
- [Includes](#includes)
- [Supported value types](#supported-value-types)
- [The Size type](#the-size-type)
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
/* block
   comment */
```

---

## Environment variable substitution

Resolved before mapping into the config interface.

```hocon
app {
  required   = ${APP_URL}      # required: startup fails if APP_URL is unset
  optional   = ${?APP_URL}     # optional: key omitted if APP_URL is unset
  withDefault = 8080           # default-then-override:
  withDefault = ${?APP_PORT}   #   keeps 8080 unless APP_PORT is set
}
```

The default-then-override idiom assigns the literal first, then re-assigns with `${?VAR}`. Because `${?VAR}` is dropped when the variable is unset, the literal survives. Use this for every value that has a sane local default but must be overridable in deployment.

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

---

## Includes

```hocon
include "database.conf"             # sibling file
include classpath("defaults.conf")  # from the classpath
include file("/etc/app/overrides.conf")
```

`reference.conf` (library defaults) is merged first, then `application.conf` is overlaid on top.

---

## Supported value types

`@ConfigSource` / `@ConfigValueExtractor` map these out of the box:

- `boolean`/`Boolean`, `short`/`Short`, `int`/`Integer`, `long`/`Long`, `double`/`Double`, `float`/`Float`, `double[]`
- `String`, `BigInteger`, `BigDecimal`, `UUID`, `Pattern`, `Properties`
- `Period`, `Duration`, `Size`
- `LocalDate`, `LocalTime`, `LocalDateTime`, `OffsetTime`, `OffsetDateTime`
- any `enum` (matched via its `toString()`)
- `List<T>`, `Set<T>`, `Map<K,V>`, `Either<A,B>` where the element/value types are any of the above
- nested objects and lists of objects via `@ConfigValueExtractor`

Extend the set with a custom `ConfigValueExtractor<T>` component.

### Examples

```java
import java.time.*;
import java.util.*;
import java.util.regex.Pattern;
import ru.tinkoff.kora.config.common.Size;
import ru.tinkoff.kora.config.common.annotation.ConfigSource;

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

A list or set can be written either as an array or as a comma-separated string — both map to the same collection.

---

## The Size type

`ru.tinkoff.kora.config.common.Size` parses human-friendly byte sizes by both the binary (IEEE 1541-2002) and decimal (SI) standards. There is no `DataSize` type in Kora.

| Value | Bytes |
|---|---|
| `1Mb` | 1,000,000 (decimal megabyte) |
| `1Mib` | 1,048,576 (binary mebibyte) |
| `1024b` | 1024 |
| `1024` | 1024 (a bare number means bytes) |

---

## Common pitfalls

| Symptom | Fix |
|---|---|
| `${VAR}` aborts startup | Required substitution with the variable unset. Use `${?VAR}` or a default-then-override. |
| Type mismatch on map | HOCON auto-converts strings to numbers/booleans, but the interface return type must match the intended type. |
| Nested type not generated | The nested object interface needs `@ConfigValueExtractor`, not `@ConfigSource`. |
| Config not loaded | `application.conf` missing from `src/main/resources/`, or a `config.resource`/`config.file` override points elsewhere. |

---

## Related

- [SKILL.md](../SKILL.md) — overview and quick start
- [config-source-reference.md](config-source-reference.md) — `@ConfigSource` vs `@ConfigValueExtractor` patterns
