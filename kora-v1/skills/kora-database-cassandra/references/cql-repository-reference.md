# CQL Repository Reference

**Module:** `ru.tinkoff.kora:database-cassandra`  
**Driver:** DataStax Java Driver 4.x

## Contents

- [Repository Declaration](#repository-declaration)
- [@EntityCassandra Annotation](#entitycassandra-annotation)
- [CQL Query Patterns](#cql-query-patterns)
- [Query Parameters](#query-parameters)
- [Return Types](#return-types)
- [Paging](#paging)
- [Custom Mappers](#custom-mappers)

---

## Repository Declaration

```java
@Repository
public interface UserRepository extends CassandraRepository {
    
    @Query("SELECT * FROM users WHERE id = :id")
    @Nullable
    User findById(UUID id);
    
    @Query("SELECT * FROM users")
    List<User> findAll();
    
    @Query("INSERT INTO users (id, name, email) VALUES (:user.id, :user.name, :user.email)")
    void insert(User user);
    
    @Query("DELETE FROM users WHERE id = :id")
    void deleteById(UUID id);
}
```

**Kotlin:**
```kotlin
@Repository
interface UserRepository : CassandraRepository {
    
    @Query("SELECT * FROM users WHERE id = :id")
    fun findById(id: UUID): User?
    
    @Query("SELECT * FROM users")
    fun findAll(): List<User>
    
    @Query("INSERT INTO users (id, name, email) VALUES (:user.id, :user.name, :user.email)")
    fun insert(user: User)
    
    @Query("DELETE FROM users WHERE id = :id")
    fun deleteById(id: UUID)
}
```

---

## @EntityCassandra Annotation

`@EntityCassandra` generates the Cassandra mappers for a DAO record at compile
time. `@Id` is optional in Cassandra (it only matters for SQL macros); `@Table`
is only needed when you use macros.

```java
@Table("users")
@EntityCassandra
public record User(
    @Column("id") UUID id,
    @Column("name") String name,
    @Column("email") String email,
    @Column("created_at") Instant createdAt,
    @Column("nickname") @Nullable String nickname
) {}
```

**Why `@EntityCassandra`?**
- Generates `$User_CassandraRowMapper.java` — maps a `Row` to the entity.
- Generates `$User_ListCassandraResultSetMapper.java` — maps a `ResultSet` to `List<Entity>`.
- Generates the mappers eagerly instead of in a slower late generation round.

**Generated mapper types:**
- `CassandraRowMapper<T>` — maps a single `Row` to an entity.
- `CassandraResultSetMapper<T>` — maps a `ResultSet` to a result (e.g. a collection).

---

## CQL Query Patterns

### SELECT Queries

```java
@Repository
public interface UserRepository extends CassandraRepository {
    
    // Single by ID
    @Query("SELECT * FROM users WHERE id = :id")
    @Nullable
    User findById(UUID id);
    
    // All with LIMIT
    @Query("SELECT * FROM users LIMIT 100")
    List<User> findFirst100();
    
    // Filter by clustering column
    @Query("SELECT * FROM events WHERE bucket = :bucket AND event_time > :timestamp")
    List<Event> findByBucketAndTime(String bucket, Instant timestamp);
    
    // Filter with IN clause
    @Query("SELECT * FROM users WHERE id IN :ids")
    List<User> findByIds(List<UUID> ids);
    
    // Allow filtering (use sparingly)
    @Query("SELECT * FROM users WHERE email = :email ALLOW FILTERING")
    List<User> findByEmail(String email);
}
```

### INSERT/UPDATE Queries

```java
@Repository
public interface UserRepository extends CassandraRepository {
    
    // Simple insert
    @Query("INSERT INTO users (id, name, email) VALUES (:user.id, :user.name, :user.email)")
    void insert(User user);
    
    // Insert with TTL
    @Query("INSERT INTO sessions (id, data) VALUES (:session.id, :session.data) USING TTL 3600")
    void insertWithTtl(Session session);
    
    // Insert if not exists (LWT)
    @Query("INSERT INTO users (id, name) VALUES (:user.id, :user.name) IF NOT EXISTS")
    @Nullable
    User insertIfNotExists(User user);
    
    // Update with condition (LWT)
    @Query("UPDATE users SET email = :email WHERE id = :id IF email = :oldEmail")
    @Nullable
    User updateIfEmailMatches(UUID id, String email, String oldEmail);
}
```

### DELETE Queries

```java
@Repository
public interface UserRepository extends CassandraRepository {
    
    // Delete by ID
    @Query("DELETE FROM users WHERE id = :id")
    void deleteById(UUID id);
    
    // Delete with condition
    @Query("DELETE FROM users WHERE id = :id IF email = :oldEmail")
    @Nullable
    User deleteIfEmailMatches(UUID id, String oldEmail);
    
    // Truncate table (use with caution)
    @Query("TRUNCATE users")
    void deleteAll();
}
```

---

## Query Parameters

### Named Parameters

```java
@Query("SELECT * FROM users WHERE id = :id AND status = :status")
List<User> findByIdAndStatus(UUID id, String status);
```

### Collection Parameters

```java
@Query("SELECT * FROM users WHERE id IN :ids")
List<User> findByIds(List<UUID> ids);

@Query("SELECT * FROM products WHERE category IN :categories")
List<Product> findByCategories(Set<String> categories);
```

### Nullable Parameters

```java
@Query("SELECT * FROM users WHERE nickname = :nickname")
List<User> findByNickname(@Nullable String nickname);
```

---

## Return Types

### Synchronous

These are the signatures Kora supports out of the box (see
`database-cassandra.md`):

| Return Type | Description |
|-------------|-------------|
| `T` | Single value/entity |
| `@Nullable T` | Nullable single value/entity |
| `Optional<T>` | Optional single value/entity |
| `List<T>` | List of entities |
| `void` | No return (INSERT/UPDATE/DELETE) |

A single-column row may map to a Java native type (`String`, `int`, `boolean`,
`UUID`, ...). This is how a lightweight-transaction method can return `boolean`:
the first column of an LWT result is the `[applied]` flag.

### Asynchronous (CompletionStage)

```java
@Query("SELECT * FROM users WHERE id = :id")
CompletableFuture<User> findByIdAsync(UUID id);

@Query("SELECT * FROM users")
CompletionStage<List<User>> findAllAsync();

@Query("INSERT INTO users (id, name) VALUES (:user.id, :user.name)")
CompletionStage<Void> insertAsync(User user);
```

### Reactive (Project Reactor)

```java
@Query("SELECT * FROM users WHERE id = :id")
Mono<User> findByIdReactive(UUID id);

@Query("SELECT * FROM users")
Flux<User> findAllReactive();

@Query("INSERT INTO users (id, name) VALUES (:user.id, :user.name)")
Mono<Void> insertReactive(User user);
```

### Kotlin Coroutines

```kotlin
@Query("SELECT * FROM users WHERE id = :id")
suspend fun findByIdAsync(id: UUID): User?

@Query("SELECT * FROM users")
fun findAllFlow(): Flow<User>
```

---

## Paging

Kora Cassandra repositories have no `Pageable` parameter. Control result size
with CQL `LIMIT` and the driver page size (`cassandra.basic.request.pageSize`),
or implement [token-based paging](https://cassandra.apache.org/doc/latest/) via
a custom `CassandraResultSetMapper`.

```java
@Query("SELECT * FROM users LIMIT 100")
List<User> findFirst100();
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
            row.getString("name"),
            row.getString("email"),
            row.getInstant("created_at")
        );
    }
}

@Repository
public interface UserRepository extends CassandraRepository {
    @Mapping(UserRowMapper.class)
    @Query("SELECT id, name, email, created_at FROM users")
    List<User> findAll();
}
```

### Result Set Mapper

```java
public class UserResultMapper implements CassandraResultSetMapper<User> {
    @Override
    public User apply(ResultSet rs) {
        Row row = rs.one();
        return (row != null) ? new User(
            row.getUuid("id"),
            row.getString("email"),
            row.getInstant("created_at")
        ) : null;
    }
}

@Repository
public interface UserRepository extends CassandraRepository {
    @Mapping(UserResultMapper.class)
    @Query("SELECT * FROM users WHERE id = :id")
    @Nullable
    User findById(UUID id);
}
```

### Column Mapper (Read)

```java
public class EventTypeMapper implements CassandraRowColumnMapper<EventType> {
    
    private static final EventType[] ALL = EventType.values();

    @Override
    public EventType apply(GettableByName row, int index) {
        int code = row.getInt(index);
        for (EventType type : ALL) {
            if (type.code() == code) {
                return type;
            }
        }
        return EventType.UNKNOWN;
    }
}

public enum EventType {
    UNKNOWN(-10), CREATE(1), UPDATE(2), DELETE(3);
    private final int code;
    EventType(int code) { this.code = code; }
    public int code() { return code; }
}

@Table("events")
@EntityCassandra
public record Event(
    @Id UUID id,
    @Mapping(EventTypeMapper.class) @Column("type") EventType type,
    Instant createdAt
) {}
```

### Column Mapper (Write)

```java
public class EventTypeParameterMapper implements CassandraParameterColumnMapper<EventType> {
    @Override
    public void apply(SettableByName<?> stmt, int index, @Nullable EventType value) {
        if (value != null) {
            stmt.setInt(index, value.code());
        } else {
            stmt.setToNull(index);
        }
    }
}

@Repository
public interface EventRepository extends CassandraRepository {
    @Query("INSERT INTO events (id, type, created_at) VALUES (:id, :type, :createdAt)")
    void insert(UUID id, @Mapping(EventTypeParameterMapper.class) EventType type, Instant createdAt);
}
```

### Reactive Result Set Mapper

```java
public class EventPartResultSetMapper implements
        CassandraReactiveResultSetMapper<Map<Integer, List<EventPart>>, Mono<Map<Integer, List<EventPart>>>> {

    @Override
    public Mono<Map<Integer, List<EventPart>>> apply(ReactiveResultSet rows) {
        return Flux.from(rows)
                .map(row -> new EventPart(row.getString(0), row.getInt(1)))
                .collect(HashMap::new, (collector, value) -> {
                    var parts = collector.computeIfAbsent(value.field1(), k -> new ArrayList<>());
                    parts.add(value);
                });
    }
}

@Repository
public interface EventRepository extends CassandraRepository {
    @Mapping(EventPartResultSetMapper.class)
    @Query("SELECT id, type FROM events")
    Mono<Map<Integer, List<EventPart>>> findAllParts();
}
```

---

## See Also

- [UDT Mapping Reference](udt-mapping-reference.md) — @UDT, custom types
- [Consistency Reference](consistency-reference.md) — consistency levels, profiles
- [Async Patterns Reference](async-patterns-reference.md) — CompletionStage, reactive
