# Entity Mapping Reference

**Applies to:** Kora 2.x (`io.koraframework:database-jdbc`)

## Contents

- [Core annotations](#core-annotations)
- [Kotlin use-site targets](#kotlin-use-site-targets)
- [Nullability](#nullability)
- [Embedded types](#embedded-types)
- [Naming strategy](#naming-strategy)
- [Supported column types](#supported-column-types)
- [JSONB mapping (PostgreSQL)](#jsonb-mapping-postgresql)
- [Generated identifiers](#generated-identifiers)
- [Common pitfalls](#common-pitfalls)

---

## Core annotations

| Annotation | Package | Target |
|------------|---------|--------|
| `@EntityJdbc` | **`io.koraframework.database.jdbc.annotation`** | `TYPE` |
| `@Table("name")` | `io.koraframework.database.common.annotation` | `TYPE` |
| `@Column("name")` | `io.koraframework.database.common.annotation` | `FIELD`, `PARAMETER`, `RECORD_COMPONENT`, `TYPE_USE` |
| `@Id` | `io.koraframework.database.common.annotation` | `FIELD`, `PARAMETER`, `RECORD_COMPONENT`, `METHOD` |
| `@Embedded("prefix_")` | `io.koraframework.database.common.annotation` | `FIELD`, `PARAMETER`, `RECORD_COMPONENT` |

`@EntityJdbc` is the only one whose package changed in 2.0. It makes the processor emit
`$<Entity>_JdbcRowMapper`, `$<Entity>_JdbcResultSetMapper` and a list variant, so the repository
never has to build a converter by reflection.

```java
@EntityJdbc
@Table("users")
public record User(
        @Id Long id,
        @Column("email_address") String email,
        String firstName,                       // -> first_name
        @Nullable LocalDateTime createdAt) {}   // -> created_at
```

`@Column` is only needed when the column name differs from the entity's naming strategy
(`snake_lower_case` by default). `@Id` is required for `%{…#where = @id}`, for `%{…#updates}` to
exclude the key, and for `@Id`-on-method generated keys.

`@Table` is optional — without it the table name is the class name run through the same naming
strategy (`OrderItem` → `order_item`).

---

## Kotlin use-site targets

Kora reads the **field**, so annotate data-class properties with `@field:`:

```kotlin
@EntityJdbc
@Table("entities")
data class Entity(
    @field:Id val id: String,
    @field:Column("value1") val field1: Int,
    val value2: String,
    val value3: String?
)
```

`@field:Id`, `@field:Column`, `@field:Embedded` are the forms used throughout the migrated
examples. `@Mapping` is the exception: it also targets `PARAMETER`, and the examples apply it
without a use-site target (see [custom-mappers-reference.md](custom-mappers-reference.md)). Tag
annotations such as `@Pg` / `@PgJsonb` behave the same way — the tag is read from the data-class
constructor parameter, so `@Pg val tags: List<String>` needs no target
(see [postgres-mappers-reference.md](postgres-mappers-reference.md#kotlin)).

---

## Nullability

**Java** uses JSpecify `org.jspecify.annotations.Nullable`. The processor accepts any annotation
whose fully-qualified name ends in `.Nullable`, but JSpecify is what the framework and the migrated
examples use, and it is what the rest of Kora 2.0 is marked with.

JSpecify annotations are **type-use**, so position matters on a qualified nested type:

```java
// wrong: error: type annotation @Nullable is not expected here
void set(PreparedStatement stmt, int index, @Nullable Entity.FieldType value);

// right
void set(PreparedStatement stmt, int index, Entity.@Nullable FieldType value);
```

`@Column` shares the `TYPE_USE` target and behaves the same way on qualified types.

**Kotlin** expresses nullability in the type — `String?`. Do not carry Java nullability annotations
into Kotlin sources.

A field with no nullability marker is treated as non-null; a `NULL` in that column surfaces as a
failure while reading the row, not as a silent `null`.

---

## Embedded types

`@Embedded` on a field flattens a nested record/data class into the parent's columns. The optional
value is a prefix prepended to every nested column name.

```java
public record Address(String street, String city, @Column("zip_code") String zip) {}

@EntityJdbc
@Table("users")
public record User(
        @Id Long id,
        String email,
        @Embedded("address_") Address address) {}   // address_street, address_city, address_zip_code
```

### Composite keys

```java
@EntityJdbc
@Table("order_items")
public record OrderItem(
        @Id @Embedded OrderItemId id,
        @Column("quantity") int quantity,
        @Column("price") BigDecimal price) {

    public record OrderItemId(
            @Column("order_id") Long orderId,
            @Column("product_id") Long productId) {}
}
```

The embedded key type does **not** need `@EntityJdbc` — it is expanded into the parent's mapper.

Repository usage:

```java
@Query("SELECT %{return#selects} FROM %{return#table} WHERE %{id#where}")
@Nullable
OrderItem findById(OrderItem.OrderItemId id);
```

`%{id#where}` expands to `order_id = :id.orderId AND product_id = :id.productId`.
`%{entity#where = @id}` does the same from the parent entity, expanding the embedded key into all
of its columns.

`@Embedded` also composes with a nullable embedded value: `@Id @Embedded @Nullable EntityId id`
still expands to every key column.

---

## Naming strategy

Without `@Column`, a field name is converted by the entity's naming strategy — `SnakeCaseNameConverter`
unless `@NamingStrategy` says otherwise. `@NamingStrategy` is
`io.koraframework.common.annotation.NamingStrategy`; converters live in `io.koraframework.common.naming`
and must have an accessible no-arg constructor.

| Converter | Result for `firstName` |
|-----------|------------------------|
| `NoopNameConverter` | `firstName` |
| `SnakeCaseNameConverter` (default) | `first_name` |
| `SnakeCaseUpperNameConverter` | `FIRST_NAME` |
| `PascalCaseNameConverter` | `FirstName` |
| `CamelCaseNameConverter` | `firstName` |

```java
@EntityJdbc
@NamingStrategy(NoopNameConverter.class)
public record Entity(String id, String name) {}
```

The strategy applies to the `@Table` name as well when `@Table` is absent. There is **no**
`jdbc.namingStrategy` config key — naming is annotation-driven only.

---

## Supported column types

Two tiers, both provided out of the box.

**Inlined natively** by the processor (direct `ResultSet` / `PreparedStatement` calls, no mapper
component involved):

`boolean`, `short`, `int`, `long`, `float`, `double` and their boxed forms, `String`,
`BigDecimal`, `byte[]`, `LocalDate`, `LocalDateTime`.

**Served by `JdbcMapperModule`** (`@DefaultComponent` mappers, pulled in by `JdbcDatabaseModule`):
everything above plus `Byte`, `UUID`, `LocalTime`, `OffsetTime`, `OffsetDateTime`.

Anything else — `Instant`, `BigInteger`, `Duration`, enums, `List<T>` arrays, JSONB payloads,
domain value types — needs a `JdbcResultColumnMapper<T>` and/or `JdbcParameterColumnMapper<T>`.
Without one the build fails with `No component found for dependency: JdbcResultColumnMapper<X>`.
See [custom-mappers-reference.md](custom-mappers-reference.md).

**On PostgreSQL, `database-jdbc-postgres` supplies the common ones** — tagged, so they apply only
where the tag is written (see [postgres-mappers-reference.md](postgres-mappers-reference.md)):

| Java type | Tag | PostgreSQL |
|-----------|-----|-----------|
| `List<T>` (parameters also `Set<T>`, `Collection<T>`), `T[]`, primitive arrays | `@Pg` | `BOOLEAN[]`, `SMALLINT[]`, `INTEGER[]`, `BIGINT[]`, `REAL[]`, `DOUBLE PRECISION[]`, `NUMERIC[]`, `VARCHAR[]`, `UUID[]` |
| `Duration`, `Period` | `@Pg` | `INTERVAL` |
| `PgRange<Integer/Long/BigDecimal/LocalDate/LocalDateTime/OffsetDateTime>` | none | `INT4RANGE`, `INT8RANGE`, `NUMRANGE`, `DATERANGE`, `TSRANGE`, `TSTZRANGE` |
| a `@Json` type, `JsonNullable<T>` | `@PgJson` / `@PgJsonb` | `JSON` / `JSONB` |

Typical PostgreSQL column choices:

| Java type | PostgreSQL |
|-----------|-----------|
| `boolean` / `Boolean` | `BOOLEAN` |
| `int` / `Integer` | `INTEGER` |
| `long` / `Long` | `BIGINT` |
| `double` / `Double` | `DOUBLE PRECISION` |
| `BigDecimal` | `NUMERIC(p, s)` |
| `String` | `VARCHAR(n)` / `TEXT` |
| `byte[]` | `BYTEA` |
| `UUID` | `UUID` |
| `LocalDate` | `DATE` |
| `LocalTime` | `TIME` |
| `LocalDateTime` | `TIMESTAMP` |
| `OffsetTime` | `TIME WITH TIME ZONE` |
| `OffsetDateTime` | `TIMESTAMP WITH TIME ZONE` |

---

## JSONB mapping (PostgreSQL)

With `database-jdbc-postgres`, tag the field `@PgJsonb` (`@PgJson` for a `json` column) and annotate
the payload **type** with `@Json`:

```java
@Repository
public interface JsonbRepository extends JdbcRepository {

    @EntityJdbc
    record Entity(UUID id, @Column("value") @PgJsonb JsonbValue value) {
        @Json
        public record JsonbValue(String name, String surname) {}
    }

    @Query("SELECT * FROM entities_jsonb WHERE id = :id")
    @Nullable
    Entity findById(UUID id);

    @Query("INSERT INTO entities_jsonb(id, value) VALUES (:entity.id, :entity.value)")
    void insert(Entity entity);
}

@KoraApp
public interface Application extends
        HoconConfigModule, LogbackModule, JsonModule, PostgresJdbcDatabaseModule {}
```

The parameter is sent as a `jsonb`-typed `PGobject`, so the SQL needs no `::jsonb` cast, and a
`jsonb` operator such as `value @> :filter` works with a `@PgJsonb` parameter. Details, `@PgJson` vs
`@PgJsonb` and `JsonNullable<T>`: [postgres-mappers-reference.md](postgres-mappers-reference.md#json-and-jsonb-pgjson--pgjsonb).

### Without `database-jdbc-postgres`

The migrated examples predate the module and declare a small generic `@Module` tagged `@Json`
instead, so the processor picks it for `@Json`-annotated fields:

```java
@Module
public interface JdbcJsonbMapperModule {

    @Json
    default <T> JdbcParameterColumnMapper<T> jdbcJsonParameterColumnMapper(JsonWriter<T> writer) {
        return (stmt, index, value) -> {
            if (value != null) {
                var jsonb = new PGobject();
                jsonb.setType("jsonb");
                jsonb.setValue(writer.toString(value));
                stmt.setObject(index, jsonb);
            } else {
                stmt.setNull(index, Types.NULL);
            }
        };
    }

    @Json
    default <T> JdbcResultColumnMapper<T> jdbcJsonResultColumnMapper(JsonReader<T> reader) {
        return (row, index) -> {
            var value = row.getString(index);
            return value == null ? null : reader.read(value);
        };
    }
}
```

`JsonWriter.toString` / `JsonReader.read` no longer declare checked exceptions in 2.0 — the
`*Unchecked` variants are gone.

Entity and application wiring:

```java
@Repository
public interface JsonbRepository extends JdbcRepository {

    @EntityJdbc
    record Entity(UUID id, @Column("value") @Json JsonbValue value) {
        @Json
        public record JsonbValue(String name, String surname) {}
    }

    @Query("SELECT * FROM entities_jsonb WHERE id = :id")
    @Nullable
    Entity findById(UUID id);

    @Query("INSERT INTO entities_jsonb(id, value) VALUES (:entity.id, :entity.value::jsonb)")
    void insert(Entity entity);
}

@KoraApp
public interface Application extends
        HoconConfigModule, LogbackModule, JsonModule, JdbcDatabaseModule, JdbcJsonbMapperModule {}
```

`@Json` and `JsonReader`/`JsonWriter` come from `io.koraframework.json.common(.annotation)`, artifact
`io.koraframework:json-common`, module `io.koraframework.json.common.JsonModule`. The examples keep
a `::jsonb` cast in the INSERT. Prefer `@PgJsonb` for new code — same result, no module to maintain.

---

## Generated identifiers

### Sequence / identity

```sql
CREATE TABLE users (
    id    BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    email VARCHAR(255) NOT NULL
);
```

```java
@EntityJdbc
@Table("users")
public record User(@Id Long id, String email) {
    public User(String email) { this(null, email); }   // convenience ctor for inserts
}

@Query("INSERT INTO %{entity#inserts -= @id}")
@Id
Long insert(User user);
```

### Client-generated UUID

```java
@EntityJdbc
@Table("users")
public record User(@Id UUID id, String email) {
    public User(String email) { this(UUID.randomUUID(), email); }
}

@Query("INSERT INTO %{entity#inserts}")
void insert(User user);
```

---

## Common pitfalls

| Pitfall | Consequence | Fix |
|---------|-------------|-----|
| `@EntityJdbc` imported from `io.koraframework.database.jdbc` | `cannot find symbol` | it lives in `…database.jdbc.annotation` |
| `@Nullable` placed before a qualified nested type in Java | `type annotation @Nullable is not expected here` | `Outer.@Nullable Inner` |
| Java nullability annotations copied into Kotlin | invalid annotation target under Kotlin 2.4 | use `T?` |
| Kotlin property annotated without `@field:` | the annotation lands on the constructor parameter and the column mapping is ignored | `@field:Column(...)`, `@field:Id`, `@field:Embedded` |
| `Instant` or `BigInteger` field with no mapper | `No component found for dependency: JdbcResultColumnMapper<...>` | write a column mapper, or store `OffsetDateTime`/`BigDecimal` |
| Missing `@Id` | `%{…#where = @id}` fails; `%{…#updates}` tries to write the key | annotate the key field |
| Key type mismatch between repository parameter and entity | wrong-type bind at runtime | keep both on the same type |
| Composite key modelled as separate fields | `%{id#where}` has nothing to expand | wrap it in a nested record and use `@Id @Embedded` |

---

## See also

- [repository-pattern-reference.md](repository-pattern-reference.md) — `@Repository`, `@Query`, macros
- [custom-mappers-reference.md](custom-mappers-reference.md) — the four mapper contracts
- [custom-mappers-advanced-reference.md](custom-mappers-advanced-reference.md) — when a mapper is constructed vs injected
- [postgres-mappers-reference.md](postgres-mappers-reference.md) — PostgreSQL arrays, `interval`, ranges, `json`/`jsonb`
