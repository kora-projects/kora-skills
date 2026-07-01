---
name: kora-database-migration
description: "Kora database migration modules for Flyway and Liquibase that run schema migrations on application startup. Covers the FlywayJdbcDatabaseModule and LiquibaseJdbcDatabaseModule, the database-flyway and database-liquibase artifacts, FlywayConfig/LiquibaseConfig keys (locations, changelog, executeInTransaction, validateOnMigrate, mixed), versioned SQL scripts, and the recommended out-of-process strategy (Flyway Gradle plugin, K8s Job, CI) for horizontally scaled services. Use when wiring migrations into a @KoraApp, picking Flyway vs Liquibase, configuring flyway/liquibase config sections, or fixing checksum/race-condition failures on startup."
---

# Kora Database Migration — Flyway and Liquibase

Kora ships two optional modules that run database migrations during the
application's `Lifecycle` startup, on top of the JDBC datasource:

- **Flyway** — `FlywayJdbcDatabaseModule`, artifact `database-flyway`, config class `FlywayConfig`.
- **Liquibase** — `LiquibaseJdbcDatabaseModule`, artifact `database-liquibase`, config class `LiquibaseConfig`.

Both require the [JDBC module](../kora-database-jdbc/SKILL.md) (`database-jdbc`).
Migrations execute through a `Lifecycle` interceptor (`FlywayJdbcDatabaseInterceptor` /
`LiquibaseJdbcDatabaseInterceptor`) before dependent components are initialized.

> **Production note.** Kora's maintainers **do not recommend** running migrations
> from inside the application when the service scales horizontally — every replica
> and every restart would trigger a migration. Prefer the out-of-process strategy
> (Flyway Gradle plugin locally, K8s Job / CI in production). See
> [Out-of-process migrations](#out-of-process-migrations-recommended). The
> canonical `kora-java-crud` example wires only `JdbcDatabaseModule` and runs Flyway
> via the Gradle plugin, not the migration module.

---

## Quick Start (Flyway, in-app)

**1. Dependencies** (`build.gradle`). Kora artifacts inherit the version from the
`kora-parent` BOM — never version them individually. The annotation processor is
mandatory: without it `@KoraApp` generates nothing.

```groovy
dependencies {
    koraBom platform("ru.tinkoff.kora:kora-parent:1.2.17")
    annotationProcessor "ru.tinkoff.kora:annotation-processors"

    implementation "ru.tinkoff.kora:database-jdbc"     // required datasource
    implementation "ru.tinkoff.kora:database-flyway"   // Flyway migration module
}
```

Kotlin: replace the processor with `ksp "ru.tinkoff.kora:symbol-processors"`.

**2. Plug the module into `@KoraApp`:**

```java
import ru.tinkoff.kora.common.KoraApp;
import ru.tinkoff.kora.config.hocon.HoconConfigModule;
import ru.tinkoff.kora.database.flyway.FlywayJdbcDatabaseModule;

@KoraApp
public interface Application extends
        HoconConfigModule,
        FlywayJdbcDatabaseModule { }
```

**3. Migration script** at `src/main/resources/db/migration/V1__setup_tables.sql`:

```sql
CREATE TABLE IF NOT EXISTS categories (
    id   BIGINT  NOT NULL GENERATED ALWAYS AS IDENTITY,
    name VARCHAR NOT NULL,
    PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS pets (
    id          BIGINT   NOT NULL GENERATED ALWAYS AS IDENTITY,
    name        VARCHAR  NOT NULL,
    status      SMALLINT NOT NULL,
    category_id BIGINT   NOT NULL REFERENCES categories(id),
    PRIMARY KEY (id)
);
```

**4. Configure** (`application.conf`). The JDBC datasource and the `flyway` section
both read environment variables for credentials:

```hocon
db {
  jdbcUrl  = ${POSTGRES_JDBC_URL}
  username = ${POSTGRES_USER}
  password = ${POSTGRES_PASS}
}

flyway {
  locations = ["db/migration"]   // default; classpath dir holding V*.sql
}
```

On startup Flyway scans `db/migration`, applies pending scripts in version order,
and records them in its `flyway_schema_history` table (created automatically).

---

## Flyway vs Liquibase

| | Flyway | Liquibase |
|---|---|---|
| Artifact | `database-flyway` | `database-liquibase` |
| Module | `FlywayJdbcDatabaseModule` | `LiquibaseJdbcDatabaseModule` |
| Config class | `FlywayConfig` | `LiquibaseConfig` |
| Script format | versioned SQL (`V<n>__<name>.sql`) | changelog (XML default; formatted SQL, YAML, JSON) |
| Default location | `db/migration` | `db/changelog/db.changelog-master.xml` |
| Rollback | not in the open-source Flyway | declarable in the changelog |
| Picked when | the default; simplest, SQL-only | you need declarative rollback or already have a Liquibase changelog |

Pick **one** module. Plug exactly one of the two into `@KoraApp` — they both
manage the same schema and must not run together.

---

## Flyway configuration

The keys below are the full `FlywayConfig` surface (defaults shown):

```hocon
flyway {
  enabled              = true            // run migrations on startup; false disables
  locations            = ["db/migration"] // classpath dirs with V*.sql scripts
  executeInTransaction = true            // wrap each migration in a transaction
  validateOnMigrate    = true            // verify checksums of applied scripts first
  mixed                = false           // allow transactional + non-transactional in one run
  configurationProperties {}             // raw key/value passed to Flyway#configurationProperties
}
```

- **`mixed = true`** is needed only for databases where some statements cannot run
  inside a transaction (PostgreSQL, Aurora PostgreSQL, SQL Server, SQLite) — e.g.
  `CREATE INDEX CONCURRENTLY`. When enabled, the whole run executes **without** a
  transaction.
- **`configurationProperties`** is the escape hatch for any native Flyway option
  not surfaced as a typed key (e.g. `flyway.defaultSchema`).

See [references/flyway-migration-reference.md](references/flyway-migration-reference.md)
for script naming rules, multiple locations, and checksum recovery.

---

## Liquibase configuration

`LiquibaseConfig` exposes a single key: the path to the master changelog.

```hocon
liquibase {
  changelog = "db/changelog/db.changelog-master.xml"  // default master file path
}
```

Point it at a formatted-SQL master if you prefer SQL over XML:

```hocon
liquibase {
  changelog = "db/changelog/db.changelog-master.sql"
}
```

Liquibase formatted SQL requires a header line and a `--changeset` directive per
change; rollback is declared with `--rollback`:

```sql
--liquibase formatted sql

--changeset developer:1
CREATE TABLE users (
    id    BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    email VARCHAR(255) NOT NULL UNIQUE
);
--rollback DROP TABLE users;

--changeset developer:2
CREATE TABLE orders (
    id      BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id),
    total   DECIMAL(10,2) NOT NULL
);
--rollback DROP TABLE orders;
```

See [references/liquibase-migration-reference.md](references/liquibase-migration-reference.md)
for changeset directives (contexts, labels), include files, and rollback patterns.

---

## Out-of-process migrations (recommended)

For horizontally scaled services, disable the in-app module and run migrations
once, before the app starts.

**Local development — Flyway Gradle plugin** (as in `kora-java-crud`):

```groovy
plugins {
    id "org.flywaydb.flyway" version "8.4.2"
}

flyway {
    url       = "jdbc:postgresql://localhost:5432/mydb"
    user      = "postgres"
    password  = "postgres"
    locations = ["classpath:db/migration"]
}
```

```bash
./gradlew flywayMigrate
```

**Production — Kubernetes Job** runs the migration container once before rolling
out the app, and the app keeps `flyway.enabled = false`:

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: db-migration
spec:
  backoffLimit: 1
  template:
    spec:
      restartPolicy: Never
      containers:
        - name: flyway
          image: flyway/flyway:8.4.2
          args: ["migrate"]
          env:
            - name: FLYWAY_URL
              valueFrom: { configMapKeyRef: { name: db-config, key: url } }
```

**CI** — invoke `./gradlew flywayMigrate` (or the Liquibase equivalent) as a
pipeline step against the target database before deployment.

If you keep the in-app module in a scaled deployment, two replicas may race on the
first migration. Flyway serializes via its history table lock, but a failed/locked
run can still block startup — out-of-process avoids this entirely.

---

## Testing migrations

The `kora-java-crud` example does not call Flyway by hand in tests. It uses the
Testcontainers extension `io.goodforgod:testcontainers-extensions-postgres`, which
runs the same `db/migration` scripts against a throwaway Postgres container:

```java
@TestcontainersPostgreSQL(
        network = @Network(shared = true),
        mode = ContainerMode.PER_RUN,
        migration = @Migration(
                engine = Migration.Engines.FLYWAY,
                apply  = Migration.Mode.PER_METHOD,
                drop   = Migration.Mode.PER_METHOD))
@KoraAppTest(Application.class)
class IntegrationTests implements KoraAppTestConfigModifier {

    @ConnectionPostgreSQL
    private JdbcConnection connection;

    // @TestComponent-injected repositories use the migrated schema
}
```

Test dependency:

```groovy
testImplementation "io.goodforgod:testcontainers-extensions-postgres:0.13.1"
testImplementation "org.testcontainers:junit-jupiter:1.21.4"
testImplementation "ru.tinkoff.kora:test-junit5"
```

`Migration.Engines.LIQUIBASE` switches the same extension to Liquibase. See
[kora-testing-junit-java](../kora-testing-junit-java/SKILL.md) for `@KoraAppTest`.

---

## What's in references/ and assets/

| File | Purpose |
|------|---------|
| [references/flyway-migration-reference.md](references/flyway-migration-reference.md) | Script naming, multiple locations, transactional vs `mixed`, checksum recovery |
| [references/liquibase-migration-reference.md](references/liquibase-migration-reference.md) | Formatted-SQL changesets, rollback, contexts/labels, includes |
| [assets/V1__initial_schema.sql.template](assets/V1__initial_schema.sql.template) | Flyway initial migration starter |
| [assets/002-orders-table.sql.template](assets/002-orders-table.sql.template) | Follow-up Flyway/Liquibase change starter |
| [assets/db.changelog-master.sql.template](assets/db.changelog-master.sql.template) | Liquibase formatted-SQL master changelog |
| [assets/README.md](assets/README.md) | How to copy and rename the templates |

---

## Common pitfalls

| Symptom | Fix |
|---------|-----|
| No migrations run on startup | `flyway.enabled`/module present; `locations` points at a real classpath dir holding `V*.sql` |
| "Validation failed. Checksum changed" | An applied script was edited. Never edit applied migrations — add a new versioned script, or repair the history out-of-process |
| `CREATE INDEX CONCURRENTLY` fails inside a transaction | Set `flyway.mixed = true` (whole run becomes non-transactional) |
| Two replicas race on first deploy | Disable the in-app module; run migrations via Gradle plugin / K8s Job / CI |
| Liquibase formatted SQL ignored | First line must be `--liquibase formatted sql`; each change needs `--changeset <author>:<id>` |
| Both modules plugged into `@KoraApp` | Keep exactly one of `FlywayJdbcDatabaseModule` / `LiquibaseJdbcDatabaseModule` |

---

## Related skills

- [kora-database-jdbc](../kora-database-jdbc/SKILL.md) — datasource and `@Repository` setup (prerequisite)
- [kora-testing-junit-java](../kora-testing-junit-java/SKILL.md) — `@KoraAppTest` + Testcontainers
- [kora-config-hocon](../kora-config-hocon/SKILL.md) — `flyway`/`liquibase` config sections
- [kora-project-dependencies](../kora-project-dependencies/SKILL.md) — BOM and module artifacts

## Source of truth

- Doc: [database-migration.md](../../.kora-agent/kora-docs/mkdocs/docs/en/documentation/database-migration.md)
- Example: [kora-java-crud](../../.kora-agent/kora-examples/examples/java/kora-java-crud)
