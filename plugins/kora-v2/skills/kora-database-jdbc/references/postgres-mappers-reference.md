# PostgreSQL Mappers Reference

**Applies to:** Kora 2.x (`io.koraframework:database-jdbc-postgres`)

## Contents

- [Module and dependency](#module-and-dependency)
- [Tags: mappers are opt-in](#tags-mappers-are-opt-in)
- [Type matrix](#type-matrix)
- [Collections and arrays (`@Pg`)](#collections-and-arrays-pg)
- [`= ANY(:ids)` instead of `IN (...)`](#-anyids-instead-of-in-)
- [Intervals (`@Pg Duration` / `@Pg Period`)](#intervals-pg-duration--pg-period)
- [Range types (`PgRange<T>`)](#range-types-pgranget)
- [JSON and JSONB (`@PgJson` / `@PgJsonb`)](#json-and-jsonb-pgjson--pgjsonb)
- [`JsonNullable<T>` columns](#jsonnullablet-columns)
- [Kotlin](#kotlin)
- [Taking only part of the module](#taking-only-part-of-the-module)
- [Common pitfalls](#common-pitfalls)

---

## Module and dependency

```groovy
dependencies {
    koraBom platform("io.koraframework:kora-bom:2.0.0.RC2")
    annotationProcessor "io.koraframework:annotation-processors"

    implementation "io.koraframework:database-jdbc-postgres"   // brings database-jdbc, json-common and the PostgreSQL driver
}
```

Kotlin: `implementation("io.koraframework:database-jdbc-postgres")` with
`ksp("io.koraframework:symbol-processors")`.

`database-jdbc-postgres` declares `database-jdbc`, `json-common` and `org.postgresql:postgresql`
(`42.7.13`) as `api` dependencies, so no separate driver line is needed.

```java
@KoraApp
public interface Application extends
        HoconConfigModule,
        LogbackModule,
        JsonModule,                    // only needed for @PgJson / @PgJsonb payloads
        PostgresJdbcDatabaseModule {}
```

`io.koraframework.database.jdbc.postgres.PostgresJdbcDatabaseModule` **extends
`JdbcDatabaseModule`** — it replaces it on the `@KoraApp` interface rather than sitting next to it.
Everything else (`jdbc` config section, repositories, `executor().inTx(...)`) is unchanged.

| Package | Contents |
|---------|----------|
| `io.koraframework.database.jdbc.postgres` | `PostgresJdbcDatabaseModule`, `PgRange<T>` |
| `io.koraframework.database.jdbc.postgres.annotation` | `@Pg`, `@PgJson`, `@PgJsonb` |
| `io.koraframework.database.jdbc.postgres.mapper` | the five `Pg*JdbcMappersModule` interfaces |
| `io.koraframework.database.jdbc.postgres.mapper.parameter` / `.result` | the mapper classes, public for custom element conversions |

---

## Tags: mappers are opt-in

Every JDK-type mapper in the module is a `@DefaultComponent` **tagged `@Pg`**, and the JSON mappers
are tagged `@PgJson` / `@PgJsonb`. A tagged mapper is only used where the same tag is written on the
entity field or the repository method parameter:

```java
@EntityJdbc
@Table("users")
public record User(@Id long id, @Pg List<String> roles, @Pg Duration ttl) {}

@Query("SELECT %{return#selects} FROM %{return#table} WHERE id = ANY(:ids)")
List<User> findByIds(@Pg List<Long> ids);
```

`@Pg`, `@PgJson` and `@PgJsonb` are meta-annotated with `@Tag` and target `FIELD`, `PARAMETER`,
`METHOD` and `TYPE_USE`. Without the tag, a `List<Long>` field is an unsupported type and the build
fails with `No component found for dependency: JdbcResultColumnMapper<List<Long>>` — the tag is what
routes it to the PostgreSQL mapper, and it keeps these mappers from capturing columns of the same
Java type in code that did not ask for them.

`PgRange<T>` is the exception: its mappers are **untagged**, because the type itself is
PostgreSQL-specific.

---

## Type matrix

| Java type (on a field / parameter) | Tag | PostgreSQL type | Direction |
|---|---|---|---|
| `List<T>`, `Set<T>`, `Collection<T>` | `@Pg` | `T[]` (array) | parameter |
| `List<T>` | `@Pg` | `T[]` (array) | result |
| `T[]` for boxed `Boolean`, `Short`, `Integer`, `Long`, `Float`, `Double`, `BigDecimal`, `String`, `UUID` | `@Pg` | array | both |
| `boolean[]`, `short[]`, `int[]`, `long[]`, `float[]`, `double[]` | `@Pg` | array | both |
| `Duration` | `@Pg` | `interval` | both |
| `Period` | `@Pg` | `interval` | both |
| `PgRange<Integer>` | — | `int4range` | both |
| `PgRange<Long>` | — | `int8range` | both |
| `PgRange<BigDecimal>` | — | `numrange` | both |
| `PgRange<LocalDate>` | — | `daterange` | both |
| `PgRange<LocalDateTime>` | — | `tsrange` | both |
| `PgRange<OffsetDateTime>` | — | `tstzrange` | both |
| any `T` with a `JsonReader<T>` / `JsonWriter<T>` | `@PgJson` | `json` | both |
| any `T` with a `JsonReader<T>` / `JsonWriter<T>` | `@PgJsonb` | `jsonb` | both |
| `JsonNullable<T>` | `@PgJson` / `@PgJsonb` | `json` / `jsonb` | both |

Collection and array **element** types and the PostgreSQL element type each is written as:

| Element | Array element type |
|---|---|
| `Boolean` / `boolean` | `bool` |
| `Short` / `short` | `int2` |
| `Integer` / `int` | `int4` |
| `Long` / `long` | `int8` |
| `Float` / `float` | `float4` |
| `Double` / `double` | `float8` |
| `BigDecimal` | `numeric` |
| `String` | `varchar` |
| `UUID` | `uuid` |

Nothing else is covered — no `List<LocalDate>`, `List<OffsetDateTime>`, enum arrays or
`byte[][]`. For those write a `JdbcParameterColumnMapper` / `JdbcResultColumnMapper`
([custom-mappers-reference.md](custom-mappers-reference.md)); the public
`PgCollectionParameterColumnMapper(elementTypeName, elementWriter)` and
`PgCollectionResultColumnMapper(elementReader)` classes are reusable building blocks for that.

---

## Collections and arrays (`@Pg`)

- **Parameters accept `List`, `Set` or `Collection`**, so a caller does not have to copy a `Set`
  into a `List` just to make the call. **Results are always `List<T>`** — there is no `Set<T>`
  result mapper; express uniqueness in SQL with `DISTINCT`.
- `null` collection ↔ SQL `NULL`. An empty collection round-trips as an empty array (`'{}'`) and
  reads back as an empty `List`, not `null`.
- `NULL` **elements** round-trip in `List<T>` and boxed `T[]` (`["a", null, "b"]`).
- **Primitive arrays cannot hold `NULL`.** Reading an array with a `NULL` element into `long[]`
  fails with `SQLException: PostgreSQL array contains NULL at index <i>, which can't be represented
  in a primitive array`. Use `List<Long>` / `Long[]` for a nullable-element column.

```java
@EntityJdbc
@Table("articles")
public record Article(
        @Id UUID id,
        String title,
        @Pg List<String> tags,          // varchar[] / text[]
        @Pg long[] relatedIds,          // bigint[] with no NULL elements
        @Pg @Nullable List<UUID> authors) {}
```

---

## `= ANY(:ids)` instead of `IN (...)`

A JDBC placeholder binds one value, so `WHERE id IN (:ids)` cannot take a list. Bind the whole
collection as one array parameter and compare with `= ANY(...)`:

```java
@Query("SELECT %{return#selects} FROM %{return#table} WHERE id = ANY(:ids)")
List<Article> findByIds(@Pg List<UUID> ids);

@Query("SELECT %{return#selects} FROM %{return#table} WHERE tags && :tags")
List<Article> findByAnyTag(@Pg Set<String> tags);

@Query("DELETE FROM articles WHERE id = ANY(:ids)")
UpdateCount deleteByIds(@Pg Collection<UUID> ids);
```

One prepared statement regardless of list size, so the statement cache is not fragmented by
`IN (?, ?, …)` variants. An empty collection matches nothing (`= ANY('{}')` is false). A `null`
collection binds SQL `NULL` and `= ANY(NULL)` matches nothing either.

---

## Intervals (`@Pg Duration` / `@Pg Period`)

Both map to `interval`, written as a `PGInterval`:

| Type | Writes | Reads | Rejects on read |
|---|---|---|---|
| `Duration` | days, hours, minutes, seconds with sub-second precision (no years/months) | days + time part | an interval with **years or months** → `SQLException: PostgreSQL interval with years or months can't be converted to Duration, use Period instead` |
| `Period` | years, months, days (no time part) | years, months, days | an interval with a **time part** → `SQLException: PostgreSQL interval with a time part can't be converted to Period, use Duration instead` |

Months have no fixed length, so the mapper refuses to guess instead of silently losing data. Pick
the Java type by what the column holds: calendar spans (`'1 month'`) → `Period`, elapsed time
(`'90 minutes'`) → `Duration`. Negative and sub-second durations round-trip.

```java
@EntityJdbc
@Table("subscriptions")
public record Subscription(@Id long id, @Pg Period billingCycle, @Pg Duration gracePeriod) {}
```

---

## Range types (`PgRange<T>`)

`io.koraframework.database.jdbc.postgres.PgRange<T>` is a record
`(lower, upper, lowerInclusive, upperInclusive, isEmpty)`. A `null` bound is unbounded (infinite)
on that side.

```java
PgRange.closed(1, 10)          // [1,10]
PgRange.closedOpen(1, 10)      // [1,10)
PgRange.openClosed(1, 10)      // (1,10]
PgRange.open(1, 10)            // (1,10)
PgRange.closedOpen(start, null) // [start,)  — unbounded above
PgRange.empty()                // 'empty'
new PgRange<>(lower, upper, lowerInclusive, upperInclusive)
```

No tag is needed:

```java
@EntityJdbc
@Table("bookings")
public record Booking(@Id long id, PgRange<OffsetDateTime> during) {}

@Query("SELECT %{return#selects} FROM %{return#table} WHERE during && :window")
List<Booking> findOverlapping(PgRange<OffsetDateTime> window);

@Query("SELECT %{return#selects} FROM %{return#table} WHERE during @> :at")
List<Booking> findAt(OffsetDateTime at);
```

**A value read back may differ from the one written.** PostgreSQL canonicalises discrete ranges
(`int4range`, `int8range`, `daterange`) to `[)` — `PgRange.closed(1, 10)` reads back as
`[1,11)` — and degenerate ranges to `empty`. Compare ranges in SQL, or normalise before asserting
equality in tests.

`tsrange`/`tstzrange` bounds use PostgreSQL's text form (`2021-01-01 10:00:00+03`), which the
mappers format and parse themselves; `tstzrange` bounds read back with the **session time zone's**
offset, so compare `toInstant()`, not the `OffsetDateTime` itself.

---

## JSON and JSONB (`@PgJson` / `@PgJsonb`)

Tag the field or parameter with the column type. The generic mappers need a `JsonWriter<T>` and a
`JsonReader<T>` for the payload type — annotate the payload with `@Json`
(`io.koraframework.json.common.annotation.Json`) and plug `JsonModule` into the graph.

```java
@Json
public record Preferences(String theme, List<String> channels) {}

@EntityJdbc
@Table("profiles")
public record Profile(@Id UUID id, @PgJsonb Preferences preferences, @PgJson @Nullable Preferences draft) {}

@Repository
public interface ProfileRepository extends JdbcRepository {

    @Query("INSERT INTO %{entity#inserts}")
    UpdateCount insert(Profile entity);

    @Query("SELECT %{return#selects} FROM %{return#table} WHERE preferences @> :filter")
    List<Profile> findByPreferences(@PgJsonb Preferences filter);
}
```

- The parameter is sent as a `PGobject` of type `json` / `jsonb`, so **no `::jsonb` cast** is
  needed in the SQL.
- `@PgJson` vs `@PgJsonb` only changes the **type of the sent parameter**. It matters for queries:
  `jsonb` operators (`@>`, `?`, `jsonb_path_query`) require a `jsonb` operand, so a filter
  parameter compared with a `jsonb` column must be `@PgJsonb`. Reading is identical.
- Put **only** the PostgreSQL tag on the field. `@Json` is itself a tag, and the processor takes
  the first tag annotation it finds on a field — `@Json @PgJsonb Preferences` asks for a
  `@Json`-tagged mapper, not the PostgreSQL one. `@Json` goes on the payload **type**.
- `null` ↔ SQL `NULL`.

---

## `JsonNullable<T>` columns

`io.koraframework.json.common.JsonNullable<T>` distinguishes "absent" from "JSON `null`". With
`@PgJson` / `@PgJsonb` it maps to three column states:

| `JsonNullable<T>` | Written as | Read from |
|---|---|---|
| `JsonNullable.undefined()` | SQL `NULL` | SQL `NULL` |
| `JsonNullable.nullValue()` | JSON literal `null` | JSON literal `null` |
| `JsonNullable.of(value)` | the serialised value | any other JSON value |

A `null` reference is written as SQL `NULL`, like `undefined()`. Declare the field non-null — an
SQL `NULL` reads as `undefined()`, never as a `null` reference.

```java
@EntityJdbc
@Table("patches")
public record Patch(@Id long id, @PgJsonb JsonNullable<Preferences> preferences) {}
```

---

## Kotlin

Same annotations, no use-site target — like `@Mapping`, the tag is read from the constructor
parameter of a data class. Kotlin collection and array types map onto the same mappers:

| Kotlin | Java equivalent |
|---|---|
| `List<Long>`, `Set<String>`, `Collection<UUID>` | `List<Long>`, `Set<String>`, `Collection<UUID>` |
| `LongArray`, `IntArray`, `DoubleArray`, `BooleanArray`, … | `long[]`, `int[]`, `double[]`, `boolean[]` |
| `Array<String>`, `Array<Long>` | `String[]`, `Long[]` |
| `List<String?>` | a nullable-element array |

```kotlin
@EntityJdbc
@Table("articles")
data class Article(
    @field:Id val id: UUID,
    val title: String,
    @Pg val tags: List<String>,
    @Pg val relatedIds: LongArray,
    @Pg val authors: List<UUID>?,
    @PgJsonb val preferences: Preferences,
    val during: PgRange<OffsetDateTime>?
)

@Repository
interface ArticleRepository : JdbcRepository {

    @Query("SELECT %{return#selects} FROM %{return#table} WHERE id = ANY(:ids)")
    fun findByIds(@Pg ids: List<UUID>): List<Article>
}
```

Column names follow the same `snake_lower_case` conversion as Java (`relatedIds` → `related_ids`).

---

## Taking only part of the module

`PostgresJdbcDatabaseModule` is `JdbcDatabaseModule` plus five mapper interfaces from
`io.koraframework.database.jdbc.postgres.mapper`, which can be inherited one by one:

| Interface | Covers |
|---|---|
| `PgIntervalJdbcMappersModule` | `@Pg Duration`, `@Pg Period` |
| `PgCollectionJdbcMappersModule` | `@Pg List/Set/Collection<T>` |
| `PgArrayJdbcMappersModule` | `@Pg` boxed and primitive arrays |
| `PgRangeJdbcMappersModule` | `PgRange<T>` |
| `PgJsonJdbcMappersModule` | `@PgJson` / `@PgJsonb`, including `JsonNullable<T>` |

```java
@KoraApp
public interface Application extends HoconConfigModule, JsonModule,
        JdbcDatabaseModule, PgJsonJdbcMappersModule {}
```

Because every mapper is a `@DefaultComponent`, a `@Component` of the same type **and the same
tag** replaces it without an ambiguity error.

---

## Common pitfalls

| Symptom | Cause / fix |
|---|---|
| `No component found for dependency: JdbcParameterColumnMapper<List<Long>>` | the field/parameter has no `@Pg`; add the tag (and `database-jdbc-postgres`) |
| `No component found` for a `@Pg`/`@PgJsonb`-tagged mapper | `PostgresJdbcDatabaseModule` (or the matching `Pg*JdbcMappersModule`) is not on the `@KoraApp` |
| `No component found for dependency: JsonWriter<X>` behind a `@PgJsonb` field | the payload type has no `@Json` / `JsonModule` is missing |
| `@Json @PgJsonb` on one field, PostgreSQL mapper not used | the first tag wins — keep `@PgJsonb` on the field, `@Json` on the payload type |
| `operator does not exist: jsonb @> json` | the filter parameter is `@PgJson`; use `@PgJsonb` for `jsonb` operators |
| `WHERE id IN (:ids)` with a list | use `WHERE id = ANY(:ids)` with a `@Pg` collection parameter |
| `SQLException: PostgreSQL array contains NULL at index …` | the column has `NULL` elements; use `List<T>` / boxed `T[]` instead of a primitive array |
| `interval with years or months can't be converted to Duration` | the column stores calendar units; use `@Pg Period` |
| `interval with a time part can't be converted to Period` | the column stores a time part; use `@Pg Duration` |
| `Set<T>` field fails to read | results are always `List<T>`; declare the field `List<T>` |
| `PgRange.closed(1, 10)` reads back as `[1,11)` | PostgreSQL canonicalises discrete ranges to `[)` — expected |
| Both `JdbcDatabaseModule` and `PostgresJdbcDatabaseModule` listed | redundant; `PostgresJdbcDatabaseModule` already extends `JdbcDatabaseModule` |

---

## See also

- [entity-mapping-reference.md](entity-mapping-reference.md) — natively supported types, naming
- [custom-mappers-reference.md](custom-mappers-reference.md) — writing a mapper for a type this module does not cover
- [custom-mappers-advanced-reference.md](custom-mappers-advanced-reference.md) — tags, construct vs inject
