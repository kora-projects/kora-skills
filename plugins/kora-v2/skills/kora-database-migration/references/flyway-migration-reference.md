# Flyway Migration Reference

Kora 2.0 module `io.koraframework.database.flyway.FlywayJdbcDatabaseModule`, artifact
`io.koraframework:database-flyway`, config type `FlywayConfig`, config section `flyway`.
Requires `io.koraframework:database-jdbc` and `JdbcDatabaseModule` on the `@KoraApp` interface.

Bundled third-party version: **`org.flywaydb:flyway-core` 13.9.0**.

## Contents

- [Dependencies and the dialect artifact](#dependencies-and-the-dialect-artifact)
- [Configuration](#configuration)
- [Migration mode](#migration-mode)
- [Script naming](#script-naming)
- [Directory layout and multiple locations](#directory-layout-and-multiple-locations)
- [Transactional vs mixed](#transactional-vs-mixed)
- [Native Flyway options via configurationProperties](#native-flyway-options-via-configurationproperties)
- [Connection pool sizing](#connection-pool-sizing)
- [Checksum and failure recovery](#checksum-and-failure-recovery)
- [Testing](#testing)

---

## Dependencies and the dialect artifact

`database-flyway` declares `flyway-core` and nothing else. Since Flyway 10, support for each
specific database lives in its own artifact, resolved through a `ServiceLoader` registry. With none
on the classpath Flyway cannot identify the connection and fails **at startup**, inside graph
initialization:

```
org.flywaydb.core.api.FlywayException: Unsupported Database: PostgreSQL 16.2
```

The name in the message is `DatabaseMetaData.getDatabaseProductName()` plus the major/minor version,
so it names the database you are actually connected to — which makes it easy to misread as a
version-support problem. It is a missing-artifact problem.

`io.koraframework:kora-bom` constrains only Kora's own modules, so the dialect artifact must carry
an explicit version. Keep it identical to the `flyway-core` version `database-flyway` brings in.

```groovy
dependencies {
    koraBom platform("io.koraframework:kora-bom:$koraVersion")   // koraVersion=2.0.0.RC2
    annotationProcessor "io.koraframework:annotation-processors"

    implementation "io.koraframework:database-jdbc"
    implementation "io.koraframework:database-flyway"
    implementation "org.flywaydb:flyway-database-postgresql:13.9.0"

    runtimeOnly "org.postgresql:postgresql:42.7.13"
}
```

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

| Database | Artifact |
|---|---|
| PostgreSQL | `org.flywaydb:flyway-database-postgresql` |
| MySQL / MariaDB | `org.flywaydb:flyway-mysql` |
| Oracle | `org.flywaydb:flyway-database-oracle` |
| SQL Server | `org.flywaydb:flyway-sqlserver` |
| HSQLDB | `org.flywaydb:flyway-database-hsqldb` |

Confirm what actually resolved before blaming the config:

```bash
./gradlew dependencies --configuration runtimeClasspath | grep flyway
```

A version skew between `flyway-core` and the dialect artifact is the second-most-common failure
after omitting the artifact entirely. The migrated Kora 2.0 example apps pin `13.1.0`–`13.8.1` while the
framework catalog is on `13.9.0`; align both to whatever `flyway-core` your build resolves.

---

## Configuration

Complete `FlywayConfig` surface with defaults — there are exactly seven keys:

```hocon
flyway {
  enabled              = true             // (1)
  mode                 = MIGRATE          // (2)
  locations            = ["db/migration"] // (3)
  executeInTransaction = true             // (4)
  validateOnMigrate    = true             // (5)
  mixed                = false            // (6)
  configurationProperties { }             // (7)
}
```

1. Run migrations when the `JdbcDataSource` node initializes. `false` skips them entirely — this is
   the switch to flip when migrations move out of process.
2. `MIGRATE` | `REPAIR` | `CLEAN_MIGRATE`, matched exactly and case-sensitively.
3. Classpath directories holding migration scripts. A HOCON array, or a single comma-separated
   string (`locations = "db/migration/common,db/migration/postgresql"`).
4. Wrap each migration in a transaction.
5. Verify checksums of already-applied scripts before migrating; a mismatch fails the run.
6. Allow mixing transactional and non-transactional statements in one run — see below.
7. Flat `Map<String, String>` of raw `flyway.*` properties for options with no typed key.

YAML form (`config-yaml`, `YamlConfigModule`):

```yaml
flyway:
  enabled: true
  mode: MIGRATE
  locations: ["db/migration"]
  executeInTransaction: true
  validateOnMigrate: true
  mixed: false
  configurationProperties: {}
```

`FlywayConfig` is a `@ConfigMapper` interface with `mapNullAsEmptyObject = true` and a default for
every method, so the `flyway` section may be omitted entirely — the module then migrates
`db/migration` with the defaults above.

Keys that do **not** exist in `FlywayConfig` and must not be written into the `flyway` section:
`baselineOnMigrate`, `cleanDisabled`, `schemas`, `table`, `outOfOrder`, `placeholders`, `url`,
`user`, `password`. The connection comes from the `jdbc` section; the rest go through
`configurationProperties`.

---

## Migration mode

```hocon
flyway { mode = MIGRATE }
```

| Mode | Effect |
|---|---|
| `MIGRATE` | Default. Applies pending scripts in version order. |
| `REPAIR` | Realigns the `flyway_schema_history` table (checksums, failed entries) **instead of** migrating. A recovery mode, not a startup mode. |
| `CLEAN_MIGRATE` | **Drops everything in the schema**, then migrates from scratch. Local development and disposable test databases only — never a deployed environment. |

The value is matched against the enum constant name exactly:

```
ConfigValueException: Unknown enum value: migrate when expected one of [MIGRATE, REPAIR, CLEAN_MIGRATE]
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
3. The description is separated from the version by a **double** underscore.
4. Scripts live on the classpath under one of the `locations` directories, i.e. under
   `src/main/resources/`.

Applied scripts are recorded in Flyway's own `flyway_schema_history` table, which it creates on
first run.

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

The string form is equivalent and is what the migrated guide apps use:

```hocon
flyway { locations = "db/migration/common,db/migration/postgresql" }
```

---

## Transactional vs mixed

By default each migration runs in a transaction; any failing statement rolls the whole script back:

```sql
-- V1__create_tables.sql
CREATE TABLE users (
    id    BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    email VARCHAR(255) NOT NULL
);
CREATE INDEX idx_users_email ON users(email);
```

Some statements cannot run inside a transaction (PostgreSQL, Aurora PostgreSQL, SQL Server,
SQLite) — most commonly `CREATE INDEX CONCURRENTLY`. Set `flyway.mixed = true`; the entire run then
executes **without** a transaction:

```hocon
flyway { mixed = true }
```

```sql
-- V2__concurrent_index.sql
CREATE INDEX CONCURRENTLY idx_users_created ON users(created_at);
```

There is no per-script switch in the Kora module — `FlywayJdbcDatabaseInterceptor` passes
`executeInTransaction` and `mixed` straight to the Flyway builder for the whole run. If only one
script needs non-transactional execution, prefer moving that script to an out-of-process run rather
than making every migration non-transactional.

---

## Native Flyway options via configurationProperties

Options `FlywayConfig` does not surface as typed keys go through `configurationProperties`, using
Flyway's own property names. Those names are **`flyway.`-prefixed** (`flyway.defaultSchema`,
`flyway.baselineOnMigrate`, `flyway.table`, `flyway.outOfOrder`, `flyway.placeholders.<name>`, …).

Kora maps `configurationProperties` as a **flat** `Map<String, String>`: one level of keys, each
value a scalar. An unquoted dotted key makes HOCON build a nested object instead, and the string
mapper rejects it. **Quote the whole key:**

```hocon
flyway {
  configurationProperties {
    "flyway.defaultSchema"      = "public"
    "flyway.baselineOnMigrate"  = "true"
    "flyway.placeholders.owner" = "app_user"
  }
}
```

```yaml
flyway:
  configurationProperties:
    "flyway.defaultSchema": "public"
```

Wrong — HOCON nests this into `flyway { defaultSchema = "public" }` and the run fails with
`ConfigValueException: Config expected value with type 'StringValue'`:

```hocon
flyway {
  configurationProperties {
    flyway.defaultSchema = "public"   # WRONG: dotted key must be quoted
  }
}
```

---

## Connection pool sizing

In-app Flyway takes **two** connections from the Hikari pool at once — one for the migration and one
for the schema-history lock. The framework's own `FlywayJdbcDataSourceInterceptorTest` builds its
`JdbcDatabaseConfig` with `maxPoolSize = 2` for exactly that reason.

```hocon
jdbc {
  maxPoolSize = 10   // must be >= 2 while in-app Flyway migration is enabled
}
```

With `jdbc.maxPoolSize = 1` the migration blocks waiting for a connection it can never get, and the
service hangs during graph initialization until `connectionTimeout` expires. Liquibase needs only
one connection.

---

## Checksum and failure recovery

**`Validation failed. Checksum changed`** — an applied script was edited after it ran. Do not edit
applied scripts. Recover out-of-process with the Flyway Gradle plugin or CLI (`flywayRepair` /
`flyway repair`) to realign the history table, then add new versioned scripts going forward.
Disabling `validateOnMigrate` masks the problem and is not advisable in production.

`mode = REPAIR` performs the same repair from inside the application, but it **replaces** the
migration for that startup — the app repairs and does not apply pending scripts. Use it as a
deliberate one-off deployment, never as a standing configuration.

**Migration failed mid-run** — fix the SQL, repair the failed state out-of-process, then re-run.
With `executeInTransaction = true` a failed transactional script leaves no partial schema; with
`mixed = true` it may.

**Startup failed inside the interceptor** — the exception propagates out of graph initialization and
the application exits. Any checked exception is wrapped:
`IllegalStateException: Graph interceptor failed with checked exception for node … and interceptor …`.
Read the cause, not the wrapper.

---

## Testing

`@KoraAppTest` builds the real graph, so the Flyway interceptor runs against the test database and
the schema is in place before the first test method. Override the connection with
`KoraAppTestConfigModifier` — note the section is **`jdbc`**, and HOCON embedded in a test source
carries exactly the same key names as `application.conf`:

```java
@Testcontainers
@KoraAppTest(TestApplication.class)
class UserRepositoryPostgresTest implements KoraAppTestConfigModifier {

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
                flyway {
                  locations = "db/migration"
                }
                """)
                .withSystemProperty("POSTGRES_JDBC_URL", POSTGRES.getJdbcUrl())
                .withSystemProperty("POSTGRES_USER", POSTGRES.getUsername())
                .withSystemProperty("POSTGRES_PASS", POSTGRES.getPassword());
    }
}
```

The dialect artifact must be on the **test** runtime classpath too, so a test-only migration setup
declares both:

```groovy
testImplementation "io.koraframework:database-flyway"
testImplementation "org.flywaydb:flyway-database-postgresql:13.9.0"
```

`mode = CLEAN_MIGRATE` is a legitimate choice for a shared, non-disposable test database that must
start from a known state; a per-test container does not need it.

Container wiring and `@KoraAppTest` mechanics —
[kora-testing-junit-java](../../kora-testing-junit-java/SKILL.md) /
[kora-testing-junit-kotlin](../../kora-testing-junit-kotlin/SKILL.md).

---

## Related

- [../SKILL.md](../SKILL.md) — overview, interceptor mechanism, out-of-process strategy
- [liquibase-migration-reference.md](liquibase-migration-reference.md) — Liquibase alternative
- [kora-database-jdbc](../../kora-database-jdbc/SKILL.md) — the `jdbc` section and repositories
