# Advanced JDBC Mapper Patterns

**Kora Version:** 1.2.x

This reference covers advanced patterns for JDBC column mappers in Kora, including auto-discovery, enum handling, and generic factory patterns.

---

## Column Mapper Auto-Discovery

### @Column and @Mapping Are NOT Always Required

#### Column Naming

By default, Kora maps record field names to `snake_lower_case` column names:

| Java/Kotlin Field | Default Column Name |
|-------------------|---------------------|
| `userId` | `user_id` |
| `firstName` | `first_name` |
| `simple` | `simple` |
| `HTTPClient` | `h_t_t_p_client` |

Use `@Column` **only** when:
- Column name differs from snake_case convention
- Using JOIN aliases
- Working with legacy schemas

```java
// No @Column needed — defaults to snake_case
@EntityJdbc
public record User(
    @Id Long id,           // → id
    String firstName,      // → first_name
    String email           // → email
) {}

// @Column needed for non-standard names
@EntityJdbc
public record Product(
    @Id Long id,
    @Column("SKU") String sku,           // Non-standard case
    @Column("price_cents") int priceCents // Explicit name
) {}
```

#### Custom Type Mappers Auto-Discovery

If you register a `@Component` implementing `JdbcResultColumnMapper<T>` or `JdbcParameterColumnMapper<T>`, Kora **auto-discovers it by type** — no `@Mapping` annotation needed on repository methods.

```java
// Custom enum stored as VARCHAR
@Component
public final class StatusResultMapper implements JdbcResultColumnMapper<Status> {
    @Override
    @Nullable
    public Status apply(ResultSet rs, int index, int columnCount) throws SQLException {
        String value = rs.getString(index);
        return value != null ? Status.valueOf(value) : null;
    }
}

@Component
public final class StatusParameterMapper implements JdbcParameterColumnMapper<Status> {
    @Override
    public void apply(PreparedStatement statement, int index, @Nullable Status value) throws SQLException {
        statement.setString(index, value != null ? value.name() : null);
    }
}

// Repository — NO @Mapping needed! Mapper auto-discovered by type
@Repository
public interface OrderRepository extends JdbcRepository {
    @Query("SELECT %{return#selects} FROM orders WHERE id = :id")
    @Nullable
    Order findById(Long id);  // Order has Status field, mapper picked up automatically
}
```

Use `@Mapping(XxxMapper.class)` **only** when:
- Multiple mappers exist for the same type (ambiguity)
- Mapper is not a `@Component` (e.g., external library class)

---

## Generic Enum Mapper Pattern

For services with many enums, use a generic factory pattern instead of one mapper per enum.

### Pattern: TypeRef + Descriptor

```java
@Module
public interface EnumMappersModule {
    
    // 1. Descriptor factory — Kora reifies the enum type via TypeRef
    @Default
    @Component
    default <E extends Enum<E>> EnumColumnDescriptor<E> enumColumnDescriptor(TypeRef<E> typeRef) {
        Class<E> enumClass = (Class<E>) typeRef.getRawType();
        Map<String, E> byName = Arrays.stream(enumClass.getEnumConstants())
            .collect(Collectors.toMap(Enum::name, Function.identity()));
        return new EnumColumnDescriptor<>(enumClass, byName);
    }
    
    // 2. Result mapper — reads via descriptor's byName map
    @Default
    @Component
    default <E extends Enum<E>> JdbcResultColumnMapper<E> enumResultMapper(EnumColumnDescriptor<E> descriptor) {
        return (rs, index, columnCount) -> {
            String value = rs.getString(index);
            E result = descriptor.byName().get(value);
            if (result == null && value != null) {
                throw new IllegalStateException("Unknown enum value: " + value);
            }
            return result;
        };
    }
    
    // 3. Parameter mapper — writes enum.name()
    @Default
    @Component
    default <E extends Enum<E>> JdbcParameterColumnMapper<E> enumParameterMapper(EnumColumnDescriptor<E> descriptor) {
        return (stmt, index, value) -> stmt.setString(index, value != null ? value.name() : null);
    }
}

// Descriptor holds reified type info
public record EnumColumnDescriptor<E extends Enum<E>>(Class<E> enumClass, Map<String, E> byName) {}
```

### How It Works

1. **TypeRef reification:** Kora synthesizes `TypeRef.of(Class)` from the reified generic type
2. **Descriptor anchors reification:** Both mappers receive the same `EnumColumnDescriptor<E>` — this "anchors" the type parameter `E`
3. **Bound ensures specificity:** `E extends Enum<E>` ensures factories only match domain enums, not OpenAPI-generated enums

### Usage

```java
// Domain enum
public enum OrderStatus { PENDING, PAID, SHIPPED, CANCELLED }

// Entity uses enum
@EntityJdbc
public record Order(
    @Id Long id,
    OrderStatus status,  // Mapped automatically via generic pattern
    Instant createdAt
) {}

// Repository — no explicit mapper wiring
@Repository
public interface OrderRepository extends JdbcRepository {
    @Query("SELECT %{return#selects} FROM orders WHERE id = :id")
    @Nullable
    Order findById(Long id);
}
```

### Verification

Inspect generated `$ApplicationImpl`:

```java
// Generated graph should contain:
this.enumResultMapper<OrderStatus>(this.get(descriptorNode));
this.enumParameterColumnMapper<OrderStatus>(this.get(descriptorNode));
```

### Overriding for Custom Storage

For enums with non-standard storage (e.g., numeric codes, external API values), define a more specific monomorphic mapper:

```java
@Component
public final class PaymentStatusMapper implements JdbcResultColumnMapper<PaymentStatus> {
    @Override
    @Nullable
    public PaymentStatus apply(ResultSet rs, int index, int columnCount) throws SQLException {
        int code = rs.getInt(index);
        return PaymentStatus.fromCode(code);  // Custom mapping logic
    }
}
```

The monomorphic mapper takes precedence over the generic chain.

---

## ⚠️ Generic Helpers Must NOT Be Inside @Module

**Problem:** Kora treats generic methods in a `@Module` as "generic factories" (container.md §Generic Factory) and may use them for **ANY** matching type in the graph — this leads to implicit, hard-to-debug behavior.

**Wrong:**
```java
@Module
public interface JdbcMappersModule {
    // BAD: generic method inside module becomes a generic factory
    private <E extends Enum<E>> JdbcResultColumnMapper<E> enumMapper(Class<E> enumClass) {
        return (rs, index, columnCount) -> {
            String value = rs.getString(index);
            return value != null ? Enum.valueOf(enumClass, value) : null;
        };
    }
    
    // This becomes a generic factory usable for ANY Enum, not just intended ones
}
```

**Correct:** Move generic helpers to top-level `private static` methods in the same file — they are not module members and do not enter the graph:

```java
@Module
public interface JdbcMappersModule {
    // GOOD: monomorphic per-type factories
    @Default
    @Component
    default JdbcResultColumnMapper<Status> statusMapper() {
        return enumMapper(Status.class);
    }
    
    @Default
    @Component
    default JdbcResultColumnMapper<Role> roleMapper() {
        return enumMapper(Role.class);
    }
}

// Top-level helper — NOT a module member, does not enter the graph
private static <E extends Enum<E>> JdbcResultColumnMapper<E> enumMapper(Class<E> enumClass) {
    return (rs, index, columnCount) -> {
        String value = rs.getString(index);
        return value != null ? Enum.valueOf(enumClass, value) : null;
    };
}
```

**Verification:** Inspect generated `$ApplicationImpl` — it should contain `object : JdbcMappersModule {}` with monomorphic methods only, no generic factories.

---

## @Batch Limitations

### @Batch Does NOT Return Rows

`@Batch` is for bulk INSERT/UPDATE/DELETE operations. It returns `UpdateCount[]` or `void`, **not** the inserted rows.

```java
// ✅ Works — returns update counts
@Query("INSERT INTO users(name, email) VALUES (:name, :email)")
@Batch
UpdateCount[] insertBatch(List<String> names, List<String> emails);

// ❌ Does NOT work — @Batch can't return rows
@Query("INSERT INTO users(name, email) VALUES (:name, :email) RETURNING id")
@Batch
List<Long> insertBatchReturning(List<String> names, List<String> emails);
```

### Multi-Row INSERT…RETURNING Pattern

For multi-row inserts with returned IDs, use a `default` method with `inTx()`:

```java
@Repository
public interface UserRepository extends JdbcRepository {
    
    // Single-row insert with RETURNING
    @Query("INSERT INTO users(name, email) VALUES (:name, :email) RETURNING id")
    @Id
    Long insertReturning(String name, String email);
    
    // Multi-row insert with RETURNING — manual pattern
    default List<Long> insertBatchReturning(List<User> users) {
        return getJdbcConnectionFactory().inTx(() -> {
            List<Long> ids = new ArrayList<>();
            for (User user : users) {
                Long id = insertReturning(user.name(), user.email());
                ids.add(id);
            }
            return ids;
        });
    }
}
```

All `@Query` methods called inside the `inTx()` lambda join the same transaction.

---

## See Also

- [Repository Pattern Reference](references/repository-pattern-reference.md) — `@Repository`, `@Query`, macros
- [Entity Mapping Reference](references/entity-mapping-reference.md) — `@Table`, `@Column`, `@Id`, type mapping
- [Custom Mappers Reference](references/custom-mappers-reference.md) — Basic mapper patterns
- [Transactions Reference](references/transactions-reference.md) — `inTx()`, transaction boundaries
