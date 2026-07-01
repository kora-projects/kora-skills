# Flyway Migration Reference

Kora module `FlywayJdbcDatabaseModule`, artifact `ru.tinkoff.kora:database-flyway`,
config class `FlywayConfig`. Requires the JDBC module (`database-jdbc`).

## Contents

- [Configuration](#configuration)
- [Script naming](#script-naming)
- [Directory layout and multiple locations](#directory-layout-and-multiple-locations)
- [Transactional vs mixed](#transactional-vs-mixed)
- [Native Flyway options via configurationProperties](#native-flyway-options-via-configurationproperties)
- [Checksum and failure recovery](#checksum-and-failure-recovery)
- [Testing](#testing)

---

## Configuration

Full `FlywayConfig` surface with defaults:

```hocon
flyway {
  enabled              = true             // (1)
  locations            = ["db/migration"] // (2)
  executeInTransaction = true             // (3)
  validateOnMigrate    = true             // (4)
  mixed                = false            // (5)
  configurationProperties {}              // (6)
}
```

1. Run migrations when the application starts. `false` disables them entirely.
2. Classpath directories holding migration scripts.
3. Wrap each migration in a transaction.
4. Verify checksums of already-applied scripts before migrating; a mismatch fails the run.
5. Allow mixing transactional and non-transactional statements in one run — see below.
6. Raw key/value map forwarded to `Flyway#configurationProperties` for options not surfaced as typed keys.

YAML form:

```yaml
flyway:
  enabled: true
  locations: ["db/migration"]
  executeInTransaction: true
  validateOnMigrate: true
  mixed: false
  configurationProperties: {}
```

---

## Script naming

```
V<version>__<description>.sql
```

```
V1__initial_schema.sql
V1.1__add_users_table.sql
V2__add_user_roles.sql
V2.1__add_email_index.sql
```

Rules:

1. Version numbers must be unique and are applied in ascending order.
2. Never modify an applied script — its checksum is recorded; add a new version instead.
3. The description is separated by a double underscore.
4. The Kora module applies SQL scripts (`.sql`); the file lives on the classpath under a `locations` directory.

---

## Directory layout and multiple locations

```
src/main/resources/
└── db/
    └── migration/
        ├── V1__initial_schema.sql
        ├── V2__add_user_roles.sql
        └── V3__add_audit_columns.sql
```

Several directories can be listed; scripts merge and execute in global version order:

```hocon
flyway {
  locations = ["db/migration/common", "db/migration/postgresql"]
}
```

---

## Transactional vs mixed

By default each migration runs in a transaction; any failing statement rolls the
whole script back:

```sql
-- V1__create_tables.sql
CREATE TABLE users (
    id    BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    email VARCHAR(255) NOT NULL
);
CREATE INDEX idx_users_email ON users(email);
```

Some statements cannot run inside a transaction (PostgreSQL, Aurora PostgreSQL,
SQL Server, SQLite) — most commonly `CREATE INDEX CONCURRENTLY`. Set
`flyway.mixed = true`; the entire run then executes **without** a transaction:

```hocon
flyway { mixed = true }
```

```sql
-- V2__concurrent_index.sql
CREATE INDEX CONCURRENTLY idx_users_created ON users(created_at);
```

There is no per-script comment switch in the Kora module — transactional behavior
is governed by `executeInTransaction` and `mixed` in config.

---

## Native Flyway options via configurationProperties

Options the Kora `FlywayConfig` does not expose as typed keys are passed through
`configurationProperties` exactly as Flyway names them:

```hocon
flyway {
  configurationProperties {
    flyway.defaultSchema = "public"
  }
}
```

---

## Checksum and failure recovery

**"Validation failed. Checksum changed"** — an applied script was edited after it
ran. Do not edit applied scripts. Recover out-of-process with the Flyway Gradle
plugin / CLI (`flywayRepair` / `flyway repair`) to realign the history table, then
add new versioned scripts going forward. Disabling `validateOnMigrate` masks the
problem and is not advised for production.

**Migration failed mid-run** — fix the SQL, repair the failed state
out-of-process, then re-run. With `executeInTransaction = true` a failed
transactional script leaves no partial schema; with `mixed = true` it may.

---

## Testing

Use the Testcontainers extension `io.goodforgod:testcontainers-extensions-postgres`,
which runs the same `db/migration` scripts against a disposable container (this is
the `kora-java-crud` pattern):

```java
@TestcontainersPostgreSQL(
        network = @Network(shared = true),
        mode = ContainerMode.PER_RUN,
        migration = @Migration(
                engine = Migration.Engines.FLYWAY,
                apply  = Migration.Mode.PER_METHOD,
                drop   = Migration.Mode.PER_METHOD))
@KoraAppTest(Application.class)
class UserRepositoryTest implements KoraAppTestConfigModifier {

    @ConnectionPostgreSQL
    private JdbcConnection connection;
}
```

`apply = PER_METHOD` / `drop = PER_METHOD` recreate a clean schema for each test.

---

## Related

- [../SKILL.md](../SKILL.md) — overview and quick start
- [liquibase-migration-reference.md](liquibase-migration-reference.md) — Liquibase alternative
