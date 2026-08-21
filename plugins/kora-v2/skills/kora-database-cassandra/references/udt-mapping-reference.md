# UDT Mapping Reference

**Module:** `ru.tinkoff.kora:database-cassandra`  
**Driver:** DataStax Java Driver 4.x

## Contents

- [Overview](#overview)
- [UDT Declaration](#udt-declaration)
- [UDT with Collections](#udt-with-collections)
- [Nested UDTs](#nested-udts)
- [UDT with Custom Mappers](#udt-with-custom-mappers)
- [Kotlin UDT Data Classes](#kotlin-udt-data-classes)
- [UDT Migration Scripts](#udt-migration-scripts)
- [Best Practices](#best-practices)

---

## Overview

Cassandra User-Defined Types (UDTs) allow modeling nested data structures. Kora supports UDTs through the `@UDT` annotation.

**Use cases:**
- Address structures (street, city, zip)
- Name components (first, middle, last)
- Complex nested data (coordinates, settings)
- Collections of structured data

---

## UDT Declaration

### Inline UDT Pattern (Recommended)

```java
@Repository
public interface UserRepository extends CassandraRepository {
    
    @EntityCassandra
    record User(String id, Name name) {
        
        @UDT
        public record Name(String first, String middle, String last) {}
    }
    
    @Query("SELECT * FROM users WHERE id = :id")
    @Nullable
    User findById(String id);
    
    @Query("INSERT INTO users (id, name) VALUES (:user.id, :user.name)")
    void insert(User user);
}
```

**CQL:**
```sql
CREATE TYPE name (
    first TEXT,
    middle TEXT,
    last TEXT
);

CREATE TABLE users (
    id TEXT PRIMARY KEY,
    name FROZEN<name>
);
```

### Separate UDT Class

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
    @Column("email") String email,
    @Column("address") AddressUDT address,
    @Column("addresses") List<AddressUDT> addresses
) {}
```

**CQL:**
```sql
CREATE TYPE address (
    street TEXT,
    city TEXT,
    zipCode TEXT
);

CREATE TABLE users (
    id UUID PRIMARY KEY,
    email TEXT,
    address FROZEN<address>,
    addresses LIST<FROZEN<address>>
);
```

---

## UDT with Collections

### List of UDTs

```java
@UDT
public record TagUDT(
    @Column("name") String name,
    @Column("score") int score
) {}

@Table("articles")
@EntityCassandra
public record Article(
    @Id String id,
    @Column("title") String title,
    @Column("tags") List<TagUDT> tags
) {}
```

**CQL:**
```sql
CREATE TYPE tag (
    name TEXT,
    score INT
);

CREATE TABLE articles (
    id TEXT PRIMARY KEY,
    title TEXT,
    tags LIST<FROZEN<tag>>
);
```

### Set of UDTs

```java
@Table("articles")
@EntityCassandra
public record Article(
    @Id String id,
    @Column("title") String title,
    @Column("unique_tags") Set<TagUDT> uniqueTags
) {}
```

**CQL:**
```sql
CREATE TABLE articles (
    id TEXT PRIMARY KEY,
    title TEXT,
    unique_tags SET<FROZEN<tag>>
);
```

### Map with UDT Values

```java
@Table("products")
@EntityCassandra
public record Product(
    @Id String id,
    @Column("name") String name,
    @Column("prices") Map<String, PriceUDT> prices
) {}

@UDT
public record PriceUDT(
    @Column("amount") BigDecimal amount,
    @Column("currency") String currency
) {}
```

**CQL:**
```sql
CREATE TYPE price (
    amount DECIMAL,
    currency TEXT
);

CREATE TABLE products (
    id TEXT PRIMARY KEY,
    name TEXT,
    prices MAP<TEXT, FROZEN<price>>
);
```

---

## Nested UDTs

```java
@UDT
public record CoordinatesUDT(
    @Column("latitude") double latitude,
    @Column("longitude") double longitude
) {}

@UDT
public record LocationUDT(
    @Column("name") String name,
    @Column("coordinates") CoordinatesUDT coordinates
) {}

@Table("stores")
@EntityCassandra
public record Store(
    @Id String id,
    @Column("name") String name,
    @Column("location") LocationUDT location
) {}
```

**CQL:**
```sql
CREATE TYPE coordinates (
    latitude DOUBLE,
    longitude DOUBLE
);

CREATE TYPE location (
    name TEXT,
    coordinates FROZEN<coordinates>
);

CREATE TABLE stores (
    id TEXT PRIMARY KEY,
    name TEXT,
    location FROZEN<location>
);
```

---

## UDT with Custom Mappers

### Custom UDT Reader

```java
public class AddressUDTReader implements CassandraRowColumnMapper<AddressUDT> {
    @Override
    public AddressUDT apply(GettableByName row, int index) {
        UdtValue udtValue = row.getUdtValue(index);
        if (udtValue == null) {
            return null;
        }
        return new AddressUDT(
            udtValue.getString("street"),
            udtValue.getString("city"),
            udtValue.getString("zipCode")
        );
    }
}

@Table("users")
@EntityCassandra
public record User(
    @Id UUID id,
    @Column("email") String email,
    @Mapping(AddressUDTReader.class) @Column("address") AddressUDT address
) {}
```

### Custom UDT Writer

```java
public class AddressUDTWriter implements CassandraParameterColumnMapper<AddressUDT> {
    @Override
    public void apply(SettableByName<?> stmt, int index, @Nullable AddressUDT value) {
        if (value != null) {
            UdtValue udtValue = stmt.getType(index).newValue();
            udtValue.setString("street", value.street());
            udtValue.setString("city", value.city());
            udtValue.setString("zipCode", value.zipCode());
            stmt.setUdtValue(index, udtValue);
        } else {
            stmt.setToNull(index);
        }
    }
}

@Repository
public interface UserRepository extends CassandraRepository {
    @Query("INSERT INTO users (id, email, address) VALUES (:id, :email, :address)")
    void insert(UUID id, String email, @Mapping(AddressUDTWriter.class) AddressUDT address);
}
```

---

## Kotlin UDT Data Classes

```kotlin
@UDT
data class NameUDT(
    @field:Column("first") val first: String,
    @field:Column("middle") val middle: String?,
    @field:Column("last") val last: String
)

@UDT
data class AddressUDT(
    @field:Column("street") val street: String,
    @field:Column("city") val city: String,
    @field:Column("zipCode") val zipCode: String
)

@Table("users")
@EntityCassandra
data class User(
    @field:Column("id") @field:Id val id: UUID,
    @field:Column("name") val name: NameUDT,
    @field:Column("address") val address: AddressUDT,
    @field:Column("addresses") val addresses: List<AddressUDT>
)
```

---

## UDT Migration Scripts

```sql
-- 001_create_types.cql
CREATE TYPE IF NOT EXISTS name (
    first TEXT,
    middle TEXT,
    last TEXT
);

CREATE TYPE IF NOT EXISTS address (
    street TEXT,
    city TEXT,
    zipCode TEXT
);

-- 002_create_tables.cql
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY,
    name FROZEN<name>,
    address FROZEN<address>,
    addresses LIST<FROZEN<address>>
);
```

---

## Best Practices

1. **Use `@UDT` annotation** — Required for UDT class recognition
2. **Add `@Column` to every field** — Explicit column mapping
3. **Prefer inline UDTs** — Keep UDT close to repository
4. **Use FROZEN for collections** — Required for UDT collections
5. **Keep UDTs immutable** — Use records/data classes
6. **Avoid deeply nested UDTs** — Limit to 2-3 levels max

---

## Common Pitfalls

1. **Missing `@UDT` annotation** — UDT won't be recognized
2. **Missing `FROZEN` in CQL** — Required for UDT collections
3. **Schema mismatch** — Ensure CQL type matches Java UDT
4. **Null handling** — Use `@Nullable` for nullable UDT fields

---

## See Also

- [CQL Repository Reference](cql-repository-reference.md) — Repository patterns, queries
- [Consistency Reference](consistency-reference.md) — Consistency levels, profiles
