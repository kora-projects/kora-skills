# Connection Pool Reference (HikariCP)

**Source:** `.kora-agent/kora-docs/mkdocs/docs/en/documentation/database-jdbc.md` ("Configuration")
**Module:** `ru.tinkoff.kora:database-jdbc` (HikariCP is bundled with the module)

The pool is configured through the `db` section of `JdbcDatabaseConfig`. Time values are HOCON durations (`"10s"`), never millisecond integers. For the complete key list see [database-jdbc-config-reference.md](database-jdbc-config-reference.md).

## Contents

- [Pool keys](#pool-keys)
- [Tuning by workload](#tuning-by-workload)
- [Leak detection](#leak-detection)
- [Troubleshooting](#troubleshooting)

---

## Pool keys

| Key | Default | Meaning |
|-----|---------|---------|
| `maxPoolSize` | 10 | maximum connections in the pool |
| `minIdle` | 0 | minimum ready idle connections |
| `connectionTimeout` | `10s` | max wait to acquire a connection |
| `validationTimeout` | `5s` | max wait to validate a connection |
| `idleTimeout` | `10m` | idle time before a connection is retired |
| `maxLifetime` | `15m` | max connection lifetime |
| `leakDetectionThreshold` | `0s` | warn if a connection is held this long (`0s` = off) |
| `initializationFailTimeout` | `0s` | max wait for pool initialization at startup |

These are Kora config keys, not raw Hikari property names.

---

## Tuning by workload

Right-size `maxPoolSize` to the database's connection budget, not to request concurrency — a small pool of busy connections beats a large idle one.

```hocon
# Low traffic (dev / internal tools)
db { maxPoolSize = 5,  minIdle = 1, idleTimeout = "5m",  maxLifetime = "20m" }

# Medium traffic (production microservice)
db { maxPoolSize = 20, minIdle = 5, idleTimeout = "10m", maxLifetime = "30m" }

# High traffic
db { maxPoolSize = 50, minIdle = 10, idleTimeout = "15m", maxLifetime = "30m" }
```

---

## Leak detection

Set `leakDetectionThreshold` to a non-zero duration to log a stack trace when a connection is held longer than expected. In Kora you rarely manage connections by hand — `@Query` methods and `inTx()` release them automatically — so leaks usually come from manual `Connection` use that skips try-with-resources.

```hocon
db.leakDetectionThreshold = "30s"
```

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `Connection is not available, request timed out` | pool exhausted | raise `maxPoolSize`, shorten transactions, check for leaks |
| `Connection timeout` at startup | DB unreachable | verify `jdbcUrl`/credentials/network; tune `connectionTimeout` |
| `ClassNotFoundException: org.postgresql.Driver` | missing driver | add the JDBC driver dependency |
| `connectionTimeout` ignored | value given as a number | use a duration string: `"10s"` |
| possible connection leak logged | connection held too long | wrap manual `Connection` use in try-with-resources / `inTx()` |

For a second database, do **not** hand-build a `HikariDataSource`; declare a tagged `JdbcDatabaseConfig` + `JdbcDatabase` in `@KoraApp` and tag the repository — see [repository-pattern-reference.md](repository-pattern-reference.md#multiple-databases).

---

## See also

- [database-jdbc-config-reference.md](database-jdbc-config-reference.md) — full config key list, drivers, telemetry
- [transactions-reference.md](transactions-reference.md) — transaction boundaries
