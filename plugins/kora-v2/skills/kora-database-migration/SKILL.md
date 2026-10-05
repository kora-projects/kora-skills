---
name: kora-database-migration
description: "Kora 2.0 schema migrations on startup — FlywayJdbcDatabaseModule (io.koraframework:database-flyway) and LiquibaseJdbcDatabaseModule (io.koraframework:database-liquibase), wired as a GraphInterceptor<JdbcDataSource>. Covers FlywayConfig (enabled, mode, locations, executeInTransaction, validateOnMigrate, mixed, configurationProperties), LiquibaseConfig.changelog, the mandatory Flyway dialect artifact, and the out-of-process strategy for scaled services. Use when adding migrations to a @KoraApp, choosing Flyway vs Liquibase, or fixing 'Unsupported Database', checksum, or startup-race failures."
license: Apache-2.0
metadata:
  kora-version: "2.x"
---

# Kora Database Migration — Flyway and Liquibase

> **Kora sub-skill — obey the [kora-v2 meta rules](../../SKILL.md) on every task:** **R0** ground the workspace on Kora 2.0 refs before starting (framework source at tag `2.0.0.RC2` + `kora-examples` at `migration/2.0` + Kora 2.0 docs at koraframework.io/v2, which trail the source; 1.x `kora-docs` pages are never an authority) · **R1** read this sub-skill before writing code · **R2** Kora 2.0 APIs only — no Spring/Micronaut/Quarkus, no Kora 1.x APIs, no invented annotations or config keys · **R3** journal any incorrect Kora usage. Add comments/Javadoc only if asked.

| | Flyway | Liquibase |
|---|---|---|
| **Artifact** | `io.koraframework:database-flyway` | `io.koraframework:database-liquibase` |
| **Module** | `io.koraframework.database.flyway.FlywayJdbcDatabaseModule` | `io.koraframework.database.liquibase.LiquibaseJdbcDatabaseModule` |
| **Config type** | `FlywayConfig` | `LiquibaseConfig` |
| **Config section** | `flyway` | `liquibase` |
| **Interceptor** | `FlywayJdbcDatabaseInterceptor` | `LiquibaseJdbcDatabaseInterceptor` |
| **Third-party version** | `flyway-core` **13.9.0** | `liquibase-core` **5.0.4** |
| **Extra artifact needed** | **Yes** — a per-database dialect (`org.flywaydb:flyway-database-postgresql`) | No — `liquibase-core` bundles the standard databases |
| **Prerequisite** | `io.koraframework:database-jdbc` + `JdbcDatabaseModule` on `@KoraApp` | same |

Both modules are optional add-ons to the [JDBC module](../kora-database-jdbc/SKILL.md). Neither has a
Cassandra counterpart — migrations attach to the **JDBC** datasource only.

---

## 1. How migrations run — the interceptor, not a lifecycle hook

`FlywayJdbcDatabaseModule` contributes exactly one thing to the graph: a
`FlywayJdbcDatabaseInterceptor implements GraphInterceptor<JdbcDataSource>`. At compile time the
`@KoraApp` processor matches every `GraphInterceptor<T>` component against the nodes of type `T` and
wires it into the generated graph. At runtime the graph calls `afterInit(dataSource)` **after
`JdbcDataSource.init()` has opened and validated the pool, and before any component that depends on
the datasource is constructed**. Liquibase works identically.

Three consequences that drive every decision below:

1. **Migrations block startup.** They run inside graph initialization, so the service is not
   listening and not ready until the migration finishes. A migration failure surfaces as a graph
   initialization error and the application exits.
2. **Every replica migrates.** The interceptor is attached per graph, so a horizontally scaled
   deployment runs it once per pod on every rollout — see §6.
3. **The interceptor needs pool capacity.** Flyway takes **two** connections (migration + schema
   history lock); Liquibase takes one. `jdbc.maxPoolSize = 1` deadlocks an in-app Flyway migration
   at startup with no error message — the framework's own Flyway test pins the pool at `2` for
   exactly this reason.

Nothing else is required: no `@Root`, no ordering config, no explicit module method. Plugging the
module in is the whole wiring.

---

## 2. Quick start — Flyway

**1. Dependencies.** Kora artifacts inherit their version from `io.koraframework:kora-bom`. The
dialect artifact does **not** — `kora-bom` only constrains Kora's own modules, so it carries an
explicit version.

```groovy
dependencies {
    koraBom platform("io.koraframework:kora-bom:$koraVersion")   // koraVersion=2.0.0.RC2
    annotationProcessor "io.koraframework:annotation-processors"

    implementation "io.koraframework:database-jdbc"
    implementation "io.koraframework:database-flyway"
    // Since Flyway 10 per-database support lives in separate artifacts and
    // database-flyway ships only flyway-core: without this the app dies at
    // startup with "FlywayException: Unsupported Database: PostgreSQL 16.2".
    implementation "org.flywaydb:flyway-database-postgresql:13.9.0"

    runtimeOnly "org.postgresql:postgresql:42.7.13"
}
```

Kotlin — same coordinates, `ksp("io.koraframework:symbol-processors")` instead of the annotation
processor:

```kotlin
dependencies {
    implementation(platform("io.koraframework:kora-bom:${property("koraVersion")}"))
    ksp("io.koraframework:symbol-processors:${property("koraVersion")}")

    implementation("io.koraframework:database-jdbc")
    implementation("io.koraframework:database-flyway")
    implementation("org.flywaydb:flyway-database-postgresql:13.9.0")

    runtimeOnly("org.postgresql:postgresql:42.7.13")
}
```

Pick the dialect artifact for your database (`flyway-database-postgresql`, `flyway-mysql`,
`flyway-database-oracle`, …) and pin it to the same version as the `flyway-core` that
`database-flyway` brings in — `13.9.0` for Kora `2.0.0.RC2`. Verify with
`./gradlew dependencies --configuration runtimeClasspath | grep flyway`.

**2. Plug both modules into `@KoraApp`.** `FlywayJdbcDatabaseModule` supplies only the interceptor;
the datasource still comes from `JdbcDatabaseModule`.

```java
import io.koraframework.application.graph.KoraApplication;
import io.koraframework.common.annotation.KoraApp;
import io.koraframework.config.hocon.HoconConfigModule;
import io.koraframework.database.flyway.FlywayJdbcDatabaseModule;
import io.koraframework.database.jdbc.JdbcDatabaseModule;

@KoraApp
public interface Application extends
        HoconConfigModule,
        JdbcDatabaseModule,
        FlywayJdbcDatabaseModule {

    static void main(String[] args) {
        KoraApplication.run(ApplicationGraph::graph);
    }
}
```

```kotlin
@KoraApp
interface Application :
    HoconConfigModule,
    JdbcDatabaseModule,
    FlywayJdbcDatabaseModule

fun main() {
    KoraApplication.run(ApplicationGraph::graph)
}
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

**4. Configure** `application.conf`. The JDBC section is **`jdbc`** in Kora 2.0 — it was `db` in
1.x, and a leftover `db { }` block fails startup with
`ConfigValueException: Config expected value, but got null at path: 'ROOT.jdbc.username'`.

```hocon
jdbc {
  jdbcUrl  = ${POSTGRES_JDBC_URL}
  username = ${POSTGRES_USER}
  password = ${POSTGRES_PASS}
  poolName = "my-service"
  maxPoolSize = 10          // must be >= 2 while in-app Flyway migration runs
}

flyway {
  locations = "db/migration"
}
```

Every `FlywayConfig` and `LiquibaseConfig` key has a default and both are declared `@ConfigMapper`
with `mapNullAsEmptyObject = true`, so **the section itself is optional** — a module with no
`flyway { }` block migrates `db/migration` with defaults.

---

## 3. Flyway configuration

The complete `FlywayConfig` surface — these seven keys are all that exists:

```hocon
flyway {
  enabled              = true              // run on startup; false skips migration entirely
  mode                 = MIGRATE           // MIGRATE | REPAIR | CLEAN_MIGRATE (exact case)
  locations            = ["db/migration"]  // classpath dirs holding V*.sql
  executeInTransaction = true              // wrap each migration in a transaction
  validateOnMigrate    = true              // verify checksums of applied scripts first
  mixed                = false             // allow transactional + non-transactional in one run
  configurationProperties { }              // raw flyway.* properties, flat quoted keys
}
```

- **`mode`** is new in Kora 2.0 and is matched **exactly, uppercase**. `mode = migrate` fails with
  `Unknown enum value: migrate when expected one of [MIGRATE, REPAIR, CLEAN_MIGRATE]`.
  `CLEAN_MIGRATE` **drops the schema** before migrating — a local/test convenience, never
  production.
- **`locations`** accepts either a HOCON array or a single comma-separated string; the migrated
  guide apps use the string form (`locations = "db/migration"`).
- **`mixed = true`** is for statements that cannot run in a transaction (`CREATE INDEX
  CONCURRENTLY` on PostgreSQL, and equivalents on Aurora PostgreSQL, SQL Server, SQLite). The whole
  run then executes **without** a transaction.
- **`configurationProperties`** maps to `Flyway.configure().configuration(Map)`, whose keys are
  Flyway's own `flyway.`-prefixed property names. Kora maps it as a **flat** `Map<String, String>`,
  so the dotted key must be quoted — unquoted, HOCON nests it and the config mapper throws:

  ```hocon
  flyway {
    configurationProperties {
      "flyway.defaultSchema"    = "public"
      "flyway.baselineOnMigrate" = "true"
    }
  }
  ```

Full details — script naming, multiple locations, checksum recovery, testing —
[references/flyway-migration-reference.md](references/flyway-migration-reference.md).

---

## 4. Liquibase configuration

`LiquibaseConfig` exposes a **single** key:

```hocon
liquibase {
  changelog = "db/changelog/db.changelog-master.xml"   // default
}
```

Point it at a formatted-SQL master to keep native SQL:

```hocon
liquibase {
  changelog = "db/changelog/db.changelog-master.sql"
}
```

Two asymmetries against Flyway that matter:

- **There is no `liquibase.enabled` key.** `LiquibaseJdbcDatabaseInterceptor.afterInit` runs
  `update()` unconditionally. To stop in-app migration you must remove
  `LiquibaseJdbcDatabaseModule` from the `@KoraApp` interface — there is no config switch.
- **No dialect artifact is needed.** `org.liquibase:liquibase-core` 5.0.4 aggregates
  `liquibase-standard`, which carries the mainstream database implementations; the framework's own
  Liquibase test migrates a real PostgreSQL with `liquibase-core` alone.

Formatted-SQL changelogs need a header line and a `--changeset` per change; rollback is declared
with `--rollback`:

```sql
--liquibase formatted sql

--changeset developer:1
CREATE TABLE users (
    id    BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    email VARCHAR(255) NOT NULL UNIQUE
);
--rollback DROP TABLE users;
```

Changeset directives, contexts/labels, includes and rollback patterns —
[references/liquibase-migration-reference.md](references/liquibase-migration-reference.md).

---

## 5. Choosing between them

| | Flyway | Liquibase |
|---|---|---|
| Script format | versioned SQL (`V<n>__<name>.sql`) | changelog (XML default; formatted SQL, YAML, JSON) |
| Default location | `db/migration` | `db/changelog/db.changelog-master.xml` |
| Rollback | not in open-source Flyway | declared in the changelog, applied out-of-process |
| Disable in-app | `flyway.enabled = false` | remove the module from `@KoraApp` |
| Extra dependency | dialect artifact **required** | none |
| Pick when | default choice; SQL-only, simplest | you need declarative rollback or already own a changelog |

Plug in **exactly one**. Both interceptors attach to the same `JdbcDataSource` node and would both
manage the same schema.

**Tables owned by other Kora modules.** `io.koraframework:scheduling-db-scheduler` ships the schema
of its `kora_scheduling_db_scheduler_jobs` table (the default `scheduling.dbScheduler.tableName`) as
classpath resources: plain scripts `db/kora/scheduling-db-scheduler/schema/<database>.sql`
(`postgresql`, `mysql`, `mariadb`, `mssql`, `oracle`, `hsql`) and an idempotent Liquibase changelog
`db/kora/scheduling-db-scheduler/liquibase/changelog.yaml`. There are **no versioned Flyway
migrations** to point `flyway.locations` at — copy the script for your database into your own
migrations under the next free version (`V42__create_kora_scheduling_db_scheduler_jobs.sql`). With
Liquibase, `include` the changelog from your master changelog; its `dbms`-guarded changesets are
marked as ran when the table already exists, and they always create the default table name.
Earlier 2.0 snapshots shipped `db/scheduling-db/flyway/<database>/V1__create_scheduled_tasks.sql`
(table `scheduled_tasks`, colliding with an application `V1__`) and defaulted `tableName` to
`kora_scheduling_db_jobs`; neither exists any more. Details: [kora-aop-scheduling-db](../kora-aop-scheduling-db/SKILL.md).

---

## 6. Out-of-process migrations (recommended for scaled services)

§1 established the mechanism: the interceptor runs during graph initialization, once per replica,
on every rollout. Both tools serialize concurrent runs with a database lock (Flyway around
`flyway_schema_history`, Liquibase via `DATABASECHANGELOGLOCK`), so replicas do not corrupt each
other — but every pod still waits for that lock, a run that dies mid-migration can leave it held,
and a bad migration takes down the whole rollout rather than one job. For anything beyond a single
instance, run migrations **once, before the app starts**.

**Local development — Flyway Gradle plugin.** The canonical `kora-java-crud` example takes this
route: it wires only `JdbcDatabaseModule`, with no `database-flyway` dependency at all, and migrates
through the plugin.

```groovy
buildscript {
    dependencies {
        // the plugin runs in the Gradle JVM, so the dialect goes on the buildscript classpath
        classpath "org.flywaydb:flyway-database-postgresql:13.9.0"
    }
}

plugins {
    id "org.flywaydb.flyway" version "13.9.0"
}

flyway {
    url       = "jdbc:postgresql://localhost:5432/mydb"
    user      = "postgres"
    password  = "postgres"
    locations = ["classpath:db/migration"]
    baselineOnMigrate = true
}
```

```bash
./gradlew flywayMigrate
```

Keep the plugin and its dialect artifact on the same version. (`kora-java-crud` currently pairs
plugin `13.0.0` with dialect `12.10.0`; treat that as example drift, not a pattern to copy.)

**Production — Kubernetes Job** run once before the rollout, with the app keeping
`flyway.enabled = false` (Flyway) or no migration module at all (Liquibase):

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
          image: flyway/flyway:13.9.0
          args: ["migrate"]
          env:
            - name: FLYWAY_URL
              valueFrom: { configMapKeyRef: { name: db-config, key: url } }
```

The Liquibase equivalent is `liquibase/liquibase:5.0.4` with
`args: ["--changelog-file=db/changelog/db.changelog-master.xml", "update"]`, or the
`org.liquibase.gradle` plugin (`3.1.0`) locally.

**CI** — run the same command as a pipeline step against the target database before deploying.

---

## 7. Common pitfalls

| Symptom | Cause / fix |
|---|---|
| `FlywayException: Unsupported Database: PostgreSQL 16.2` at startup | `database-flyway` ships only `flyway-core`. Add `org.flywaydb:flyway-database-postgresql` (or your database's artifact) at the same version as `flyway-core`. |
| `ConfigValueException: … got null at path: 'ROOT.jdbc.username'` | The datasource section is `jdbc` in 2.0, not `db`. Applies to HOCON inside `KoraConfigModification.ofString("""…""")` too. |
| Startup hangs with no error while Flyway migrates | `jdbc.maxPoolSize` is 1. Flyway needs two connections; raise it to at least 2. |
| `Unknown enum value: migrate when expected one of [MIGRATE, REPAIR, CLEAN_MIGRATE]` | `flyway.mode` is exact-match uppercase. |
| `Config expected value with type 'StringValue'` under `configurationProperties` | An unquoted dotted key made HOCON nest an object. Quote the whole key: `"flyway.defaultSchema" = "public"`. |
| Nothing migrates although the module is present | `flyway.enabled = false`, or `locations` points at a classpath dir with no `V*.sql`. Liquibase has no `enabled` key — check the changelog path instead. |
| `Validation failed. Checksum changed` | An applied script was edited. Never edit applied migrations; add a new version and repair the history out-of-process. |
| `CREATE INDEX CONCURRENTLY` fails inside a transaction | `flyway.mixed = true` — the whole run becomes non-transactional. |
| All replicas migrate on every rollout | Expected: the interceptor is per graph. Move to a Job/CI step and set `flyway.enabled = false`. |
| Liquibase formatted SQL ignored | First line must be `--liquibase formatted sql`; each change needs `--changeset <author>:<id>`. |
| `ChangeLogParseException: … requires a valid Liquibase license key` | `--include` / `--includeAll` in a **formatted-SQL** changelog are Pro-only in Liquibase 5. Split with an XML master that `<include>`s the `.sql` children. |
| Both modules on `@KoraApp` | Keep exactly one of `FlywayJdbcDatabaseModule` / `LiquibaseJdbcDatabaseModule`. |
| `package ru.tinkoff.kora.database.flyway does not exist` | 1.x coordinates. Group is `io.koraframework`, BOM is `io.koraframework:kora-bom` — `kora-parent` does not exist in 2.0. |

---

## References & assets

| File | Purpose |
|---|---|
| [references/flyway-migration-reference.md](references/flyway-migration-reference.md) | Full `FlywayConfig`, dialect artifacts, script naming, `mixed`, `configurationProperties`, checksum recovery, testing |
| [references/liquibase-migration-reference.md](references/liquibase-migration-reference.md) | `LiquibaseConfig`, formatted-SQL changesets, rollback, contexts/labels, includes, testing |
| [assets/V1__initial_schema.sql.template](assets/V1__initial_schema.sql.template) | Flyway initial migration starter (`db/migration/V1__*.sql`) |
| [assets/db.changelog-master.sql.template](assets/db.changelog-master.sql.template) | Liquibase formatted-SQL master changelog |
| [assets/002-orders-table.sql.template](assets/002-orders-table.sql.template) | Liquibase follow-up changeset, `<include>`d from an XML master |

## Related skills

- [kora-database-jdbc](../kora-database-jdbc/SKILL.md) — `JdbcDatabaseModule`, the `jdbc` section, repositories (prerequisite)
- [kora-config-hocon](../kora-config-hocon/SKILL.md) — how the `flyway` / `liquibase` sections are mapped
- [kora-config-yaml](../kora-config-yaml/SKILL.md) — the YAML form of the same sections
- [kora-testing-junit-java](../kora-testing-junit-java/SKILL.md) · [kora-testing-junit-kotlin](../kora-testing-junit-kotlin/SKILL.md) — `@KoraAppTest` + Testcontainers with migrations
- [kora-project-dependencies](../kora-project-dependencies/SKILL.md) — BOM, module coordinates, externally-versioned dependencies
- [kora-di-runtime](../kora-di-runtime/SKILL.md) — `GraphInterceptor` and graph lifecycle
- [kora-aop-scheduling-db](../kora-aop-scheduling-db/SKILL.md) — DB-backed scheduler whose job table (default `kora_scheduling_db_scheduler_jobs`) these tools create

## Source of truth

Version-aligned authorities for Kora 2.0, in this order: framework source and tests, then the
migrated examples, then the Kora 2.0 documentation. Pages of the 1.x documentation
(`ru.tinkoff.kora`) are background only — never resolve a 2.0 question from them.

- Framework source, tag `2.0.0.RC2`:
  [database-flyway](https://github.com/kora-projects/kora/tree/2.0.0.RC2/database/database-flyway) ·
  [database-liquibase](https://github.com/kora-projects/kora/tree/2.0.0.RC2/database/database-liquibase) ·
  [database-jdbc](https://github.com/kora-projects/kora/tree/2.0.0.RC2/database/database-jdbc)
- Migrated guide apps, branch `migration/2.0` (in-app Flyway):
  [kora-java-guide-database-jdbc-advanced-app](https://github.com/kora-projects/kora-examples/tree/migration/2.0/guides/java/kora-java-guide-database-jdbc-advanced-app) ·
  [kora-kotlin-guide-database-jdbc-advanced-app](https://github.com/kora-projects/kora-examples/tree/migration/2.0/guides/kotlin/kora-kotlin-guide-database-jdbc-advanced-app)
- Migrated examples, branch `migration/2.0`:
  [kora-java-crud](https://github.com/kora-projects/kora-examples/tree/migration/2.0/examples/java/kora-java-crud) (Gradle-plugin strategy) ·
  [kora-java-petclinic](https://github.com/kora-projects/kora-examples/tree/migration/2.0/examples/java/kora-java-petclinic) (in-app module)
- Kora 2.0 documentation: [Database migration](https://koraframework.io/v2/en/documentation/database-migration/)
  (source wins where the two disagree — e.g. on the bundled Flyway version)
- Third-party: [Flyway 13 docs](https://documentation.red-gate.com/flyway) ·
  [Liquibase docs](https://docs.liquibase.com/)
