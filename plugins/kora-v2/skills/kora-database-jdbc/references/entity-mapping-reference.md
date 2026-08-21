# Entity Mapping Reference

**Source:** `.kora-agent/kora-docs/mkdocs/docs/en/documentation/database-common.md`, `database-jdbc.md`
**Examples:** `.kora-agent/kora-examples/examples/java/kora-java-database-jdbc/`
**Module:** `ru.tinkoff.kora:database-jdbc`

## Contents

- [Core annotations](#core-annotations)
- [Embedded types](#embedded-types)
- [Naming strategy](#naming-strategy)
- [Type mapping](#type-mapping)
- [JSONB mapping (PostgreSQL)](#jsonb-mapping-postgresql)
- [Nullable fields](#nullable-fields)
- [Generated identifiers](#generated-identifiers)
- [Common pitfalls](#common-pitfalls)

---

## Core Annotations

### @Table

Maps a Java record to a database table.

```java
@Table("users")
public record User(Long id, String email) {}
```

### @Column

Explicit column mapping for each field.

```java
@Table("users")
public record User(
    @Column("user_id") Long id,
    @Column("email_address") String email,
    @Column("created_at") LocalDateTime createdAt
) {}
```

**Best Practice:** Always use `@Column` for all fields to avoid ambiguity.

### @Id

Marks the primary key field.

```java
@Table("users")
public record User(
    @Id
    @Column("id")
    Long id,
    
    @Column("email")
    String email
) {}
```

**Important:** The ID type must match the database column type exactly (`Long`, `UUID`, `String`).

### @EntityJdbc

Optimizes entity mapping for JDBC module. Always use for JDBC entities.

```java
@EntityJdbc
@Table("users")
public record User(
    @Id Long id,
    String email,
    LocalDateTime createdAt
) {}
```

---

## Embedded Types

Use `@Embedded` at the **field use-site** to flatten a value object into the parent table's columns. An optional prefix (`@Embedded("address_")`) is prepended to each nested column name.

```java
public record Address(
    @Column("street") String street,
    @Column("city") String city,
    @Column("zip_code") String zipCode
) {}

@Table("users")
@EntityJdbc
public record User(
    @Id Long id,
    String email,
    @Embedded("address_") Address address  // -> address_street, address_city, address_zip_code
) {}
```

### Composite Keys with @Embedded

```java
@EntityJdbc
@Table("order_items")
public record OrderItem(
    @Id @Embedded OrderItemId id,
    @Column("quantity") int quantity,
    @Column("price") BigDecimal price
) {
    @EntityJdbc
    public record OrderItemId(
        @Column("order_id") Long orderId,
        @Column("product_id") Long productId
    ) {}
}
```

Repository usage:

```java
@Repository
public interface OrderItemRepository extends JdbcRepository {
    @Query("SELECT %{return#selects} FROM %{return#table} WHERE %{id#where}")
    @Nullable
    OrderItem findById(OrderItem.OrderItemId id);
}
```

`%{id#where}` expands to `WHERE order_id = :id.orderId AND product_id = :id.productId`; you may also write the columns out explicitly.

---

## Naming strategy

Without `@Column`, field names convert to `snake_lower_case` by default. To change the strategy for a whole entity, apply `@NamingStrategy` with a `NameConverter` (must have a no-arg constructor). Built-in converters:

| Converter | Result |
|-----------|--------|
| `NoopNameConverter` | field name as-is |
| `SnakeCaseNameConverter` | `snake_lower_case` (default) |
| `SnakeCaseUpperNameConverter` | `SNAKE_UPPER_CASE` |
| `PascalCaseNameConverter` | `PascalCase` |
| `CamelCaseNameConverter` | `camelCase` |

```java
@NamingStrategy(NoopNameConverter.class)
public record Entity(String id, String name) {}
```

`@NamingStrategy` and the converters come from `ru.tinkoff.kora.common.naming`. There is no `db.namingStrategy` config key — naming is annotation-driven only.

---

## Type Mapping

### Primitive Types

| Java Type | SQL Type | Notes |
|-----------|----------|-------|
| `boolean` | BOOLEAN | |
| `short` | SMALLINT | |
| `int` | INTEGER | |
| `long` | BIGINT | |
| `float` | REAL | |
| `double` | DOUBLE PRECISION | |

### Wrapper Types

| Java Type | SQL Type | Notes |
|-----------|----------|-------|
| `Boolean` | BOOLEAN | Nullable |
| `Short` | SMALLINT | Nullable |
| `Integer` | INTEGER | Nullable |
| `Long` | BIGINT | Nullable |
| `Float` | REAL | Nullable |
| `Double` | DOUBLE PRECISION | Nullable |

### String & Binary

| Java Type | SQL Type | Notes |
|-----------|----------|-------|
| `String` | VARCHAR(n) | |
| `String` | TEXT | PostgreSQL |
| `byte[]` | BYTEA | PostgreSQL |
| `byte[]` | BLOB | MySQL, Oracle |

### Date & Time

| Java Type | SQL Type | Notes |
|-----------|----------|-------|
| `LocalDate` | DATE | |
| `LocalTime` | TIME | |
| `LocalDateTime` | TIMESTAMP | |
| `OffsetTime` | TIME WITH TIME ZONE | |
| `OffsetDateTime` | TIMESTAMP WITH TIME ZONE | |
| `Instant` | TIMESTAMP | Converted to UTC |

### Special Types

| Java Type | SQL Type | Notes |
|-----------|----------|-------|
| `UUID` | UUID | PostgreSQL |
| `UUID` | CHAR(36) | MySQL |
| `BigDecimal` | DECIMAL(p, s) | |
| `BigInteger` | NUMERIC | |

---

## JSONB Mapping (PostgreSQL)

Use `@Json` annotation with `JdbcJsonbMapperModule`:

```java
// Application module
@KoraApp
public interface Application extends JdbcDatabaseModule, JdbcJsonbMapperModule {}

// Entity with JSONB
@EntityJdbc
@Table("users")
public record User(
    @Id UUID id,
    String email,
    @Json Profile profile  // Serialized to JSONB
) {
    @Json
    public record Profile(String firstName, String lastName) {}
}
```

`@Json` supports:
- Nested records
- Collections (`List`, `Map`)
- Other `@Json` types

---

## Nullable Fields

Use `@Nullable` for optional fields:

```java
@EntityJdbc
@Table("tasks")
public record Task(
    @Id Long id,
    @Column("title") String title,
    @Column("user_assignee_id") @Nullable Long userAssigneeId  // Optional FK
) {}
```

**Important:** Any `@Nullable` is accepted (`jakarta.annotation.Nullable`, `javax.annotation.Nullable`, `org.jetbrains.annotations.Nullable`). All fields are NotNull unless marked nullable. In Kotlin use `String?` syntax instead.

---

## Generated Identifiers

### Sequence-based (PostgreSQL IDENTITY)

```sql
CREATE TABLE users (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    email VARCHAR(255) NOT NULL
);
```

```java
@EntityJdbc
@Table("users")
public record User(@Id Long id, String email) {
    public User(String email) { this(null, email); }  // Constructor for insert
}

@Repository
public interface UserRepository extends JdbcRepository {
    @Query("INSERT INTO %{entity#inserts-= @id} RETURNING id")
    @Id
    Long insert(User user);
}
```

### UUID-based (Client-Generated)

```sql
CREATE TABLE users (
    id UUID PRIMARY KEY,
    email VARCHAR(255) NOT NULL
);
```

```java
@EntityJdbc
@Table("users")
public record User(@Id UUID id, String email) {
    public User(String email) { this(UUID.randomUUID(), email); }
}

@Repository
public interface UserRepository extends JdbcRepository {
    @Query("INSERT INTO %{entity#inserts}")
    void insert(User user);
}
```

---

## Common Pitfalls

| Pitfall | Problem | Solution |
|---------|---------|----------|
| **Missing `@EntityJdbc`** | Suboptimal result converters | Always add `@EntityJdbc` to JDBC entities |
| **Missing `@Column`** | Field not mapped or wrong name | Use `@Column("db_column_name")` for all fields |
| **Missing `@Id`** | Generated ID retrieval fails | Mark primary key with `@Id` |
| **ID type mismatch** | Repository ID type doesn't match entity | Ensure exact type match: `Long` vs `UUID` |
| **Wrong nullable handling** | `null` causes NPE | Use `@Nullable` annotation |
| **Missing `@Embedded`** | Composite key not flattened | Use `@Embedded` for value objects |

---

## See Also

- [Repository Pattern Reference](repository-pattern-reference.md) — @Repository, @Query, SQL macros
- [Custom Mappers Reference](custom-mappers-reference.md) — Custom type mapping
