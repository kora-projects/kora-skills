# Connection Pool Reference (HikariCP)

**Applies to:** Kora 2.x (`io.koraframework:database-jdbc`, HikariCP `7.1.0` transitively)

The pool is `JdbcDataSource`, a `Lifecycle` component that wraps a `HikariDataSource` and also
implements `JdbcExecutor`. It is configured through the **`jdbc`** section of `JdbcDatabaseConfig`
(renamed from `db` in 1.x). Durations are HOCON strings (`"10s"`), never millisecond integers. Full
key list: [database-jdbc-config-reference.md](database-jdbc-config-reference.md).

## Contents

- [Pool keys](#pool-keys)
- [Startup behaviour](#startup-behaviour)
- [Tuning by workload](#tuning-by-workload)
- [Leak detection](#leak-detection)
- [Pool metrics](#pool-metrics)
- [Settings Kora does not expose](#settings-kora-does-not-expose)
- [Troubleshooting](#troubleshooting)

---

## Pool keys

| Key | Default | Meaning |
|-----|---------|---------|
| `maxPoolSize` | `10` | maximum connections in the pool |
| `minIdle` | `0` | minimum ready idle connections |
| `connectionTimeout` | `10s` | max wait to acquire a connection |
| `validationTimeout` | `5s` | max wait to validate a connection |
| `idleTimeout` | `10m` | idle time before a connection is retired |
| `maxLifetime` | `15m` | maximum connection lifetime |
| `leakDetectionThreshold` | `0s` | warn when a connection is held this long; `0s` = off |
| `initializationFailTimeout` | *(unset)* | when set, validate one connection at startup within this budget |
| `readinessProbe` | `false` | include the pool in the readiness probe |
| `schema` | *(unset)* | connection schema |
| `dsProperties` | `{}` | passthrough driver `dataSourceProperties` |

These are Kora config keys, not raw Hikari property names — `JdbcDatabaseConfig.toHikariConfig`
translates them.

---

## Startup behaviour

`JdbcDataSource` always sets Hikari's own `initializationFailTimeout` to `-1`, i.e. Hikari never
blocks on startup by itself. Kora's `initializationFailTimeout` key drives a separate check in
`init()`:

- **Set** — one connection is opened and `isValid(...)` is called within the budget. Failure aborts
  graph initialisation with
  `IllegalStateException: JdbcDataSource pool '<name>' failed to start due to: …; check database
  availability, credentials, JDBC URL, and driver configuration`.
- **Unset** (the default) — the check is skipped entirely and the log line says so at DEBUG. The
  service comes up green with an unreachable database and fails on the first query instead.

Set it for anything with a deployment health gate. `readinessProbe = true` additionally keeps the
pool's health in `/system/readiness`.

Shutdown closes the pool in `release()`, logging how long it took.

---

## Tuning by workload

Size `maxPoolSize` against the database's connection budget, not against request concurrency. On
virtual threads the number of in-flight requests is no longer bounded by a thread pool, so the
JDBC pool becomes the real concurrency limit for database work — that is the point, not a problem
to configure away. A small pool of busy connections beats a large idle one.

```hocon
# Low traffic (dev / internal tools)
jdbc { maxPoolSize = 5,  minIdle = 1,  idleTimeout = "5m",  maxLifetime = "20m" }

# Medium traffic (production microservice)
jdbc { maxPoolSize = 20, minIdle = 5,  idleTimeout = "10m", maxLifetime = "30m" }

# High traffic
jdbc { maxPoolSize = 50, minIdle = 10, idleTimeout = "15m", maxLifetime = "30m" }
```

Keep `maxLifetime` comfortably below any connection age limit enforced by the database or a proxy
(PgBouncer, RDS Proxy), so Hikari retires connections before they are cut.

Sum `maxPoolSize` across every replica **and** every pool when a service has more than one — the
database sees the total.

**Never set `maxPoolSize = 1` when in-app migrations are enabled.** Flyway takes *two* connections
— one for the migration, one for schema management — so a single-connection pool starves the
interceptor during graph initialisation: startup stalls until `connectionTimeout` elapses and then
fails there, pointing at the pool rather than at the migration. Kora's own interceptor test pins
`maxPoolSize = 2` for exactly this reason. Two is the floor whenever `database-flyway` is on the
graph, even for a strictly single-threaded service.

---

## Leak detection

```hocon
jdbc.leakDetectionThreshold = "30s"
```

A non-zero value makes Hikari log a stack trace when a connection is held longer than the
threshold. In Kora, `@Query` methods and `inTx(...)` return connections for you, so a leak almost
always traces back to `executor().acquireConnection()` used without try-with-resources — that
method hands over ownership. `withConnection` / `withContext` / `inTx` do not.

Long transactions look like leaks at first: a slow `inTx` block that calls an external service
holds its connection the whole time. Move remote I/O outside the transaction before raising the
threshold.

---

## Pool metrics

`telemetry.metrics.driverMetrics` defaults to `true`, but it only produces anything when
`telemetry.metrics.enabled = true` **and** a `MeterRegistry` is on the graph. Otherwise Kora hands
Hikari a no-op registry and the pool gauges never appear:

```hocon
jdbc.telemetry.metrics {
    enabled = true          # default false in Kora 2.0
    driverMetrics = true
}
```

Wire `micrometer-module` (and an exporter) into `@KoraApp` for the registry itself.

---

## Settings Kora does not expose

Two different escape hatches, for two different targets.

**Driver properties → `dsProperties`.** `JdbcDatabaseConfig.toHikariConfig` passes the map to
`HikariConfig.setDataSourceProperties(...)`, so it reaches the **JDBC driver**, not the pool:

```hocon
jdbc.dsProperties {
    ApplicationName = "kora-service"
    prepareThreshold = "0"
}
```

A Hikari pool setting placed there — `keepaliveTime`, for example — is handed to the driver as an
unknown connection property and does nothing for the pool, without an error.

**Pool settings → `Configurer<HikariConfig>`.** For Hikari settings `JdbcDatabaseConfig` has no key
for (`keepaliveTime` and the like), contribute a `Configurer<HikariConfig>` component
(`io.koraframework.common.Configurer`). `JdbcDatabaseFactoryModule.jdbcDataSource(...)` takes it as
`@Tag(Tag.Factory.class) @Nullable Configurer<HikariConfig>`, and `Tag.Factory` resolves to the tag
of the enclosing `@FactoryModule` method. The default `JdbcDatabaseModule.jdbcDatabase()` factory is
untagged, so an **untagged** configurer — a `@Component` or a plain module method — configures the
primary `jdbc` pool, and a `@Tag(OtherDatabase.class)` one configures a second pool declared through
a `@Tag(OtherDatabase.class) @FactoryModule`:

```java
@KoraApp
public interface Application extends HoconConfigModule, JdbcDatabaseModule {

    default Configurer<HikariConfig> hikariConfigurer() {
        return hikari -> {
            hikari.setKeepaliveTime(Duration.ofMinutes(2).toMillis());
            return hikari;   // the returned config is the one used
        };
    }
}
```

The configurer runs last, after every first-class key has been applied, so it can also override
them. `JdbcDataSource` fixes `autoCommit = true` and `registerMbeans = false` before it runs — leave
`autoCommit` alone, transaction handling depends on it.

Do not build a `HikariDataSource` by hand. `JdbcDataSource` owns pool lifecycle, telemetry, the
readiness probe and the scoped connection that makes `inTx` work.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `Connection is not available, request timed out` | pool exhausted | shorten transactions, remove external calls from `inTx`, then raise `maxPoolSize` |
| Startup succeeds with the database down | `initializationFailTimeout` unset | set it (e.g. `"10s"`) |
| `IllegalStateException: JdbcDataSource pool '…' failed to start` | credentials / URL / network / driver | check `jdbcUrl`, credentials and that the driver artifact is on the classpath |
| `ClassNotFoundException: org.postgresql.Driver` | driver not declared | add the JDBC driver dependency — `database-jdbc` does not bundle one |
| `connectionTimeout` appears ignored | given as a number | durations are strings: `"10s"` |
| `ConfigValueException: … null at path: 'ROOT.jdbc.username'` | config still under `db { }` | rename the section to `jdbc` — including HOCON embedded in tests |
| No `db_*` or Hikari pool metrics | `telemetry.metrics.enabled` defaults to `false` | enable it explicitly, and put a `MeterRegistry` on the graph |
| Possible-leak stack traces | connection held too long | look for `acquireConnection()` without try-with-resources, or a long transaction |
| Startup stalls, then `Connection is not available, request timed out`, before any query runs | `maxPoolSize = 1` with in-app Flyway, which needs two connections | raise `maxPoolSize` to at least 2, or migrate out of process |
| Connections dropped by a proxy | `maxLifetime` above the proxy's limit | lower `maxLifetime` |
| `keepaliveTime` (or another Hikari pool setting) in `jdbc.dsProperties` has no effect | `dsProperties` are driver properties (`HikariConfig.setDataSourceProperties`), not pool settings | set it in a `Configurer<HikariConfig>` component — see [Settings Kora does not expose](#settings-kora-does-not-expose) |

---

## See also

- [database-jdbc-config-reference.md](database-jdbc-config-reference.md) — full key list, drivers, telemetry, YAML
- [transactions-reference.md](transactions-reference.md) — transaction boundaries and connection scope
- [repository-pattern-reference.md](repository-pattern-reference.md#multiple-databases) — wiring a second pool
