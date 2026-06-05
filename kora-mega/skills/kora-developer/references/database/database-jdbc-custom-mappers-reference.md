# Custom Database Mappers in Kora

**Source:** [.kora-agent/kora-docs/mkdocs/docs/en/documentation/database-jdbc.md](.kora-agent/kora-docs/mkdocs/docs/en/documentation/database-jdbc.md)  
**Examples:** `.kora-agent/kora-examples/kora-java-database-jdbc/`

This guide explains how to create custom mappers for JDBC and Cassandra databases in Kora Framework.

## Return Types: Prefer @Nullable over Optional

**Recommendation:** Use `@Nullable` for nullable return types instead of `Optional`.

**Why:**
- `Optional` creates garbage on every call (heap allocation)
- `@Nullable` is zero-overhead, analyzed by static analysis tools
- Kora's DI and nullability analysis work seamlessly with `@Nullable`
- Consistent with Kora's own codebase style

**Example:**
```java
// Recommended
@Nullable
User findById(String id);

// Avoid (creates unnecessary garbage)
Optional<User> findById(String id);
```

For collections, always return empty collections instead of null:
```java
List<User> findAll();  // Returns empty list if no results
```

## When to Use Custom Mappers

Use custom mappers when:
- Default type mapping isn't sufficient (e.g., custom value objects)
- You need special serialization logic (e.g., encryption, encoding)
- Working with database-specific types (e.g., PostgreSQL JSONB, arrays)
- You need to map complex nested structures

---

## JDBC Mappers

### Types of JDBC Mappers

Kora supports four types of JDBC mappers:

#### 1. JdbcResultSetMapper<T>
Maps entire ResultSet rows to objects. Use for complex multi-table joins or custom result structures.

```java
public class UserResultSetMapper implements JdbcResultSetMapper<User> {
    @Override
    public User map(ResultSet rs) {
        return new User(
            rs.getString("id"),
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

#### 2. JdbcRowMapper<T>
Maps a single row to an object. Called for each row in the result set.

```java
public class UserRowMapper implements JdbcRowMapper<User> {
    @Override
    public User mapRow(ResultSet rs, int rowNum) {
        return new User(
            rs.getString("id"),
            rs.getString("email"),
            rs.getString("name")
        );
    }
}

// Usage
@Query("SELECT * FROM users")
@Mapping(UserRowMapper.class)
List<User> findAll();
```

#### 3. JdbcResultColumnMapper<T>
Maps a single column value to a Java type. Use for custom types like JSONB, encrypted values, or value objects.

```java
public class EncryptedStringMapper implements JdbcResultColumnMapper<String> {
    private final EncryptionService encryptionService;

    public EncryptedStringMapper(EncryptionService encryptionService) {
        this.encryptionService = encryptionService;
    }

    @Override
    public String map(ResultSet rs, String columnName) throws SQLException {
        String encrypted = rs.getString(columnName);
        return encrypted != null ? encryptionService.decrypt(encrypted) : null;
    }
}

// Usage
@Query("SELECT secret FROM secrets WHERE id = :id")
@Mapping(EncryptedStringMapper.class)
@Nullable
String findSecret(String id);
```

#### 4. JdbcSqlParameterMapper<T>
Maps Java objects to SQL parameters. Use for custom types in INSERT/UPDATE statements.

```java
public class EncryptedStringParameterMapper implements JdbcSqlParameterMapper<String> {
    private final EncryptionService encryptionService;

    public EncryptedStringParameterMapper(EncryptionService encryptionService) {
        this.encryptionService = encryptionService;
    }

    @Override
    public void map(PreparedStatement ps, int index, String value) throws SQLException {
        String encrypted = encryptionService.encrypt(value);
        ps.setString(index, encrypted);
    }
}

// Usage
@Query("INSERT INTO secrets(id, secret) VALUES (:id, :secret)")
void insert(String id, @Mapping(EncryptedStringParameterMapper.class) String secret);
```

### JSONB Mapping (PostgreSQL)

For JSONB columns, use the built-in `@Json` annotation with `JdbcJsonbMapperModule`.

**Required module:** Add `JdbcJsonbMapperModule` to your application:
```java
@KoraApp
public interface Application extends JdbcDatabaseModule, JdbcJsonbMapperModule {}
```

**Usage:**
```java
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

The `@Json` annotation works with:
- Nested records
- Complex types with multiple fields
- Collections (List, Map)
- Other `@Json` types

**Repository example:**
```java
@Repository
public interface UserRepository extends JdbcRepository {
    @Query("SELECT * FROM users WHERE id = :id")
    @Nullable
    User findById(UUID id);
    
    @Query("INSERT INTO users(id, email, profile) VALUES (:id, :email, :profile::jsonb)")
    void insert(User user);
}
```

For custom JSON handling (non-record types), use `JdbcResultColumnMapper`:
```java
public class JsonbColumnMapper implements JdbcResultColumnMapper<JsonObject> {
    @Override
    public JsonObject map(ResultSet rs, String columnName) throws SQLException {
        String json = rs.getString(columnName);
        return json != null ? Json.parse(json) : null;
    }
}
```

### Array Mapping (PostgreSQL)

For PostgreSQL arrays:
```java
public class StringArrayMapper implements JdbcResultColumnMapper<List<String>> {
    @Override
    public List<String> map(ResultSet rs, String columnName) throws SQLException {
        Array array = rs.getArray(columnName);
        if (array == null) return null;
        String[] values = (String[]) array.getArray();
        return Arrays.asList(values);
    }
}

// For parameters
public class StringArrayParameterMapper implements JdbcSqlParameterMapper<List<String>> {
    @Override
    public void map(PreparedStatement ps, int index, List<String> value) throws SQLException {
        if (value == null) {
            ps.setNull(index, Types.ARRAY);
        } else {
            ps.setArray(index, ps.getConnection().createArrayOf("text", value.toArray()));
        }
    }
}
```

---

## Cassandra Mappers

### Types of Cassandra Mappers

#### 1. CassandraRowMapper<T>
Maps a Cassandra row to an object.

```java
public class EventRowMapper implements CassandraRowMapper<Event> {
    @Override
    public Event map(Row row) {
        return new Event(
            row.getString("id"),
            row.getString("name"),
            row.getInt("value")
        );
    }
}

// Usage
@Query("SELECT * FROM events WHERE id = :id")
@Mapping(EventRowMapper.class)
@Nullable
Event findById(String id);
```

#### 2. CassandraResultColumnMapper<T>
Maps a single column value to a Java type.

```java
public class InstantColumnMapper implements CassandraResultColumnMapper<Instant> {
    @Override
    public Instant map(Row row, String columnName) {
        Instant instant = row.getInstant(columnName);
        return instant != null ? instant : Instant.EPOCH;
    }
}
```

### UDT (User-Defined Type) Mapping

For Cassandra UDTs, use the `@UDT` annotation:

```java
@UDT
public record AddressUDT(
    @Column("street") String street,
    @Column("city") String city,
    @Column("zipCode") String zipCode
) {}

@EntityJdbc
@Table("users")
public record User(
    @Id String id,
    String email,
    @Column("address") AddressUDT address  // Mapped to UDT
) {}
```

**Nested UDT pattern:**
```java
@Repository
public interface UserRepository extends CassandraRepository {
    record User(String id, Name name) {
        @UDT
        public record Name(String first, String last) {}
    }

    @Query("SELECT * FROM users WHERE id = :id")
    @Nullable
    User findById(String id);
}
```

---

## Mapper Registration

### Automatic Registration

Mappers used via `@Mapping` annotation are automatically registered by Kora's annotation processor.

### Manual Registration (for mappers with dependencies)

If your mapper has dependencies (e.g., services), register it as a component:

```java
@Component
public class EncryptedStringMapper implements JdbcResultColumnMapper<String> {
    private final EncryptionService encryptionService;

    public EncryptedStringMapper(EncryptionService encryptionService) {
        this.encryptionService = encryptionService;
    }

    @Override
    public String map(ResultSet rs, String columnName) throws SQLException {
        String encrypted = rs.getString(columnName);
        return encrypted != null ? encryptionService.decrypt(encrypted) : null;
    }
}
```

Then use with `@Tag` to specify the mapper:
```java
@Query("SELECT secret FROM secrets WHERE id = :id")
@Tag(EncryptedStringMapper.class)
@Nullable
String findSecret(String id);
```

---

## Best Practices

1. **Prefer `@Nullable` over `Optional`** - Use `@Nullable` for nullable return types to avoid Optional allocation
2. **Use `@Json` for JSONB** - Built-in JSON support is simpler than custom mappers
3. **Keep mappers stateless** - Mappers should not hold mutable state
4. **Handle nulls explicitly** - Always check for null values in mappers
5. **Use nested records for complex types** - Nested `@Json` or `@UDT` records keep code organized
6. **Test mappers independently** - Write unit tests for custom mappers

---

## Examples

See working examples in `.kora-agent/kora-examples/kora-java-database-jdbc/`:
- `JdbcMapperResultSetRepository.java` - ResultSet mapper example
- `JdbcMapperRowRepository.java` - Row mapper example
- `JdbcMapperColumnRepository.java` - Column mapper example
- `JdbcMapperParameterRepository.java` - Parameter mapper example
- `JdbcJsonbRepository.java` - JSONB column handling
