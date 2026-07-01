# Async Patterns Reference

**Module:** `ru.tinkoff.kora:database-cassandra`  
**Driver:** DataStax Java Driver 4.x

## Contents

- [Overview](#overview)
- [CompletionStage (Recommended)](#completionstage-recommended)
- [Project Reactor](#project-reactor)
- [Kotlin Coroutines](#kotlin-coroutines)
- [Reactive Result Set Mappers](#reactive-result-set-mappers)
- [Virtual Threads vs Async](#virtual-threads-vs-async)
- [Batch Async Operations](#batch-async-operations)
- [Best Practices](#best-practices)

---

## Overview

Cassandra supports multiple async signatures. With Virtual Threads (Java 21+), sync signatures are recommended for simplicity, but async patterns are available for high-concurrency scenarios.

**Async options:**
1. **CompletionStage** — Standard Java async (recommended)
2. **Project Reactor** — Reactive streams (requires reactor-core)
3. **Kotlin Coroutines** — Suspend functions (requires kotlinx-coroutines)

---

## CompletionStage (Recommended)

### Basic Async Repository

```java
@Repository
public interface AsyncUserRepository extends CassandraRepository {
    
    @Query("SELECT * FROM users WHERE id = :id")
    CompletableFuture<User> findById(String id);
    
    @Query("SELECT * FROM users")
    CompletionStage<List<User>> findAll();
    
    @Query("INSERT INTO users (id, name, email) VALUES (:user.id, :user.name, :user.email)")
    CompletionStage<Void> insert(User user);
    
    @Query("DELETE FROM users WHERE id = :id")
    CompletableFuture<Void> deleteById(String id);
}
```

### Chaining Operations

```java
@Component
public class UserService {
    private final AsyncUserRepository userRepository;
    
    public UserService(AsyncUserRepository userRepository) {
        this.userRepository = userRepository;
    }
    
    public CompletionStage<User> getUserWithFallback(String id, String fallbackId) {
        return userRepository.findById(id)
            .thenCompose(user -> {
                if (user != null) {
                    return CompletableFuture.completedFuture(user);
                }
                return userRepository.findById(fallbackId);
            });
    }
    
    public CompletionStage<List<User>> getAllUsersSorted() {
        return userRepository.findAll()
            .thenApply(users -> users.stream()
                .sorted(Comparator.comparing(User::name))
                .toList());
    }
}
```

### Exception Handling

```java
public CompletionStage<User> getUserSafe(String id) {
    return userRepository.findById(id)
        .handle((user, ex) -> {
            if (ex != null) {
                throw new CompletionException("Failed to fetch user", ex);
            }
            return user;
        });
}
```

---

## Project Reactor

### Reactor Repository

Requires `io.projectreactor:reactor-core` dependency.

```java
@Repository
public interface ReactorUserRepository extends CassandraRepository {
    
    @Query("SELECT * FROM users WHERE id = :id")
    Mono<User> findById(String id);
    
    @Query("SELECT * FROM users")
    Flux<User> findAll();
    
    @Query("INSERT INTO users (id, name) VALUES (:user.id, :user.name)")
    Mono<Void> insert(User user);
    
    @Query("DELETE FROM users WHERE id = :id")
    Mono<Void> deleteById(String id);
    
    // Mono with list
    @Query("SELECT * FROM users")
    Mono<List<User>> findAllMono();
}
```

### Reactor Service

```java
@Component
public class UserService {
    private final ReactorUserRepository userRepository;
    
    public UserService(ReactorUserRepository userRepository) {
        this.userRepository = userRepository;
    }
    
    public Mono<User> getUser(String id) {
        return userRepository.findById(id)
            .switchIfEmpty(Mono.error(() -> 
                new NotFoundException("User not found")));
    }
    
    public Flux<User> getAllUsersSorted() {
        return userRepository.findAll()
            .sort(Comparator.comparing(User::name));
    }
    
    public Mono<Void> createUser(User user) {
        return userRepository.insert(user);
    }
    
    public Mono<User> getUserWithFallback(String id, String fallbackId) {
        return userRepository.findById(id)
            .switchIfEmpty(userRepository.findById(fallbackId));
    }
}
```

### Reactive Pipeline

```java
public Flux<Event> processEvents() {
    return eventRepository.findAll()
        .filter(event -> event.type() == EventType.CREATE)
        .flatMap(event -> transformEvent(event))
        .bufferTimeout(100, Duration.ofSeconds(5))
        .flatMap(batch -> eventRepository.insertBatch(batch));
}
```

---

## Kotlin Coroutines

### Coroutine Repository

Requires `org.jetbrains.kotlinx:kotlinx-coroutines-core` dependency.

```kotlin
@Repository
interface UserRepository : CassandraRepository {
    
    @Query("SELECT * FROM users WHERE id = :id")
    suspend fun findById(id: String): User?
    
    @Query("SELECT * FROM users")
    fun findAllFlow(): Flow<User>
    
    @Query("SELECT * FROM users")
    suspend fun findAll(): List<User>
    
    @Query("INSERT INTO users (id, name) VALUES (:user.id, :user.name)")
    suspend fun insert(user: User)
    
    @Query("DELETE FROM users WHERE id = :id")
    suspend fun deleteById(id: String)
}
```

### Coroutine Service

```kotlin
@Component
class UserService(private val userRepository: UserRepository) {
    
    suspend fun getUser(id: String): User {
        return userRepository.findById(id) 
            ?: throw NotFoundException("User not found")
    }
    
    fun getAllUsersFlow(): Flow<User> {
        return userRepository.findAllFlow()
            .flowOn(Dispatchers.IO)
    }
    
    suspend fun createUser(user: User): User {
        userRepository.insert(user)
        return user
    }
    
    suspend fun processUsers(): List<User> {
        return userRepository.findAllFlow()
            .filter { it.isActive }
            .toList()
    }
}
```

### Flow Operations

```kotlin
fun processEvents(): Flow<Event> {
    return eventRepository.findAllFlow()
        .filter { it.type == EventType.CREATE }
        .map { transformEvent(it) }
        .buffer(100)
        .flowOn(Dispatchers.IO)
}
```

---

## Reactive Result Set Mappers

For advanced reactive scenarios with custom result mapping:

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

## Virtual Threads vs Async

### Virtual Threads (Java 21+)

With Virtual Threads, sync signatures perform comparably to async:

```java
@Repository
public interface SyncUserRepository extends CassandraRepository {
    
    @Query("SELECT * FROM users WHERE id = :id")
    @Nullable
    User findById(String id);
    
    @Query("SELECT * FROM users")
    List<User> findAll();
}
```

**Benefits:**
- Simpler code
- Better debugging
- Stack traces preserved
- No callback hell

**When to use:** Most use cases with Java 21+

### When to Use Async

**Use async when:**
- High-concurrency scenarios (10k+ concurrent requests)
- Integration with reactive pipelines
- Backpressure handling required
- Streaming large result sets

---

## Batch Async Operations

```java
@Repository
public interface AsyncUserRepository extends CassandraRepository {
    
    @Query("INSERT INTO users (id, name) VALUES (:users.id, :users.name)")
    CompletionStage<Void> insertBatch(@Batch List<User> users);
    
    @Query("UPDATE users SET name = :users.name WHERE id = :users.id")
    CompletionStage<Void> updateBatch(@Batch List<User> users);
}
```

---

## Best Practices

1. **Prefer sync with Virtual Threads** — Simpler, debuggable code
2. **Use CompletionStage for async** — Standard Java API
3. **Avoid mixing sync/async** — Pick one pattern per repository
4. **Handle nulls properly** — Use `@Nullable`, not `Optional`
5. **Timeout long operations** — set `basic.request.timeout` (optionally per `@CassandraProfile`)
6. **Monitor async chains** — Add error handling at each stage

---

## See Also

- [CQL Repository Reference](cql-repository-reference.md) — Repository patterns, return types
- [Consistency Reference](consistency-reference.md) — Consistency levels for async operations
