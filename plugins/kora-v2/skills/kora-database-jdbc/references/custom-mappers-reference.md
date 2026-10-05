# Custom Mappers Reference

**Applies to:** Kora 2.x (`io.koraframework:database-jdbc`)

## Contents

- [The four mapper contracts](#the-four-mapper-contracts)
- [Selecting a mapper](#selecting-a-mapper)
- [Kotlin: parameters must be nullable](#kotlin-parameters-must-be-nullable)
- [Enum mapper](#enum-mapper)
- [PostgreSQL array mapper](#postgresql-array-mapper)
- [JSONB mapping](#jsonb-mapping)
- [Mappers with dependencies](#mappers-with-dependencies)
- [Best practices](#best-practices)

---

## The four mapper contracts

All four extend `Mapping.MappingFunction` (`io.koraframework.common.annotation.Mapping`).

| Contract | Package | Method | Applied to |
|----------|---------|--------|-----------|
| `JdbcResultSetMapper<T>` | `io.koraframework.database.jdbc.mapper.result` | `@Nullable T apply(ResultSet rows) throws SQLException` | the repository **method** |
| `JdbcRowMapper<T>` | `io.koraframework.database.jdbc.mapper.result` | `@Nullable T apply(ResultSet row) throws SQLException` | the repository **method** |
| `JdbcResultColumnMapper<T>` | `io.koraframework.database.jdbc.mapper.result` | `@Nullable T apply(ResultSet row, int index) throws SQLException` | an entity **field** |
| `JdbcParameterColumnMapper<T>` | `io.koraframework.database.jdbc.mapper.parameter` | `void set(PreparedStatement stmt, int index, @Nullable T value) throws SQLException` | a method **parameter** or entity field |

There is no row-number argument on `JdbcRowMapper`, and the parameter mapper's method is `set`,
not `apply`.

### 1. `JdbcResultSetMapper<T>` — the whole result

The mapper drives the cursor itself with `rs.next()`. Use it to group rows or build a structure the
generated code cannot.

```java
public final class EntityPartResultSetMapper
        implements JdbcResultSetMapper<Map<Integer, List<EntityPart>>> {

    @Override
    public Map<Integer, List<EntityPart>> apply(ResultSet rs) throws SQLException {
        var result = new LinkedHashMap<Integer, List<EntityPart>>();
        while (rs.next()) {
            var part = new EntityPart(rs.getString(1), rs.getInt(2));
            result.computeIfAbsent(part.field1(), k -> new ArrayList<>()).add(part);
        }
        return result;
    }
}

@Mapping(EntityPartResultSetMapper.class)
@Query("SELECT id, value1 FROM entities")
Map<Integer, List<EntityPart>> findAllParts();
```

`JdbcResultSetMapper` also offers static adapters over a row mapper — `singleResultSetMapper`,
`optionalResultSetMapper`, `listResultSetMapper` — which is how the generated code turns a
`JdbcRowMapper` into `T` / `Optional<T>` / `List<T>`.

### 2. `JdbcRowMapper<T>` — one row

The cursor is already positioned; do not call `next()`. Cardinality (`T`, `Optional<T>`,
`List<T>`) comes from the method's return type.

```java
public final class EntityPartRowMapper implements JdbcRowMapper<EntityPart> {

    @Override
    public EntityPart apply(ResultSet rs) throws SQLException {
        return new EntityPart(rs.getString(1), rs.getInt(2));
    }
}

@Mapping(EntityPartRowMapper.class)
@Query("SELECT id, value1 FROM entities")
List<EntityPart> findAllParts();
```

### 3. `JdbcResultColumnMapper<T>` — one column, reading

```java
public final class EntityFieldTypeResultMapper implements JdbcResultColumnMapper<Entity.FieldType> {

    private static final Entity.FieldType[] ALL = Entity.FieldType.values();

    @Override
    public Entity.FieldType apply(ResultSet rs, int index) throws SQLException {
        var code = rs.getInt(index);
        for (var type : ALL) {
            if (type.code() == code) {
                return type;
            }
        }
        return Entity.FieldType.UNKNOWN;
    }
}
```

### 4. `JdbcParameterColumnMapper<T>` — one value, writing

```java
public final class EntityFieldTypeParameterMapper
        implements JdbcParameterColumnMapper<Entity.FieldType> {

    @Override
    public void set(PreparedStatement stmt, int index, Entity.@Nullable FieldType value)
            throws SQLException {
        if (value == null) {
            stmt.setNull(index, Types.INTEGER);
        } else {
            stmt.setInt(index, value.code());
        }
    }
}
```

Note `Entity.@Nullable FieldType`: JSpecify annotations are type-use, so on a qualified nested type
they sit before the simple name. `@Nullable Entity.FieldType` is a compile error.

---

## Selecting a mapper

Two ways, and they behave differently:

**Explicitly, with `@Mapping(X.class)`** — on the method for result/row mappers, on the entity
field or the method parameter for column mappers. Repeat `@Mapping` to attach both directions to
one field (`@Mapping` is `@Repeatable`).

```java
@EntityJdbc
record Entity(String id,
              @Mapping(EntityFieldTypeResultMapper.class)
              @Mapping(EntityFieldTypeParameterMapper.class)
              @Column("value1") FieldType field1,
              String value2) {}

@Query("SELECT * FROM entities WHERE status = :status")
List<Entity> findByStatus(@Mapping(EntityFieldTypeParameterMapper.class) FieldType status);
```

**Implicitly, by type** — a field or parameter whose type is not natively supported and has no
`@Mapping` makes the generated code request a `JdbcResultColumnMapper<T>` / `JdbcParameterColumnMapper<T>`
from the graph. Register one as a `@Component` and every entity field of that type is mapped
without further annotation:

```java
@Component
public final class TaskStatusResultMapper implements JdbcResultColumnMapper<TaskStatus> {
    @Override
    public TaskStatus apply(ResultSet row, int index) throws SQLException {
        var value = row.getString(index);
        return value == null ? null : TaskStatus.valueOf(value);
    }
}

@Component
public final class TaskStatusParameterMapper implements JdbcParameterColumnMapper<TaskStatus> {
    @Override
    public void set(PreparedStatement stmt, int index, TaskStatus value) throws SQLException {
        if (value == null) {
            stmt.setNull(index, Types.VARCHAR);
        } else {
            stmt.setString(index, value.name());
        }
    }
}

// no @Mapping anywhere — the mappers are found by type
@EntityJdbc @Table("tasks")
record TaskDAO(@Column("title") String title, @Column("status") TaskStatus status) {}
```

Whether a `@Mapping`-named mapper is constructed by the generated code or injected from the graph —
and therefore whether it needs `@Component` — is decided by the mapper's own shape. That rule, and
the errors you get when it is broken, are in
[custom-mappers-advanced-reference.md](custom-mappers-advanced-reference.md).

---

## Kotlin: parameters must be nullable

The 2.0 mapper contracts are JSpecify-marked, so a Kotlin override has to match exactly:

```kotlin
class ListOfStringJdbcParameterMapper : JdbcParameterColumnMapper<List<String>> {
    // the contract declares the value @Nullable, which Kotlin enforces on the override
    override fun set(stmt: PreparedStatement, index: Int, value: List<String>?) {
        if (value == null) {
            stmt.setNull(index, Types.ARRAY)
            return
        }
        stmt.setArray(index, stmt.connection.createArrayOf("VARCHAR", value.toTypedArray()))
    }
}
```

Declaring `value: List<String>` (non-null) makes Kotlin report **`'set' overrides nothing`** — an
error that never mentions nullability. The same applies to `JdbcResultColumnMapper.apply(rs, index)`
and `JdbcRowMapper.apply(row)`.

Return types may be narrowed to non-null, so `override fun apply(rs: ResultSet, index: Int): TaskStatus`
is fine. The Java twin of the same mapper compiles either way, which is why this only bites Kotlin.

Kotlin classes are final by default — relevant to the construct-vs-inject rule linked above.

---

## Enum mapper

Store the enum as an integer code and map both directions:

```java
public enum Status {
    UNKNOWN(-10), ACTIVE(0), PENDING(1), CLOSED(2);

    private final int code;
    Status(int code) { this.code = code; }
    public int code() { return code; }
}

public final class StatusResultMapper implements JdbcResultColumnMapper<Status> {
    private static final Status[] ALL = Status.values();

    @Override
    public Status apply(ResultSet rs, int index) throws SQLException {
        var code = rs.getInt(index);
        for (var s : ALL) {
            if (s.code() == code) {
                return s;
            }
        }
        return Status.UNKNOWN;
    }
}

public final class StatusParameterMapper implements JdbcParameterColumnMapper<Status> {
    @Override
    public void set(PreparedStatement stmt, int index, @Nullable Status value) throws SQLException {
        if (value == null) {
            stmt.setNull(index, Types.INTEGER);
        } else {
            stmt.setInt(index, value.code());
        }
    }
}

@EntityJdbc
public record Task(
        @Id Long id,
        @Mapping(StatusResultMapper.class)
        @Mapping(StatusParameterMapper.class)
        @Column("status") Status status) {}
```

An enum used as a **query parameter** needs its own `@Mapping` on that parameter — the field-level
mappers only cover the entity — unless the parameter mapper is a `@Component` and therefore
discoverable by type.

Kotlin:

```kotlin
class TaskStatusResultMapper : JdbcResultColumnMapper<TaskStatus> {
    override fun apply(rs: ResultSet, index: Int): TaskStatus =
        TaskStatus.entries.firstOrNull { it.code == rs.getInt(index) } ?: TaskStatus.UNKNOWN
}

class TaskStatusParameterMapper : JdbcParameterColumnMapper<TaskStatus> {
    override fun set(stmt: PreparedStatement, index: Int, value: TaskStatus?) {
        if (value == null) stmt.setNull(index, Types.INTEGER) else stmt.setInt(index, value.code)
    }
}

@EntityJdbc
@Table("tasks")
data class Task(
    @field:Id val id: Long?,
    @Mapping(TaskStatusResultMapper::class)
    @Mapping(TaskStatusParameterMapper::class)
    @field:Column("status") val status: TaskStatus
)
```

---

## PostgreSQL array mapper

On PostgreSQL, `database-jdbc-postgres` already maps `List<T>`, `Set<T>`/`Collection<T>`
parameters and arrays of `bool`, `int2`, `int4`, `int8`, `float4`, `float8`, `numeric`, `varchar`
and `uuid` — tag the field or parameter `@Pg` and extend `PostgresJdbcDatabaseModule`
([postgres-mappers-reference.md](postgres-mappers-reference.md)). `database-jdbc` alone has no
`List<T>` column mapping, so hand-write the mappers for another database or an element type the
PostgreSQL module does not cover (`List<LocalDate>`, enum arrays, …):

```java
@Component
public final class ListOfLongJdbcParameterMapper implements JdbcParameterColumnMapper<List<Long>> {

    @Override
    public void set(PreparedStatement stmt, int index, List<Long> value) throws SQLException {
        if (value == null) {
            stmt.setNull(index, Types.ARRAY);
            return;
        }
        var sqlArray = stmt.getConnection().createArrayOf("BIGINT", value.toArray(Long[]::new));
        stmt.setArray(index, sqlArray);
    }
}

@Repository
public interface TaskRepository extends JdbcRepository {

    // no @Mapping needed: the mapper is a @Component and matches List<Long> by type
    @Query("SELECT id FROM users WHERE id = ANY(:assigneeIds)")
    List<Long> findExistingAssigneeId(List<Long> assigneeIds);
}
```

For the read direction:

```java
public final class LongListResultMapper implements JdbcResultColumnMapper<List<Long>> {

    @Override
    public List<Long> apply(ResultSet rs, int index) throws SQLException {
        var array = rs.getArray(index);
        if (array == null) {
            return List.of();
        }
        return List.of((Long[]) array.getArray());
    }
}
```

---

## JSONB mapping

On PostgreSQL tag the field `@PgJsonb` (or `@PgJson`) from `database-jdbc-postgres` and annotate the
payload type with `@Json` — see
[postgres-mappers-reference.md](postgres-mappers-reference.md#json-and-jsonb-pgjson--pgjsonb) and
[entity-mapping-reference.md](entity-mapping-reference.md#jsonb-mapping-postgresql). A hand-written
generic `@Json`-tagged module is only needed without that artifact.

The one 2.0 detail worth repeating for a hand-written JSON mapper: `JsonWriter.toString(value)` and `JsonReader.read(value)` no
longer declare checked exceptions and the `*Unchecked` variants were removed, so a `try/catch
(IOException)` carried over from 1.x becomes `exception IOException is never thrown in the
corresponding try block`.

---

## Mappers with dependencies

A mapper that needs collaborators declares them on its constructor and becomes a `@Component`; the
generated repository takes it as a constructor parameter.

```java
@Component
public final class EncryptedStringMapper implements JdbcResultColumnMapper<String> {

    private final EncryptionService encryption;

    public EncryptedStringMapper(EncryptionService encryption) {
        this.encryption = encryption;
    }

    @Override
    public String apply(ResultSet rs, int index) throws SQLException {
        var encrypted = rs.getString(index);
        return encrypted == null ? null : encryption.decrypt(encrypted);
    }
}

@Query("SELECT secret FROM secrets WHERE id = :id")
@Mapping(EncryptedStringMapper.class)
@Nullable
String findSecret(String id);
```

Omitting `@Component` here fails the graph build with
`No component found for dependency: EncryptedStringMapper`.

---

## Best practices

1. **Keep mappers stateless.** They are shared across every query that uses them.
2. **Handle `null` explicitly** in both directions — column mappers receive and must produce nulls.
3. **Prefer `@Nullable T` over `Optional<T>`** for single-row returns.
4. **Prefer `@PgJsonb` from `database-jdbc-postgres`** (or one generic tagged module elsewhere) to a
   hand-written mapper per JSON type.
5. **Pick one selection style per type.** `@Mapping` overrides by-type discovery; having both a
   `@Component` mapper and a `@Mapping` on every use is redundant and invites ambiguity.
6. **Repeat `@Mapping`** rather than looking for an array attribute — the annotation is
   `@Repeatable`, there is no `value = {...}` form.

---

## See also

- [custom-mappers-advanced-reference.md](custom-mappers-advanced-reference.md) — construct vs inject, `@Component` rules, generic mapper modules
- [postgres-mappers-reference.md](postgres-mappers-reference.md) — PostgreSQL arrays, `interval`, ranges, `json`/`jsonb`
- [entity-mapping-reference.md](entity-mapping-reference.md) — supported types, JSONB
- [repository-pattern-reference.md](repository-pattern-reference.md) — `@Repository`, `@Query`, macros
