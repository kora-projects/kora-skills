---
name: kora-database-jdbc
description: "JDBC relational database integration for Kora. Builds compile-time @Repository interfaces extending JdbcRepository with @Query, @EntityJdbc records, @Table/@Column/@Id mapping, SQL macros (%{return#selects}, %{entity#inserts}, %{entity#where = @id}), @Batch, UpdateCount, @Id-on-method generated identifiers, transactions via JdbcConnectionFactory.inTx(), and custom JdbcResultSetMapper/JdbcRowMapper/JdbcResultColumnMapper/JdbcParameterColumnMapper. Connection pooling is HikariCP, configured under the `db` HOCON/YAML section of JdbcDatabaseConfig. Use when adding a Hikari-backed PostgreSQL/MySQL/Oracle repository to a Kora service, wiring JdbcDatabaseModule, debugging \"JdbcRepository not found\" graph errors, or choosing repository return signatures."
---

# Kora Database JDBC

JDBC-based relational database access (PostgreSQL, MySQL, Oracle) with HikariCP. Repositories are `@Repository` interfaces whose implementations are generated at compile time by the annotation processor — no reflection, no runtime proxies.

> **Prefer synchronous repository signatures** (`Entity`, `@Nullable Entity`, `List<Entity>`, `UpdateCount`). The blocking JDBC driver runs on the executor bound to `JdbcDatabase`; virtual threads or a fixed pool handle blocking efficiently. Reach for `CompletionStage`/`Mono` only when a downstream contract requires it.

---

## Quick Start

### 1. Dependencies (`build.gradle`)

```groovy
dependencies {
    koraBom platform("ru.tinkoff.kora:kora-parent:1.2.17")
    annotationProcessor "ru.tinkoff.kora:annotation-processors"  // mandatory: generates *RepositoryImpl

    implementation "ru.tinkoff.kora:database-jdbc"
    implementation "ru.tinkoff.kora:config-hocon"
    implementation "ru.tinkoff.kora:logging-logback"

    implementation "org.postgresql:postgresql:42.7.7"  // JDBC driver is required (not bundled)
}
```

All `ru.tinkoff.kora:*` artifacts inherit their version from the `kora-parent` BOM — never pin them individually.

Kotlin: use `ksp "ru.tinkoff.kora:symbol-processors"` instead of `annotationProcessor`, and `implementation("...")` syntax.

### 2. Plug the module into `@KoraApp`

```java
@KoraApp
public interface Application extends
        HoconConfigModule,
        LogbackModule,
        JdbcDatabaseModule { }
```

`JdbcDatabaseModule` provides `JdbcDatabase`, its `JdbcConnectionFactory`, and the `JdbcDatabaseConfig` reader bound to the `db` config section.

### 3. Define an entity with `@EntityJdbc`

```java
@EntityJdbc
@Table("entities")
public record Entity(
        @Id @Column("id") Long id,
        @Column("value1") int field1,
        @Column("value2") String value2,
        @Nullable @Column("value3") String value3) {}
```

`@EntityJdbc` (from `ru.tinkoff.kora.database.jdbc`) makes the processor generate an optimized result converter. `@Table`/`@Column`/`@Id` come from `ru.tinkoff.kora.database.common.annotation`.

### 4. Repository with SQL macros

```java
@Repository
public interface EntityRepository extends JdbcRepository {

    @Query("SELECT %{return#selects} FROM %{return#table} WHERE id = :id")
    @Nullable
    Entity findById(Long id);

    @Query("SELECT %{return#selects} FROM %{return#table}")
    List<Entity> findAll();

    @Query("INSERT INTO %{entity#inserts}")
    UpdateCount insert(Entity entity);

    @Query("UPDATE %{entity#table} SET %{entity#updates} WHERE %{entity#where = @id}")
    UpdateCount update(Entity entity);

    @Query("DELETE FROM entities WHERE id = :id")
    UpdateCount deleteById(Long id);
}
```

### 5. Generated identifier (auto-increment / sequence)

When the database assigns the key, annotate the method with `@Id` and return the id type, or use `RETURNING`:

```java
@Query("INSERT INTO %{entity#inserts-= @id}")
@Id
Long insert(Entity entity);          // returns DB-generated key (works for @Batch too)

@Query("INSERT INTO entities(name) VALUES (:entity.name) RETURNING id")
long insertReturning(Entity entity); // explicit RETURNING projection
```

### 6. Transactions in a service

```java
@Component
public final class EntityService {
    private final EntityRepository repository;

    public EntityService(EntityRepository repository) {
        this.repository = repository;
    }

    public List<Entity> saveAll(Entity one, Entity two) {
        return repository.getJdbcConnectionFactory().inTx(() -> {
            repository.insert(one);
            repository.insert(two);
            return List.of(one, two);
        });
    }
}
```

Every repository method called inside the `inTx()` lambda joins the same transaction; an exception rolls the whole block back. `JdbcConnectionFactory` is reachable via `repository.getJdbcConnectionFactory()` or by injecting `JdbcConnectionFactory` directly.

---

## Configuration (`application.conf`)

```hocon
db {
    jdbcUrl = ${POSTGRES_JDBC_URL}   // required, e.g. "jdbc:postgresql://localhost:5432/postgres"
    username = ${POSTGRES_USER}      // required
    password = ${POSTGRES_PASS}      // required
    poolName = "kora"                // required: Hikari pool name
    maxPoolSize = 10
    minIdle = 0
    connectionTimeout = "10s"        // durations are strings, not millisecond numbers
    idleTimeout = "10m"
    maxLifetime = "15m"
    telemetry.logging.enabled = false
    telemetry.metrics.enabled = true
    telemetry.tracing.enabled = true
}
```

Externalize every credential with `${VAR}` / `${?VAR}` / `${?VAR:default}`. Full key list and YAML form: [database-jdbc-config-reference.md](references/database-jdbc-config-reference.md).

---

## SQL macros

Macros expand at compile time into SQL the developer could have written by hand. Target a method argument by name or the result via `return`; separate target and command with `#`.

| Macro | Expands to | Example result |
|-------|-----------|----------------|
| `%{return#selects}` | column list of the return entity | `id, value1, value2, value3` |
| `%{return#table}` / `%{entity#table}` | `@Table` name (or snake_case class name) | `entities` |
| `%{entity#inserts}` | full `INSERT INTO table(cols) VALUES(:entity...)` | see below |
| `%{entity#updates}` | `col = :entity.field, ...` for `SET` | `value1 = :entity.field1, ...` |
| `%{entity#where = @id}` | `WHERE` by the `@Id` field(s) | `id = :entity.id` |
| `%{id#where}` | `WHERE` for a composite-key argument named `id` | `a = :id.a AND b = :id.b` |

Field enumeration after a command: `=` keeps only the listed fields, `-=` excludes them; the `@id` keyword refers to the `@Id` field(s).

```java
@Query("INSERT INTO %{entity#inserts-= @id}")   // every column except the @Id
@Id Long insert(Entity entity);

@Query("INSERT INTO %{entity#inserts = value1,value2}")  // only these columns
UpdateCount insertPartial(Entity entity);
```

The only macro commands are `table`, `selects`, `inserts`, `updates`, `where`. There is no `deletes` command — write `DELETE FROM ... WHERE ...` explicitly.

---

## Repository method signatures

`T` is the return type, `List<T>`, `Void`, or `UpdateCount`.

| Signature | Use |
|-----------|-----|
| `T find(...)` | row must exist (throws otherwise) |
| `@Nullable T find(...)` | optional single row — **preferred** over `Optional` (no allocation) |
| `Optional<T> find(...)` | optional single row, Optional flavor |
| `List<T> find(...)` | zero-or-many (empty list, never null) |
| `UpdateCount write(...)` | number of affected rows for INSERT/UPDATE/DELETE |
| `void write(...)` | result not needed |
| `@Id Long insert(...)` | database-generated identifier |
| `CompletionStage<T>` | async — requires an `Executor` bound to `JdbcDatabase` |
| `Mono<T>` | reactive — add `io.projectreactor:reactor-core` and an `Executor` |

Kotlin adds `suspend fun ...(): T` and `T?` / `Unit` returns.

---

## References

| Topic | File |
|-------|------|
| `@Repository`, `@Query`, macros, batch, inheritance, multiple databases | [repository-pattern-reference.md](references/repository-pattern-reference.md) |
| `@Table`/`@Column`/`@Id`/`@Embedded`, naming strategy, type mapping, generated ids | [entity-mapping-reference.md](references/entity-mapping-reference.md) |
| `inTx()`, post-commit/rollback actions, isolation, locking | [transactions-reference.md](references/transactions-reference.md) |
| `JdbcResultSetMapper`/`JdbcRowMapper`/`JdbcResultColumnMapper`/`JdbcParameterColumnMapper`, enum/array/JSONB | [custom-mappers-reference.md](references/custom-mappers-reference.md) |
| HikariCP config, drivers, telemetry, YAML | [database-jdbc-config-reference.md](references/database-jdbc-config-reference.md) |
| HikariCP pool tuning by workload, leak detection | [connection-pool-reference.md](references/connection-pool-reference.md) |
| Flyway / Liquibase schema migrations | [migrations-reference.md](references/migrations-reference.md) |

---

## Assets

| Template | Purpose |
|----------|---------|
| `jdbc-entity-single-id.{java,kt}.template` | entity with a single-field id |
| `jdbc-entity-composite-id.{java,kt}.template` | entity with an `@Embedded` composite key |
| `jdbc-crud-single-id-repository.{java,kt}.template` | full CRUD repository (single id) |
| `jdbc-crud-composite-id-repository.{java,kt}.template` | full CRUD repository (composite id) |
| `jdbc-crud-abstract-macros-repository.java.template` / `jdbc-crud-abstract-single-id-macros-repository.kt.template` | reusable generic CRUD base interface |
| `jdbc-repository-with-enum-mapper.{java,kt}.template` | entity + enum column/parameter mappers |
| `jdbc-repository-with-array-mapper.java.template` | PostgreSQL array parameter mapper |
| `jdbc-service-with-transactions.java.template` | `@Component` service using `inTx()` |

Generate a starter entity + repository:

```bash
python scripts/generate_repository.py --entity User --table users --id-type Long --lang java --package com.example.model
```

---

## Testing

Use `@KoraAppTest` with `test-junit5` plus a Testcontainers PostgreSQL extension; inject the real repository with `@TestComponent` and point the config at the container.

```java
@TestcontainersPostgreSQL(mode = ContainerMode.PER_RUN,
        migration = @Migration(engine = Migration.Engines.FLYWAY,
                apply = Migration.Mode.PER_METHOD, drop = Migration.Mode.PER_METHOD))
@KoraAppTest(Application.class)
class EntityRepositoryTest implements KoraAppTestConfigModifier {

    @ConnectionPostgreSQL
    private JdbcConnection connection;

    @TestComponent
    private EntityRepository repository;

    @Override
    public KoraConfigModification config() {
        return KoraConfigModification.ofSystemProperty("POSTGRES_JDBC_URL", connection.params().jdbcUrl())
                .withSystemProperty("POSTGRES_USER", connection.params().username())
                .withSystemProperty("POSTGRES_PASS", connection.params().password());
    }

    @Test
    void insertThenFind() {
        repository.insert(new Entity(null, 1, "two", null));
        assertFalse(repository.findAll().isEmpty());
    }
}
```

Test dependencies: `testImplementation "ru.tinkoff.kora:test-junit5"` and `testImplementation "io.goodforgod:testcontainers-extensions-postgres:0.13.1"`.

---

## Common pitfalls

| Symptom | Fix |
|---------|-----|
| Graph build: "required dependency JdbcRepository / Entity not found" | `@KoraApp` must `extend JdbcDatabaseModule`; entity needs `@EntityJdbc` |
| `*RepositoryImpl` not generated | annotation processor missing (`annotation-processors` / KSP `symbol-processors`) |
| Generated id is always null | use `@Id` on the method (and exclude it via `inserts-= @id`) or add `RETURNING id` |
| Macro renders literally / fails | use `#` not `.` (`%{entity#inserts}`); only `table/selects/inserts/updates/where` exist |
| `List<T>` parameter treated as one value | annotate with `@Batch` |
| Driver `ClassNotFoundException` | add the JDBC driver dependency (it is not bundled) |
| Operations outside `inTx()` not rolled back | wrap all related calls in one `inTx()` block |
| `connectionTimeout = 30000` ignored | durations are strings: `"10s"`, `"10m"` |
| @Column on every field looks mandatory | Column names default to `snake_lower_case` — `@Column` only for non-standard names (see [Custom Mappers Advanced](references/custom-mappers-advanced-reference.md)) |
| @Mapping required for custom types | `@Component` mappers are auto-discovered by type (see [Custom Mappers Advanced](references/custom-mappers-advanced-reference.md)) |
| @Batch with RETURNING doesn't return rows | Use `default` method with `inTx()` for multi-row INSERT…RETURNING (see [Custom Mappers Advanced](references/custom-mappers-advanced-reference.md)) |

---

## Column Mappers

For advanced mapper patterns (auto-discovery, generic enum mappers, @Batch limitations), see [Custom Mappers Advanced](references/custom-mappers-advanced-reference.md).

---

## Version compatibility

| Component | Version |
|-----------|---------|
| Kora BOM (`kora-parent`) | 1.2.17 |
| Java | 21+ |
| Gradle | 9+ |
| PostgreSQL driver | 42.7.x |
