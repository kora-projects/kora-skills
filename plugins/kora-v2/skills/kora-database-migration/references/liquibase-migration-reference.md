# Liquibase Migration Reference

Kora 2.0 module `io.koraframework.database.liquibase.LiquibaseJdbcDatabaseModule`, artifact
`io.koraframework:database-liquibase`, config type `LiquibaseConfig`, config section `liquibase`.
Requires `io.koraframework:database-jdbc` and `JdbcDatabaseModule` on the `@KoraApp` interface.

Bundled third-party version: **`org.liquibase:liquibase-core` 5.0.4**.

Liquibase is the alternative to Flyway when you need declarative rollback or already maintain a
Liquibase changelog. The formatted-SQL changelog keeps native SQL while still supporting rollback,
contexts, and labels.

## Contents

- [Dependencies](#dependencies)
- [Configuration](#configuration)
- [How it runs](#how-it-runs)
- [Formatted SQL changelog](#formatted-sql-changelog)
- [Changeset examples](#changeset-examples)
- [Rollback](#rollback)
- [Contexts and labels](#contexts-and-labels)
- [Splitting the changelog](#splitting-the-changelog)
- [Testing](#testing)
- [Pitfalls](#pitfalls)

---

## Dependencies

Unlike Flyway, Liquibase needs **no per-database artifact**. `org.liquibase:liquibase-core` 5.0.4 is
an aggregate that pulls in `liquibase-standard` — which carries the implementations for PostgreSQL,
MySQL/MariaDB, Oracle, SQL Server, H2 and the rest — plus `liquibase-cli` and `liquibase-snowflake`.
The framework's own `LiquibaseJdbcDataSourceInterceptorTest` migrates a real PostgreSQL container
with `liquibase-core` alone.

```groovy
dependencies {
    koraBom platform("io.koraframework:kora-bom:$koraVersion")   // koraVersion=2.0.0.RC2
    annotationProcessor "io.koraframework:annotation-processors"

    implementation "io.koraframework:database-jdbc"
    implementation "io.koraframework:database-liquibase"

    runtimeOnly "org.postgresql:postgresql:42.7.13"
}
```

```kotlin
dependencies {
    implementation(platform("io.koraframework:kora-bom:${property("koraVersion")}"))
    ksp("io.koraframework:symbol-processors:${property("koraVersion")}")

    implementation("io.koraframework:database-jdbc")
    implementation("io.koraframework:database-liquibase")

    runtimeOnly("org.postgresql:postgresql:42.7.13")
}
```

```java
@KoraApp
public interface Application extends
        HoconConfigModule,
        JdbcDatabaseModule,
        LiquibaseJdbcDatabaseModule {

    static void main(String[] args) {
        KoraApplication.run(ApplicationGraph::graph);
    }
}
```

Everything shipped with `liquibase-core` is the **Community** edition. A handful of changelog
directives are Pro-licensed and fail the parse when used without a license key — see
[Splitting the changelog](#splitting-the-changelog).

---

## Configuration

`LiquibaseConfig` exposes a **single** key — the classpath path to the master changelog:

```hocon
liquibase {
  changelog = "db/changelog/db.changelog-master.xml"   // default
}
```

```yaml
liquibase:
  changelog: "db/changelog/db.changelog-master.xml"
```

Point it at a formatted-SQL master to keep native SQL:

```hocon
liquibase {
  changelog = "db/changelog/db.changelog-master.sql"
}
```

The path is resolved through a `ClassLoaderResourceAccessor`, so it is a **classpath resource path**
relative to `src/main/resources/`, not a filesystem path. `changelog` has a default and the type is
a `@ConfigMapper` with `mapNullAsEmptyObject = true`, so the whole `liquibase` section may be
omitted — the module then runs `db/changelog/db.changelog-master.xml`.

**There is no `liquibase.enabled` key.** `LiquibaseJdbcDatabaseInterceptor.afterInit` runs `update()`
unconditionally, so config cannot switch migrations off. To move migrations out of process, remove
`LiquibaseJdbcDatabaseModule` from the `@KoraApp` interface — that is the only switch.

Liquibase filtering features (contexts, labels) are declared on the changesets and selected via
Liquibase runtime parameters on an out-of-process run; there are no additional Kora config keys for
them.

---

## How it runs

`LiquibaseJdbcDatabaseModule` contributes a `LiquibaseJdbcDatabaseInterceptor implements
GraphInterceptor<JdbcDataSource>`. The graph calls `afterInit(dataSource)` once the JDBC pool is up
and before any dependent component is constructed. The interceptor:

1. takes **one** connection from the Hikari pool (`jdbc.maxPoolSize = 1` is enough — Flyway needs
   two, Liquibase does not);
2. resolves the dialect with `DatabaseFactory.findCorrectDatabaseImplementation(...)`;
3. parses `changelog` through a `ClassLoaderResourceAccessor` and runs `update()`;
4. records applied changesets in Liquibase's `DATABASECHANGELOG` table and holds
   `DATABASECHANGELOGLOCK` for the duration.

On failure it logs `Error during Liquibase migration` and rethrows as
`IllegalStateException: Liquibase migration failed`, which aborts graph initialization and stops the
application. `LiquibaseException` and `SQLException` are both wrapped — read the cause, not the
wrapper.

Because this runs per graph, every replica migrates on every rollout. For scaled deployments see
[../SKILL.md §6](../SKILL.md#6-out-of-process-migrations-recommended-for-scaled-services).

---

## Formatted SQL changelog

A formatted-SQL file must start with the marker line, then declare each change with a
`--changeset <author>:<id>` directive:

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

The `<author>:<id>` pair uniquely identifies a changeset; Liquibase records it in `DATABASECHANGELOG`
and never re-runs it once applied.

Directives the Community formatted-SQL parser recognises: `changeset`, `rollback`, `preconditions`
and `precondition-<name>`, `comment`, `validCheckSum`, `ignoreLines`, `property`. Attributes placed
on the `--changeset` line: `contextFilter:`, `labels:`, `dbms:`, `runOnChange:`, `runAlways:`,
`runInTransaction:`, `failOnError:`, `splitStatements:`, `stripComments:`, `endDelimiter:`,
`logicalFilePath:`.

The XML changelog is the default and is the right choice when the changes are structural
(`createTable`, `addColumn`, `addForeignKeyConstraint`) rather than raw SQL:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<databaseChangeLog
    xmlns="http://www.liquibase.org/xml/ns/dbchangelog"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xsi:schemaLocation="http://www.liquibase.org/xml/ns/dbchangelog
        http://www.liquibase.org/xml/ns/dbchangelog/dbchangelog-latest.xsd">

    <changeSet id="1" author="developer">
        <createTable tableName="users">
            <column name="id" type="BIGINT">
                <constraints primaryKey="true" nullable="false"/>
            </column>
            <column name="email" type="VARCHAR(255)">
                <constraints nullable="false" unique="true"/>
            </column>
        </createTable>
    </changeSet>

</databaseChangeLog>
```

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
--changeset developer:uuid-extension runInTransaction:false
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
--rollback DROP EXTENSION IF EXISTS "uuid-ossp";
```

---

## Rollback

Declare rollback statements with `--rollback`; use one directive per statement for multi-statement
rollbacks, in reverse order of application:

```sql
--changeset developer:audit
CREATE INDEX idx_audit_action ON audit_log(action);
ALTER TABLE audit_log ADD COLUMN created_at TIMESTAMP DEFAULT NOW();
--rollback ALTER TABLE audit_log DROP COLUMN created_at;
--rollback DROP INDEX idx_audit_action;
```

The Kora interceptor only ever runs `update()`. Rollback is invoked **out-of-process** through the
Liquibase CLI, the `org.liquibase.gradle` plugin (`3.1.0`), or the `liquibase/liquibase:5.0.4`
container:

```bash
liquibase rollback-count --count=1
liquibase rollback --tag=v1.0
liquibase rollback-to-date --date=2026-01-01
```

`--rollbackSqlFile` (rollback SQL kept in a separate file) is a **Pro-only** formatted-SQL
directive; the Community parser rejects it.

---

## Contexts and labels

Attach filters to a changeset on its directive line. `contextFilter:` is the current spelling;
`context:` is still accepted as an alias and is used only when `contextFilter:` is absent.

```sql
--changeset developer:test-seed contextFilter:dev
INSERT INTO test_data (value) VALUES ('test-only');
--rollback DELETE FROM test_data WHERE value = 'test-only';

--changeset developer:audit-cfg contextFilter:production labels:v1.0
INSERT INTO audit_config (enabled) VALUES (true);
--rollback DELETE FROM audit_config;
```

Select which changesets run with Liquibase runtime parameters on an out-of-process invocation
(`--context-filter`, `--label-filter`).

**Context filters do nothing under the Kora module.** `LiquibaseJdbcDatabaseInterceptor` calls the
no-argument `liquibase.update()`, which supplies an empty runtime `Contexts`. Liquibase's
`ContextChangeSetFilter` accepts a changeset when the *provided* context expression is empty — so
with no runtime filter **every** changeset runs, including the ones marked `contextFilter:dev`.
Never rely on a context filter to keep seed or test-only data out of a production database; put such
changesets in a separate changelog that production never points `liquibase.changelog` at.

---

## Splitting the changelog

**Use an XML (or YAML/JSON) master that includes the child files.** `<include>` and `<includeAll>`
are core Community features there:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<databaseChangeLog
    xmlns="http://www.liquibase.org/xml/ns/dbchangelog"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xsi:schemaLocation="http://www.liquibase.org/xml/ns/dbchangelog
        http://www.liquibase.org/xml/ns/dbchangelog/dbchangelog-latest.xsd">

    <include file="db/changelog/changes/001-initial-schema.sql"/>
    <include file="db/changelog/changes/002-orders-table.sql"/>
</databaseChangeLog>
```

Each included `.sql` file is a formatted-SQL changelog beginning with `--liquibase formatted sql`;
Liquibase picks the parser from the extension plus that first line, so mixing an XML master with
formatted-SQL children is fully supported.

**Do not use `--include file:` inside a formatted-SQL master.** In Liquibase 5 the formatted-SQL
`include` / `includeAll` directives are **Pro-only**, and the Community parser fails the changelog:

```
ChangeLogParseException: Error parsing command line: Using 'include in Formatted SQL changelog'
requires a valid Liquibase license key.
```

Inside the Kora interceptor that surfaces as `IllegalStateException: Liquibase migration failed`
during graph initialization — the service does not start. The same gate covers `--includeAll`,
`--rollbackSqlFile` and `--tagDatabase:`.

If you want a single-file, SQL-only changelog, keep every changeset in one master and split by
`--changeset` id instead of by file.

---

## Testing

`@KoraAppTest` builds the real graph, so the Liquibase interceptor runs against the test database
and the schema exists before the first test method. Override the connection with
`KoraAppTestConfigModifier` — the datasource section is **`jdbc`**, and HOCON embedded in a test
source uses exactly the same key names as `application.conf`:

```java
@Testcontainers
@KoraAppTest(TestApplication.class)
class OrderRepositoryPostgresTest implements KoraAppTestConfigModifier {

    @Container
    static final PostgreSQLContainer<?> POSTGRES = new PostgreSQLContainer<>("postgres:16-alpine");

    @Override
    public KoraConfigModification config() {
        return KoraConfigModification.ofString("""
                jdbc {
                  jdbcUrl  = ${POSTGRES_JDBC_URL}
                  username = ${POSTGRES_USER}
                  password = ${POSTGRES_PASS}
                  poolName = "kora-test"
                }
                liquibase {
                  changelog = "db/changelog/db.changelog-master.xml"
                }
                """)
                .withSystemProperty("POSTGRES_JDBC_URL", POSTGRES.getJdbcUrl())
                .withSystemProperty("POSTGRES_USER", POSTGRES.getUsername())
                .withSystemProperty("POSTGRES_PASS", POSTGRES.getPassword());
    }
}
```

A test-only migration setup declares the module on the test configuration:

```groovy
testImplementation "io.koraframework:database-liquibase"
```

There is no `enabled = false` to reset a shared test database between runs — use a fresh container
per test class, or run `liquibase dropAll` out of process.

Container wiring and `@KoraAppTest` mechanics —
[kora-testing-junit-java](../../kora-testing-junit-java/SKILL.md) /
[kora-testing-junit-kotlin](../../kora-testing-junit-kotlin/SKILL.md).

---

## Pitfalls

| Symptom | Cause / fix |
|---|---|
| Changelog ignored, no changesets run | First line must be `--liquibase formatted sql` for a `.sql` changelog. |
| `ChangeLogParseException: … requires a valid Liquibase license key` | A Pro-only directive in a formatted-SQL file — `--include`, `--includeAll`, `--rollbackSqlFile`, `--tagDatabase:`. Move the split to an XML master. |
| `IllegalStateException: Liquibase migration failed` at startup | The interceptor wraps every `LiquibaseException` / `SQLException`. Read the cause. |
| Changelog file not found | `changelog` is a **classpath** path resolved by `ClassLoaderResourceAccessor`, relative to `src/main/resources/` — not a filesystem path, no leading `/`. |
| Cannot disable in-app migration through config | Correct — `LiquibaseConfig` has no `enabled` key. Remove `LiquibaseJdbcDatabaseModule` from `@KoraApp`. |
| Change never applied, or re-applied unexpectedly | Each change needs a unique `--changeset <author>:<id>`; editing an applied changeset changes its checksum. |
| Rollback does nothing | Provide `--rollback` directives, one per statement, and run rollback out of process. |
| `contextFilter:dev` seed data appeared in production | Expected. The interceptor calls `update()` with no runtime contexts, and an empty provided filter accepts every changeset. Separate the changelog instead. |
| `package ru.tinkoff.kora.database.liquibase does not exist` | 1.x coordinates. Group is `io.koraframework`; `kora-parent` does not exist in 2.0. |

---

## Related

- [../SKILL.md](../SKILL.md) — overview, interceptor mechanism, out-of-process strategy
- [flyway-migration-reference.md](flyway-migration-reference.md) — Flyway alternative
- [kora-database-jdbc](../../kora-database-jdbc/SKILL.md) — the `jdbc` section and repositories
