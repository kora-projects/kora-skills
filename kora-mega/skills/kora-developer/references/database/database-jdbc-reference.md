# JDBC Database Reference (database-jdbc)

**Source:** [.kora-agent/kora-docs/mkdocs/docs/en/documentation/database-jdbc.md](.kora-agent/kora-docs/mkdocs/docs/en/documentation/database-jdbc.md)  
**Examples:** `.kora-agent/kora-examples/kora-java-database-jdbc/`, `.kora-agent/kora-examples/kora-java-crud/`

**Module:** `ru.tinkoff.kora:database-jdbc`  
**Connection Pool:** HikariCP

---

## Dependency

```groovy
// build.gradle
dependencies {
    implementation "ru.tinkoff.kora:database-jdbc"
    
    // Database driver (required)
    implementation "org.postgresql:postgresql:42.7.3"  // PostgreSQL
    // implementation "mysql:mysql-connector-java:8.0.33"  // MySQL
    // implementation "com.oracle.database.jdbc:ojdbc11:21.9.0.0"  // Oracle
}
```

```java
// Module
@KoraApp
public interface Application extends JdbcDatabaseModule { }
```

---

## Configuration

### application.conf (HOCON) — Basic

```hocon
db {
    jdbcUrl = ${POSTGRES_JDBC_URL}
    username = ${POSTGRES_USER}
    password = ${POSTGRES_PASS}
    maxPoolSize = 10
    poolName = "kora"
}
```

> **Note:** For advanced configuration (HikariCP pool settings, telemetry, multiple databases), see [JDBC Configuration Reference](database-jdbc-config-reference.md).

---

## Repository Pattern

### Basic Repository

```java
@Repository
public interface UserRepository extends JdbcRepository {
    
    @Query("SELECT %{return#selects} FROM %{return#table} WHERE id = :id")
    @Nullable
    User findById(Long id);
    
    @Query("SELECT %{return#selects} FROM %{return#table}")
    List<User> findAll();
    
    @Query("%{entity#inserts}")
    void insert(User user);
    
    @Query("%{entity#updates}")
    void update(User user);
    
    @Query("DELETE FROM users WHERE id = :id")
    void delete(Long id);
}
```

### Entity Definition

```java
@Table("users")
public record User(
    @Id Long id,
    @Column("email") String email,
    @Column("created_at") LocalDateTime createdAt,
    @Nullable String nickname  // Optional field
) {}
```

---

## Transaction Management

### Using inTx()

```java
@Component
public class UserService {
    private final UserRepository userRepository;
    private final JdbcConnectionFactory connectionFactory;
    
    public UserService(UserRepository userRepository, JdbcConnectionFactory connectionFactory) {
        this.userRepository = userRepository;
        this.connectionFactory = connectionFactory;
    }
    
    public void createUser(User user) {
        connectionFactory.inTx(() -> {
            userRepository.insert(user);
            // Additional operations within same transaction
        });
    }
}
```

### With Connection Access

```java
public void createUserWithAudit(User user, AuditLog log) {
    connectionFactory.inTx(connection -> {
        userRepository.insert(user);
        
        // Use raw connection for custom operations
        try (PreparedStatement stmt = connection.prepareStatement(
                "INSERT INTO audit_log (action, timestamp) VALUES (?, ?)")) {
            stmt.setString(1, log.action());
            stmt.setTimestamp(2, Timestamp.valueOf(log.timestamp()));
            stmt.executeUpdate();
        }
    });
}
```

### Post-Commit Actions

```java
public void createUser(User user) {
    connectionFactory.inTx(() -> {
        userRepository.insert(user);
        
        var context = connectionFactory.currentConnectionContext();
        context.addPostCommitAction(() -> {
            // Executed after transaction commits
            sendWelcomeEmail(user.email());
        });
    });
}
```

### Post-Rollback Actions

```java
public void createUser(User user) {
    connectionFactory.inTx(() -> {
        userRepository.insert(user);
        
        var context = connectionFactory.currentConnectionContext();
        context.addPostRollbackAction((conn, ex) -> {
            // Executed after transaction rollback
            logger.error("Failed to create user", ex);
        });
    });
}
```

---

## Custom Mappers

### ResultSet Mapper

```java
public class UserResultSetMapper implements JdbcResultSetMapper<User> {
    @Override
    public User apply(ResultSet rs) throws SQLException {
        return new User(
            rs.getLong("id"),
            rs.getString("email"),
            rs.getTimestamp("created_at").toLocalDateTime(),
            rs.getString("nickname")
        );
    }
}

@Repository
public interface UserRepository extends JdbcRepository {
    @Mapping(UserResultSetMapper.class)
    @Query("SELECT id, email, created_at, nickname FROM users WHERE id = :id")
    User findById(Long id);
}
```

### Row Mapper

```java
public class UserRowMapper implements JdbcRowMapper<User> {
    @Override
    public User apply(ResultSet rs, int rowNum) throws SQLException {
        return new User(
            rs.getLong("id"),
            rs.getString("email"),
            rs.getTimestamp("created_at").toLocalDateTime(),
            rs.getString("nickname")
        );
    }
}

@Repository
public interface UserRepository extends JdbcRepository {
    @Mapping(UserRowMapper.class)
    @Query("SELECT id, email, created_at, nickname FROM users")
    List<User> findAll();
}
```

### Column Mapper

```java
public class EmailColumnMapper implements JdbcResultColumnMapper<String> {
    @Override
    public String apply(ResultSet rs, int index) throws SQLException {
        return rs.getString(index).toLowerCase();
    }
}

@Table("users")
public record User(
    @Id Long id,
    @Mapping(EmailColumnMapper.class) String email,
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
public interface UserRepository extends JdbcRepository {
    @Query("SELECT * FROM users WHERE session_id = :sessionId")
    List<User> findBySessionId(@Mapping(UuidParameterMapper.class) UUID sessionId);
}
```

---

## Batch Operations

### Batch Insert

```java
@Repository
public interface UserRepository extends JdbcRepository {
    @Query("%{entity#inserts}")
    void insert(@Batch List<User> users);
}

// Usage
List<User> newUsers = List.of(user1, user2, user3);
userRepository.insert(newUsers);
```

### Batch Update

```java
@Repository
public interface UserRepository extends JdbcRepository {
    @Query("%{entity#updates}")
    void update(@Batch List<User> users);
}
```

### Batch with Generated IDs

```java
@Repository
public interface UserRepository extends JdbcRepository {
    @Query("INSERT INTO users(email, created_at) VALUES (:user.email, :user.createdAt)")
    @Id
    long insert(@Batch List<User> users);
}
```

---

## Advanced Queries

### Select by List (PostgreSQL)

```java
@Component
class ListOfStringJdbcParameterMapper implements JdbcParameterColumnMapper<List<String>> {
    @Override
    public void set(PreparedStatement stmt, int index, List<String> value) throws SQLException {
        String[] typedArray = value.toArray(String[]::new);
        Array sqlArray = stmt.getConnection().createArrayOf("VARCHAR", typedArray);
        stmt.setArray(index, sqlArray);
    }
}

@Repository
public interface UserRepository extends JdbcRepository {
    @Query("SELECT * FROM users WHERE id = ANY(:ids)")
    List<User> findAllByIds(@Mapping(ListOfStringJdbcParameterMapper.class) List<Long> ids);
}
```

### Manual Query with Connection

```java
@Component
public class UserService {
    private final UserRepository repository;
    
    public UserService(UserRepository repository) {
        this.repository = repository;
    }
    
    public List<User> searchUsers(String query) {
        return repository.getJdbcConnectionFactory().inTx(connection -> {
            String sql = """
                SELECT id, email, created_at 
                FROM users 
                WHERE email ILIKE ? OR nickname ILIKE ?
                LIMIT 100
                """;
            
            try (PreparedStatement stmt = connection.prepareStatement(sql)) {
                String pattern = "%" + query + "%";
                stmt.setString(1, pattern);
                stmt.setString(2, pattern);
                
                try (ResultSet rs = stmt.executeQuery()) {
                    List<User> users = new ArrayList<>();
                    while (rs.next()) {
                        users.add(new User(
                            rs.getLong("id"),
                            rs.getString("email"),
                            rs.getTimestamp("created_at").toLocalDateTime(),
                            rs.getString("nickname")
                        ));
                    }
                    return users;
                }
            }
        });
    }
}
```

---

## Multiple Databases

### Configuration

```java
@KoraApp
public interface Application extends JdbcDatabaseModule {
    
    // Tag for secondary database
    final class SecondaryDatabase {}
    
    @Tag(SecondaryDatabase.class)
    default JdbcDatabaseConfig secondaryJdbcConfig(
            Config config,
            ConfigValueExtractor<JdbcDatabaseConfig> extractor) {
        var value = config.get("db.secondary");
        return extractor.extract(value);
    }
    
    @Tag(SecondaryDatabase.class)
    default JdbcDatabase secondaryDatabase(
            @Tag(SecondaryDatabase.class) JdbcDatabaseConfig config,
            DataBaseTelemetryFactory telemetryFactory,
            @Tag(SecondaryDatabase.class) @Nullable Executor executor) {
        return new JdbcDatabase(config, telemetryFactory, executor);
    }
}
```

### Secondary Repository

```java
@Repository(executorTag = @Tag(SecondaryDatabase.class))
public interface AuditRepository extends JdbcRepository {
    
    @Query("INSERT INTO audit_log (action, timestamp) VALUES (:action, :timestamp)")
    void log(String action, LocalDateTime timestamp);
}
```

### Configuration

> **Note:** See [JDBC Configuration Reference](database-jdbc-config-reference.md#multiple-databases) for complete multiple database configuration including pool settings and telemetry.

---

## Supported Types

| Type | Java | SQL |
|------|------|-----|
| Boolean | `boolean`, `Boolean` | `BOOLEAN` |
| Short | `short`, `Short` | `SMALLINT` |
| Integer | `int`, `Integer` | `INTEGER` |
| Long | `long`, `Long` | `BIGINT` |
| Double | `double`, `Double` | `DOUBLE` |
| Float | `float`, `Float` | `REAL` |
| Byte Array | `byte[]` | `BYTEA`, `BLOB` |
| String | `String` | `VARCHAR`, `TEXT` |
| BigDecimal | `BigDecimal` | `DECIMAL`, `NUMERIC` |
| UUID | `UUID` | `UUID` |
| LocalDate | `LocalDate` | `DATE` |
| LocalTime | `LocalTime` | `TIME` |
| LocalDateTime | `LocalDateTime` | `TIMESTAMP` |
| OffsetTime | `OffsetTime` | `TIME WITH TIME ZONE` |
| OffsetDateTime | `OffsetDateTime` | `TIMESTAMP WITH TIME ZONE` |

---

## Return Types

| Signature | Description |
|-----------|-------------|
| `T method()` | Single entity |
| `@Nullable T method()` | Nullable single entity |
| `Optional<T> method()` | Optional single entity |
| `List<T> method()` | List of entities |
| `CompletionStage<T> method()` | Async (requires Executor) |
| `Mono<T> method()` | Reactive (requires Reactor) |
| `UpdateCount method()` | Number of affected rows |
| `void method()` | No return value |

---

## Best Practices

1. **Always use `@EntityJdbc`** for entity records to enable optimized result converters
2. **Prefer macros** (`%{return#selects}`, `%{entity#inserts}`) over manual column listing
3. **Use transactions** for multiple database operations
4. **Configure connection pool** based on workload (maxPoolSize, minIdle)
5. **Enable telemetry** for observability in production
6. **Use batch operations** for bulk inserts/updates
7. **Handle nullable fields** with `@Nullable` annotation
8. **Use custom mappers** for complex type conversions

---

## Common Pitfalls

1. **Missing driver dependency** - JDBC module requires separate driver (PostgreSQL, MySQL, etc.)
2. **Incorrect pool configuration** - Too small pool causes connection exhaustion
3. **Forgetting `inTx()`** - Operations outside transaction won't rollback on error
4. **Wrong column names** - Ensure `@Column` matches database column names
5. **Missing `@Id`** - Required for generated identifier retrieval
6. **Batch without `@Batch`** - List parameters require `@Batch` annotation

---

## See Also

- [Database Common Reference](database-common-reference.md) - Entity mapping, macros, naming strategies
- [JDBC Configuration Reference](database-jdbc-config-reference.md) - HikariCP pool settings, multiple databases, telemetry
- [Database Cassandra Reference](database-cassandra-reference.md) - Cassandra module
- [Logging Reference](../kora-bootstrap/references/logging-reference.md) - Module telemetry logging
