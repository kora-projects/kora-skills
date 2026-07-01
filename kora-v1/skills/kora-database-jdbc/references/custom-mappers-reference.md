# Custom Mappers Reference

**Source:** `.kora-agent/kora-docs/mkdocs/docs/en/documentation/database-jdbc.md` ("Mapping")
**Examples:** `.kora-agent/kora-examples/examples/java/kora-java-database-jdbc/` (`JdbcMapper*Repository.java`, `JdbcJsonbMapperModule.java`)
**Module:** `ru.tinkoff.kora:database-jdbc`

## Contents

- [Types of JDBC mappers](#types-of-jdbc-mappers)
- [Enum mapper](#enum-mapper-example)
- [PostgreSQL array mapper](#postgresql-array-mapper)
- [JSONB mapping](#jsonb-mapping-postgresql)
- [Mappers with dependencies](#mappers-with-dependencies)
- [Best practices](#best-practices)

---

## Types of JDBC Mappers

Kora supports four mapper interfaces, all from `ru.tinkoff.kora.database.jdbc.mapper.*`. Select a mapper with `@Mapping(MapperClass.class)` on the method (result mappers) or on the field/parameter (column mappers).

### 1. JdbcResultSetMapper<T>

Maps the entire `ResultSet` to one value; the mapper itself iterates with `rs.next()`. Use for grouping rows or assembling custom result structures. Selected with `@Mapping` on the method.

```java
public class UserResultSetMapper implements JdbcResultSetMapper<User> {
    @Override
    public User apply(ResultSet rs) throws SQLException {
        return new User(
            rs.getLong("id"),
            rs.getString("email"),
            rs.getString("name")
        );
    }
}

// Usage in repository
@Repository
public interface UserRepository extends JdbcRepository {
    @Query("SELECT * FROM users WHERE id = :id")
    @Mapping(UserResultSetMapper.class)
    @Nullable
    User findById(String id);
}
```

### 2. JdbcRowMapper<T>

Maps the current row to an object; invoked once per row (cursor already positioned, no `next()` call). Signature is `apply(ResultSet rs)` — there is no row-number argument.

```java
public class UserRowMapper implements JdbcRowMapper<User> {
    @Override
    public User apply(ResultSet rs) throws SQLException {
        return new User(
            rs.getLong("id"),
            rs.getString("email"),
            rs.getTimestamp("created_at").toLocalDateTime()
        );
    }
}

// Usage
@Query("SELECT * FROM users")
@Mapping(UserRowMapper.class)
List<User> findAll();
```

### 3. JdbcResultColumnMapper<T>

Maps a single column value to a Java type. Use for custom types like enums, JSONB, encrypted values.

```java
public class LowercaseEmailMapper implements JdbcResultColumnMapper<String> {
    @Override
    public String apply(ResultSet rs, int index) throws SQLException {
        return rs.getString(index).toLowerCase();
    }
}

// Usage on entity field
@EntityJdbc
@Table("users")
public record User(
    @Id Long id,
    @Mapping(LowercaseEmailMapper.class) String email,
    String name
) {}
```

### 4. JdbcParameterColumnMapper<T>

Maps Java objects to SQL parameters. Use for custom types in INSERT/UPDATE statements.

```java
public class UuidParameterMapper implements JdbcParameterColumnMapper<UUID> {
    @Override
    public void set(PreparedStatement stmt, int index, @Nullable UUID value) throws SQLException {
        if (value != null) {
            stmt.setString(index, value.toString());
        } else {
            stmt.setNull(index, Types.OTHER);
        }
    }
}

// Usage
@Repository
public interface UserRepository extends JdbcRepository {
    @Query("SELECT * FROM users WHERE session_id = :sessionId")
    List<User> findBySessionId(@Mapping(UuidParameterMapper.class) UUID sessionId);
}
```

---

## Enum Mapper Example

Map database integer codes to Java enums:

```java
public enum Status {
    UNKNOWN(-10), ACTIVE(0), PENDING(1), CLOSED(2);
    public final int code;
    Status(int code) { this.code = code; }
}

@Component
public class StatusResultMapper implements JdbcResultColumnMapper<Status> {
    private static final Status[] ALL = Status.values();
    
    @Override
    public Status apply(ResultSet rs, int index) throws SQLException {
        int code = rs.getInt(index);
        for (Status s : ALL) {
            if (s.code == code) return s;
        }
        return Status.UNKNOWN;
    }
}

@Component
public class StatusParameterMapper implements JdbcParameterColumnMapper<Status> {
    @Override
    public void set(PreparedStatement stmt, int index, @Nullable Status value) throws SQLException {
        if (value != null) {
            stmt.setInt(index, value.code);
        } else {
            stmt.setNull(index, Types.INTEGER);
        }
    }
}

@EntityJdbc
public record Task(
    @Id Long id,
    @Mapping(StatusResultMapper.class)     // repeat @Mapping for each direction
    @Mapping(StatusParameterMapper.class)
    @Column("status") Status status
) {}
```

Apply both a result mapper and a parameter mapper by repeating `@Mapping` on the field (as in `JdbcMapperColumnRepository` in the examples).

---

## PostgreSQL Array Mapper

```java
@Component
public class ListOfLongJdbcParameterMapper implements JdbcParameterColumnMapper<List<Long>> {
    @Override
    public void set(PreparedStatement stmt, int index, List<Long> value) throws SQLException {
        if (value == null) {
            stmt.setNull(index, Types.ARRAY);
            return;
        }
        Long[] typedArray = value.toArray(Long[]::new);
        Array sqlArray = stmt.getConnection().createArrayOf("BIGINT", typedArray);
        stmt.setArray(index, sqlArray);
    }
}

@Repository
public interface UserRepository extends JdbcRepository {
    @Query("SELECT * FROM users WHERE id = ANY(:ids)")
    List<User> findAllByIds(@Mapping(ListOfLongJdbcParameterMapper.class) List<Long> ids);
}
```

---

## JSONB Mapping (PostgreSQL)

Use built-in `@Json` annotation with `JdbcJsonbMapperModule`:

```java
// Required module
@KoraApp
public interface Application extends JdbcDatabaseModule, JdbcJsonbMapperModule {}

// Usage in entity
@EntityJdbc
@Table("users")
public record User(
    @Id UUID id,
    String email,
    @Json Profile profile  // Automatically serialized to JSONB
) {
    @Json
    public record Profile(String firstName, String lastName) {}
}
```

The `JdbcJsonbMapperModule` shown above is not built into Kora — it is a small `@Module` you define once that produces generic `@Json` JDBC column mappers (it depends on `JsonModule`/`JsonCommonModule`). The canonical implementation from the examples (`JdbcJsonbMapperModule.java`):

```java
@Module
public interface JdbcJsonbMapperModule {

    @Json
    default <T> JdbcParameterColumnMapper<T> jdbcJsonParameterColumnMapper(JsonWriter<T> writer) {
        return (stmt, index, value) -> {
            if (value != null) {
                var jsonb = new PGobject();
                jsonb.setType("jsonb");
                jsonb.setValue(writer.toStringUnchecked(value));
                stmt.setObject(index, jsonb);
            } else {
                stmt.setNull(index, Types.NULL);
            }
        };
    }

    @Json
    default <T> JdbcResultColumnMapper<T> jdbcJsonResultColumnMapper(JsonReader<T> reader) {
        return (row, index) -> {
            var value = row.getString(index);
            return value == null ? null : reader.readUnchecked(value);
        };
    }
}
```

Insert with an explicit cast so PostgreSQL accepts the value as `jsonb`:

```java
@Query("INSERT INTO entities_jsonb(id, value) VALUES (:entity.id, :entity.value::jsonb)")
void insert(Entity entity);
```

---

## Mappers with dependencies

A mapper used via `@Mapping` is instantiated by the annotation processor automatically. If the mapper needs injected collaborators (a service, config), declare it as a `@Component` and Kora supplies the same instance to the generated repository — still selected by `@Mapping`, not `@Tag`:

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
        return encrypted != null ? encryption.decrypt(encrypted) : null;
    }
}

@Query("SELECT secret FROM secrets WHERE id = :id")
@Mapping(EncryptedStringMapper.class)
@Nullable
String findSecret(String id);
```

---

## Best practices

1. **Keep mappers stateless** — no mutable state.
2. **Handle nulls explicitly** — column mappers receive null values.
3. **Prefer `@Nullable`** over `Optional` for nullable single-row returns.
4. **Prefer the `@Json` module** for JSONB over hand-written column mappers.
5. **Select mappers with `@Mapping`** — on the method for result/row mappers, on the field/parameter for column mappers.

---

## See also

- [entity-mapping-reference.md](entity-mapping-reference.md) — `@Table`, `@Column`, type mapping
- [repository-pattern-reference.md](repository-pattern-reference.md) — `@Repository`, `@Query` usage
