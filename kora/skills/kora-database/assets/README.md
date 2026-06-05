# Kora Database Assets

Ready-to-use templates for JDBC and Cassandra database patterns in Kora Framework.

## Templates

### Entity Templates

| Template | Description | Use Case |
|----------|-------------|----------|
| `jdbc-entity-single-id.java.template` | Entity with single-field ID (String/UUID/Long) | Most common pattern |
| `jdbc-entity-composite-id.java.template` | Entity with composite ID (nested record + @Embedded) | Composite primary keys |
| `cassandra-entity-single-id.java.template` | Cassandra entity with single ID (UUID/String/Long) | Cassandra column families |
| `cassandra-entity-composite-id.java.template` | Cassandra entity with composite ID (nested record) | Composite partition/clustering keys |

### Repository Templates

| Template | Description | Use Case |
|----------|-------------|----------|
| `jdbc-crud-single-id-repository.java.template` | Full CRUD with single ID | Standard JDBC repositories |
| `jdbc-crud-composite-id-repository.java.template` | Full CRUD with composite ID | Composite key entities |
| `jdbc-crud-abstract-macros-repository.java.template` | Abstract base for inheritance | Avoid code duplication across many repositories |
| `cassandra-crud-single-id-repository.java.template` | Full CRUD for Cassandra with single ID | Cassandra repositories with lightweight transactions |
| `cassandra-crud-composite-id-repository.java.template` | Full CRUD for Cassandra with composite ID | Composite partition/clustering key repositories |
| `cassandra-crud-abstract-repository.java.template` | Abstract base for Cassandra inheritance | Reusable Cassandra CRUD base |

### Reference Documentation

| File | Description |
|------|-------------|
| [database-jdbc-custom-mappers-reference.md](../references/database-jdbc-custom-mappers-reference.md) | Guide to custom mappers (ResultSet, Row, Column, Parameter), JSONB, arrays, UDTs |
| [database-cassandra-reference.md](../references/database-cassandra-reference.md) | Cassandra module reference (UDTs, async, profiles, LWT) |

## Usage

1. Copy the template to your project
2. Replace placeholders:
   - `${package}` — Your Java package name
   - `${entity_name}` — Entity class name
   - `${repository_name}` — Repository interface name
   - `${table_name}` — Database table name
   - For single-ID templates (JDBC & Cassandra):
     - `${id_type}` — Type of ID field (e.g., `UUID`, `String`, `Long`)
   - For composite ID template only:
     - `${id1_type}` / `${id2_type}` — Type of each ID field (e.g., `UUID`, `String`, `Long`)
     - `${id1_field}` / `${id2_field}` — Name of each ID field (e.g., `userId`, `orderId`)
     - `${id1_default}` / `${id2_default}` — Default value for no-arg constructor (e.g., `UUID.randomUUID()`, `null`)

3. Customize fields and types as needed
4. Create corresponding database migration

**Important:** The ID type in repository methods must match the entity's `@Id` field type exactly. If your entity uses `UUID id`, the repository must use `findById(UUID id)`, not `findById(String id)`.

## Best Practices

### Always Use Synchronous Signatures

**ALWAYS prefer synchronous return types** in repository interfaces:

```java
// Recommended - synchronous with virtual threads
@Nullable
User findById(String id);

List<User> findAll();

// Avoid - unnecessary complexity
CompletionStage<User> findById(String id);
Mono<User> findById(String id);
```

**Why:**
- Virtual threads handle blocking efficiently
- Better debugging with standard stack traces
- Simpler, more readable code
- Comparable or better performance than reactive

Use `CompletionStage` only when you need explicit non-blocking behavior (e.g., calling external APIs from repository methods).

### Return Types
- **Use `@Nullable`** for nullable single results (zero overhead)
- **Avoid `Optional`** — creates garbage on every call
- **Return empty collections** for multi-result queries (never null)

### SQL Macros (JDBC only)
- `%{return#selects}` — Column list for SELECT
- `%{entity#inserts}` — Full INSERT statement
- `%{entity#updates}` — SET clause for UPDATE
- `%{entity#where = @id}` — WHERE clause by ID
- `%{id#where}` — WHERE clause for composite ID

### Cassandra-Specific Notes

**No UPDATE with SET clause:** Cassandra requires explicit column assignments in UPDATE statements:
```java
// Correct for Cassandra
@Query("UPDATE users SET field1 = :field1, field2 = :field2 WHERE id = :id")
void update(User entity);

// Incorrect - JDBC macro syntax
@Query("UPDATE %{entity#table} SET %{entity#updates} WHERE %{entity#where = @id}")
void update(User entity);
```

**Lightweight Transactions (LWT):** Use `IF NOT EXISTS` for conditional inserts:
```java
@Query("INSERT INTO users (id, field1) VALUES (:id, :field1) IF NOT EXISTS")
boolean insertIfNotExists(User entity);
```

**TRUNCATE instead of DELETE ALL:** For Cassandra, use TRUNCATE to clear all data:
```java
@Query("TRUNCATE users")
void deleteAll();
```

### JSONB (PostgreSQL JDBC only)
Add `JdbcJsonbMapperModule` to your application:
```java
@KoraApp
public interface Application extends JdbcDatabaseModule, JdbcJsonbMapperModule {}
```

Then use `@Json` annotation on fields:
```java
@EntityJdbc
public record User(@Id UUID id, @Json Profile profile) {}
```

See [jdbc-custom-mappers-reference.md](jdbc-custom-mappers-reference.md) for details.

## Examples

See working implementations in `.kora-agent/kora-examples/`:

**JDBC Examples** (`kora-java-database-jdbc/`):
- `JdbcCrudMacrosRepository.java` — Basic CRUD with macros
- `JdbcCrudMacrosIdCompositeRepository.java` — Composite ID pattern
- `AbstractJdbcCrudRepository.java` — Abstract base for inheritance
- `JdbcJsonbRepository.java` — JSONB column handling

**Cassandra Examples** (`kora-java-database-cassandra/`):
- `CassandraCrudSyncRepository.java` — Basic sync CRUD with batch operations
- `CassandraUdtRepository.java` — UDT with nested record pattern
- `CassandraProfileRepository.java` — Profile-based configuration
- `CassandraAsyncRepository.java` — Async signatures with CompletionStage
