# Database Common Reference (database-common)

**Source:** [.kora-agent/kora-docs/mkdocs/docs/en/documentation/database-repository.md](.kora-agent/kora-docs/mkdocs/docs/en/documentation/database-repository.md)  
**Examples:** `.kora-agent/kora-examples/kora-java-crud/`

**Shared patterns for all Kora database modules:** JDBC, Cassandra, R2DBC, Vert.x

---

## Entity Mapping

### @Table Annotation

```java
@Table("users")
public record User(Long id, String email) {}

// Kotlin
@Table("users")
data class User(val id: Long, val email: String)
```

### @Column Annotation

```java
@Table("users")
public record User(
    @Id
    @Column("user_id")
    Long id,
    
    @Column("email_address")
    String email,
    
    @Column("created_at")
    LocalDateTime createdAt
) {}
```

**Important:** Always use `@Column` annotations for all fields to explicitly map database columns.

### @Id Annotation

```java
@Table("users")
public record User(
    @Id  // Marks primary key
    @Column("id")
    Long id,
    
    @Column("email")
    String email
) {}
```

### @Embedded Annotation

Flattens value objects into parent table columns:

```java
@Embedded
public record Address(
    @Column("street") String street,
    @Column("city") String city,
    @Column("zip_code") String zipCode
) {}

@Table("users")
public record User(
    @Id Long id,
    String email,
    @Embedded Address address  // Flattens to address_street, address_city, address_zip_code
) {}
```

### @EntityJdbc Annotation (JDBC-specific)

Optimizes entity mapping for JDBC module:

```java
@EntityJdbc
@Table("users")
public record User(
    @Id Long id,
    String email,
    LocalDateTime createdAt
) {}
```

**Best Practice:** Always use `@EntityJdbc` for JDBC entities to enable optimized result converters.

---

## SQL Macros

Kora provides macros for generating SQL statements at compile time.

### Macro Types

| Macro | Generates | Example |
|-------|-----------|---------|
| `%{return#selects}` | Column list for SELECT | `SELECT %{return#selects} FROM users` |
| `%{return#table}` | Table name | `SELECT * FROM %{return#table}` |
| `%{entity#inserts}` | Full INSERT statement | `%{entity#inserts}` |
| `%{entity#updates}` | Full UPDATE statement | `%{entity#updates}` |
| `%{entity#deletes}` | Full DELETE statement | `%{entity#deletes}` |
| `%{entity#where}` | WHERE clause by ID | `WHERE %{entity#where}` |

### SELECT Macros

```java
@Repository
public interface UserRepository {
    
    // Generates: SELECT id, email, created_at FROM users WHERE id = :id
    @Query("SELECT %{return#selects} FROM %{return#table} WHERE id = :id")
    User findById(Long id);
    
    // Generates: SELECT id, email, created_at FROM users
    @Query("SELECT %{return#selects} FROM %{return#table}")
    List<User> findAll();
}
```

### INSERT Macros

```java
@Repository
public interface UserRepository {
    
    // Generates: INSERT INTO users (id, email, created_at) VALUES (:id, :email, :createdAt)
    @Query("%{entity#inserts}")
    void insert(User user);
    
    // Generates: INSERT INTO users (email, created_at) VALUES (:email, :createdAt)
    @Query("%{entity#inserts-=id}")
    void insertWithoutId(User user);
    
    // Generates: INSERT INTO users (email) VALUES (:email)
    @Query("%{entity#inserts=id,email}")
    void insertEmailOnly(Long id, String email);
}
```

### UPDATE Macros

```java
@Repository
public interface UserRepository {
    
    // Generates: UPDATE users SET email = :email, created_at = :createdAt WHERE id = :id
    @Query("%{entity#updates}")
    void update(User user);
    
    // Generates: UPDATE users SET email = :email WHERE id = :id
    @Query("%{entity#updates-=createdAt}")
    void updateEmail(User user);
    
    // Generates: UPDATE users SET email = :email, nickname = :nickname WHERE id = :id
    @Query("%{entity#updates=id,email,nickname}")
    void updateFields(Long id, String email, String nickname);
}
```

### WHERE Macros

```java
@Repository
public interface UserRepository {
    
    // Generates: DELETE FROM users WHERE id = :id
    @Query("DELETE FROM %{return#table} WHERE %{entity#where}")
    void delete(Long id);
    
    // Generates: SELECT * FROM users WHERE id = :id AND email = :email
    @Query("SELECT * FROM %{return#table} WHERE %{entity#where} AND email = :email")
    User findByIdAndEmail(Long id, String email);
}
```

---

## Naming Strategies

Kora supports multiple naming strategies for automatic column name conversion.

### Built-in Strategies

| Strategy | Description | Example |
|----------|-------------|---------|
| `SNAKE_CASE` | Java camelCase → SQL snake_case | `createdAt` → `created_at` |
| `CAMEL_CASE` | SQL snake_case → Java camelCase | `created_at` → `createdAt` |
| `PASCAL_CASE` | Java camelCase → SQL PascalCase | `createdAt` → `CreatedAt` |
| `NOOP` | No conversion (exact match) | `created_at` → `created_at` |

### Configuration

```hocon
db {
    namingStrategy = "SNAKE_CASE"  // Default
}
```

```yaml
db:
  namingStrategy: "SNAKE_CASE"
```

### Custom Naming Strategy

```java
public class CustomNamingStrategy implements DatabaseNamingStrategy {
    @Override
    public String convert(String name) {
        return "prefix_" + name.toLowerCase();
    }
}

// Configuration
db {
    namingStrategy = "com.example.CustomNamingStrategy"
}
```

---

## Repository Pattern

### Basic Repository

```java
@Repository
public interface UserRepository {
    
    @Query("SELECT * FROM users WHERE id = :id")
    @Nullable
    User findById(Long id);
    
    @Query("SELECT * FROM users")
    List<User> findAll();
    
    @Query("INSERT INTO users (email) VALUES (:email)")
    void insert(String email);
}
```

### Repository with Executor Tag

```java
@Repository(executorTag = @Tag(SecondaryDatabase.class))
public interface SecondaryRepository {
    
    @Query("SELECT * FROM secondary_table WHERE id = :id")
    SecondaryEntity findById(Long id);
}
```

### Repository with Keyspace (Cassandra)

```java
@Repository(keyspace = "analytics_keyspace")
public interface AnalyticsRepository {
    
    @Query("SELECT * FROM events WHERE type = :type")
    List<Event> findByType(String type);
}
```

---

## Field Enumeration Syntax

Macros support field enumeration for fine-grained control.

### Include Specific Fields

```java
// Only include specified fields
@Query("%{entity#inserts=id,email}")
void insertWithEmail(Long id, String email);

@Query("%{entity#updates=email,nickname}")
void updateEmailAndNickname(Long id, String email, String nickname);
```

### Exclude Specific Fields

```java
// Exclude @Id field (auto-generated)
@Query("%{entity#inserts-=id}")
void insertWithoutId(User user);

// Exclude multiple fields
@Query("%{entity#inserts-=id,createdAt}")
void insertWithoutIdAndTimestamp(User user);
```

---

## Return Types

### Synchronous (Recommended with Virtual Threads)

| Signature | Description |
|-----------|-------------|
| `T method()` | Single entity (throws if not found) |
| `@Nullable T method()` | Nullable single entity |
| `Optional<T> method()` | Optional single entity |
| `List<T> method()` | List of entities |
| `Set<T> method()` | Set of entities |
| `int method()` | Number of affected rows |
| `void method()` | No return value |

### Asynchronous

| Signature | Description |
|-----------|-------------|
| `CompletionStage<T> method()` | Async (recommended) |
| `CompletionStage<@Nullable T> method()` | Async nullable |
| `CompletionStage<List<T>> method()` | Async list |

### Reactive (Requires Additional Dependencies)

| Signature | Description |
|-----------|-------------|
| `Mono<T> method()` | Reactive single (requires Reactor) |
| `Flux<T> method()` | Reactive stream (requires Reactor) |
| `Flow<T> method()` | Kotlin Flow (requires Coroutines) |

---

## Parameter Types

### Basic Types

All basic Java types are supported:
- Primitives: `boolean`, `short`, `int`, `long`, `double`, `float`
- Wrappers: `Boolean`, `Short`, `Integer`, `Long`, `Double`, `Float`
- Strings: `String`
- Numbers: `BigDecimal`, `BigInteger`
- UUID: `UUID`
- Dates: `LocalDate`, `LocalTime`, `LocalDateTime`, `OffsetTime`, `OffsetDateTime`, `Instant`
- Binary: `byte[]`

### Collection Types

```java
@Repository
public interface UserRepository {
    
    // List parameter (IN clause)
    @Query("SELECT * FROM users WHERE id IN :ids")
    List<User> findAllByIds(List<Long> ids);
    
    // Set parameter
    @Query("SELECT * FROM users WHERE status IN :statuses")
    List<User> findByStatuses(Set<String> statuses);
}
```

---

## Custom Mappers

### ResultSet Mapper (JDBC)

```java
public class UserResultSetMapper implements JdbcResultSetMapper<User> {
    @Override
    public User apply(ResultSet rs) throws SQLException {
        return new User(
            rs.getLong("id"),
            rs.getString("email"),
            rs.getTimestamp("created_at").toLocalDateTime()
        );
    }
}

@Repository
public interface UserRepository {
    @Mapping(UserResultSetMapper.class)
    @Query("SELECT * FROM users WHERE id = :id")
    User findById(Long id);
}
```

### Row Mapper (JDBC)

```java
public class UserRowMapper implements JdbcRowMapper<User> {
    @Override
    public User apply(ResultSet rs, int rowNum) throws SQLException {
        return new User(
            rs.getLong("id"),
            rs.getString("email"),
            rs.getTimestamp("created_at").toLocalDateTime()
        );
    }
}
```

### Result Mapper (Cassandra)

```java
public class UserResultMapper implements CassandraResultMapper<User> {
    @Override
    public User apply(AsyncResultSet rs) {
        Row row = rs.one();
        if (row == null) return null;
        return new User(
            row.getUuid("id"),
            row.getString("email"),
            row.getLocalDateTime("created_at")
        );
    }
}
```

### Row Mapper (Cassandra)

```java
public class UserRowMapper implements CassandraRowMapper<User> {
    @Override
    public User apply(Row row) {
        return new User(
            row.getUuid("id"),
            row.getString("email"),
            row.getLocalDateTime("created_at")
        );
    }
}
```

### Column Mapper

```java
public class LowercaseEmailMapper implements JdbcResultColumnMapper<String> {
    @Override
    public String apply(ResultSet rs, int index) throws SQLException {
        return rs.getString(index).toLowerCase();
    }
}

@Table("users")
public record User(
    @Id Long id,
    @Mapping(LowercaseEmailMapper.class) String email,
    LocalDateTime createdAt
) {}
```

### Parameter Mapper

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

@Repository
public interface UserRepository {
    @Query("SELECT * FROM users WHERE session_id = :sessionId")
    List<User> findBySessionId(@Mapping(UuidParameterMapper.class) UUID sessionId);
}
```

---

## Batch Operations

### Batch Annotation

```java
@Repository
public interface UserRepository {
    
    @Query("%{entity#inserts}")
    void insert(@Batch List<User> users);
    
    @Query("%{entity#updates}")
    void update(@Batch List<User> users);
}
```

### Batch with Generated IDs

```java
@Repository
public interface UserRepository {
    
    @Query("INSERT INTO users (email) VALUES (:email)")
    @Id
    Long insert(@Batch List<User> users);
}
```

---

## Best Practices

1. **Always use `@Column`** for explicit column mapping
2. **Use `@EntityJdbc`** for JDBC entities (optimized converters)
3. **Prefer macros** over manual SQL for CRUD operations
4. **Use virtual threads** for synchronous signatures
5. **Use `CompletionStage`** for async operations
6. **Configure naming strategy** once per application
7. **Use `@Embedded`** for value objects
8. **Use custom mappers** for complex type conversions
9. **Use batch operations** for bulk inserts/updates
10. **Handle nullable fields** with `@Nullable` annotation

---

## Common Pitfalls

1. **Missing `@Column`** — Fields won't be mapped without explicit annotation
2. **Missing `@Id`** — Required for primary key identification
3. **Wrong macro syntax** — Use `%{entity#inserts}` not `%{entity.inserts}`
4. **Field name mismatch** — Ensure method parameters match `:paramName` in queries
5. **Missing `@Batch`** — List parameters require `@Batch` annotation
6. **Wrong return type** — Ensure return type matches query result
7. **Naming strategy confusion** — Choose one strategy and stick with it

---

## See Also

- [Database JDBC Reference](database-jdbc-reference.md) — JDBC-specific patterns
- [Database Cassandra Reference](database-cassandra-reference.md) — Cassandra-specific patterns
- [Database Vert.x Reference](database-vertx-reference.md) — Vert.x module
- [Database R2DBC Reference](database-r2dbc-reference.md) — R2DBC module
