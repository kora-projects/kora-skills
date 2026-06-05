# Cassandra Database Reference (database-cassandra)

**Source:** [.kora-agent/kora-docs/mkdocs/docs/en/documentation/database-cassandra.md](.kora-agent/kora-docs/mkdocs/docs/en/documentation/database-cassandra.md)  
**Examples:** `.kora-agent/kora-examples/kora-java-database-cassandra/`

**Module:** `ru.tinkoff.kora:database-cassandra`  
**Driver:** DataStax Java Driver 4.x

---

## Dependency

```groovy
// build.gradle
dependencies {
    implementation "ru.tinkoff.kora:database-cassandra"
    
    // Cassandra driver (included transitively)
    // implementation "com.datastax.oss:java-driver-core:4.17.0"
}
```

```java
// Module
@KoraApp
public interface Application extends CassandraDatabaseModule { }
```

---

## Configuration

### application.conf (HOCON) — Basic

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
    telemetry {
        logging {
            enabled = true
        }
    }
}
```

> **Note:** For advanced configuration (consistency levels, retry policies, load balancing, timeouts, profiles), see [Cassandra Configuration Reference](database-cassandra-config-reference.md).

---

## Repository Pattern

### Basic Repository

```java
@Repository
public interface UserRepository {
    
    @Query("SELECT * FROM users WHERE id = :id")
    @Nullable
    User findById(UUID id);
    
    @Query("SELECT * FROM users")
    List<User> findAll();
    
    @Query("INSERT INTO users (id, email, created_at) VALUES (:id, :email, :createdAt)")
    void insert(User user);
    
    @Query("UPDATE users SET email = :email WHERE id = :id")
    void update(User user);
    
    @Query("DELETE FROM users WHERE id = :id")
    void delete(UUID id);
}
```

### Entity Definition

```java
@Table("users")
public record User(
    @Id
    @Column("id")
    UUID id,
    
    @Column("email")
    String email,
    
    @Column("created_at")
    LocalDateTime createdAt,
    
    @Nullable
    @Column("nickname")
    String nickname
) {}
```

---

## UDT (User-Defined Types) Support

### UDT Definition

```java
@UDT
public record AddressUDT(
    @Column("street") String street,
    @Column("city") String city,
    @Column("zipCode") String zipCode
) {}
```

### Using UDT in Entity

```java
@Table("users")
public record User(
    @Id UUID id,
    String email,
    @Column("address") AddressUDT address,
    @Column("addresses") List<AddressUDT> addresses
) {}
```

### UDT Repository

```java
@Repository
public interface UserRepository {
    
    @Query("INSERT INTO users (id, email, address) VALUES (:id, :email, :address)")
    void insertWithAddress(User user);
    
    @Query("SELECT * FROM users WHERE address.city = :city")
    List<User> findByCity(String city);
}
```

---

## Profile-Based Configuration

### Profile Annotation

```java
@Repository
@CassandraProfile("analytics")
public interface AnalyticsRepository {
    
    @Query("SELECT * FROM events WHERE type = :type")
    List<Event> findByType(String type);
    
    @Query("SELECT * FROM events WHERE created_at > :timestamp")
    List<Event> findByTimestamp(LocalDateTime timestamp);
}
```

### Profile Configuration

> **Note:** See [Cassandra Configuration Reference](database-cassandra-config-reference.md#profile-based-configuration) for complete profile configuration including consistency levels, retry policies, and timeouts.

---

## Async Signatures

### CompletionStage (Recommended)

```java
@Repository
public interface UserRepository {
    
    @Query("SELECT * FROM users WHERE id = :id")
    CompletionStage<@Nullable User> findByIdAsync(UUID id);
    
    @Query("SELECT * FROM users")
    CompletionStage<List<User>> findAllAsync();
    
    @Query("INSERT INTO users (id, email) VALUES (:id, :email)")
    CompletionStage<Void> insertAsync(User user);
}
```

### Reactor (Requires reactor-core)

```java
@Repository
public interface UserRepository {
    
    @Query("SELECT * FROM users WHERE id = :id")
    Mono<@Nullable User> findByIdReactive(UUID id);
    
    @Query("SELECT * FROM users")
    Flux<User> findAllReactive();
}
```

### Kotlin Flow (Requires kotlinx-coroutines)

```kotlin
@Repository
interface UserRepository {
    
    @Query("SELECT * FROM users WHERE id = :id")
    suspend fun findByIdAsync(id: UUID): User?
    
    @Query("SELECT * FROM users")
    fun findAllFlow(): Flow<User>
}
```

---

## Custom Mappers

### Row Mapper

```java
public class UserRowMapper implements CassandraRowMapper<User> {
    @Override
    public User apply(Row row) {
        return new User(
            row.getUuid("id"),
            row.getString("email"),
            row.getLocalDateTime("created_at"),
            row.getString("nickname")
        );
    }
}

@Repository
public interface UserRepository {
    @Mapping(UserRowMapper.class)
    @Query("SELECT id, email, created_at, nickname FROM users")
    List<User> findAll();
}
```

### Result Mapper

```java
public class UserResultMapper implements CassandraResultMapper<User> {
    @Override
    public User apply(AsyncResultSet rs) {
        Row row = rs.one();
        if (row == null) {
            return null;
        }
        return new User(
            row.getUuid("id"),
            row.getString("email"),
            row.getLocalDateTime("created_at"),
            row.getString("nickname")
        );
    }
}

@Repository
public interface UserRepository {
    @Mapping(UserResultMapper.class)
    @Query("SELECT * FROM users WHERE id = :id")
    @Nullable
    User findById(UUID id);
}
```

### Column Mapper

```java
public class LowercaseEmailMapper implements CassandraResultColumnMapper<String> {
    @Override
    public String apply(Row row, int index) {
        return row.getString(index).toLowerCase();
    }
}

@Table("users")
public record User(
    @Id UUID id,
    @Mapping(LowercaseEmailMapper.class) String email,
    LocalDateTime createdAt
) {}
```

### Parameter Mapper

```java
public class InstantParameterMapper implements CassandraParameterColumnMapper<Instant> {
    @Override
    public void set(BoundStatementBuilder stmt, int index, @Nullable Instant value) {
        if (value != null) {
            stmt.setInstant(index, value);
        } else {
            stmt.setToNull(index);
        }
    }
}

@Repository
public interface UserRepository {
    @Query("SELECT * FROM users WHERE created_at > :timestamp")
    List<User> findByTimestamp(@Mapping(InstantParameterMapper.class) Instant timestamp);
}
```

---

## Batch Operations

### Batch Insert

```java
@Repository
public interface UserRepository {
    
    @Query("INSERT INTO users (id, email, created_at) VALUES (:id, :email, :createdAt)")
    void insert(@Batch List<User> users);
}

// Usage
List<User> newUsers = List.of(user1, user2, user3);
userRepository.insert(newUsers);
```

### Batch with Different Operations

```java
@Repository
public interface UserRepository {
    
    @Query("INSERT INTO users (id, email) VALUES (:id, :email)")
    void insertBatch(@Batch List<User> users);
    
    @Query("UPDATE users SET email = :email WHERE id = :id")
    void updateBatch(@Batch List<User> users);
    
    @Query("DELETE FROM users WHERE id = :id")
    void deleteBatch(@Batch List<UUID> ids);
}
```

---

## Advanced Queries

### Pagination

```java
@Repository
public interface UserRepository {
    
    @Query("SELECT * FROM users")
    List<User> findAll(Pageable pageable);
    
    @Query("SELECT * FROM users WHERE email LIKE :pattern")
    List<User> findByEmailPattern(String pattern, Pageable pageable);
}

// Usage
Pageable pageable = Pageable.ofSize(100);
List<User> users = userRepository.findAll(pageable);
```

### Custom Query with Options

```java
@Component
public class UserService {
    private final UserRepository repository;
    private final CqlSession session;
    
    public List<Event> searchEvents(String query) {
        String cql = """
            SELECT * FROM events 
            WHERE title LIKE ? OR description LIKE ?
            LIMIT 100
            """;
        
        try {
            String pattern = "%" + query + "%";
            ResultSet rs = session.execute(cql, pattern, pattern);
            
            List<Event> events = new ArrayList<>();
            for (Row row : rs) {
                events.add(new Event(
                    row.getUuid("id"),
                    row.getString("title"),
                    row.getString("description"),
                    row.getInstant("created_at")
                ));
            }
            return events;
        } catch (Exception e) {
            throw new RuntimeException("Failed to search events", e);
        }
    }
}
```

### Lightweight Transactions (LWT)

```java
@Repository
public interface UserRepository {
    
    @Query("INSERT INTO users (id, email) VALUES (:id, :email) IF NOT EXISTS")
    boolean insertIfNotExists(User user);
    
    @Query("UPDATE users SET email = :email WHERE id = :id IF email = :oldEmail")
    boolean updateIfEmailMatches(UUID id, String email, String oldEmail);
}
```

---

## Multiple Keyspaces

> **Note:** See [Cassandra Configuration Reference](database-cassandra-config-reference.md#multiple-keyspaces) for `additionalKeyspaces` configuration.

### Repository with Keyspace

```java
@Repository(keyspace = "analytics_keyspace")
public interface AnalyticsRepository {
    
    @Query("SELECT * FROM events WHERE type = :type")
    List<Event> findByType(String type);
}
```

---

## Supported Types

| Type | Java | CQL |
|------|------|-----|
| Boolean | `boolean`, `Boolean` | `BOOLEAN` |
| Short | `short`, `Short` | `SMALLINT` |
| Integer | `int`, `Integer` | `INT` |
| Long | `long`, `Long` | `BIGINT` |
| Double | `double`, `Double` | `DOUBLE` |
| Float | `float`, `Float` | `FLOAT` |
| Byte Array | `byte[]` | `BLOB` |
| String | `String` | `TEXT`, `VARCHAR`, `ASCII` |
| UUID | `UUID` | `UUID`, `TIMEUUID` |
| LocalDate | `LocalDate` | `DATE` |
| LocalTime | `LocalTime` | `TIME` |
| LocalDateTime | `LocalDateTime` | `TIMESTAMP` |
| Instant | `Instant` | `TIMESTAMP` |
| BigDecimal | `BigDecimal` | `DECIMAL` |
| BigInteger | `BigInteger` | `VARINT` |
| List<T> | `List<T>` | `list<type>` |
| Set<T> | `Set<T>` | `set<type>` |
| Map<K,V> | `Map<K,V>` | `map<key, value>` |
| UDT | `@UDT` annotated class | User-defined type |

---

## Return Types

| Signature | Description |
|-----------|-------------|
| `T method()` | Single entity (synchronous) |
| `@Nullable T method()` | Nullable single entity |
| `Optional<T> method()` | Optional single entity |
| `List<T> method()` | List of entities |
| `Set<T> method()` | Set of entities |
| `CompletionStage<T> method()` | Async (recommended) |
| `Mono<T> method()` | Reactive (requires Reactor) |
| `Flux<T> method()` | Reactive stream (requires Reactor) |
| `Flow<T> method()` | Kotlin Flow (requires Coroutines) |
| `void method()` | No return value (INSERT/UPDATE/DELETE) |

---

## Best Practices

1. **Use virtual threads** for synchronous signatures instead of reactive wrappers
2. **Prefer `CompletionStage`** for async operations over Reactor/Flow
3. **Use UDTs** for complex nested data structures
4. **Configure profiles** for different consistency requirements
5. **Enable telemetry** for observability in production
6. **Use batch operations** for bulk inserts/updates
7. **Handle nullable fields** with `@Nullable` annotation
8. **Use custom mappers** for complex type conversions
9. **Configure connection pool** based on workload
10. **Use lightweight transactions** sparingly (performance impact)

---

## Common Pitfalls

1. **Missing `@Id`** — Required for entity primary key identification
2. **Wrong consistency level** — Default may not suit your use case
3. **Forgetting UDT mapping** — Complex types require `@UDT` annotation
4. **Batch size too large** — Keep batches under 1000 operations
5. **Missing contact points** — At least one contact point required
6. **Keyspace mismatch** — Ensure repository keyspace matches table location
7. **Async without CompletionStage** — Prefer virtual threads for sync code
8. **No timeout configuration** — Always configure request timeouts

---

## See Also

- [Database Common Reference](database-common-reference.md) - Entity mapping, macros, naming strategies
- [Cassandra Configuration Reference](database-cassandra-config-reference.md) - Full configuration reference (timeouts, consistency, profiles, telemetry)
- [Database JDBC Reference](database-jdbc-reference.md) - JDBC module
- [Logging Reference](../kora-bootstrap/references/logging-reference.md) - Module telemetry logging
