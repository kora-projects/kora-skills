# JDBC Configuration Reference

**Source:** `.kora-agent/kora-docs/mkdocs/docs/en/documentation/database-jdbc.md` ("Configuration")
**Examples:** `.kora-agent/kora-examples/examples/java/kora-java-database-jdbc/src/main/resources/application.conf`
**Module:** `ru.tinkoff.kora:database-jdbc` (HikariCP connection pool)

All keys live under the `db` section and are read into `JdbcDatabaseConfig`. Time values are **HOCON durations** (`"10s"`, `"10m"`), not millisecond numbers.

## Contents

- [Full configuration](#full-configuration)
- [Key reference](#key-reference)
- [YAML form](#yaml-form)
- [Database drivers](#database-drivers)
- [Telemetry](#telemetry)
- [Environment variables](#environment-variables)

---

## Full configuration

```hocon
db {
    jdbcUrl = ${POSTGRES_JDBC_URL}        // required
    username = ${POSTGRES_USER}           // required
    password = ${POSTGRES_PASS}           // required
    poolName = "kora"                     // required: Hikari pool name
    schema = "public"                     // optional connection schema
    maxPoolSize = 10
    minIdle = 0
    connectionTimeout = "10s"
    validationTimeout = "5s"
    idleTimeout = "10m"
    maxLifetime = "15m"
    leakDetectionThreshold = "0s"         // 0 = disabled
    initializationFailTimeout = "0s"
    readinessProbe = false                // include pool in the readiness probe
    dsProperties {                        // extra driver dataSourceProperties
        hostRecheckSeconds = "2"
    }
    telemetry {
        logging.enabled = false           // default false
        metrics {
            enabled = true                // default true
            slo = [1, 10, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000, 30000, 60000, 90000]
        }
        tracing.enabled = true            // default true
    }
}
```

---

## Key reference

| Key | Meaning |
|-----|---------|
| `jdbcUrl` | JDBC connection URL (**required**) |
| `username` / `password` | credentials (**required**) |
| `poolName` | Hikari connection-set name (**required**) |
| `schema` | connection schema |
| `maxPoolSize` | max connections in the pool |
| `minIdle` | min ready connections kept idle |
| `connectionTimeout` | max time to acquire a connection |
| `validationTimeout` | max time to validate a connection |
| `idleTimeout` | max idle time before a connection is retired |
| `maxLifetime` | max lifetime of a connection |
| `leakDetectionThreshold` | log a leak if a connection is held this long (`0s` = off) |
| `initializationFailTimeout` | max wait for pool init at startup |
| `readinessProbe` | enable the readiness probe for this pool |
| `dsProperties` | passthrough driver `dataSourceProperties` (e.g. isolation, host recheck) |
| `telemetry.logging.enabled` | module logging (default `false`) |
| `telemetry.metrics.enabled` | module metrics (default `true`) |
| `telemetry.metrics.slo` | SLO buckets for the query DistributionSummary |
| `telemetry.tracing.enabled` | module tracing (default `true`) |

There is no `db.namingStrategy` key — entity naming is controlled by `@NamingStrategy`/`@Column` (see [entity-mapping-reference.md](entity-mapping-reference.md)).

---

## YAML form

With `ru.tinkoff.kora:config-yaml` instead of `config-hocon`:

```yaml
db:
  jdbcUrl: ${POSTGRES_JDBC_URL}
  username: ${POSTGRES_USER}
  password: ${POSTGRES_PASS}
  poolName: "kora"
  maxPoolSize: 10
  connectionTimeout: "10s"
  idleTimeout: "10m"
  maxLifetime: "15m"
  telemetry:
    logging:
      enabled: false
    metrics:
      enabled: true
    tracing:
      enabled: true
```

---

## Database drivers

The driver is **not** bundled — add it explicitly.

```groovy
implementation "org.postgresql:postgresql:42.7.7"          // jdbc:postgresql://host:5432/db
implementation "com.mysql:mysql-connector-j:8.3.0"         // jdbc:mysql://host:3306/db
implementation "com.oracle.database.jdbc:ojdbc11:21.9.0.0" // jdbc:oracle:thin:@host:1521:SID
```

---

## Telemetry

Database queries emit metrics, traces, and (optionally) logs through the standard Kora telemetry pipeline. Toggle each channel under `db.telemetry.*`. Wire the corresponding modules (`metrics-micrometer`, `tracing-opentelemetry`, `logging-logback`) into `@KoraApp` to export them.

```hocon
db.telemetry {
    logging.enabled = true   // log each query (default false; verbose)
    metrics.enabled = true
    tracing.enabled = true
}
```

---

## Environment variables

Externalize every credential. HOCON substitution forms: `${VAR}` (required), `${?VAR}` (optional), `${?VAR:default}`.

```hocon
db {
    jdbcUrl = ${POSTGRES_JDBC_URL}
    username = ${POSTGRES_USER}
    password = ${POSTGRES_PASS}
}
```

---

## See also

- [connection-pool-reference.md](connection-pool-reference.md) — Hikari pool tuning
- [repository-pattern-reference.md](repository-pattern-reference.md) — multiple databases via `@Tag`
