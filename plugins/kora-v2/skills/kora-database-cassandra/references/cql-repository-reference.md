# CQL Repository Reference

**Artifact:** `io.koraframework:database-cassandra`
**Module:** `io.koraframework.database.cassandra.CassandraDatabaseModule`
**Driver:** DataStax Java Driver 4.19.3, resolved from `org.apache.cassandra:java-driver-core`,
Java packages `com.datastax.oss.driver.api.*`

## Contents

- [Repository declaration](#repository-declaration)
- [@EntityCassandra and generated mappers](#entitycassandra-and-generated-mappers)
- [Query parameters](#query-parameters)
- [Return types](#return-types)
- [Batches](#batches)
- [Lightweight transactions](#lightweight-transactions)
- [SQL macros](#sql-macros)
- [Custom mappers](#custom-mappers)
- [Manual queries](#manual-queries)
- [Multiple sessions and keyspaces](#multiple-sessions-and-keyspaces)
- [Paging](#paging)

---

## Repository declaration

A Cassandra repository is an interface (or abstract class) annotated with
`io.koraframework.database.common.annotation.Repository` that extends
`io.koraframework.database.cassandra.CassandraRepository`. The processor picks the generator by
that base interface; without it the build fails with
`@Repository type doesn't extend any supported repository interface.`

```java
import io.koraframework.database.cassandra.CassandraRepository;
import io.koraframework.database.common.annotation.Query;
import io.koraframework.database.common.annotation.Repository;
import org.jspecify.annotations.Nullable;

@Repository
public interface UserRepository extends CassandraRepository {

    @Query("SELECT * FROM users WHERE id = :id")
    @Nullable
    User findById(String id);

    @Query("SELECT * FROM users")
    List<User> findAll();

    @Query("INSERT INTO users(id, value1, value2) VALUES (:user.id, :user.field1, :user.value2)")
    void insert(User user);

    @Query("DELETE FROM users WHERE id = :id")
    void deleteById(String id);
}
```

```kotlin
@Repository
interface UserRepository : CassandraRepository {

    @Query("SELECT * FROM users WHERE id = :id")
    fun findById(id: String): User?

    @Query("SELECT * FROM users")
    fun findAll(): List<User>

    @Query("INSERT INTO users(id, value1, value2) VALUES (:user.id, :user.field1, :user.value2)")
    fun insert(user: User)

    @Query("DELETE FROM users WHERE id = :id")
    fun deleteById(id: String)
}
```

The generated `UserRepository_Impl` implements `executor()` and takes a `CassandraExecutor` (plus
any injected mappers) in its constructor. Nothing else is required — the module supplies the
`CassandraSession` that implements `CassandraExecutor`.

`@Query` also accepts `classpath:/path/to/file.cql` to load the statement from a resource on the
source or class path.

---

## @EntityCassandra and generated mappers

`@EntityCassandra` (`io.koraframework.database.cassandra.annotation.EntityCassandra`) marks a
record / data class / Java bean as a Cassandra row shape and generates its mappers in the first
processing round:

| Generated type | Contract |
|---|---|
| `$Entity_CassandraRowMapper` | `CassandraRowMapper<Entity>` |
| `$Entity_CassandraResultSetMapper` | `CassandraResultSetMapper<Entity>` |
| `$Entity_ListCassandraResultSetMapper` | `CassandraResultSetMapper<List<Entity>>` |

They are produced by the Kora extension, not registered as `@Component`s, so they never collide
with a mapper you declare yourself. Without `@EntityCassandra` the same mappers are still generated
by the extension when a repository asks for them — annotating the DAO just moves that work into
the first round and gives a clearer failure when the type is not mappable.

```java
@EntityCassandra
public record User(
    String id,
    @Column("value1") int field1,
    String value2,
    @Nullable String value3
) {}
```

```kotlin
@EntityCassandra
data class User(
    val id: String,
    @field:Column("value1") val field1: Int,
    val value2: String,
    val value3: String?
)
```

- Column name defaults to `snake_case` of the component name; `@Column("…")` overrides it.
  `@NamingStrategy` on the type changes the converter.
- Nullability: Java uses JSpecify `@Nullable` (type-use — write `@Nullable String value3`, and
  `Outer.@Nullable Inner` for a qualified nested type). Kotlin uses `String?`. A null column read
  into a non-nullable component throws
  `NullPointerException: Result field value3 is not nullable but row value3 has null`.
- `@Table` and `@Id` are only consumed by [SQL macros](#sql-macros). Hand-written CQL ignores them.
- Kotlin: use the `@field:` use-site target for `@Column`, `@Id` and `@Embedded` — KSP reads the
  property declaration. `@Mapping` is read from the property without a target.

### Embedded fields

`@Embedded` flattens a nested record into the owning entity's columns, optionally with a prefix:

```java
@EntityCassandra
@Table("events")
public record Event(@Id @Embedded EventId id, String payload) {

    public record EventId(String bucket, UUID eventId) {}
}
```

Binding uses the full path: `:event.id.bucket`, `:event.id.eventId`.

`@Embedded` over a **collection** field reads the child columns as nullable first, so a row whose
embedded part is entirely absent contributes no element instead of failing; a child that is only
*partially* null still fails its non-null check. Scalar embedded records — the composite-key shape
above — are read with the fields' own nullability.

---

## Query parameters

Placeholders are `:name`. Every method parameter must be referenced or the build fails with
`Query parameter is unused: <name>`; every placeholder must have a parameter.

```java
// simple parameters
@Query("SELECT * FROM users WHERE id = :id AND status = :status")
List<User> findByIdAndStatus(String id, String status);

// entity parameter — one placeholder per column, dotted accessor
@Query("INSERT INTO users(id, value1) VALUES (:user.id, :user.field1)")
void insert(User user);

// nullable parameter — bound with setToNull when null
@Query("SELECT * FROM users WHERE nickname = :nickname ALLOW FILTERING")
List<User> findByNickname(@Nullable String nickname);
```

A `com.datastax.oss.driver.api.core.CqlSession` parameter is recognised as the connection parameter
and is not bound to a placeholder.

Types bound natively without any mapper (`CassandraMapperModule` / `CassandraNativeTypes`):
`boolean`, `short`, `byte`, `int`, `long`, `double`, `float` and their boxes, `String`,
`BigDecimal`, `BigInteger`, `UUID`, `ByteBuffer`, `byte[]`, `LocalTime`, `LocalDate`,
`LocalDateTime`, `ZonedDateTime`, `Instant`, `CqlDuration`. Anything else needs a
`CassandraParameterColumnMapper<T>` — from `@UDT` generation, from `@Mapping`, or from a component.

### `IN` clauses

There is **no** built-in `CassandraParameterColumnMapper<List<T>>` for native element types, so a
declarative `IN` binding does not resolve:

```java
// FAILS: No component found for dependency: CassandraParameterColumnMapper<List<String>>
@Query("SELECT * FROM users WHERE id IN :ids")
List<User> findByIds(List<String> ids);
```

Use the [manual query API](#manual-queries) with `bindIn`, which expands the collection into one
positional placeholder per element, or supply your own list mapper through `@Mapping`.

---

## Return types

### Java

| Return type | Notes |
|---|---|
| `void` | INSERT / UPDATE / DELETE / TRUNCATE |
| `T`, `@Nullable T` | single row; a `CassandraResultSetMapper<T>` is derived from the row mapper |
| primitives | single-column row; `boolean` reads the LWT `[applied]` flag |
| `Optional<T>` | supplied by `CassandraMapperModule#cassandraOptionalResultSetMapper` |
| `List<T>` | `CassandraResultSetMapper<List<T>>` |
| `CompletionStage<T>`, `CompletableFuture<T>` | driver `executeAsync` path; also `…<Void>` and `…<List<T>>` |

### Kotlin

| Return type | Notes |
|---|---|
| `Unit` | INSERT / UPDATE / DELETE / TRUNCATE |
| `T`, `T?` | single row; a non-null declaration adds a `!!` to the generated code |
| `List<T>` | list result |

Kotlin has **no** async form:

- `suspend` is rejected by `RepositoryBuilder` before any generator runs —
  `Suspend methods are not supported by the repository generator.`
- `Flow<T>` is not usable: it appears in no framework test and in no migrated example, and the
  generator's non-suspend path applies the chosen mapper to a `ResultSet` while the `Flow` branch
  hands it a `CassandraRowMapper` whose `apply` takes a `Row`, so the generated file does not compile.
- `Optional<T>` has no Kotlin branch either — use `T?`.

Removed framework-wide and unsupported here: `Mono`, `Flux`, `ReactiveResultSet`,
`CassandraReactiveResultSetMapper`. `database-cassandra` has no Reactor dependency at all.

`UpdateCount` is handled only by the JDBC generator; a Cassandra method returning it fails looking
for `CassandraResultSetMapper<UpdateCount>`.

---

## Batches

Mark the collection parameter with `@Batch` and keep the CQL as a **single-row** statement. The
generator builds `BatchStatement.builder(DefaultBatchType.UNLOGGED)` and binds one bound statement
per element.

```java
@Query("INSERT INTO users(id, value1, value2) VALUES (:user.id, :user.field1, :user.value2)")
void insertBatch(@Batch List<User> user);

@Query("UPDATE users SET value1 = :user.field1 WHERE id = :user.id")
void updateBatch(@Batch List<User> user);
```

A batch method produces no mapped result — `parseResultMapper` returns nothing as soon as a
`@Batch` parameter is present. Return `void` (Java), `Unit` (Kotlin) or `CompletionStage<Void>`
(Java async). Cassandra batches are for atomicity within a partition, not for throughput; batching
across partitions is an anti-pattern.

---

## Lightweight transactions

Cassandra has no transactions and `CassandraExecutor` exposes no `inTx`. `IF` / `IF NOT EXISTS`
gives per-partition compare-and-set; the driver returns a row whose first column is `[applied]`.

```java
@Query("INSERT INTO users(id, value1) VALUES (:user.id, :user.field1) IF NOT EXISTS")
boolean insertIfNotExists(User user);

@Query("UPDATE users SET value2 = :value2 WHERE id = :id IF value2 = :oldValue2")
boolean updateIfMatches(String id, String value2, String oldValue2);

@Query("DELETE FROM users WHERE id = :id IF value2 = :oldValue2")
boolean deleteIfMatches(String id, String oldValue2);
```

`boolean` works because a single-column row maps through the `@DefaultComponent`
`CassandraRowMapper<Boolean>`, which reads column 0. To inspect the losing row instead, return the
entity and mark it `@Nullable`. Serial consistency for LWT comes from
`cassandra.basic.request.serialConsistency` — see the
[Consistency Reference](consistency-reference.md).

---

## SQL macros

Macros are expanded by the shared `QueryMacrosParser`, so they work for Cassandra repositories too.
Commands: `table`, `table as <alias>`, `columns`, `selects`, `values`, `inserts`, `updates`,
`where`. Selectors: `= f1, f2` to include, `-= f1, f2` to exclude, `@id` for the `@Id` field.

```java
@Repository
public interface UserRepository extends CassandraRepository {

    @Query("SELECT %{return#selects} FROM %{return#table} WHERE id = :id")
    @Nullable
    User findById(String id);

    @Query("INSERT INTO %{entity#inserts}")
    void insert(User entity);

    @Query("INSERT INTO %{entity#inserts -= @id}")
    void insertWithoutId(User entity);

    @Query("UPDATE %{entity#table} SET %{entity#updates} WHERE %{entity#where = @id}")
    void update(User entity);
}
```

- The **target** before `#` is a method parameter name, `return`, or a type-variable name — not an
  arbitrary label. `%{entity#…}` works because the method has a parameter called `entity`.
- `%{entity#inserts}` already emits `table(col, …) VALUES (:path, …)`, so write
  `INSERT INTO %{entity#inserts}` with no extra clause.
- `%{…#updates}` skips `@Id` fields; `%{…#where = @id}` produces `id_col = :path` for the `@Id`
  field (`AND`-joined when the id is `@Embedded`).
- `%{return#…}` is invalid on a `void` method (`Void` return target) — use the type-variable or
  parameter form there.
- The entity needs `@Table` (otherwise the table name is `snake_case` of the type name) and `@Id`
  for `@id` selectors.

### Generic base repositories

Macros resolve type variables through `asMemberOf`, so a shared CRUD interface works. Two forms,
both exercised by the framework's macro tests:

```java
public interface AbstractCassandraCrudRepository<K, V> extends CassandraRepository {

    // parameter target: the key column name comes from @Column on the K type argument
    @Query("SELECT %{return#selects} FROM %{return#table} WHERE %{keyArg#where}")
    @Nullable
    V findById(K keyArg);

    // type-variable target: usable when no parameter carries the entity type
    @Query("TRUNCATE %{V#table}")
    void deleteAll();
}

@Repository
public interface UserRepository
        extends AbstractCassandraCrudRepository<@Column("id") String, User> {}
```

When the target is a type variable **and** a parameter has that type, placeholders are written
against the parameter's name (`:entity.id`), not against the variable.

Two Cassandra-specific cautions:

1. `%{return#selects}` emits an explicit column list. That is fine in CQL, but `SELECT *` is
   equally valid and less brittle when the table has columns the DAO does not model.
2. The macro parser's "is this a scalar?" guard is `JdbcNativeTypes`, which does not know `UUID`,
   `Instant`, `LocalTime`, `ZonedDateTime` or `ByteBuffer`. This only matters when such a type is
   the macro **target** itself (`%{id#columns}` on a `UUID` parameter); ordinary entity components
   of those types expand to plain columns as expected.

---

## Custom mappers

| Contract | Package | Signature |
|---|---|---|
| `CassandraRowMapper<T>` | `…cassandra.mapper.result` | `@Nullable T apply(Row row)` |
| `CassandraResultSetMapper<T>` | `…cassandra.mapper.result` | `@Nullable T apply(ResultSet rows)` |
| `CassandraRowColumnMapper<T>` | `…cassandra.mapper.result` | `@Nullable T apply(GettableByName row, int index)` |
| `CassandraAsyncResultSetMapper<T>` | `…cassandra.mapper.result` | `CompletionStage<T> apply(AsyncResultSet rows)` |
| `CassandraParameterColumnMapper<T>` | `…cassandra.mapper.parameter` | `void apply(SettableByName<?> stmt, int index, @Nullable T value)` |

Wire them with `io.koraframework.common.annotation.Mapping` on the method (row / result-set /
async), on an entity component (column read + write) or on a query parameter (parameter write).

```java
@Repository
public interface EventRepository extends CassandraRepository {

    @Component
    final class EventPartRowMapper implements CassandraRowMapper<EventPart> {
        @Override
        public EventPart apply(Row row) {
            return new EventPart(row.getString(0), row.getInt(1));
        }
    }

    @Mapping(EventPartRowMapper.class)
    @Query("SELECT id, value1 FROM events")
    List<EventPart> findAllParts();
}
```

Read + write column mappers on one entity component — note the JSpecify position on the qualified
nested type in the write mapper:

```java
@Component
final class FieldTypeReadMapper implements CassandraRowColumnMapper<Entity.FieldType> {
    @Override
    public Entity.FieldType apply(GettableByName row, int index) {
        var code = row.getInt(index);
        for (var type : Entity.FieldType.values()) {
            if (type.code() == code) return type;
        }
        return Entity.FieldType.UNKNOWN;
    }
}

@Component
final class FieldTypeWriteMapper implements CassandraParameterColumnMapper<Entity.FieldType> {
    @Override
    public void apply(SettableByName<?> stmt, int index, Entity.@Nullable FieldType value) {
        if (value != null) stmt.setInt(index, value.code()); else stmt.setToNull(index);
    }
}

@EntityCassandra
record Entity(
    String id,
    @Mapping(FieldTypeReadMapper.class)
    @Mapping(FieldTypeWriteMapper.class)
    @Column("value1") FieldType field1
) { enum FieldType { UNKNOWN, ONE, TWO; int code() { … } } }
```

### When a mapper must be a `@Component`

The generated repository builds its mapper fields through `FieldFactory`, which decides per mapper:

- **Java** — `@Mapping` has no tag **and** the mapper class is `final` with a public no-arg
  constructor → the repository emits `this._mapper = new Mapper()`. `@Component` is then optional
  (the migrated Kora examples still declare it; an unreferenced component is simply pruned).
- **Kotlin** — the class is not `open` and has a single no-arg constructor → same inline
  construction. The migrated Kotlin example declares its mappers as plain top-level classes with no
  `@Component`.
- **Otherwise** — constructor dependencies, a non-`final` / `open` class, or a tagged mapping →
  the mapper becomes a constructor parameter of the generated repository and must exist in the
  graph, or the build fails with `No component found for dependency: …`.

Declare at most one component per mapper type: two `@Component`s implementing the same
`CassandraRowMapper<T>` produce `Multiple components match dependency:`. The scalar mappers in
`CassandraMapperModule` are `@DefaultComponent`, so your own `@Component` for the same type
replaces them without conflict.

### Kotlin override signatures

The contracts are `@NullMarked`, so parameters declared `@Nullable` must be `T?` in Kotlin.
Return types may be narrowed to non-null.

```kotlin
class FieldTypeWriteMapper : CassandraParameterColumnMapper<Entity.FieldType> {
    override fun apply(stmt: SettableByName<*>, index: Int, value: Entity.FieldType?) { … }
}

class EntityPartRowMapper : CassandraRowMapper<EntityPart> {
    override fun apply(row: Row): EntityPart = EntityPart(row.getString(0)!!, row.getInt(1))
}
```

`value: Entity.FieldType` (non-null) compiles in Java and fails in Kotlin with
`'apply' overrides nothing`, which never mentions nullability.

---

## Manual queries

`CassandraRepository.executor()` returns the `CassandraExecutor` — the 2.0 replacement for the 1.x
`getCassandraConnectionFactory()`. It is also injectable on its own, since `CassandraSession`
implements it.

```java
public interface CassandraExecutor {
    CqlSession currentSession();
    DatabaseTelemetry telemetry();

    <T> T query(QueryContext queryContext, Function<PreparedStatement, T> callback);
    <T> T query(CassandraQuery query, Function<BoundStatement, T> callback);
    <T> T query(CassandraQuery query, CassandraResultSetMapper<T> mapper);
    @Nullable <T> T queryOne(CassandraQuery query, CassandraRowMapper<T> mapper);
    <T> Optional<T> queryOptional(CassandraQuery query, CassandraRowMapper<T> mapper);
    <T> List<T> queryList(CassandraQuery query, CassandraRowMapper<T> mapper);
}
```

There is no `inTx` and no transaction API of any kind — Cassandra has no transactions.

`CassandraQuery` builds an immutable, parameter-bound statement. Two builders:

```java
// named placeholders, converted to positional ones on build()
var query = CassandraQuery.named()
    .cql("SELECT id, name FROM users WHERE tenant_id = :tenant_id")
    .bind("tenant_id", tenantId)
    .cqlIf(" AND status = :status", status != null)
    .bindIf("status", status, status != null)
    .cqlIf(" AND id IN (:ids)", !ids.isEmpty())
    .bindInIf("ids", ids, !ids.isEmpty())
    .build();

// positional placeholders
var query = CassandraQuery.template()
    .cql("SELECT id, name FROM users WHERE tenant_id = ?")
    .bind(tenantId)
    .cqlIf(" AND status = ?", status != null, status)
    .build();

// one-shot positional form
var query = CassandraQuery.template("SELECT id, name FROM users WHERE id = ?", id);
```

`bindIn("ids", List.of(1, 2, 3))` rewrites `id IN (:ids)` to `id IN (?, ?, ?)` and binds each
element. An empty collection is rejected at `build()`. Every named placeholder must be bound and
every bound name must appear in the CQL.

Statement options are set through `opts`:

```java
CassandraQuery.named()
    .cql("SELECT * FROM users WHERE id = :id")
    .bind("id", id)
    .opts(o -> o
        .consistencyLevel(DefaultConsistencyLevel.LOCAL_QUORUM)
        .serialConsistencyLevel(DefaultConsistencyLevel.LOCAL_SERIAL)
        .pageSize(500)
        .timeout(Duration.ofSeconds(5))
        .idempotent(true)
        .tracing(false))
    .build();
```

All `executor()` helpers run inside the module's telemetry scope, so manual queries appear in the
same logs, metrics and traces as generated ones. Build CQL fragments yourself only from trusted
identifiers — user values always go through `bind` / `bindIn`.

---

## Multiple sessions and keyspaces

`CassandraDatabaseModule` supplies one session bound to the `cassandra` config path via
`@FactoryModule CassandraDatabaseFactoryModule cassandraDatabase() { return new CassandraDatabaseFactoryModule("cassandra"); }`.

For a second cluster or keyspace, declare another factory module under a tag and point the
repository at it with `@Repository(executorTag = …)`:

```java
public interface AnalyticsCassandraModule extends CassandraMapperModule {

    @Tag(Analytics.class)
    @FactoryModule
    default CassandraDatabaseFactoryModule analyticsCassandra() {
        return new CassandraDatabaseFactoryModule("cassandraAnalytics");
    }
}

@Repository(executorTag = Analytics.class)
public interface AnalyticsRepository extends CassandraRepository { … }
```

`@Tag` on the factory-module method propagates to everything the module produces: inside a
`@FactoryModule`, the `@Tag(Tag.Factory.class)` parameters of
`CassandraDatabaseFactoryModule` resolve to the enclosing method's tag. Extend
`CassandraMapperModule` (not `CassandraDatabaseModule`) in the extra module so the untagged
default session is not declared twice.

---

## Paging

There is no `Pageable` parameter. Bound result size with CQL `LIMIT`, with the driver page size
(`cassandra.basic.request.pageSize`, or `pageSize` on a `CassandraQuery`), or by walking pages
yourself in a `CassandraResultSetMapper` — `ResultSet` fetches transparently, and
`AsyncResultSet.hasMorePages()` / `fetchNextPage()` is what
`CassandraAsyncResultSetMapper.list(...)` uses.

```java
@Query("SELECT * FROM events WHERE bucket = :bucket AND event_time > :from LIMIT 100")
List<Event> findPage(String bucket, Instant from);
```

---

## See Also

- [UDT Mapping Reference](udt-mapping-reference.md)
- [Consistency Reference](consistency-reference.md)
- [Async Patterns Reference](async-patterns-reference.md)
- [Cassandra Config Reference](cassandra-config-reference.md)
