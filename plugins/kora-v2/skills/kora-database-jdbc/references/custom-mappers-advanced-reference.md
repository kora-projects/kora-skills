# Advanced JDBC Mapper Patterns

**Applies to:** Kora 2.x (`io.koraframework:database-jdbc`)

How the generated repository actually obtains its mappers, what that means for `@Component`, and
the batch limits that follow from the generated code.

## Contents

- [Constructed or injected: the rule](#constructed-or-injected-the-rule)
- [The @Component decision table](#the-component-decision-table)
- [Auto-discovery by type](#auto-discovery-by-type)
- [Column naming without @Column](#column-naming-without-column)
- [Overriding a built-in mapper](#overriding-a-built-in-mapper)
- [Generic mapper factories in a @Module](#generic-mapper-factories-in-a-module)
- [Tagging mappers](#tagging-mappers)
- [@Batch capabilities and limits](#batch-capabilities-and-limits)
- [Multi-row INSERT…RETURNING](#multi-row-insertreturning)
- [Stale-build diagnostics](#stale-build-diagnostics)

---

## Constructed or injected: the rule

When a `@Mapping(X.class)` names a mapper, the processor decides between two code shapes.

**Java** — X is instantiated inline when it is `final` **and** has a public no-arg constructor
**and** carries no `@Tag`:

```java
// generated
private static final EntityFieldTypeResultMapper _field1Mapper = new EntityFieldTypeResultMapper();
```

Otherwise X becomes a constructor parameter of the generated implementation and must be supplied by
the graph:

```java
// generated
private final TestResultMapper _resultMapper;
public $TestRepository_Impl(JdbcExecutor executor, TestResultMapper _resultMapper) { … }
```

**Kotlin** — the same split, expressed in Kotlin terms: the class is instantiated inline when it is
not `open`, has exactly one constructor, and that constructor has no parameters. Kotlin classes are
final by default, so a plain `class XMapper : JdbcRowMapper<T>()` with an empty constructor is
constructed inline; adding `open` or a constructor parameter moves it to the graph.

Practical consequence: a small stateless mapper referenced only through `@Mapping` needs **no**
`@Component` and no registration at all. Mark it `final` in Java (Kotlin gets it for free) and it
costs nothing at graph build time.

---

## The @Component decision table

| Mapper shape | How the repository gets it | `@Component` |
|---|---|---|
| `@Mapping(X.class)`, X `final` (Kotlin: not `open`), public no-arg ctor, untagged | constructed inline: `new X()` | **not needed** — an unused graph node, and a second component of the same mapper type makes by-type lookups ambiguous |
| `@Mapping(X.class)`, X non-`final` in Java (Kotlin: `open`) | injected as a constructor parameter | **required** |
| `@Mapping(X.class)`, X has constructor dependencies | injected as a constructor parameter | **required** |
| `@Mapping(X.class)` with `@Tag(...)` | injected, tagged | **required**, with the matching `@Tag` |
| No `@Mapping`, non-native column/parameter type | resolved from the graph **by type** | **required** |

The two errors this produces:

- `No component found for dependency: JdbcResultColumnMapper<Status>` — the mapper is injected but
  nothing in the graph produces it. Add `@Component`, or provide it from a `@Module`.
- `Multiple components match dependency: JdbcResultColumnMapper<Status>` — two graph components
  produce the same mapper type for a by-type lookup. Remove the redundant one, distinguish them
  with `@Tag`, or name the intended one with `@Mapping`.

A mapper that is both `@Component` and referenced by `@Mapping` while being `final` + no-arg is not
an error; it is simply dead weight, and it becomes a real problem the moment a second mapper of the
same type appears.

---

## Auto-discovery by type

An entity field or a query parameter whose type is not natively supported and carries no `@Mapping`
makes the generated code request the mapper from the graph by type. Registering the mapper as a
`@Component` is then all the wiring there is:

```java
@Component
public final class TaskStatusResultMapper implements JdbcResultColumnMapper<TaskStatus> { … }

@Component
public final class TaskStatusParameterMapper implements JdbcParameterColumnMapper<TaskStatus> { … }

@Component
public final class ListOfLongJdbcParameterMapper implements JdbcParameterColumnMapper<List<Long>> { … }
```

```java
@EntityJdbc
@Table("tasks")
public record TaskDAO(
        @Column("title") String title,
        @Column("status") TaskStatus status,                    // -> TaskStatusResultMapper
        @Column("user_assignee_id") @Nullable Long userAssigneeId) {}

@Query("SELECT id FROM users WHERE id = ANY(:assigneeIds)")
List<Long> findExistingAssigneeId(List<Long> assigneeIds);      // -> ListOfLongJdbcParameterMapper
```

Reach for `@Mapping` only when the by-type route cannot decide: two mappers for one type, or a
mapper you do not want in the graph at all.

On PostgreSQL the `List<Long>` mapper above is already shipped by `database-jdbc-postgres` — tag the
parameter `@Pg List<Long> assigneeIds` instead of writing it
([postgres-mappers-reference.md](postgres-mappers-reference.md)).

---

## Column naming without `@Column`

Field names are converted by the entity's naming strategy, `SnakeCaseNameConverter` by default:

| Field | Column |
|-------|--------|
| `userId` | `user_id` |
| `firstName` | `first_name` |
| `simple` | `simple` |
| `executorUuid` | `executor_uuid` |
| `HTTPClient` | `http_client` |
| `userID` | `user_id` |

Java (annotation processor) and Kotlin (KSP) apply the same conversion, so a Kotlin entity needs
no `@Column` for a plain camel-case property either.

`@Column` earns its place when the column name is not what the converter produces, when a JOIN
aliases a column, or on a legacy schema. Blanket `@Column` on every field is noise.

Change the strategy for a whole entity with `@NamingStrategy(X.class)` from
`io.koraframework.common.annotation`; converters live in `io.koraframework.common.naming` and need
an accessible no-arg constructor.

---

## Overriding a built-in mapper

`JdbcMapperModule` (pulled in by `JdbcDatabaseModule`) declares its mappers with
`@DefaultComponent`. A plain `@Component` of the same type **wins** over a `@DefaultComponent`
without any ambiguity error, so overriding the built-in `UUID` or `OffsetDateTime` handling is just
a matter of declaring your own:

```java
@Component
public final class BinaryUuidResultMapper implements JdbcResultColumnMapper<UUID> {

    @Override
    public UUID apply(ResultSet rs, int index) throws SQLException {
        var bytes = rs.getBytes(index);
        return bytes == null ? null : UUID.nameUUIDFromBytes(bytes);
    }
}
```

Two plain `@Component`s for the same type are still ambiguous — the override only works against
`@DefaultComponent`.

---

## Generic mapper factories in a `@Module`

A generic method on a `@Module` is a **template**: Kora instantiates it per requested type
argument. This is how one factory covers every `@Json` payload type:

```java
@Module
public interface JdbcJsonbMapperModule {

    @Json
    default <T> JdbcParameterColumnMapper<T> jdbcJsonParameterColumnMapper(JsonWriter<T> writer) {
        return (stmt, index, value) -> { … };
    }

    @Json
    default <T> JdbcResultColumnMapper<T> jdbcJsonResultColumnMapper(JsonReader<T> reader) {
        return (row, index) -> { … };
    }
}
```

`database-jdbc-postgres` ships exactly this pair for PostgreSQL, tagged `@PgJson` / `@PgJsonb`
([postgres-mappers-reference.md](postgres-mappers-reference.md#json-and-jsonb-pgjson--pgjsonb)) —
write your own only for another database or payload encoding.

The `@Json` tag is what keeps the template narrow: it only satisfies fields that are themselves
annotated `@Json`. **An untagged generic factory for `JdbcResultColumnMapper<T>` would match every
column of every unsupported type in the whole graph** — including ones you never intended — and the
resulting behaviour is very hard to trace back. Always tag a generic mapper factory, or keep the
factory monomorphic:

```java
@Module
public interface JdbcEnumMappersModule {

    default JdbcResultColumnMapper<Status> statusResultMapper() {
        return (rs, index) -> Status.fromCode(rs.getInt(index));
    }

    default JdbcResultColumnMapper<Role> roleResultMapper() {
        return (rs, index) -> Role.fromCode(rs.getInt(index));
    }
}
```

Monomorphic factory methods are explicit, appear one node per type in the graph, and cannot leak
into an unrelated column.

If a factory genuinely needs the runtime type it is being instantiated for, Kora can inject
`TypeRef<T>` — the graph builder synthesises `TypeRef.of(X.class)` for the resolved type argument.
Verify the generated graph (`build/generated/**/…Graph`) after adding one; a template that resolves
more broadly than intended is visible there as extra nodes.

---

## Tagging mappers

`@Tag` on the mapper plus `@Mapping` with the same tag pins one specific instance when several
exist for a type. A tagged mapper is **always** injected, never constructed inline, so it must be
in the graph.

```java
@Tag(Encrypted.class)
@Component
public final class EncryptedStringMapper implements JdbcResultColumnMapper<String> { … }
```

---

## `@Batch` capabilities and limits

`@Batch` is `@Target(PARAMETER)` — it annotates the `List` parameter, never the method.

**Supported return types**

| Return | Backing call |
|--------|-------------|
| `void` | `executeBatch()` |
| `UpdateCount` | `executeLargeBatch()`, counts summed |
| `int[]` | `executeBatch()` raw counts |
| `long[]` | `executeLargeBatch()` raw counts |
| `@Id` + id type or `List<idType>` | `executeBatch()` + `getGeneratedKeys()` |

```java
@Query("INSERT INTO %{entity#inserts}")
UpdateCount insertBatch(@Batch List<Entity> entity);

@Query("INSERT INTO %{entity#inserts -= @id}")
@Id
List<Long> insertBatchReturningIds(@Batch List<Entity> entity);
```

**Not supported:** an arbitrary projection. A batch method returning `List<String>` of selected
rows fails the build with *"Invalid JDBC `@Batch` repository method return type … Supported return
types without generated keys …"*.

**Counts are summed verbatim.** The generated code returns
`new UpdateCount(LongStream.of(executeLargeBatch()).sum())`, so a driver that reports
`Statement.SUCCESS_NO_INFO` (`-2`) drags the sum down. Treat an implausible or negative count as
"the driver did not say", and use `int[]` / `long[]` when the per-statement values matter. (The
manual `JdbcExecutor.executeUpdateBatch(batch)` helper does normalise `SUCCESS_NO_INFO` to
`UpdateCount(-1)`; the generated repository path does not.)

Generated keys **do** work with `@Batch` in 2.0 (`@Id List<Long>`), so reaching for a manual loop is
only necessary when you need per-row projections rather than keys.

---

## Multi-row INSERT…RETURNING

When you need a full projected row back per inserted record, write a `default` method and loop
inside one transaction:

```java
@Repository
public interface UserRepository extends JdbcRepository {

    @Query("INSERT INTO users(name, email) VALUES (:name, :email) RETURNING id, created_at")
    UserCreated insertReturning(String name, String email);

    default List<UserCreated> insertAllReturning(List<User> users) {
        return executor().inTx(() -> {
            var created = new ArrayList<UserCreated>(users.size());
            for (var user : users) {
                created.add(insertReturning(user.name(), user.email()));
            }
            return created;
        });
    }
}
```

Every `@Query` method called inside the lambda joins that transaction, so the loop is atomic. In
Kotlin the same `default`/loop body needs `JdbcExecutor.SqlSupplier { … }`.

---

## Stale-build diagnostics

On an incremental build the database processor can read a repository interface from a **class file**
that has no parameter names, and then report a placeholder error on source that is perfectly
correct:

```
SQL query placeholder has no matching method parameter: :id
Available parameters:
  - :arg0
```

`:arg0` is the tell — the processor is looking at compiled bytecode, not your source. Fix it with
`./gradlew clean` or `--rerun-tasks`; do not rename parameters to `arg0`, and do not add
`-parameters` expecting it to help across the module boundary.

Related: after a package rename, phantom errors mentioning the old package usually come from stale
files under `build/generated`. Clean, never hand-edit generated sources.

---

## See also

- [custom-mappers-reference.md](custom-mappers-reference.md) — the four mapper contracts and how to select them
- [entity-mapping-reference.md](entity-mapping-reference.md) — supported types, naming, JSONB
- [repository-pattern-reference.md](repository-pattern-reference.md) — `@Repository`, `@Query`, macros
- [transactions-reference.md](transactions-reference.md) — `executor().inTx(...)`
