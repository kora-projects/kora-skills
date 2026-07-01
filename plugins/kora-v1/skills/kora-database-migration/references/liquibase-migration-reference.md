# Liquibase Migration Reference

Kora module `LiquibaseJdbcDatabaseModule`, artifact `ru.tinkoff.kora:database-liquibase`,
config class `LiquibaseConfig`. Requires the JDBC module (`database-jdbc`).

Liquibase is the alternative to Flyway when you need declarative rollback or
already maintain a Liquibase changelog. The formatted-SQL changelog keeps native
SQL while still supporting rollback, contexts, and labels.

## Contents

- [Configuration](#configuration)
- [Formatted SQL changelog](#formatted-sql-changelog)
- [Changeset examples](#changeset-examples)
- [Rollback](#rollback)
- [Contexts and labels](#contexts-and-labels)
- [Splitting the changelog with includes](#splitting-the-changelog-with-includes)
- [Testing](#testing)
- [Pitfalls](#pitfalls)

---

## Configuration

`LiquibaseConfig` exposes a single key — the path to the master changelog. The
default is the XML master; point it at a formatted-SQL master to use SQL instead.

```hocon
liquibase {
  changelog = "db/changelog/db.changelog-master.sql"  // default: db.changelog-master.xml
}
```

```yaml
liquibase:
  changelog: "db/changelog/db.changelog-master.sql"
```

Liquibase filtering features such as contexts and labels are declared on the
changesets and selected via Liquibase runtime parameters, not via additional Kora
config keys.

---

## Formatted SQL changelog

A formatted-SQL file must start with the marker line, then declare each change
with a `--changeset <author>:<id>` directive:

```sql
--liquibase formatted sql

--changeset developer:1
CREATE TABLE users (
    id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    email      VARCHAR(255) NOT NULL UNIQUE,
    first_name VARCHAR(100),
    last_name  VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX idx_users_email ON users(email);
--rollback DROP INDEX idx_users_email;
--rollback DROP TABLE users;

--changeset developer:2
CREATE TABLE orders (
    id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id    BIGINT NOT NULL REFERENCES users(id),
    total      DECIMAL(10,2) NOT NULL,
    status     VARCHAR(50) DEFAULT 'PENDING',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX idx_orders_user_id ON orders(user_id);
--rollback DROP TABLE orders;
```

The `<author>:<id>` pair uniquely identifies a changeset; Liquibase records it in
its `DATABASECHANGELOG` table and never re-runs it once applied.

---

## Changeset examples

```sql
--changeset developer:add-phone
ALTER TABLE users ADD COLUMN phone VARCHAR(20);
--rollback ALTER TABLE users DROP COLUMN phone;
```

```sql
--changeset developer:fk-orders-user
ALTER TABLE orders
    ADD CONSTRAINT fk_orders_user FOREIGN KEY (user_id) REFERENCES users(id);
--rollback ALTER TABLE orders DROP CONSTRAINT fk_orders_user;
```

```sql
--changeset developer:seed-roles labels:seed-data
INSERT INTO roles (id, name) VALUES (1, 'USER');
INSERT INTO roles (id, name) VALUES (2, 'ADMIN');
--rollback DELETE FROM roles WHERE id IN (1, 2);
```

```sql
--changeset developer:uuid-extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
--rollback DROP EXTENSION IF EXISTS "uuid-ossp";
```

---

## Rollback

Declare rollback statements with `--rollback`; use one directive per statement for
multi-statement rollbacks:

```sql
--changeset developer:audit
CREATE INDEX idx_audit_action ON audit_log(action);
ALTER TABLE audit_log ADD COLUMN created_at TIMESTAMP DEFAULT NOW();
--rollback ALTER TABLE audit_log DROP COLUMN created_at;
--rollback DROP INDEX idx_audit_action;
```

Rollback itself is invoked out-of-process via the Liquibase CLI / Gradle plugin
(the Kora module only runs `update` on startup):

```bash
liquibase rollbackCount 1
liquibase rollback --tag=v1.0
liquibase rollbackToDate 2024-01-01
```

---

## Contexts and labels

Attach contexts/labels to a changeset on its directive line:

```sql
--changeset developer:test-seed context:dev
INSERT INTO test_data (value) VALUES ('test-only');
--rollback DELETE FROM test_data WHERE value = 'test-only';

--changeset developer:audit-cfg context:production labels:v1.0
INSERT INTO audit_config (enabled) VALUES (true);
--rollback DELETE FROM audit_config;
```

Select which changesets run with Liquibase runtime parameters when invoking
Liquibase out-of-process (`--contexts`, `--labels`).

---

## Splitting the changelog with includes

A SQL master can reference other formatted-SQL files with `--include`:

```sql
--liquibase formatted sql

--include file:db/changelog/changes/001-initial-schema.sql
--include file:db/changelog/changes/002-orders-table.sql
```

Each included file is itself a formatted-SQL changelog beginning with
`--liquibase formatted sql`.

---

## Testing

Use the Testcontainers extension with the Liquibase engine; it runs the master
changelog against a disposable Postgres container:

```java
@TestcontainersPostgreSQL(
        network = @Network(shared = true),
        mode = ContainerMode.PER_RUN,
        migration = @Migration(
                engine = Migration.Engines.LIQUIBASE,
                apply  = Migration.Mode.PER_METHOD,
                drop   = Migration.Mode.PER_METHOD))
@KoraAppTest(Application.class)
class OrderRepositoryTest implements KoraAppTestConfigModifier {

    @ConnectionPostgreSQL
    private JdbcConnection connection;
}
```

```groovy
testImplementation "io.goodforgod:testcontainers-extensions-postgres:0.13.1"
testImplementation "org.testcontainers:junit-jupiter:1.21.4"
testImplementation "ru.tinkoff.kora:test-junit5"
```

---

## Pitfalls

| Symptom | Fix |
|---------|-----|
| Changelog ignored | First line must be `--liquibase formatted sql` |
| Change never applied / re-applied unexpectedly | Each change needs a unique `--changeset <author>:<id>` |
| Rollback does nothing | Provide `--rollback` directives; use one per statement |
| Context filter has no effect | Pass `--contexts`/`--labels` to the out-of-process Liquibase run |

---

## Related

- [../SKILL.md](../SKILL.md) — overview and quick start
- [flyway-migration-reference.md](flyway-migration-reference.md) — Flyway alternative
