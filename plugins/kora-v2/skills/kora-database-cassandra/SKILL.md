---
name: kora-database-cassandra
description: "Kora 2.0 Cassandra/ScyllaDB repositories — @Repository interfaces extending CassandraRepository, @Query CQL, @EntityCassandra, @UDT, @Batch, @CassandraProfile, CassandraRowMapper/CassandraResultSetMapper/CassandraParameterColumnMapper, and the executor() + CassandraQuery manual API from io.koraframework:database-cassandra. Use when adding a Cassandra repository, mapping rows or user-defined types, tuning driver profiles and consistency under the cassandra config section, or porting a Kora 1.x Cassandra repository that still uses suspend/Mono/Flux or getCassandraConnectionFactory()."
license: Apache-2.0
metadata:
  kora-version: "2.x"
---

# Kora Database Cassandra

> **Kora sub-skill — obey the [kora-v2 meta rules](../../SKILL.md) on every task:** **R0** ground the workspace on Kora 2.0 refs before starting (framework source at tag `2.0.0.RC2` + `kora-examples` at `migration/2.0` + Kora 2.0 docs at koraframework.io/v2, which trail the source; 1.x `kora-docs` pages are never an authority) · **R1** read this sub-skill before writing code · **R2** Kora 2.0 APIs only — no Spring/Micronaut/Quarkus, no Kora 1.x APIs, no invented annotations or config keys · **R3** journal any incorrect Kora usage. Add comments/Javadoc only if asked.

| | |
|---|---|
| **Artifact** | `io.koraframework:database-cassandra` (BOM `io.koraframework:kora-bom`) |
| **Module** | `CassandraDatabaseModule` — `io.koraframework.database.cassandra` |
| **Base interface** | `CassandraRepository` — one method, `CassandraExecutor executor()` |
| **Shared DB annotations** | `io.koraframework.database.common.annotation` — `@Repository`, `@Query`, `@Batch`, `@Table`, `@Column`, `@Id`, `@Embedded` |
| **Cassandra annotations** | `io.koraframework.database.cassandra.annotation` — `@EntityCassandra`, `@UDT`, `@CassandraProfile` |
| **Mapper contracts** | `…cassandra.mapper.result.{CassandraRowMapper, CassandraRowColumnMapper, CassandraResultSetMapper, CassandraAsyncResultSetMapper}` · `…cassandra.mapper.parameter.CassandraParameterColumnMapper` |
| **Manual query API** | `CassandraExecutor` + `CassandraQuery` — `io.koraframework.database.cassandra` |
| **Config section** | `cassandra` |
| **Driver** | `org.apache.cassandra:java-driver-core` 4.19.3 — the **Java packages are still `com.datastax.oss.driver.api.*`** |

## ⚑ The driver moved Maven coordinates, not Java packages

Kora 2.0 resolves the DataStax driver from `org.apache.cassandra:java-driver-core` (with
`org.apache.cassandra:java-driver-metrics-micrometer` for driver metrics), replacing the 1.x
`com.datastax.oss:java-driver-core`. The **groupId** changed; the **package names did not**.
`CqlSession`, `Row`, `ResultSet`, `SettableByName`, `GettableByName`, `UdtValue`,
`UserDefinedType` and `ConsistencyLevel` all still live under `com.datastax.oss.driver.api.*`,
and every Kora 2.0 Cassandra API imports them from there.

So `import com.datastax.oss.driver.api.core.cql.Row;` is **correct** in a 2.0 service; only a
build file that names `com.datastax.oss:java-driver-core` is stale. In practice you never write
the coordinate at all — `io.koraframework:database-cassandra` brings the driver transitively.

---

## Quick Start

### 1. Dependency

**Java** (`build.gradle`):

```groovy
configurations {
    koraBom
    annotationProcessor.extendsFrom(koraBom); compileOnly.extendsFrom(koraBom); implementation.extendsFrom(koraBom)
    api.extendsFrom(koraBom); testImplementation.extendsFrom(koraBom); testAnnotationProcessor.extendsFrom(koraBom)
}

dependencies {
    koraBom platform("io.koraframework:kora-bom:$koraVersion")   // koraVersion=2.0.0.RC2
    annotationProcessor "io.koraframework:annotation-processors"

    implementation "io.koraframework:database-cassandra"
    implementation "io.koraframework:config-hocon"
    implementation "io.koraframework:logging-logback"
}
```

**Kotlin** (`build.gradle.kts`) — KSP instead of `annotationProcessor`, never `kapt`:

```kotlin
plugins {
    kotlin("jvm") version "2.4.20"
    id("com.google.devtools.ksp") version "2.3.12"
}

dependencies {
    implementation(platform("io.koraframework:kora-bom:${property("koraVersion")}"))
    ksp("io.koraframework:symbol-processors:${property("koraVersion")}")

    implementation("io.koraframework:database-cassandra")
    implementation("io.koraframework:config-hocon")
    implementation("io.koraframework:logging-logback")
}
```

Java toolchain 25 is the floor for every Kora 2.0 artifact.

### 2. Enable the module

```java
@KoraApp
public interface Application extends HoconConfigModule, LogbackModule, CassandraDatabaseModule {

    static void main(String[] args) {
        KoraApplication.run(ApplicationGraph::graph);
    }
}
```

### 3. Entity

```java
@EntityCassandra
public record User(
    String id,
    @Column("value1") int field1,
    String value2,
    @Nullable String value3
) {}
```

`@Nullable` is JSpecify (`org.jspecify.annotations.Nullable`) and is **type-use**: put it directly
on the type it qualifies. Without `@Nullable` on a component, a null column throws
`NullPointerException` from the generated row mapper.

`@Table` is only needed for [SQL macros](references/cql-repository-reference.md#sql-macros); `@Id`
only matters to macros too — Cassandra needs no primary-key marker for hand-written CQL.
Column names default to `snake_case` of the component name when `@Column` is absent.

### 4. Repository

```java
@Repository
public interface UserRepository extends CassandraRepository {

    @Query("SELECT * FROM users WHERE id = :id")
    @Nullable
    User findById(String id);

    @Query("SELECT * FROM users")
    List<User> findAll();

    @Query("INSERT INTO users(id, value1, value2, value3) VALUES (:user.id, :user.field1, :user.value2, :user.value3)")
    void insert(User user);

    @Query("DELETE FROM users WHERE id = :id")
    void deleteById(String id);
}
```

> **Entity parameter binding:** when a method parameter is an entity, each column binds through the
> dotted accessor `:param.field` (`:user.id`). A bare `:id` resolves only when `id` is itself the
> name of a method parameter, as in `findById(String id)`. An unused method parameter is a
> compile error (`Query parameter is unused`).

### 5. Configuration

```hocon
cassandra {
  auth {
    login = ${CASSANDRA_USER}
    password = ${CASSANDRA_PASS}
  }
  basic {
    contactPoints = ${CASSANDRA_CONTACT_POINTS}
    dc = ${CASSANDRA_DC}
    sessionKeyspace = ${CASSANDRA_KEYSPACE}
    request {
      timeout = 5s
    }
  }
  telemetry.logging.enabled = true
}
```

`telemetry.logging.enabled` and `telemetry.metrics.enabled` default to **false** in Kora 2.0 —
turn them on explicitly or you get no query logs and no `db_*` metrics.

---

## Execution model — what a repository method may return

Kora 2.0 contracts are synchronous and run on virtual threads. Cassandra keeps one narrow
exception: the **Java** generator still emits the driver's own `executeAsync` path.

| Language | Supported return types |
|---|---|
| Java | `void`, `T`, `@Nullable T`, primitives, `Optional<T>`, `List<T>`, **and** `CompletionStage<T>` / `CompletableFuture<T>` (including `…<Void>` and `…<List<T>>`) |
| Kotlin | `Unit`, `T`, `T?`, `List<T>` — **synchronous only** |

- **Kotlin `suspend` is rejected at compile time.** The KSP repository builder fails before any
  generator runs, with `Suspend methods are not supported by the repository generator.` The
  suggested replacement is Java `StructuredTaskScope` for real parallelism.
- **`Flow<T>` is not a usable Kotlin return type** either: nothing in the framework tests or the
  migrated Kotlin example uses it, and the generator's non-suspend path applies the mapper to a
  `ResultSet` while the `Flow` branch supplies a `CassandraRowMapper` whose `apply` takes a `Row`
  — the generated file does not type-check.
- **Reactor is gone.** `database-cassandra` has no Reactor dependency, no `Mono`/`Flux` handling
  and no `CassandraReactiveResultSetMapper`. Do not add `reactor-core` for it.
- `Optional<T>` works in Java only; in Kotlin use `T?`.
- `UpdateCount` is a JDBC-only return type — the Cassandra generator does not handle it.

Java async example (this is the shape the migrated Kora example ships and tests):

```java
@Repository
public interface UserAsyncRepository extends CassandraRepository {

    @Query("SELECT * FROM users WHERE id = :id")
    CompletableFuture<User> findById(String id);

    @Query("SELECT * FROM users")
    CompletionStage<List<User>> findAll();

    @Query("INSERT INTO users(id, value1) VALUES (:user.id, :user.field1)")
    CompletionStage<Void> insert(User user);
}
```

See [Async Patterns Reference](references/async-patterns-reference.md) for chaining, batching and
the Kotlin migration path.

---

## CRUD, batches and lightweight transactions

```java
// Batch: one single-row statement, the list parameter marked @Batch.
// The generator builds a BatchStatement with DefaultBatchType.UNLOGGED.
@Query("INSERT INTO users(id, value1) VALUES (:user.id, :user.field1)")
void insertBatch(@Batch List<User> user);

// LWT: the first column of the result is the [applied] flag, so boolean works
@Query("INSERT INTO users(id, value1) VALUES (:user.id, :user.field1) IF NOT EXISTS")
boolean insertIfNotExists(User user);

@Query("UPDATE users SET value2 = :value2 WHERE id = :id IF value2 = :oldValue2")
boolean updateIfMatches(String id, String value2, String oldValue2);

@Query("TRUNCATE users")
void deleteAll();
```

A `@Batch` method must not declare a result mapper — the generator returns no mapped result for
batch statements. Cassandra has **no transactions**: `CassandraExecutor` has no `inTx` and there
is nothing equivalent to JDBC's `JdbcExecutor.inTx(...)`. LWT (`IF`/`IF NOT EXISTS`) is per-partition
compare-and-set, not a multi-statement transaction.

`IN` clauses need care: Kora ships **no** `CassandraParameterColumnMapper<List<T>>` for native
element types, so `@Query("… WHERE id IN :ids") List<User> findByIds(List<String> ids)` fails the
graph with `No component found for dependency: CassandraParameterColumnMapper<List<String>>`.
Bind an `IN` list with `CassandraQuery.named().bindIn(...)` through `executor()`, or supply your
own list mapper via `@Mapping`.

---

## User-defined types

```java
@Repository
public interface UserRepository extends CassandraRepository {

    @EntityCassandra
    record Entity(String id, Name name) {

        @UDT
        record Name(String first, String last) {}
    }

    @Query("SELECT * FROM entities_udt WHERE id = :id")
    @Nullable
    Entity findById(String id);

    @Query("INSERT INTO entities_udt(id, name) VALUES (:entity.id, :entity.name)")
    void insert(Entity entity);
}
```

```sql
CREATE TYPE IF NOT EXISTS username(first text, last text);
CREATE TABLE IF NOT EXISTS entities_udt (id VARCHAR, name FROZEN<username>, PRIMARY KEY (id));
```

`@UDT` carries **no type name**. The generated mappers read the user-defined type off the bound
statement's own metadata (`_stmt.getType(index)`) and address fields by column name, so the CQL
type may be called anything — only the field names have to line up. Kora generates mappers for a
scalar UDT and for `List<UDT>`; `Set<UDT>` and `Map<K, UDT>` are **not** generated and need a
hand-written mapper. Details in [UDT Mapping Reference](references/udt-mapping-reference.md).

---

## Driver profiles

Request tuning lives under `basic.request`. A profile overrides any `basic.request.*` /
`advanced.*` key it declares and inherits the rest from the root section.

```hocon
cassandra {
  basic.request {
    consistency = "QUORUM"
    serialConsistency = "SERIAL"
    timeout = 5s
  }
  profiles {
    analytics {
      basic.request.consistency = "ONE"
      basic.request.timeout = 30s
      basic.request.pageSize = 1000
    }
  }
}
```

```java
@CassandraProfile("analytics")
@Query("SELECT * FROM events WHERE type = :type ALLOW FILTERING")
List<Event> findByType(String type);
```

`@CassandraProfile` is `@Target(METHOD)` — it cannot go on the repository interface.
See [Consistency Reference](references/consistency-reference.md).

---

## Manual queries — `executor()` and `CassandraQuery`

`CassandraRepository.executor()` returns a `CassandraExecutor` (this replaces the 1.x
`getCassandraConnectionFactory()`). It exposes the live `CqlSession` plus telemetry-wrapped
helpers, and pairs with the `CassandraQuery` builder for dynamic CQL:

```java
var query = CassandraQuery.named()
    .cql("SELECT id, name FROM users WHERE tenant_id = :tenant_id")
    .bind("tenant_id", tenantId)
    .cqlIf(" AND status = :status", status != null)
    .bindIf("status", status, status != null)
    .cqlIf(" AND id IN (:ids)", !ids.isEmpty())
    .bindInIf("ids", ids, !ids.isEmpty())
    .opts(o -> o.consistencyLevel(DefaultConsistencyLevel.LOCAL_QUORUM).pageSize(500))
    .build();

List<User> users = repository.executor()
    .queryList(query, row -> new User(row.getString("id"), row.getString("name")));
```

`CassandraExecutor` also has `currentSession()`, `telemetry()`, `query(...)`, `queryOne(...)` and
`queryOptional(...)`. `queryOne` returns `@Nullable T`. Full API in the
[CQL Repository Reference](references/cql-repository-reference.md#manual-queries).

---

## Custom mappers and the `@Component` rule

| Contract | Signature | Applied with |
|---|---|---|
| `CassandraRowMapper<T>` | `@Nullable T apply(Row row)` | `@Mapping` on the method |
| `CassandraResultSetMapper<T>` | `@Nullable T apply(ResultSet rows)` | `@Mapping` on the method |
| `CassandraRowColumnMapper<T>` | `@Nullable T apply(GettableByName row, int index)` | `@Mapping` on an entity component |
| `CassandraParameterColumnMapper<T>` | `void apply(SettableByName<?> stmt, int index, @Nullable T value)` | `@Mapping` on a parameter or entity component |
| `CassandraAsyncResultSetMapper<T>` | `CompletionStage<T> apply(AsyncResultSet rows)` | `@Mapping` on a Java async method |

**Whether a mapper needs `@Component` is decided by its constructor**, because the generated
repository either constructs the mapper itself or asks the graph for it:

- Java — mapper class is `final` **and** has a public no-arg constructor, and `@Mapping` carries no
  tag → the repository does `new Mapper()` in its own constructor. `@Component` is then optional.
- Kotlin — class is not `open` and has a single no-arg constructor → same, constructed inline.
- Anything else (constructor dependencies, a non-`final`/`open` class, a tagged mapping) → the
  mapper becomes a constructor parameter of the generated repository and **must** be in the graph,
  or the build fails with `No component found for dependency: …`.

Declare **one** component per mapper type; two `@Component`s implementing the same
`CassandraRowMapper<T>` give `Multiple components match dependency:`. Kora's own scalar mappers in
`CassandraMapperModule` are `@DefaultComponent`, so your own `@Component` for the same type wins
without conflict.

**Kotlin nullability trap.** The contracts are `@NullMarked`, so an override must match the
declared nullability exactly. `CassandraParameterColumnMapper.apply` takes `@Nullable T value`:

```kotlin
class FieldTypeParameterMapper : CassandraParameterColumnMapper<FieldType> {
    override fun apply(stmt: SettableByName<*>, index: Int, value: FieldType?) {   // T? — required
        if (value != null) stmt.setInt(index, value.code) else stmt.setToNull(index)
    }
}
```

With `value: FieldType` Kotlin reports `'apply' overrides nothing` and never mentions nullability.
The Java twin compiles either way, so a mechanically ported mapper fails only on the Kotlin side.
Return types may be narrowed to non-null; only parameters must stay nullable.

---

## Assets

### Entities and UDTs
| Template | Language | Description |
|---|---|---|
| `cassandra-entity-single-id.java.template` | Java | `@EntityCassandra` record, single-field key |
| `cassandra-entity-single-id.kt.template` | Kotlin | `@EntityCassandra` data class, single-field key |
| `cassandra-entity-composite-id.java.template` | Java | `@Id @Embedded` composite key record |
| `cassandra-entity-composite-id.kt.template` | Kotlin | `@Id @Embedded` composite key data class |
| `cassandra-entity-with-udt.java.template` | Java | Entity with a UDT field and `List<UDT>` |
| `cassandra-udt.java.template` | Java | Basic `@UDT` record |
| `cassandra-udt.kt.template` | Kotlin | Basic `@UDT` data class |
| `cassandra-nested-udt.java.template` | Java | `@UDT` containing another `@UDT` |

### Repositories
| Template | Language | Description |
|---|---|---|
| `cassandra-crud-single-id-repository.java.template` | Java | Synchronous CRUD + batch + LWT |
| `cassandra-crud-single-id-repository.kt.template` | Kotlin | Synchronous CRUD + batch + LWT |
| `cassandra-crud-composite-id-repository.java.template` | Java | CRUD over a composite key |
| `cassandra-crud-composite-id-repository.kt.template` | Kotlin | CRUD over a composite key |
| `cassandra-crud-abstract-repository.java.template` | Java | Generic base interface driven by SQL macros |
| `cassandra-crud-abstract-repository.kt.template` | Kotlin | Generic base interface driven by SQL macros |
| `cassandra-lwt-repository.java.template` | Java | Lightweight transactions in depth |
| `cassandra-lwt-repository.kt.template` | Kotlin | Lightweight transactions in depth |
| `cassandra-async-repository.java.template` | Java | `CompletionStage` / `CompletableFuture` repository (Java only) |

### Mappers
| Template | Language | Description |
|---|---|---|
| `cassandra-mappers.java.template` | Java | Row / result-set / column read+write mappers, `@Component` rule |
| `cassandra-mappers.kt.template` | Kotlin | Same, with the mandatory `value: T?` override signature |

---

## Reference Documents

| Document | Description |
|---|---|
| [CQL Repository Reference](references/cql-repository-reference.md) | `@EntityCassandra`, generated mapper names, parameters, return types, SQL macros, `executor()` + `CassandraQuery`, multiple sessions |
| [UDT Mapping Reference](references/udt-mapping-reference.md) | `@UDT` semantics, nesting, `List<UDT>`, what is not generated |
| [Consistency Reference](references/consistency-reference.md) | Consistency levels, driver profiles, LWT serial consistency |
| [Async Patterns Reference](references/async-patterns-reference.md) | Java `CompletionStage` repositories, `CassandraAsyncResultSetMapper`, Kotlin migration off `suspend`/`Flow` |
| [Cassandra Config Reference](references/cassandra-config-reference.md) | Every `cassandra.*` key that exists, telemetry defaults, `Configurer` components |

---

## Migrating a Kora 1.x Cassandra repository

| Kora 1.x | Kora 2.0 |
|---|---|
| `ru.tinkoff.kora:database-cassandra`, BOM `kora-parent` | `io.koraframework:database-cassandra`, BOM `io.koraframework:kora-bom` |
| `ru.tinkoff.kora.database.*` | `io.koraframework.database.*` |
| `com.datastax.oss:java-driver-core` in the build | `org.apache.cassandra:java-driver-core` (transitive — usually just delete the line) |
| `com.datastax.oss.driver.api.*` imports | **unchanged** — keep them |
| `getCassandraConnectionFactory()` | `executor()` returning `CassandraExecutor` |
| `Mono<T>` / `Flux<T>` methods | synchronous `T` / `List<T>`, or Java `CompletionStage<T>` |
| `CassandraReactiveResultSetMapper` | removed — use `CassandraResultSetMapper` / `CassandraAsyncResultSetMapper` |
| Kotlin `suspend fun` / `Flow<T>` methods | plain `fun` returning `T?` / `List<T>` |
| `jakarta.annotation.Nullable` | `org.jspecify.annotations.Nullable` (type-use position) |

The config section is still `cassandra` and the key layout under `basic` / `advanced` / `profiles`
/ `auth` / `telemetry` is unchanged — JDBC's `db` → `jdbc` rename has **no** Cassandra counterpart.
What did change under `telemetry` is the defaults: logging and metrics are now off unless enabled.

---

## Common Pitfalls

| Symptom | Fix |
|---|---|
| `Suspend methods are not supported by the repository generator` | Kotlin repositories are synchronous — drop `suspend`; use `StructuredTaskScope` for parallel fan-out |
| Generated Kotlin file does not compile after adding `Flow<T>` | `Flow` is not a supported Cassandra return type — return `List<T>` |
| `No component found for dependency: CassandraRowMapper<X>` | Annotate `X` with `@EntityCassandra`, or supply a `CassandraRowMapper<X>` `@Component` / `@Mapping` |
| `No component found for dependency: CassandraParameterColumnMapper<List<T>>` | No built-in list binder — use `CassandraQuery.bindIn(...)` or write the mapper |
| `No component found for dependency: …Mapper` for a mapper you wrote | It has constructor deps or is non-`final`/`open` — add `@Component` |
| `Multiple components match dependency: CassandraRowMapper<X>` | Two `@Component`s for the same mapper type — keep one |
| `'apply' overrides nothing` on a Kotlin mapper | The `value` parameter must be `T?` |
| `NullPointerException: Result field x is not nullable but row y has null` | Add `@Nullable` (JSpecify) to that entity component / make the Kotlin property `T?` |
| `@CassandraProfile` rejected on the interface | It is `@Target(METHOD)` — move it onto each `@Query` method |
| `Query parameter is unused: x` | Every method parameter must appear as `:x` (or `:x.field` for entities) in the CQL |
| No query logs, no `db_*` metrics | `cassandra.telemetry.logging.enabled` / `metrics.enabled` default to `false` |
| `basic.consistency` silently ignored | Consistency lives at `basic.request.consistency` |
| `CassandraSession failed to start for contact points …` | Check contact points, `basic.dc`, keyspace, credentials, TLS, network |

---

## Best Practices

1. **Model tables from query patterns.** Cassandra has no joins and no ad-hoc filtering; every
   `ALLOW FILTERING` in production code is a modelling bug waiting to happen.
2. **Annotate DAOs with `@EntityCassandra`** so row and result-set mappers are generated in the
   first processing round rather than through the late extension fallback.
3. **Prefer synchronous signatures.** They run on virtual threads and keep stack traces intact;
   reach for Java `CompletionStage` only when you actually pipeline the futures.
4. **Use `@Nullable`, not `Optional`,** for nullable single-row results — and it is the only option
   in Kotlin.
5. **Keep DTOs and DAOs apart.** An `@Json` HTTP model is not a Cassandra entity.
6. **Scope consistency with `@CassandraProfile`,** not by rewriting queries.
7. **Test against a real container.** The Kora examples use
   `io.goodforgod:testcontainers-extensions-scylla` with `@KoraAppTest`; see
   [`kora-testing-junit-java`](../kora-testing-junit-java/SKILL.md) /
   [`kora-testing-junit-kotlin`](../kora-testing-junit-kotlin/SKILL.md).
