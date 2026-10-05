# JDBC Configuration Reference

**Applies to:** Kora 2.x (`io.koraframework:database-jdbc`, HikariCP `7.1.0`)

Every key lives under the **`jdbc`** section and is read into
`io.koraframework.database.jdbc.JdbcDatabaseConfig`. Time values are HOCON durations (`"10s"`,
`"10m"`), never millisecond numbers.

## Contents

- [The section was renamed](#the-section-was-renamed)
- [Full configuration](#full-configuration)
- [Key reference](#key-reference)
- [Telemetry](#telemetry)
- [YAML form](#yaml-form)
- [Database drivers](#database-drivers)
- [Environment variables](#environment-variables)
- [Test configuration](#test-configuration)
- [A second database](#a-second-database)

---

## The section was renamed

Kora 1.x read this configuration from `db { … }`. Kora 2.0 reads it from **`jdbc { … }`** —
`JdbcDatabaseModule` wires `new JdbcDatabaseFactoryModule("jdbc")`.

A leftover `db { }` block is not a config error: HOCON simply carries an unrecognised section, the
build stays green, and the application dies during graph initialisation with

```
ConfigValueException: Config expected value, but got null at path: 'ROOT.jdbc.username'
```

which names a section your file does not contain. If you see that message, look for `db { }`, not
for a typo under `jdbc`.

---

## Full configuration

```hocon
jdbc {
    jdbcUrl = ${POSTGRES_JDBC_URL}        // required
    username = ${POSTGRES_USER}           // required
    password = ${POSTGRES_PASS}           // required
    poolName = "kora"                     // required — also the telemetry pool label
    schema = "public"                     // optional connection schema

    maxPoolSize = 10
    minIdle = 0
    connectionTimeout = "10s"
    validationTimeout = "5s"
    idleTimeout = "10m"
    maxLifetime = "15m"
    leakDetectionThreshold = "0s"         // 0s = disabled
    initializationFailTimeout = "10s"     // omit to skip the startup connectivity check
    readinessProbe = false

    dsProperties {                        // passed through to Hikari dataSourceProperties
        ApplicationName = "kora-service"
    }

    telemetry {
        logging.enabled = true            // default false
        metrics {
            enabled = true                // default false
            driverMetrics = true          // default true — Hikari pool metrics
        }
        tracing.enabled = true            // default true
    }
}
```

---

## Key reference

| Key | Type | Default | Meaning |
|-----|------|---------|---------|
| `jdbcUrl` | string | **required** | JDBC connection URL |
| `username` | string | **required** | database user |
| `password` | string | **required** | database password |
| `poolName` | string | **required** | Hikari pool name; also the `pool` label on database telemetry |
| `schema` | string | `null` | connection schema |
| `maxPoolSize` | int | `10` | maximum connections in the pool |
| `minIdle` | int | `0` | minimum ready idle connections |
| `connectionTimeout` | duration | `10s` | max wait to acquire a connection from the pool |
| `validationTimeout` | duration | `5s` | max wait for connection validation |
| `idleTimeout` | duration | `10m` | idle time before a connection is retired |
| `maxLifetime` | duration | `15m` | maximum connection lifetime |
| `leakDetectionThreshold` | duration | `0s` | log a stack trace when a connection is held this long; `0s` disables |
| `initializationFailTimeout` | duration | **`null`** | when set, the pool opens and validates one connection at startup within this budget; when absent the check is **skipped entirely** |
| `readinessProbe` | boolean | `false` | include this pool in the readiness probe |
| `dsProperties` | object | `{}` | passed verbatim to Hikari `dataSourceProperties` — JDBC driver properties, not pool settings |
| `telemetry.*` | object | see below | logging / metrics / tracing |

`initializationFailTimeout` deserves attention when porting: it has **no default**. Leave it out and
the service starts even when the database is unreachable, failing later on the first query. Set it
(the migrated examples use `"10s"`) to fail fast at startup with

```
IllegalStateException: JdbcDataSource pool 'kora' failed to start due to: …;
check database availability, credentials, JDBC URL, and driver configuration
```

Kora does **not** expose every Hikari knob as a first-class key. JDBC **driver** properties go
through `dsProperties` (Hikari `dataSourceProperties`); Hikari **pool** settings without a key, such
as `keepaliveTime`, go through a `Configurer<HikariConfig>` component — in `dsProperties` they reach
the driver and do nothing. See
[connection-pool-reference.md](connection-pool-reference.md#settings-kora-does-not-expose).

---

## Telemetry

`jdbc.telemetry` maps to `DatabaseTelemetryConfig`, which extends the shared `TelemetryConfig`:

| Key | Default | Notes |
|-----|---------|-------|
| `telemetry.logging.enabled` | **`false`** | logs each query |
| `telemetry.metrics.enabled` | **`false`** | query duration metrics |
| `telemetry.metrics.driverMetrics` | `true` | hands the Micrometer registry to Hikari for pool metrics — only takes effect when `metrics.enabled` is on |
| `telemetry.metrics.slo` | 1…90000 ms buckets | SLO buckets for the query timer |
| `telemetry.metrics.tags` | `{}` | extra tags on every metric from this module |
| `telemetry.tracing.enabled` | `true` | query spans |
| `telemetry.tracing.attributes` | `{}` | extra attributes on every span |

**Logging and metrics default to `false` in Kora 2.0.** A service that showed `db_*` metrics under
1.x will silently stop reporting them after a migration unless the config turns them on:

```hocon
jdbc.telemetry {
    logging.enabled = true
    metrics.enabled = true
}
```

Nothing warns about this — the metrics endpoint answers `200` with the metric simply absent. The
exporters themselves still have to be on the graph (`micrometer-module`, `opentelemetry-tracing`,
`logging-logback`).

---

## YAML form

With `io.koraframework:config-yaml` and `YamlConfigModule` instead of the HOCON pair:

```yaml
jdbc:
  jdbcUrl: ${POSTGRES_JDBC_URL}
  username: ${POSTGRES_USER}
  password: ${POSTGRES_PASS}
  poolName: "kora"
  maxPoolSize: 10
  connectionTimeout: "10s"
  idleTimeout: "10m"
  maxLifetime: "15m"
  initializationFailTimeout: "10s"
  telemetry:
    logging:
      enabled: true
    metrics:
      enabled: true
    tracing:
      enabled: true
```

---

## Database drivers

The driver is **not** bundled with `database-jdbc` — add it explicitly.

```groovy
implementation "org.postgresql:postgresql:42.7.7"          // jdbc:postgresql://host:5432/db
implementation "com.mysql:mysql-connector-j:9.2.0"         // jdbc:mysql://host:3306/db
implementation "com.oracle.database.jdbc:ojdbc11:23.7.0.25.01" // jdbc:oracle:thin:@host:1521:SID
```

The Kora build tests against PostgreSQL `42.7.13`; the migrated example applications pin `42.7.7`
and the guides pin `42.7.3`. Any recent `42.7.x` works — pick the newest patch your organisation
allows. MySQL and Oracle versions are your choice; Kora constrains neither through the BOM.

`io.koraframework:database-jdbc-postgres` is the exception: it declares `org.postgresql:postgresql`
(`42.7.13`) as an `api` dependency, so a service on that module needs no separate driver line.

`JdbcDataSource` derives the telemetry "database" label from the URL scheme
(`jdbc:postgresql:…` → `postgresql`), so a malformed `jdbcUrl` fails during construction rather
than on first use.

---

## Environment variables

Externalise every credential. HOCON substitution forms: `${VAR}` (required, fails if absent),
`${?VAR}` (optional, key stays unset), and `key = default` followed by `key = ${?VAR}` to override.

```hocon
jdbc {
    jdbcUrl = ${POSTGRES_JDBC_URL}
    username = ${POSTGRES_USER}
    password = ${POSTGRES_PASS}
    poolName = "kora"
    maxPoolSize = 10
    maxPoolSize = ${?DB_MAX_POOL_SIZE}
}
```

---

## Test configuration

The same section name applies inside test sources. A `@KoraAppTest` supplies config through
`KoraConfigModification`, and HOCON written inline there is **not** covered by any scan that only
reads `.conf` / `.yaml` files:

```java
@Override
public KoraConfigModification config() {
    return KoraConfigModification.ofString("""
            jdbc {
              jdbcUrl = ${POSTGRES_JDBC_URL}
              username = ${POSTGRES_USER}
              password = ${POSTGRES_PASS}
              poolName = "kora-jdbc-test"
            }
            """)
            .withSystemProperty("POSTGRES_JDBC_URL", connection.params().jdbcUrl())
            .withSystemProperty("POSTGRES_USER", connection.params().username())
            .withSystemProperty("POSTGRES_PASS", connection.params().password());
}
```

When the application's own `application.conf` already reads those variables, the test can skip the
inline HOCON entirely and just set the properties:

```java
return KoraConfigModification.ofSystemProperty("POSTGRES_JDBC_URL", connection.params().jdbcUrl())
        .withSystemProperty("POSTGRES_USER", connection.params().username())
        .withSystemProperty("POSTGRES_PASS", connection.params().password());
```

---

## A second database

Nest the second pool's keys under any path and point a tagged `@FactoryModule` at it:

```hocon
jdbc {
    jdbcUrl = ${POSTGRES_JDBC_URL}
    username = ${POSTGRES_USER}
    password = ${POSTGRES_PASS}
    poolName = "primary"

    other {
        jdbcUrl = ${REPORTING_JDBC_URL}
        username = ${REPORTING_USER}
        password = ${REPORTING_PASS}
        poolName = "reporting"
    }
}
```

The graph wiring is in
[repository-pattern-reference.md](repository-pattern-reference.md#multiple-databases).

---

## See also

- [connection-pool-reference.md](connection-pool-reference.md) — pool sizing and leak detection
- [repository-pattern-reference.md](repository-pattern-reference.md) — repositories and macros
- [transactions-reference.md](transactions-reference.md) — `executor().inTx(...)`
