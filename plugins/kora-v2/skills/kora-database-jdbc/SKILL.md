---
name: kora-database-jdbc
description: "Kora 2.0 JDBC repositories — @Repository interfaces extending JdbcRepository, @Query with SQL macros (%{return#selects}, %{entity#inserts}, %{entity#where = @id}), @EntityJdbc from io.koraframework.database.jdbc.annotation, @Table/@Column/@Id/@Embedded/@Batch, UpdateCount, generated keys via @Id on the method, JdbcResultSetMapper/JdbcRowMapper/JdbcResultColumnMapper/JdbcParameterColumnMapper, transactions through repository.executor().inTx(...) on JdbcExecutor, and PostgreSQL types via database-jdbc-postgres (@Pg arrays/List and interval, PgRange, @PgJson/@PgJsonb). HikariCP pool configured under the jdbc config section. Use when adding a PostgreSQL/MySQL/Oracle repository to a Kora service, porting a 1.x repository, or debugging 'Config expected value, but got null at path ROOT.jdbc.username', suspend-repository rejections, or repository mapper graph errors."
license: Apache-2.0
metadata:
  kora-version: "2.x"
---

# Kora Database JDBC

> **Kora sub-skill — obey the [kora-v2 meta rules](../../SKILL.md) on every task:** **R0** ground the workspace on Kora 2.0 refs before starting (framework source at tag `2.0.0.RC2` + `kora-examples` at `migration/2.0` + Kora 2.0 docs at koraframework.io/v2, which trail the source; 1.x `kora-docs` pages are never an authority) · **R1** read this sub-skill before writing code · **R2** Kora 2.0 APIs only — no Spring/Micronaut/Quarkus, no Kora 1.x APIs, no invented annotations or config keys · **R3** journal any incorrect Kora usage. Add comments/Javadoc only if asked.

| | |
|---|---|
| **Artifact** | `io.koraframework:database-jdbc` (BOM `io.koraframework:kora-bom`) |
| **Processor** | `annotationProcessor "io.koraframework:annotation-processors"` (Java) · `ksp("io.koraframework:symbol-processors")` (Kotlin) |
| **Graph module** | `io.koraframework.database.jdbc.JdbcDatabaseModule` |
| **Config section** | **`jdbc`** (was `db` in Kora 1.x) |
| **Pool** | HikariCP `7.1.0`, pulled in transitively by `database-jdbc` |
| **PostgreSQL types** | `io.koraframework:database-jdbc-postgres` → `io.koraframework.database.jdbc.postgres.PostgresJdbcDatabaseModule` (arrays, `interval`, ranges, `json`/`jsonb`) |

JDBC access to relational databases. A repository is a `@Repository` interface extending
`JdbcRepository`; the annotation processor (Java) or KSP (Kotlin) generates
`$<Name>_Impl` at compile time — no reflection, no runtime proxies.

**Repository contracts are synchronous.** There is no reactive, `CompletionStage` or Kotlin
`suspend` repository in Kora 2.0; blocking JDBC runs on virtual threads. A `suspend` repository
method is rejected by KSP with *"Suspend methods are not supported by the repository generator."*
R2DBC and Vert.x SQL do not exist in 2.0 at all.

---

## Quick start

### 1. Dependencies

```groovy
dependencies {
    koraBom platform("io.koraframework:kora-bom:2.0.0.RC2")
    annotationProcessor "io.koraframework:annotation-processors"   // mandatory: generates $<Name>_Impl

    implementation "io.koraframework:database-jdbc"
    implementation "io.koraframework:config-hocon"
    implementation "io.koraframework:logging-logback"

    implementation "org.postgresql:postgresql:42.7.7"              // the driver is NOT bundled
}
```

On PostgreSQL, `implementation "io.koraframework:database-jdbc-postgres"` replaces both the
`database-jdbc` line and the driver line — it depends on `database-jdbc` and brings
`org.postgresql:postgresql` with it. See [PostgreSQL types](#postgresql-types-database-jdbc-postgres).

Kotlin uses `ksp("io.koraframework:symbol-processors")` instead of `annotationProcessor`.
Artifacts inherit their version from `kora-bom` — never pin `io.koraframework:*` individually.
Java 25 is the floor: Kora 2.0 artifacts are compiled to class-file 69.

### 2. Plug the module into `@KoraApp`

```java
@KoraApp
public interface Application extends
        HoconConfigModule,
        LogbackModule,
        JdbcDatabaseModule {

    static void main(String[] args) {
        KoraApplication.run(ApplicationGraph::graph);
    }
}
```

`JdbcDatabaseModule` supplies the `JdbcDataSource` (which *is* the `JdbcExecutor`), the default
column/row mappers from `JdbcMapperModule`, and the `JdbcDatabaseConfig` reader bound to the
**`jdbc`** config section.

### 3. Define an entity

```java
@EntityJdbc
@Table("entities")
public record Entity(
        @Id String id,
        @Column("value1") int field1,
        String value2,
        @Nullable String value3) {}
```

- `@EntityJdbc` — `io.koraframework.database.jdbc.annotation.EntityJdbc` (**moved** in 2.0; it was
  `…database.jdbc.EntityJdbc` in 1.x).
- `@Table`, `@Column`, `@Id`, `@Embedded`, `@Batch`, `@Query`, `@Repository` — all in
  `io.koraframework.database.common.annotation`, unchanged position.
- `@Nullable` — JSpecify `org.jspecify.annotations.Nullable`. It is a **type-use** annotation, so on
  a qualified nested type it goes before the simple name: `Entity.@Nullable FieldType`.
- Without `@Column` a field maps to its `snake_lower_case` name (`executorUuid` → `executor_uuid`,
  `HTTPClient` → `http_client`) — the annotation processor and KSP produce the same names.

Kotlin uses use-site targets on data-class properties:

```kotlin
@EntityJdbc
@Table("entities")
data class Entity(
    @field:Id val id: String,
    @field:Column("value1") val field1: Int,
    val value2: String,
    val value3: String?
)
```

### 4. Repository with SQL macros

```java
@Repository
public interface EntityRepository extends JdbcRepository {

    @Query("SELECT %{return#selects} FROM %{return#table} WHERE id = :id")
    @Nullable
    Entity findById(String id);

    @Query("SELECT %{return#selects} FROM %{return#table}")
    List<Entity> findAll();

    @Query("INSERT INTO %{entity#inserts}")
    UpdateCount insert(Entity entity);

    @Query("UPDATE %{entity#table} SET %{entity#updates} WHERE %{entity#where = @id}")
    UpdateCount update(Entity entity);

    @Query("DELETE FROM entities WHERE id = :id")
    UpdateCount deleteById(String id);
}
```

A macro target must be resolvable **in that method**: a parameter name, `return`, or a type
parameter of the repository. `%{entity#table}` in a method that has no parameter called `entity`
fails to compile with *"Query macro target `entity` cannot be resolved"* — write the table name
literally there, or use `%{V#table}` in a generic base interface.

### 5. Database-generated identifier

```java
@Query("INSERT INTO entities_sequence(name) VALUES (:entity.name)")
@Id
Long insertGenerated(Entity entity);              // via Statement.getGeneratedKeys()

@Query("INSERT INTO entities_sequence(name) VALUES (:entity.name)")
@Id
List<Long> insertGenerated(@Batch List<Entity> entity);   // works for @Batch too

@Query("INSERT INTO entities_sequence(name) VALUES (:entity.name) RETURNING id")
long insert(Entity entity);                       // explicit RETURNING projection
```

### 6. Transactions

```java
@Component
public final class EntityService {

    private final EntityRepository repository;

    public EntityService(EntityRepository repository) {
        this.repository = repository;
    }

    public List<Entity> saveAll(Entity one, Entity two) {
        return repository.executor().inTx(() -> {
            repository.insert(one);
            repository.insert(two);
            return List.of(one, two);
        });
    }
}
```

`JdbcRepository.executor()` returns the `JdbcExecutor` (**replaces** 1.x
`getJdbcConnectionFactory()`). Every repository call inside the lambda joins the same transaction;
a thrown exception rolls the whole block back.

**Kotlin needs an explicit SAM constructor** — the `inTx` overloads no longer infer from a bare
lambda:

```kotlin
val saved = repository.executor().inTx(JdbcExecutor.SqlSupplier {
    repository.insert(one)
    listOf(one)
})

repository.executor().inTx(JdbcExecutor.SqlRunnable {
    repository.deleteAll()
})
```

Without it the compiler reports `Cannot infer type for type parameter T` or
`Overload resolution ambiguity` — neither mentions transactions.

---

## Configuration (`application.conf`)

```hocon
jdbc {
    jdbcUrl = ${POSTGRES_JDBC_URL}   // required
    username = ${POSTGRES_USER}      // required
    password = ${POSTGRES_PASS}      // required
    poolName = "kora"                // required
    maxPoolSize = 10
    minIdle = 0
    connectionTimeout = "10s"        // durations are strings, not millisecond numbers
    idleTimeout = "10m"
    maxLifetime = "15m"
    initializationFailTimeout = "10s"  // omit to skip the startup connectivity check entirely
    telemetry.logging.enabled = true    // default false
    telemetry.metrics.enabled = true    // default false
}
```

The section is **`jdbc`**, not `db`. A leftover `db { }` block compiles fine and dies at startup
with `ConfigValueException: Config expected value, but got null at path: 'ROOT.jdbc.username'` —
which names a section your config does not contain. The same rename applies to HOCON embedded in
test sources through `KoraConfigModification.ofString("""…""")`.

Full key list, telemetry sub-keys and the YAML form:
[database-jdbc-config-reference.md](references/database-jdbc-config-reference.md).

---

## PostgreSQL types (`database-jdbc-postgres`)

Arrays, `interval`, range types and `json`/`jsonb` need no hand-written mappers on PostgreSQL. Put
`PostgresJdbcDatabaseModule` on the `@KoraApp` **in place of** `JdbcDatabaseModule` (it extends
it) and opt in per field or parameter with a tag:

```java
@EntityJdbc
@Table("articles")
public record Article(
        @Id Long id,
        @Pg List<String> tags,                  // varchar[]
        @Pg @Nullable Duration ttl,             // interval
        PgRange<LocalDate> validity,            // daterange — PgRange needs no tag
        @PgJsonb Attributes attributes) {}      // jsonb; Attributes is a @Json record

@Query("SELECT %{return#selects} FROM %{return#table} WHERE id = ANY(:ids)")
List<Article> findByIds(@Pg List<Long> ids);
```

- `@Pg`, `@PgJson`, `@PgJsonb` live in `io.koraframework.database.jdbc.postgres.annotation`;
  `PgRange` in `io.koraframework.database.jdbc.postgres`. The mappers are tagged, so an untagged
  `List<Long>` field is still unsupported.
- `@Pg` element types: `bool`, `int2`, `int4`, `int8`, `float4`, `float8`, `numeric`, `varchar`,
  `uuid` — as `List<T>` (parameters also `Set<T>`/`Collection<T>`), boxed `T[]`, or primitive
  arrays. `@Pg Duration` / `@Pg Period` map to `interval`.
- `@PgJson` / `@PgJsonb` pick the sent parameter type (`jsonb` operators such as `@>` need
  `@PgJsonb`); no `::jsonb` cast in SQL. `JsonNullable<T>` keeps SQL `NULL` and JSON `null` apart.
- Kotlin writes the tags without a use-site target: `@Pg val tags: List<String>`.

Full matrix, null handling, `= ANY(:ids)`, range canonicalisation and pitfalls:
[postgres-mappers-reference.md](references/postgres-mappers-reference.md).

---

## SQL macros

Macros expand at compile time into SQL you could have written by hand. `#` separates the target
from the command; the target is a method parameter name, `return`, a nested path
(`return.user`), or a repository/method type parameter.

| Macro | Expands to |
|-------|-----------|
| `%{entity#table}` | `@Table` value, else the `snake_case` class name |
| `%{entity#table as e}` | the same, plus an SQL alias — other macros then qualify columns with it |
| `%{return#selects}` | selected columns, adding `AS` aliases when a `table as` alias is in play |
| `%{entity#columns}` | bare column names |
| `%{entity#values}` | named bind parameters (`:entity.id, :entity.field1, …`) |
| `%{entity#inserts}` | `table(columns) VALUES (:values)` |
| `%{entity#updates}` | `column = :field` assignments, **`@Id` fields excluded automatically** |
| `%{entity#where}` | `column = :field` predicates joined with `AND` |

Those eight are the whole set — `table`, `table as`, `selects`, `columns`, `values`, `inserts`,
`updates`, `where`. There is no `deletes` command; write `DELETE FROM … WHERE …` yourself.

Field enumeration follows the command: `=` keeps only the listed fields, `-=` excludes them, and
`@id` refers to the `@Id` field(s).

```java
@Query("INSERT INTO %{entity#inserts -= @id}")           // every column except the @Id
@Id Long insert(Entity entity);

@Query("INSERT INTO %{entity#table}(%{entity#columns -= @id}) VALUES (%{entity#values -= @id})")
UpdateCount insertExplicit(Entity entity);

@Query("INSERT INTO %{entity#inserts} ON CONFLICT (%{entity#selects = @id}) DO UPDATE SET %{entity#updates}")
UpdateCount upsert(Entity entity);
```

---

## Repository method signatures

| Signature | Use |
|-----------|-----|
| `T find(...)` | single row; when the row is absent the generated code throws `NullPointerException: Result mapping is expected non-null, but was null` |
| `@Nullable T find(...)` | optional single row — **preferred** over `Optional` |
| `Optional<T> find(...)` | optional single row, `Optional` flavour |
| `List<T> find(...)` | zero-or-many (empty list, never null) |
| `UpdateCount write(...)` | affected-row count; `UpdateCount.value()` is a `long` |
| `void write(...)` | result not needed |
| `@Id Long insert(...)` / `@Id List<Long> insert(@Batch …)` | database-generated identifiers |
| `int[]` / `long[]` write(`@Batch` …) | raw per-statement batch counts |

Kotlin writes the same set with `T?` and `Unit`. **`suspend` is rejected**, and so are
`Mono`/`Flux`/`CompletionStage` — those contracts no longer exist.

---

## References

| Topic | File |
|-------|------|
| `@Repository`, `@Query`, macros, batch, generated ids, joins, generic base repos, second database | [repository-pattern-reference.md](references/repository-pattern-reference.md) |
| `@Table`/`@Column`/`@Id`/`@Embedded`, naming strategy, supported types, JSONB, nullability | [entity-mapping-reference.md](references/entity-mapping-reference.md) |
| `executor().inTx(...)`, isolation levels, post-commit/rollback actions, locking, Kotlin SAM | [transactions-reference.md](references/transactions-reference.md) |
| PostgreSQL module: `@Pg` arrays/collections and `interval`, `PgRange`, `@PgJson`/`@PgJsonb`, `JsonNullable`, `= ANY(:ids)` | [postgres-mappers-reference.md](references/postgres-mappers-reference.md) |
| The four mapper contracts, enum/array/JSONB mappers, `@Mapping`, Kotlin nullability | [custom-mappers-reference.md](references/custom-mappers-reference.md) |
| When a mapper is constructed vs injected, `@Component` rules, generic mapper modules, batch limits | [custom-mappers-advanced-reference.md](references/custom-mappers-advanced-reference.md) |
| Full `jdbc` config key list, telemetry defaults, drivers, YAML | [database-jdbc-config-reference.md](references/database-jdbc-config-reference.md) |
| HikariCP pool tuning, leak detection, pool troubleshooting | [connection-pool-reference.md](references/connection-pool-reference.md) |
| Flyway / Liquibase schema migrations | [migrations-reference.md](references/migrations-reference.md) |

---

## Assets

| Template | Purpose |
|----------|---------|
| `jdbc-entity-single-id.{java,kt}.template` | entity with a single-field id |
| `jdbc-entity-composite-id.{java,kt}.template` | entity with an `@Embedded` composite key |
| `jdbc-crud-single-id-repository.{java,kt}.template` | full CRUD repository (single id) |
| `jdbc-crud-composite-id-repository.{java,kt}.template` | full CRUD repository (composite id) |
| `jdbc-crud-abstract-macros-repository.java.template`, `jdbc-crud-abstract-single-id-macros-repository.kt.template` | reusable generic CRUD base interface |
| `jdbc-repository-with-enum-mapper.{java,kt}.template` | entity + enum column/parameter mappers |
| `jdbc-postgres-repository.{java,kt}.template` | `database-jdbc-postgres`: `@Pg` list/interval, `PgRange`, `@PgJsonb`, `= ANY(:ids)` |
| `jdbc-repository-with-array-mapper.java.template` | hand-written `List<T>` mappers discovered by type (types the PostgreSQL module does not cover) |
| `jdbc-service-with-transactions.java.template` | `@Component` service using `executor().inTx()` |

Generate a starter entity + repository:

```bash
python3 scripts/generate_repository.py --entity User --table users --id-type Long --lang java \
    --package com.example.repository --dry-run
```

Drop `--dry-run` to write the files.

---

## Common pitfalls

| Symptom | Fix |
|---------|-----|
| `Config expected value, but got null at path: 'ROOT.jdbc.username'` | the config section is `jdbc`, not `db` — including inside `KoraConfigModification.ofString(...)` in tests |
| `cannot find symbol: class EntityJdbc` after a 1.x port | `@EntityJdbc` moved to `io.koraframework.database.jdbc.annotation` |
| KSP: *"Suspend methods are not supported by the repository generator"* | repositories are synchronous; removing `suspend` propagates up the call chain — see [transactions-reference.md](references/transactions-reference.md#kotlin-removing-suspend) |
| `Cannot infer type for type parameter T` / `Overload resolution ambiguity` on `inTx` | Kotlin needs `JdbcExecutor.SqlSupplier { … }` or `JdbcExecutor.SqlRunnable { … }` |
| `getJdbcConnectionFactory()` does not exist | it is `executor()`, returning `JdbcExecutor` |
| Kotlin mapper: `'set' overrides nothing` / `'apply' overrides nothing` | the 2.0 contracts are JSpecify-marked; declare the parameter `T?` |
| `No component found for dependency: JdbcResultColumnMapper<X>` | the mapper is injected, not constructed — add `@Component` (see [custom-mappers-advanced-reference.md](references/custom-mappers-advanced-reference.md)) |
| `Multiple components match dependency` for a mapper | two graph components produce the same mapper type — drop the redundant `@Component`, or disambiguate with `@Mapping`/`@Tag` |
| `Query macro target 'entity' cannot be resolved` | the macro target must be a parameter of *that* method; use a literal table name or `%{V#table}` |
| `$<Name>_Impl` not generated | the processor is missing (`annotation-processors` / KSP `symbol-processors`) |
| Java build dies with `NullPointerException: Cannot invoke "javax.lang.model.element.Element.getAnnotationMirrors()" because "element" is null`, `JdbcTypesExtension.getDependencyGenerator` in the trace | a repository method returns `byte[]` or `List<byte[]>`: the extension resolves `JdbcResultSetMapper<byte[]>` and asks the array type for its `@EntityJdbc` element, which an array does not have. Fixed in `2.0.0.RC2` (kora-projects/kora PR #959) — only `2.0.0.RC1` is affected, KSP never was; on RC1 return a single-column `@EntityJdbc` record (`record Payload(byte[] data)`, `List<Payload>`) |
| Client gets an error for committed work; an `afterCommit` fires for a rolled-back transaction; `StackOverflowError` through `JdbcExecutor.doInTx` | a post-commit action failure propagates out of `inTx`; on `2.0.0.RC1` (fixed in `2.0.0.RC2`, kora-projects/kora PR #967) actions are also never cleared from the context and the first failure skips the rest — see [transactions-reference.md](references/transactions-reference.md#post-commit-and-post-rollback-actions) |
| `SQL query placeholder has no matching method parameter: :id / Available parameters: - :arg0` | stale incremental build — the processor read the interface from a class file without parameter names; `./gradlew clean` or `--rerun-tasks` |
| Metrics/logs for queries never appear | `telemetry.logging.enabled` and `telemetry.metrics.enabled` default to **false** in 2.0 |
| `No component found for dependency: JdbcResultColumnMapper<List<Long>>` on PostgreSQL | add `database-jdbc-postgres`, extend `PostgresJdbcDatabaseModule`, and tag the field/parameter `@Pg` |
| `WHERE id IN (:ids)` with a `List` parameter | bind one array: `WHERE id = ANY(:ids)` with `@Pg List<Long> ids` |
| `connectionTimeout = 30000` ignored | durations are strings: `"10s"`, `"10m"` |
| Driver `ClassNotFoundException` | add the JDBC driver dependency; it is not bundled |
| Looking for an R2DBC or Vert.x SQL module | neither exists in 2.0; synchronous JDBC on virtual threads is the only option |

---

## Version compatibility

| Component | Version |
|-----------|---------|
| Kora BOM (`io.koraframework:kora-bom`) | `2.0.0.RC2` from `mavenCentral()` |
| Java | 25 (hard floor — artifacts are class-file 69) |
| Kotlin / KSP | 2.4.20 / 2.3.12 |
| Gradle | 9.7.1 |
| HikariCP | 7.1.0 (transitive via `database-jdbc`) |
| PostgreSQL driver | 42.7.x — the framework tests against `42.7.13` (the version `database-jdbc-postgres` brings); the migrated examples pin `42.7.7` |
