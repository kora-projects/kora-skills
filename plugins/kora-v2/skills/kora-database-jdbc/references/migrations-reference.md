# Migrations Reference (Flyway / Liquibase)

**Applies to:** Kora 2.x — `io.koraframework:database-flyway`, `io.koraframework:database-liquibase`

This page covers only what a **JDBC** repository author needs: how a migration module attaches to
the `JdbcDataSource` this skill configures, and the 2.0 details that change during a port. The
`kora-database-migration` skill owns the full surface — changelog authoring, rollbacks, Gradle
plugins, CI strategy.

> Full skill: [`kora-database-migration`](../../kora-database-migration/SKILL.md)

## Contents

- [How it attaches](#how-it-attaches)
- [Flyway](#flyway)
- [Liquibase](#liquibase)
- [Migration files](#migration-files)
- [Running migrations out of process](#running-migrations-out-of-process)
- [What changed from 1.x](#what-changed-from-1x)

---

## How it attaches

Both modules install a `GraphInterceptor<JdbcDataSource>`. The interceptor's `afterInit` runs
**after** the pool is initialised and **before** anything that depends on it, so repositories never
see a pre-migration schema. There is no separate datasource, no second pool, and no ordering
annotation to get right: adding the module to `@KoraApp` is the whole wiring.

Because it hangs off `JdbcDataSource`, the migration inherits the `jdbc` section's URL,
credentials and pool — do not repeat them under `flyway` / `liquibase`.

---

## Flyway

```groovy
implementation "io.koraframework:database-flyway"
// database-flyway ships flyway-core only; the dialect artifact is the application's job
implementation "org.flywaydb:flyway-database-postgresql:13.9.0"
```

Without the dialect artifact, Flyway 10+ fails at startup with `Unsupported Database: PostgreSQL`.
Kora's catalog pins Flyway `13.9.0`; keep `flyway-core` and the dialect on the same version.

**The pool needs at least two connections.** Flyway uses one connection for the migration and a
second for schema management, so `jdbc.maxPoolSize = 1` starves the interceptor during graph
initialisation — startup stalls until `connectionTimeout` and then fails on the pool, not on the
migration. Kora's own interceptor test pins `maxPoolSize = 2` for this reason.

```java
@KoraApp
public interface Application extends
        HoconConfigModule,
        LogbackModule,
        JdbcDatabaseModule,
        FlywayJdbcDatabaseModule { }
```

```hocon
flyway {
    enabled = true                       // default true
    mode = MIGRATE                       // MIGRATE (default) | REPAIR | CLEAN_MIGRATE
    locations = ["db/migration"]         // default ["db/migration"]
    executeInTransaction = true
    validateOnMigrate = true
    mixed = false
    configurationProperties {            // raw Flyway properties passthrough
        flyway.defaultSchema = "public"
    }
}
```

`FlywayJdbcDatabaseModule` wires `new FlywayFactoryModule("flyway")`, so the section name is
`flyway`. `CLEAN_MIGRATE` drops the schema before migrating — never enable it outside a
throwaway environment.

## Liquibase

```groovy
implementation "io.koraframework:database-liquibase"
```

```java
@KoraApp
public interface Application extends
        HoconConfigModule,
        LogbackModule,
        JdbcDatabaseModule,
        LiquibaseJdbcDatabaseModule { }
```

```hocon
liquibase {
    changelog = "db/changelog/db.changelog-master.xml"   // this is the default
}
```

`LiquibaseJdbcDatabaseModule` wires `new LiquibaseFactoryModule("liquibase")`. Kora's catalog pins
Liquibase `5.0.4`.

---

## Migration files

Flyway, `src/main/resources/db/migration/`, named `V<version>__<description>.sql`:

```
db/migration/
├── V1__init_schema.sql
├── V1_1__add_users_table.sql
└── V2__add_indexes.sql
```

```sql
-- V1__init_schema.sql
CREATE TABLE users (
    id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    email      VARCHAR(255) NOT NULL UNIQUE,
    first_name VARCHAR(255) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);
```

Keep the column names in step with the entity's naming strategy — `snake_lower_case` by default,
so `firstName` needs a `first_name` column unless the field carries `@Column`. See
[entity-mapping-reference.md](entity-mapping-reference.md#naming-strategy).

Liquibase uses `src/main/resources/db/changelog/`, XML by default (`db.changelog-master.xml`);
point `changelog` elsewhere for YAML or JSON.

---

## Running migrations out of process

Migrating on startup races when several replicas start together, and it couples schema changes to
deployment. For anything horizontally scaled, run migrations as their own step — the Flyway Gradle
plugin, a Flyway container in `docker-compose`, a Kubernetes `Job`, or a CI stage — and set
`flyway.enabled = false` in the service. Kora's module is the convenient path for local
development, tests and single-instance services.

Integration tests are the exception where startup migration shines: the Testcontainers extensions
used by the migrated examples apply Flyway migrations per test method against a throwaway database.

---

## What changed from 1.x

| 1.x | 2.0 |
|-----|-----|
| `ru.tinkoff.kora:database-flyway` / `-liquibase` | `io.koraframework:database-flyway` / `-liquibase` |
| `ru.tinkoff.kora.database.flyway.FlywayJdbcDatabaseModule` | `io.koraframework.database.flyway.FlywayJdbcDatabaseModule` |
| The datasource the interceptor wraps was configured under `db { }` | it is configured under **`jdbc { }`** |
| — | Flyway `13.9.0` needs a separate dialect artifact (`flyway-database-postgresql`) |

The `flyway` and `liquibase` section names themselves did not change.

---

## See also

- [`kora-database-migration`](../../kora-database-migration/SKILL.md) — the full migration skill
- [database-jdbc-config-reference.md](database-jdbc-config-reference.md) — the `jdbc` section the migration reuses
- [entity-mapping-reference.md](entity-mapping-reference.md) — column naming that the schema must match
