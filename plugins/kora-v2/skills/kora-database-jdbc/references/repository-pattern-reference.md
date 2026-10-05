# Repository Pattern Reference

**Applies to:** Kora 2.x (`io.koraframework:database-jdbc`)

## Contents

- [Repository declaration](#repository-declaration)
- [SQL macros](#sql-macros)
- [Macro targets](#macro-targets)
- [Field enumeration](#field-enumeration)
- [Return types](#return-types)
- [Batch queries](#batch-queries)
- [Generated identifiers](#generated-identifiers)
- [Manual query and connection control](#manual-query-and-connection-control)
- [Composite keys](#composite-keys)
- [Joins and projections](#joins-and-projections)
- [Table aliases in macros](#table-aliases-in-macros)
- [Pessimistic locking](#pessimistic-locking)
- [Generic CRUD base interface](#generic-crud-base-interface)
- [Multiple databases](#multiple-databases)
- [Removed in 2.0](#removed-in-20)

---

## Repository declaration

A repository is an interface annotated with `@Repository` that extends `JdbcRepository`. The
annotation processor (Java) or KSP (Kotlin) generates the implementation `$<Name>_Impl` at
compile time; a nested repository gets its outer classes folded into the name
(`$Outer_Inner_Impl`).

```java
@Repository
public interface EntityRepository extends JdbcRepository {

    @Query("SELECT %{return#selects} FROM %{return#table} WHERE id = :id")
    @Nullable
    Entity findById(String id);

    @Query("SELECT %{return#selects} FROM %{return#table}")
    List<Entity> findAll();
}
```

Packages:

| Symbol | Package |
|--------|---------|
| `@Repository`, `@Query`, `@Id`, `@Table`, `@Column`, `@Embedded`, `@Batch` | `io.koraframework.database.common.annotation` |
| `UpdateCount` | `io.koraframework.database.common` |
| `JdbcRepository`, `JdbcExecutor` | `io.koraframework.database.jdbc` |
| `@EntityJdbc` | **`io.koraframework.database.jdbc.annotation`** |
| `JdbcResultSetMapper`, `JdbcRowMapper`, `JdbcResultColumnMapper` | `io.koraframework.database.jdbc.mapper.result` |
| `JdbcParameterColumnMapper` | `io.koraframework.database.jdbc.mapper.parameter` |
| `@Mapping`, `@Component`, `@Module`, `@Tag` | `io.koraframework.common.annotation` |

Only `@EntityJdbc` changed package between 1.x and 2.0 — check each import individually rather
than applying one rewrite rule to all of them.

`JdbcRepository` declares exactly one method:

```java
JdbcExecutor executor();
```

---

## SQL macros

Macros expand at compile time into plain SQL. The syntax is `%{target#command}`, optionally
followed by a field selector. The complete 2.0 command set:

| Command | Expands to |
|---------|-----------|
| `table` | the `@Table` value, else the class name converted with the entity's naming strategy (`snake_case` by default) |
| `table as <alias>` | the table name plus an SQL alias; every other macro on that target then qualifies its columns with the alias |
| `selects` | the selected columns, adding `AS <column>` when a `table as` alias is active and the column was renamed |
| `columns` | bare column names, comma separated |
| `values` | named bind parameters — `:entity.id, :entity.field1, …` |
| `inserts` | `table(col, …) VALUES (:path, …)` — the whole tail of an `INSERT INTO` |
| `updates` | `col = :path, …` for a `SET` clause; fields annotated `@Id` are **always excluded** |
| `where` | `col = :path` predicates joined with ` AND ` |

There is no `deletes` command. Write `DELETE FROM … WHERE …` explicitly, or use
`DELETE FROM %{entity#table} WHERE %{entity#where = @id}` when the method takes the entity.

```java
@Repository
public interface EntityRepository extends JdbcRepository {

    @EntityJdbc
    @Table("entities")
    record Entity(@Id String id,
                  @Column("value1") int field1,
                  String value2,
                  @Nullable String value3) {}

    // SELECT id, value1, value2, value3 FROM entities WHERE id = ?
    @Query("SELECT %{return#selects} FROM %{return#table} WHERE id = :id")
    @Nullable
    Entity findById(String id);

    // INSERT INTO entities(id, value1, value2, value3) VALUES (?, ?, ?, ?)
    @Query("INSERT INTO %{entity#inserts}")
    UpdateCount insert(Entity entity);

    // UPDATE entities SET value1 = ?, value2 = ?, value3 = ? WHERE id = ?
    @Query("UPDATE %{entity#table} SET %{entity#updates} WHERE %{entity#where = @id}")
    UpdateCount update(Entity entity);

    // INSERT INTO entities(...) VALUES (...) ON CONFLICT (id) DO UPDATE SET value1 = ?, ...
    @Query("INSERT INTO %{entity#inserts} ON CONFLICT (%{entity#selects = @id}) DO UPDATE SET %{entity#updates}")
    UpdateCount upsert(Entity entity);
}
```

### Macro targets

A target must resolve **within the annotated method**. The resolver tries, in order:

1. a method parameter with that name — `%{entity#inserts}` needs a parameter called `entity`;
2. `return` — the method's return type, unwrapping `Optional` and collections. `return` is rejected
   on `void` and on `UpdateCount` returns;
3. a type parameter of the enclosing repository or of the method — `%{V#table}` in a generic base
   interface;
4. a dotted path into a nested entity field — `%{return.user#selects}`.

A target that resolves to none of these fails the build with
*"Query macro target `X` cannot be resolved"*. This is the single most common macro mistake when
porting: `%{entity#table}` inside `deleteById(Long id)` has no `entity` parameter, so it never
compiles. Write the table name literally there.

### Field enumeration

After the command, `=` keeps only the listed fields and `-=` excludes them. `@id` refers to the
`@Id` field(s); any other token is a **field name** (not a column name).

```java
// INSERT INTO entities(value1, value2, value3) VALUES (?, ?, ?)   -- @Id excluded
@Query("INSERT INTO %{entity#inserts -= @id}")
@Id
Long insert(Entity entity);

// INSERT INTO entities(id, value2, value3) VALUES (?, ?, ?)       -- field1 excluded
@Query("INSERT INTO %{entity#inserts -= field1}")
UpdateCount insertPartial(Entity entity);

// INSERT INTO entities(value1, value2, value3) VALUES (?, ?, ?)   -- columns/values split
@Query("INSERT INTO %{entity#table}(%{entity#columns -= @id}) VALUES (%{entity#values -= @id})")
UpdateCount insertExplicit(Entity entity);
```

Whitespace around `#`, `=` and `-=` is stripped, so `%{entity#inserts-=@id}` and
`%{entity#inserts -= @id}` are the same macro.

---

## Return types

| Signature | Behaviour |
|-----------|-----------|
| `T method()` | single row; an absent row throws `NullPointerException: Result mapping is expected non-null, but was null` |
| `@Nullable T method()` | optional single row — **preferred** (no allocation) |
| `Optional<T> method()` | optional single row, `Optional` flavour |
| `List<T> method()` | zero-or-many, empty list never null |
| `UpdateCount method()` | affected-row count; runs `PreparedStatement.executeLargeUpdate()` |
| `void method()` | result discarded |
| `@Id <IdType> method()` | database-generated identifier |

`UpdateCount` is `record UpdateCount(long value)` in `io.koraframework.database.common`.

Every `SQLException` raised while running a generated query is rethrown as
`io.koraframework.database.jdbc.exception.UncheckedSqlException`, so repository methods
declare no checked exceptions.

Kotlin mirrors the set with `T?` and `Unit`.

**`suspend` is a compile error.** KSP reports:

```
Repository method is invalid:
  findById
Problem:
  Suspend methods are not supported by the repository generator.
```

`Mono`, `Flux` and `CompletionStage` repository contracts were removed with them.

---

## Batch queries

`@Batch` (on the **parameter**, `@Target(PARAMETER)`) sends the statements in one round trip.

```java
@Query("INSERT INTO %{entity#inserts}")
UpdateCount insertBatch(@Batch List<Entity> entity);      // summed affected rows

@Query("INSERT INTO %{entity#inserts}")
void insertBatchVoid(@Batch List<Entity> entity);         // result discarded

@Query("INSERT INTO test(value) VALUES (:value)")
long[] counts(@Batch List<String> value);                 // raw executeLargeBatch() result

@Query("INSERT INTO %{entity#inserts -= @id}")
@Id
List<Long> insertBatchReturningIds(@Batch List<Entity> entity);   // generated keys
```

Supported batch return types are `void`, `UpdateCount`, `int[]`, `long[]`, and — with `@Id` — the
generated-key type or a `List` of it. An arbitrary projection fails the build with *"Invalid JDBC
`@Batch` repository method return type"*.

`UpdateCount` from a batch is the plain **sum** of what `executeLargeBatch()` returned. A driver
that reports `Statement.SUCCESS_NO_INFO` (`-2`) contributes that value to the sum, so a negative or
implausible count means "the driver did not tell us", not "no rows changed" — use `int[]` / `long[]`
if you need to inspect the per-statement values.

---

## Generated identifiers

Two independent mechanisms:

```java
@EntityJdbc
record Entity(@Id Long id, @Column("name") String name) {
    public Entity(String name) { this(null, name); }
}

// 1. @Id on the method: prepareStatement(..., RETURN_GENERATED_KEYS) + getGeneratedKeys()
@Query("INSERT INTO entities_sequence(name) VALUES (:entity.name)")
@Id
Long insertGenerated(Entity entity);

// 2. explicit RETURNING projection, read as an ordinary result
@Query("INSERT INTO entities_sequence(name) VALUES (:entity.name) RETURNING id")
long insert(Entity entity);
```

Both are used in the migrated examples. `@Id` on the method also works with `@Batch`, returning
`List<Long>`, and it may be combined with an explicit `RETURNING id` clause (PostgreSQL's driver
uses the clause you wrote instead of appending its own).

---

## Manual query and connection control

When `@Query` is not enough, write a `default` method and drive `JdbcExecutor` directly. Calls
inside it join the surrounding transaction.

```java
@Repository
public interface EntityRepository extends JdbcRepository {

    @EntityJdbc
    record Entity(Long id, String name) {}

    default long insert(Entity entity) {
        return executor().withConnection(connection -> {
            var sql = "INSERT INTO entities(name) VALUES (?) RETURNING id";
            try (var ps = connection.prepareStatement(sql)) {
                ps.setString(1, entity.name());
                try (var rs = ps.executeQuery()) {
                    rs.next();
                    return rs.getLong(1);
                }
            }
        });
    }
}
```

`JdbcExecutor` also exposes typed helpers that carry telemetry:
`query(JdbcQuery, JdbcResultSetMapper<T>)`, `queryOne`, `queryOptional`, `queryList`,
`executeUpdate`, `executeUpdateBatch`, plus `acquireConnection()`, `currentConnection()` and
`currentContext()` (both nullable outside an active call).

---

## Composite keys

Model the key as a nested record/data class and flatten it with `@Id @Embedded`. Query it with
`%{id#where}`, where `id` is the parameter name.

```java
@Repository
public interface EntityRepository extends JdbcRepository {

    @EntityJdbc
    @Table("entities_composite_uuid")
    record Entity(@Id @Embedded EntityId id,
                  @Column("name") String name) {

        public record EntityId(UUID a, UUID b) {}
    }

    // ... WHERE a = :id.a AND b = :id.b
    @Query("SELECT %{return#selects} FROM %{return#table} WHERE %{id#where}")
    @Nullable
    Entity findById(Entity.EntityId id);

    @Query("INSERT INTO %{entity#inserts}")
    UpdateCount insert(Entity entity);

    // ... WHERE a = :entity.id.a AND b = :entity.id.b
    @Query("UPDATE %{entity#table} SET %{entity#updates} WHERE %{entity#where = @id}")
    UpdateCount update(Entity entity);

    @Query("DELETE FROM entities_composite_uuid WHERE %{id#where}")
    UpdateCount deleteById(Entity.EntityId id);
}
```

`@Embedded("prefix_")` prepends a prefix to every nested column name. `%{entity#where = @id}`
expands an embedded id into all of its columns joined with `AND`.

---

## Joins and projections

A repository may return a projection distinct from any table entity. Alias the joined columns so
they match the projection's `@Column` / `@Embedded` names.

```java
@EntityJdbc
@Table("tasks")
public record TaskDAO(
        @Column("title") String title,
        @Column("status") TaskStatus status,
        @Column("description") @Nullable String description,
        @Column("user_assignee_id") @Nullable Long userAssigneeId) {

    @EntityJdbc
    public record SelectAssigned(
            @Column("task_id") @Id Long id,
            @Column("created_at") LocalDateTime createdAt,
            @Embedded("assignee_") UserDAO assigned,
            @Embedded TaskDAO base) {}
}

@Query("""
        SELECT t.id AS task_id, t.created_at,
               u.id AS assignee_id, u.name AS assignee_name, u.email AS assignee_email,
               t.title, t.status, t.description, t.user_assignee_id
        FROM tasks t
        JOIN users u ON u.id = t.user_assignee_id
        WHERE t.user_assignee_id = ANY(:assigneeIds)
        ORDER BY t.id
        """)
List<TaskDAO.SelectAssigned> findAssignedByAssigneeIds(@Pg List<Long> assigneeIds);
```

`= ANY(:assigneeIds)` binds the whole list as one PostgreSQL array; the `@Pg` tag selects the
`List<Long>` mapper from `database-jdbc-postgres`
([postgres-mappers-reference.md](postgres-mappers-reference.md)). `IN (:assigneeIds)` cannot take a list.

### Table aliases in macros

`table as` lets the macro engine write the join for you, including the `AS` aliases the embedded
projection needs:

```java
@EntityJdbc @Table("users")  record User(@Id String id, String name) {}
@EntityJdbc @Table("orders") record Order(@Id String id, @Column("user_id") String userId, String number) {}
record UserOrderView(@Embedded("u_") User user, @Embedded("o_") Order order) {}

// SELECT u.id AS u_id, u.name AS u_name, o.id AS o_id, o.user_id AS o_user_id, o.number AS o_number
// FROM users u JOIN orders o ON o.user_id = u.id WHERE u.id = ?
@Query("""
        SELECT %{return#selects}
        FROM %{return.user#table as u} JOIN %{return.order#table as o} ON o.user_id = u.id
        WHERE u.id = :id
        """)
@Nullable
UserOrderView find(String id);
```

Once an alias is declared for a target, `%{…#where}` on that target also qualifies its columns
(`e.id = ?` rather than `id = ?`).

---

## Pessimistic locking

`SELECT … FOR UPDATE` only holds the lock inside a transaction:

```java
@Query("SELECT %{return#selects} FROM %{return#table} WHERE id = :id FOR UPDATE")
@Nullable
Account findByIdForUpdate(Long id);
```

Call it from inside `executor().inTx(...)` — see
[transactions-reference.md](transactions-reference.md).

---

## Generic CRUD base interface

Put reusable CRUD on a generic interface **without** `@Repository`; concrete repositories extend it
and bind the entity type. Inside the base, target the type parameter (`%{V#…}`) when the method has
no entity parameter.

```java
public interface AbstractJdbcCrudRepository<K, V> extends JdbcRepository {

    @Query("SELECT %{return#selects} FROM %{return#table}")
    List<V> findAll();

    @Query("INSERT INTO %{entity#inserts}")
    UpdateCount insert(V entity);

    @Query("INSERT INTO %{entity#inserts}")
    UpdateCount insertBatch(@Batch List<V> entity);

    @Query("UPDATE %{entity#table} SET %{entity#updates} WHERE %{entity#where = @id}")
    UpdateCount update(V entity);

    @Query("INSERT INTO %{entity#inserts} ON CONFLICT (%{entity#selects = @id}) DO UPDATE SET %{entity#updates}")
    UpdateCount upsert(V entity);

    @Query("DELETE FROM %{entity#table} WHERE %{entity#where = @id}")
    UpdateCount delete(V entity);

    // no `entity` parameter here -> target the repository's type parameter instead
    @Query("DELETE FROM %{V#table}")
    UpdateCount deleteAll();
}

@Repository
public interface EntityRepository extends AbstractJdbcCrudRepository<String, EntityRepository.Entity> {

    @EntityJdbc
    @Table("entities")
    record Entity(@Id String id, @Column("value1") int field1, String value2) {}

    @Query("SELECT %{return#selects} FROM %{return#table} WHERE id = :id")
    @Nullable
    Entity findById(String id);

    @Query("DELETE FROM entities WHERE id = :id")
    UpdateCount deleteById(String id);
}
```

---

## Multiple databases

`@Repository` carries `Class<?> executorTag() default Tag.class`. When it is set, the generated
implementation takes a **tagged `JdbcExecutor`** as its first constructor parameter:

```java
@Repository(executorTag = OtherDatabase.class)
public interface OtherRepository extends JdbcRepository { }
```

Note the shape: a bare class literal, not `@Tag(OtherDatabase.class)`.

Supply the tagged executor with a tagged `@FactoryModule`. `JdbcDatabaseFactoryModule` takes the
config path, and its members are annotated `@Tag(Tag.Factory.class)`, which means "the tag of the
enclosing module" — so the tag on the factory method propagates to the `JdbcDataSource` it builds,
and `JdbcDataSource` implements `JdbcExecutor`:

```java
@KoraApp
public interface Application extends HoconConfigModule, LogbackModule, JdbcDatabaseModule {

    final class OtherDatabase {}

    @Tag(OtherDatabase.class)
    @FactoryModule
    default JdbcDatabaseFactoryModule otherJdbcDatabase() {
        return new JdbcDatabaseFactoryModule("jdbc.other");
    }
}
```

```hocon
jdbc {
    jdbcUrl = ${POSTGRES_JDBC_URL}
    username = ${POSTGRES_USER}
    password = ${POSTGRES_PASS}
    poolName = "primary"

    other {
        jdbcUrl = ${REPORTING_JDBC_URL}
        username = ${REPORTING_USER}
        password = ${REPORTING_PASS}
        poolName = "reporting"
    }
}
```

Repositories on the primary database need no tag — `JdbcDatabaseModule` already wires
`new JdbcDatabaseFactoryModule("jdbc")` untagged.

Do **not** hand-build a `HikariDataSource`: `JdbcDataSource` owns pool lifecycle, telemetry, the
readiness probe and the transaction scope.

---

## Removed in 2.0

| 1.x | 2.0 |
|-----|-----|
| `ru.tinkoff.kora.database.jdbc.EntityJdbc` | `io.koraframework.database.jdbc.annotation.EntityJdbc` |
| `repository.getJdbcConnectionFactory()` | `repository.executor()` → `JdbcExecutor` |
| `JdbcConnectionFactory` type | `JdbcExecutor` (implemented by `JdbcDataSource`) |
| `JdbcDatabase` component | `JdbcDataSource` (built by `JdbcDatabaseFactoryModule`) |
| `db { … }` config section | `jdbc { … }` |
| `suspend` / `Mono` / `Flux` / `CompletionStage` repository methods | synchronous signatures on virtual threads |
| `database-r2dbc`, `database-vertx` artifacts | **do not exist** — no replacement beyond synchronous JDBC |

---

## See also

- [entity-mapping-reference.md](entity-mapping-reference.md)
- [transactions-reference.md](transactions-reference.md)
- [custom-mappers-reference.md](custom-mappers-reference.md)
- [database-jdbc-config-reference.md](database-jdbc-config-reference.md)
