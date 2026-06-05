---
name: kora-database
description: Database integration in Kora applications using JDBC and Cassandra. Prefer JDBC/Cassandra + Virtual Threads over reactive approaches (R2DBC/Vert.x). Use when creating repositories, writing @Query methods, configuring HikariCP, or integrating Cassandra. Triggers: JdbcRepository, @Query, @Transaction, CassandraRepository, HikariConfig, database migrations, Flyway, Liquibase.
---

# Kora Database Skill

**Focus:** JDBC and Cassandra database integration with Kora Framework.

> **Important:** While Kora supports R2DBC and Vert.x, prefer **JDBC + Virtual Threads** for relational databases and **Cassandra + Virtual Threads** for NoSQL. This approach provides better debugging, simpler code, and comparable performance with modern virtual threads.
>
> **ALWAYS prefer synchronous repository signatures** — use `Entity` or `@Nullable Entity` return types, not `CompletionStage`, `Mono`, or `Flux`. Virtual threads handle blocking efficiently, making reactive patterns unnecessary for most use cases.

Read this first when:
- adding a database repository with `@Repository` and `@Query` annotations,
- modeling entity classes with `@Table`, `@Column`, and `@Id` mappings,
- wiring transactions via `JdbcConnectionFactory.inTx()`,
- choosing between JDBC (recommended) vs R2DBC/Vert.x (not recommended),
- running database migrations with Flyway/Liquibase via Testcontainers.

## Quick Start

### 1. Add Dependencies

```groovy
// build.gradle
dependencies {
    implementation "ru.tinkoff.kora:database-jdbc"
    
    // Database driver (required)
    implementation "org.postgresql:postgresql:42.7.3"  // PostgreSQL
    
    // Cassandra
    implementation "ru.tinkoff.kora:database-cassandra" // DataStax driver included transitively
}
```

### 2. Configure Application Module

```java
@KoraApp
public interface Application extends 
    JdbcDatabaseModule,      // JDBC support
    CassandraDatabaseModule  // Cassandra support
{}
```

### 3. Define Entity

```java
@EntityJdbc
@Table("users")
public record User(
    @Column("id") @Id Long id,
    @Column("email") String email,
    @Column("created_at") LocalDateTime createdAt
) {}
```

**Important:** Use `@EntityJdbc` annotation for JDBC entities to enable optimized result converters.

### 4. Create Repository

```java
@Repository
public interface UserRepository extends JdbcRepository {
    
    @Query("SELECT * FROM users WHERE id = :id")
    User findById(Long id);
    
    @Query("SELECT * FROM users WHERE email = :email")
    Optional<User> findByEmail(String email);
    
    @Query("INSERT INTO users (email, created_at) VALUES (:email, :createdAt)")
    void insert(String email, LocalDateTime createdAt);
    
    @Query("UPDATE users SET email = :email WHERE id = :id")
    void update(Long id, String email);
    
    @Query("DELETE FROM users WHERE id = :id")
    void delete(Long id);
}
```

**Important:** Repositories should extend `JdbcRepository` (for JDBC) or `CassandraRepository` (for Cassandra) to inherit base functionality.

### 5. Use in Component

```java
@Component
public class UserService {
    private final UserRepository userRepository;
    
    public UserService(UserRepository userRepository) {
        this.userRepository = userRepository;
    }
    
    public User getUser(Long id) {
        return userRepository.findById(id);
    }
}
```

---

## Quick Reference

### Common Annotations

| Annotation | Purpose | Example |
|------------|---------|---------|
| `@Table` | Map record to table | `@Table("users")` |
| `@Column` | Map field to column | `@Column("email_address")` |
| `@Id` | Mark primary key | `@Id @Column("id") Long id` |
| `@Embedded` | Flatten value object | `@Embedded Address address` |
| `@Repository` | Mark repository interface | `@Repository` |
| `@Query` | Define SQL/CQL query | `@Query("SELECT * FROM users")` |
| `@Batch` | Enable batch operations | `void insert(@Batch List<User> users)` |
| `@Mapping` | Use custom mapper | `@Mapping(CustomMapper.class)` |

### Common Macros

| Macro | Generates |
|-------|-----------|
| `%{return#selects}` | SELECT column list |
| `%{return#table}` | Table name |
| `%{entity#inserts}` | Full INSERT statement |
| `%{entity#updates}` | Full UPDATE statement |
| `%{entity#deletes}` | Full DELETE statement |
| `%{entity#where}` | WHERE clause by ID |

### Transaction Pattern

```java
connectionFactory.inTx(() -> {
    repository.insert(user);
    var context = connectionFactory.currentConnectionContext();
    context.addPostCommitAction(() -> sendEmail(user));
});
```

### Return Types

| Pattern | Use | Example |
|---------|-----|---------|
| `@Nullable Entity` | Single result (preferred) | Zero overhead, works with static analysis |
| `Optional<Entity>` | Single result (avoid) | Creates garbage, not recommended |
| `List<Entity>` | Multiple results | Returns empty list if no results |
| `UpdateCount` | INSERT/UPDATE/DELETE | Affected rows count |

---

## Core Concepts

### Entity Mapping

Use `@Table` to map Java records to database tables. Field mapping is done via `@Column` annotations.

**Primary Keys:** Use `@Id` to mark the primary key field.

**Embedded Types:** Use `@Embedded` for value objects that should be flattened into the parent table.

```java
@Embedded
public record Address(String street, String city, String zipCode) {}

@Table("users")
@EntityJdbc
public record User(
    @Column("id") @Id Long id,
    @Column("name") String email,
    @Embedded Address address  // Flattens to address_street, address_city, address_zip
) {}
```

### Repository Pattern

Repositories are interfaces annotated with `@Repository`. Kora generates implementations at compile time.

**Base Interfaces:** Extend `JdbcRepository` (for JDBC) or `CassandraRepository` (for Cassandra) to inherit base functionality.

**Query Methods:** Use `@Query` with SQL or CQL. Parameters are matched by name.

**ID Type Matching:** The ID type in repository methods must exactly match the entity's `@Id` field type:
- If entity has `String id`, use `findById(String id)`
- If entity has `UUID id`, use `findById(UUID id)`
- If entity has `Long id`, use `findById(Long id)`
- For composite IDs, use the nested record type: `findById(Entity.ID id)`

**Return Types:** Supported return types include:
- Single entity: `Entity`, `@Nullable Entity` (preferred), `Optional<Entity>` (avoid - creates garbage)
- Collections: `List<Entity>`, `Set<Entity>` (always return empty collection, not null)
- Update count: `UpdateCount` (for INSERT/UPDATE/DELETE)
- Batch operations: `UpdateCount` with `@Batch` parameter
- Primitives: `int`, `long`, `boolean`

**Important:** ALWAYS prefer **synchronous signatures** in repository interfaces. Kora uses virtual threads (Project Loom) which provide:
- Better debugging with standard stack traces
- Simpler, more readable code
- Comparable or better performance than reactive approaches
- No need for `Mono`, `Flux`, or `CompletionStage` unless you have specific non-blocking requirements

Use `CompletionStage` only when you need explicit non-blocking behavior (e.g., calling external APIs from repository methods).

### SQL Macros

Kora provides macros for generating SQL:

| Macro | Generates |
|-------|-----------|
| `%{return#selects}` | Column list for SELECT |
| `%{entity#inserts}` | INSERT statement |
| `%{entity#updates}` | UPDATE statement |
| `%{entity#deletes}` | DELETE statement |

```java
@Repository
public interface UserRepository {
    @Query("SELECT %{return#selects} FROM users WHERE id = :id")
    User findById(Long id);
    
    @Query("%{entity#inserts}")
    void insert(User user);
    
    @Query("%{entity#updates}")
    void update(User user);
}
```

### Transaction Management

Use `JdbcConnectionFactory.inTx()` for transactions:

```java
@Component
public class UserService {
    private final UserRepository userRepository;
    private final JdbcConnectionFactory connectionFactory;
    
    public void createUserWithAddress(User user, Address address) {
        connectionFactory.inTx(() -> {
            userRepository.insert(user);
            // If this throws, entire transaction rolls back
        });
    }
}
```

### Custom Mappers

When default mapping isn't sufficient, implement custom mappers:

**ResultSet Mapper:**
```java
public class CustomUserMapper implements JdbcResultSetMapper<User> {
    @Override
    public User map(ResultSet rs) {
        return new User(
            rs.getLong("id"),
            rs.getString("email"),
            rs.getTimestamp("created_at").toLocalDateTime()
        );
    }
}
```

**Row Mapper:**
```java
public class CustomUserRowMapper implements JdbcRowMapper<User> {
    @Override
    public User mapRow(ResultSet rs, int rowNum) {
        return new User(
            rs.getLong("id"),
            rs.getString("email"),
            rs.getTimestamp("created_at").toLocalDateTime()
        );
    }
}
```

---

## JDBC Configuration

### application.conf

```hocon
db {
    jdbcUrl = ${POSTGRES_JDBC_URL}  # "jdbc:postgresql://localhost:5432/mydb"
    username = ${POSTGRES_USER}
    password = ${POSTGRES_PASS}
    
    # HikariCP pool settings
    maxPoolSize = 10
    minIdle = 2
    connectionTimeout = 30000
    idleTimeout = 600000
    maxLifetime = 1800000
    
    # Telemetry (optional)
    telemetry.logging.enabled = true
}
```

**Best Practice:** Use environment variable substitution for credentials and connection strings.

### application.yaml

```yaml
db:
  jdbcUrl: ${POSTGRES_JDBC_URL}
  username: ${POSTGRES_USER}
  password: ${POSTGRES_PASS}
  maxPoolSize: 10
  minIdle: 2
  connectionTimeout: 30000
```

---

## Cassandra Configuration

### application.conf

```hocon
cassandra {
    auth {
        login = ${CASSANDRA_USER}
        password = ${CASSANDRA_PASS}
    }
    basic {
        contactPoints = ${CASSANDRA_CONTACT_POINTS}  # ["localhost:9042"]
        dc = ${CASSANDRA_DC}  # "datacenter1"
        sessionKeyspace = ${CASSANDRA_KEYSPACE}  # "mykeyspace"
        
        # Connection settings
        request {
            timeout = 5s
        }
    }
    
    # Telemetry (optional)
    telemetry.logging.enabled = true
}
```

**Best Practice:** Use environment variable substitution for credentials and connection settings.

### UDT Support

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
    @Column("id") @Id Long id,
    @Column("name") String name,
    AddressUDT address
) {}
```

**Alternative Pattern (Nested UDT):** You can also define UDTs as nested records inside the entity:

```java
@Repository
public interface UserRepository extends CassandraRepository {
    @EntityCassandra
    record User(String id, Name name) {
        @UDT
        public record Name(String first, String last) {}
    }
    
    @Query("SELECT * FROM users WHERE id = :id")
    @Nullable
    User findById(String id);
}
```

### Profile-Based Configuration

```java
@Repository
@CassandraProfile("analytics")
public interface AnalyticsRepository {
    @Query("SELECT * FROM events WHERE type = :type")
    List<Event> findByType(String type);
}
```

```hocon
cassandra {
    profiles {
        analytics {
            consistency = "ONE"
            serialConsistency = "ANY"
            requestTimeout = "30s"
        }
    }
}
```

---

## Common Pitfalls

1. **Missing @Repository annotation** — Repositories must be annotated with `@Repository`
2. **Forgetting to extend base repository** — Extend `JdbcRepository` or `CassandraRepository` for base functionality
3. **Missing @EntityJdbc for JDBC entities** — Use `@EntityJdbc` for optimized result converters
4. **Incorrect parameter names** — Ensure method parameters match `:paramName` in queries
5. **Forgetting @Id** — Entity primary keys must be marked with `@Id`
6. **Transaction scope** — `inTx()` requires a lambda; operations outside won't be transactional
7. **Connection pool exhaustion** — Configure `maximumPoolSize` appropriately for your workload
8. **Using reactive types unnecessarily** — ALWAYS prefer sync signatures with Virtual Threads; use `CompletionStage` only for explicit non-blocking requirements
9. **Missing @Batch annotation** — Batch operations require `@Batch` on List parameters
10. **Wrong config path for Cassandra** — Use `cassandra.` prefix, not `database.cassandra.`
11. **ID type mismatch** — Repository ID type must match entity's `@Id` field type exactly (String vs UUID vs Long)

---

## Reference Files

**Core References:**
- [Database Common Reference](references/database-common-reference.md) — Entity mapping, SQL macros, naming strategies
- [JDBC Module Reference](references/database-jdbc-reference.md) — Transaction management, batch operations, multiple databases
- [Cassandra Module Reference](references/database-cassandra-reference.md) — UDTs, profile-based config, async signatures, lightweight transactions
- [JDBC Custom Mappers Reference](references/database-jdbc-custom-mappers-reference.md) — ResultSet/Row/Column/Parameter mappers, JSONB, arrays, `@Nullable` vs `Optional`

**Configuration References:**
- [JDBC Configuration Reference](references/database-jdbc-config-reference.md) — HikariCP pool settings, driver setup, multiple databases, telemetry
- [Cassandra Configuration Reference](references/database-cassandra-config-reference.md) — Contact points, consistency levels, profiles, retry policies

**Testing:**
- See [kora-testing skill](../kora-testing/) — integration testing with testcontainers-extensions, JUnit5 extension, migrations

---

## Examples

**JDBC Examples** (`.kora-agent/kora-examples/kora-java-database-jdbc/`):
- `JdbcCrudMacrosRepository` — Basic CRUD with SQL macros (`%{return#selects}`, `%{entity#inserts}`)
- `JdbcCrudMacrosIdCompositeRepository` — Composite ID with `%{id#where}` macro
- `AbstractJdbcCrudRepository` — Abstract base for inheritance pattern
- `JdbcMapperResultSetRepository` — Custom `JdbcResultSetMapper` for complex result mapping
- `JdbcTransactionsRepository` — Transaction management with `inTx()`, post-commit/rollback actions
- `JdbcMultipleDatabasesRepository` — Multiple databases with `@Tag` annotation
- `JdbcJsonbRepository` — JSONB column handling with `@Json` annotation
- `application.conf` — Environment variable configuration pattern (`${POSTGRES_JDBC_URL}`, `${POSTGRES_USER}`, `${POSTGRES_PASS}`)

**Cassandra Examples** (`.kora-agent/kora-examples/kora-java-database-cassandra/`):
- `CassandraCrudSyncRepository` — Basic CRUD with `extends CassandraRepository`, batch operations
- `CassandraUdtRepository` — UDT with nested record pattern (`record Entity { @UDT record Name(...) {} }`)
- `CassandraProfileRepository` — Profile-based configuration with `@CassandraProfile`
- `CassandraAsyncRepository` — Async signatures with `CompletionStage`
- `application.conf` — Environment variable configuration (`${CASSANDRA_USER}`, `${CASSANDRA_PASS}`, `${CASSANDRA_CONTACT_POINTS}`)

---

## Assets

Ready-to-use templates in `assets/` directory:

**JDBC Templates:**
- `jdbc-entity-single-id.java.template` — Entity with single-field ID
- `jdbc-entity-composite-id.java.template` — Entity with composite ID (@Embedded)
- `jdbc-crud-single-id-repository.java.template` — Full CRUD with single ID
- `jdbc-crud-composite-id-repository.java.template` — Full CRUD with composite ID
- `jdbc-crud-abstract-macros-repository.java.template` — Abstract base for inheritance

**Cassandra Templates:**
- `cassandra-entity-single-id.java.template` — Cassandra entity with UUID ID
- `cassandra-entity-composite-id.java.template` — Cassandra entity with composite ID
- `cassandra-crud-single-id-repository.java.template` — CRUD with lightweight transactions (IF NOT EXISTS)
- `cassandra-crud-composite-id-repository.java.template` — CRUD for composite partition/clustering keys
- `cassandra-crud-abstract-repository.java.template` — Abstract base for Cassandra inheritance

See [assets/README.md](assets/README.md) for usage instructions and placeholder documentation.

---

## Why JDBC + Virtual Threads?

Modern virtual threads (Project Loom, Java 21+) provide:
- **Simpler debugging** — Standard stack traces, no callback hell
- **Better tooling** — Works with existing profilers, debuggers
- **Comparable performance** — Virtual threads handle blocking efficiently
- **Easier testing** — No need for StepVerifier or async test utilities

The same applies to Cassandra: prefer the synchronous DataStax driver with virtual threads over reactive wrappers.

---

## Common Pitfalls

- **ID type mismatch** → repository ID type must match entity's `@Id` field exactly (e.g., `UUID` vs `String`).
- **Missing `@Query` named parameters** → use `:param` syntax, not `$1` positional.
- **No RETURNING for generated IDs** → use `RETURNING` clause to get generated ID after insert.
- **Missing `@EntityJdbc`** → entity class not recognized without `@EntityJdbc` annotation.
- **Transaction without `@Transaction`** → annotate methods requiring transactional boundaries.
- **Sync vs reactive** → prefer sync signatures (`Entity`, `@Nullable Entity`); reactive adds complexity without benefit.
