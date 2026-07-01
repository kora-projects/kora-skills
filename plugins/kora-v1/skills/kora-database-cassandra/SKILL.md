---
name: kora-database-cassandra
description: "Kora Cassandra/ScyllaDB repositories over the DataStax driver via CassandraDatabaseModule. Covers @Repository extends CassandraRepository, @Query CQL, @EntityCassandra DAO records, @Column/@Id, @UDT user-defined types, @Batch writes, @CassandraProfile per-method consistency, custom CassandraRowMapper/CassandraResultSetMapper/CassandraParameterColumnMapper, and async signatures (CompletionStage, Mono/Flux, Kotlin suspend/Flow). Use when adding a Cassandra repository, mapping rows or UDTs, tuning consistency/timeout under cassandra.basic.request, or wiring contact points and keyspace."
---

# Kora Database Cassandra Skill

**Focus:** Cassandra/ScyllaDB distributed database integration using DataStax Java Driver 4.x.

> **Use for:** High-write-throughput, horizontally-scalable NoSQL workloads with tunable consistency levels, time-series data, event sourcing, and distributed systems requiring eventual consistency.

**Read this first when:**
- Adding a Cassandra repository with `@Repository` and CQL queries
- Modeling entities with `@EntityCassandra`, `@UDT` for user-defined types
- Configuring profile-based consistency levels and request timeouts
- Implementing async signatures with `CompletionStage`, Reactor, or Kotlin Flow

---

## Quick Start

### 1. Add Dependency

All Kora artifacts inherit their version from the `kora-parent` BOM; never pin
individual `ru.tinkoff.kora:*` versions. Annotation processing is mandatory —
without it no repository implementation is generated.

```groovy
dependencies {
    koraBom platform("ru.tinkoff.kora:kora-parent:1.2.17")
    annotationProcessor "ru.tinkoff.kora:annotation-processors"   // Java
    // ksp "ru.tinkoff.kora:symbol-processors"                    // Kotlin (instead of annotationProcessor)

    implementation "ru.tinkoff.kora:database-cassandra"
    implementation "ru.tinkoff.kora:config-hocon"
    implementation "ru.tinkoff.kora:logging-logback"

    // Optional: only when repository methods return Mono/Flux
    implementation "io.projectreactor:reactor-core:3.6.18"
}
```

### 2. Enable Module

```java
@KoraApp
public interface Application extends CassandraDatabaseModule {}
```

### 3. Define Entity

```java
@Table("users")
@EntityCassandra
public record User(
    @Column("id") @Id UUID id,
    @Column("name") String name,
    @Column("email") String email,
    @Column("created_at") Instant createdAt,
    @Column("nickname") @Nullable String nickname
) {}
```

### 4. Create Repository

```java
@Repository
public interface UserRepository extends CassandraRepository {
    
    @Query("SELECT * FROM users WHERE id = :id")
    @Nullable
    User findById(UUID id);
    
    @Query("SELECT * FROM users")
    List<User> findAll();
    
    @Query("INSERT INTO users (id, name, email, created_at) VALUES (:user.id, :user.name, :user.email, :user.createdAt)")
    void insert(User user);
    
    @Query("DELETE FROM users WHERE id = :id")
    void deleteById(UUID id);
}
```

> **Entity parameter binding:** when a method parameter is an entity object,
> each column is bound through the dotted accessor `:param.field`
> (e.g. `:user.id`), not a bare `:id`. A bare `:id` only resolves when `id` is
> itself the name of a method parameter (as in `findById(UUID id)`).

### 5. Configure Connection

```hocon
cassandra {
    auth {
        login = ${CASSANDRA_USER}
        password = ${CASSANDRA_PASS}
    }
    basic {
        contactPoints = ["localhost:9042"]
        dc = "datacenter1"
        sessionKeyspace = "mykeyspace"
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

---

## Basic CRUD Patterns

### Insert

```java
@Query("INSERT INTO users (id, name, email) VALUES (:user.id, :user.name, :user.email)")
void insert(User user);

// Batch insert: one single-row INSERT bound to entity fields, parameter marked @Batch
@Query("INSERT INTO users (id, name, email) VALUES (:user.id, :user.name, :user.email)")
void insertBatch(@Batch List<User> user);

// Conditional insert (LWT)
@Query("INSERT INTO users (id, name) VALUES (:user.id, :user.name) IF NOT EXISTS")
boolean insertIfNotExists(User user);
```

### Select

```java
@Query("SELECT * FROM users WHERE id = :id")
@Nullable
User findById(UUID id);

@Query("SELECT * FROM users WHERE id IN :ids")
List<User> findByIds(List<UUID> ids);

@Query("SELECT * FROM users LIMIT 100")
List<User> findFirst100();
```

### Update

```java
@Query("UPDATE users SET name = :user.name, email = :user.email WHERE id = :user.id")
void update(User user);

// Conditional update (LWT)
@Query("UPDATE users SET email = :email WHERE id = :id IF email = :oldEmail")
boolean updateIfEmailMatches(UUID id, String email, String oldEmail);
```

### Delete

```java
@Query("DELETE FROM users WHERE id = :id")
void deleteById(UUID id);

@Query("TRUNCATE users")
void deleteAll();
```

---

## Async Signatures

### CompletionStage (Recommended)

```java
@Query("SELECT * FROM users WHERE id = :id")
CompletableFuture<User> findByIdAsync(UUID id);

@Query("INSERT INTO users (id, name) VALUES (:user.id, :user.name)")
CompletionStage<Void> insertAsync(User user);
```

### Project Reactor

```java
@Query("SELECT * FROM users WHERE id = :id")
Mono<User> findByIdReactive(UUID id);

@Query("SELECT * FROM users")
Flux<User> findAllReactive();
```

### Kotlin Coroutines

```kotlin
@Query("SELECT * FROM users WHERE id = :id")
suspend fun findByIdAsync(id: UUID): User?

@Query("SELECT * FROM users")
fun findAllFlow(): Flow<User>
```

---

## UDT Support

```java
@UDT
public record AddressUDT(
    @Column("street") String street,
    @Column("city") String city,
    @Column("zipCode") String zipCode
) {}

@Table("users")
@EntityCassandra
public record User(
    @Column("id") @Id UUID id,
    @Column("name") String name,
    @Column("address") AddressUDT address
) {}
```

---

## Profile-Based Consistency

All request-level tuning (consistency, timeout, page size) lives under
`basic.request`. A profile overrides any `basic.request.*` (and `advanced.*`)
key for the queries that reference it.

### Configuration

```hocon
cassandra {
    basic {
        request {
            consistency = "QUORUM"        // default consistency for all queries
            serialConsistency = "SERIAL"  // consistency for lightweight transactions
            timeout = "5s"
        }
    }
    profiles {
        analytics {
            basic.request.consistency = "ONE"
            basic.request.timeout = "30s"
        }
        critical {
            basic.request.consistency = "ALL"
            basic.request.timeout = "5s"
        }
    }
}
```

### Using Profiles

`@CassandraProfile` targets methods only (`@Target(ElementType.METHOD)`). It
cannot be placed on the repository interface — apply it per `@Query` method.

```java
@Repository
public interface EventRepository extends CassandraRepository {

    @CassandraProfile("analytics")
    @Query("SELECT * FROM events WHERE type = :type ALLOW FILTERING")
    List<Event> findByType(String type);
}
```

---

## Assets

### Entity Templates
| Template | Language | Description |
|----------|----------|-------------|
| `cassandra-entity-single-id.java.template` | Java | Entity with single-field ID |
| `cassandra-entity-single-id.kt.template` | Kotlin | Data class with single-field ID |
| `cassandra-entity-composite-id.java.template` | Java | Entity with composite partition key |
| `cassandra-entity-composite-id.kt.template` | Kotlin | Data class with composite key |
| `cassandra-entity-with-udt.java.template` | Java | Entity with UDT and List<UDT> |

### Repository Templates
| Template | Language | Description |
|----------|----------|-------------|
| `cassandra-crud-single-id-repository.java.template` | Java | CRUD with LWT support |
| `cassandra-crud-single-id-repository.kt.template` | Kotlin | Kotlin CRUD repository |
| `cassandra-crud-composite-id-repository.java.template` | Java | CRUD for composite key |
| `cassandra-crud-composite-id-repository.kt.template` | Kotlin | Kotlin composite key CRUD |
| `cassandra-async-repository.java.template` | Java | CompletionStage async |
| `cassandra-async-repository.kt.template` | Kotlin | Kotlin async |
| `cassandra-lwt-repository.java.template` | Java | Lightweight transactions |
| `cassandra-lwt-repository.kt.template` | Kotlin | Kotlin LWT |
| `cassandra-kotlin-coroutine-repository.kt.template` | Kotlin | Kotlin coroutines + Flow |

### UDT Templates
| Template | Language | Description |
|----------|----------|-------------|
| `cassandra-udt.java.template` | Java | Basic UDT (Address example) |
| `cassandra-udt.kt.template` | Kotlin | Kotlin UDT data class |
| `cassandra-nested-udt.java.template` | Java | Nested UDT structure |

---

## Reference Documents

| Document | Description |
|----------|-------------|
| [CQL Repository Reference](references/cql-repository-reference.md) | @EntityCassandra, CQL queries, custom mappers, return types |
| [UDT Mapping Reference](references/udt-mapping-reference.md) | @UDT, nested types, collections of UDTs |
| [Consistency Reference](references/consistency-reference.md) | Consistency levels, profiles, retry policies |
| [Async Patterns Reference](references/async-patterns-reference.md) | CompletionStage, Reactor, Kotlin Flow |
| [Cassandra Config Reference](references/cassandra-config-reference.md) | Connection, timeouts, load balancing, multiple keyspaces |

---

## Best Practices

1. **Use `@EntityCassandra` on DAO records** — generates the Cassandra row and
   result-set mappers eagerly at compile time instead of in a late generation round.
2. **Add `@Column` to every component** — makes the CQL column name explicit
   (e.g. Java `createdAt` -> column `created_at`).
3. **`@Id` is optional** — Cassandra needs no special primary-key marker; add
   `@Id` only when you use [SQL macros](references/cql-repository-reference.md).
4. **Use `@Nullable`, not `Optional`** — for nullable single-row return values.
5. **Extend `CassandraRepository`** — required base interface for the generator.
6. **Keep DTOs and DAOs separate** — HTTP `@Json` DTOs are not Cassandra entities.
7. **Apply `@CassandraProfile` per method** — separate analytics from critical reads.
8. **Model tables from query patterns** — avoid unbounded `SELECT ... FROM table` scans in production.

---

## Common Pitfalls

| Symptom | Fix |
|---------|-----|
| `@CassandraProfile` rejected on the interface | It is `@Target(METHOD)` — move it onto each `@Query` method. |
| Config key `basic.consistency` ignored | Consistency lives under `basic.request.consistency`. |
| Profile timeout ignored (`requestTimeout`) | Override `basic.request.timeout` inside the profile, not a flat key. |
| Complex field not mapped | Nested types need `@UDT`; collections of UDTs need `FROZEN` in CQL. |
| `Required field is not nullable but row has null` | Add `@Nullable` to the optional record component. |
| Repository method not generated | Annotation processor missing, or the interface does not extend `CassandraRepository`. |
