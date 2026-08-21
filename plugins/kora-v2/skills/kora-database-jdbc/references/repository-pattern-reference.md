# Repository Pattern Reference

**Source:** `.kora-agent/kora-docs/mkdocs/docs/en/documentation/database-common.md`, `database-jdbc.md`
**Examples:** `.kora-agent/kora-examples/examples/java/kora-java-database-jdbc/`, `.kora-agent/kora-examples/examples/java/kora-java-crud/`
**Module:** `ru.tinkoff.kora:database-jdbc`

## Contents

- [Repository declaration](#repository-declaration)
- [SQL macros](#sql-macros)
- [Field enumeration](#field-enumeration)
- [Return types](#return-types)
- [Batch queries](#batch-queries)
- [Generated identifiers](#generated-identifiers)
- [Manual query / connection control](#manual-query--connection-control)
- [Composite keys](#composite-keys)
- [Joins and projections](#joins-and-projections)
- [Pessimistic locking](#pessimistic-locking)
- [Generic CRUD base interface](#generic-crud-base-interface)
- [Multiple databases](#multiple-databases)

---

## Repository declaration

A repository is an interface annotated with `@Repository` extending `JdbcRepository`. Kora generates the implementation (`$<Name>_Impl`) at compile time.

```java
@Repository
public interface EntityRepository extends JdbcRepository {

    @Query("SELECT %{return#selects} FROM %{return#table} WHERE id = :id")
    @Nullable
    Entity findById(Long id);

    @Query("SELECT %{return#selects} FROM %{return#table}")
    List<Entity> findAll();
}
```

`@Repository`, `@Query`, `@Batch`, `@Id`, `@Table`, `@Column` come from `ru.tinkoff.kora.database.common.annotation`. `JdbcRepository` and `@EntityJdbc` come from `ru.tinkoff.kora.database.jdbc`.

---

## SQL macros

Macros expand into SQL at compile time. The macro target is a method argument name or `return`; `#` separates target and command.

| Macro | Expands to |
|-------|-----------|
| `%{return#selects}` | column list of the return entity |
| `%{return#table}` / `%{entity#table}` | `@Table` value, else snake_case class name |
| `%{entity#inserts}` | full `INSERT INTO table(cols) VALUES(:entity.field, ...)` |
| `%{entity#updates}` | `col = :entity.field, ...` clause for `SET` |
| `%{entity#where = @id}` | `WHERE` over the `@Id` field(s) |
| `%{id#where}` | `WHERE` over a composite-key argument named `id` |

The complete set of commands is `table`, `selects`, `inserts`, `updates`, `where`. There is **no** `deletes` macro — write `DELETE FROM ... WHERE ...` by hand.

```java
@Repository
public interface EntityRepository extends JdbcRepository {

    @Table("entities")
    record Entity(@Id Long id,
                  @Column("entity_name") String name,
                  String code) {}

    // SELECT id, entity_name, code FROM entities
    @Query("SELECT %{return#selects} FROM %{return#table}")
    List<Entity> findAll();

    // INSERT INTO entities(id, entity_name, code) VALUES(:entity.id, :entity.name, :entity.code)
    @Query("INSERT INTO %{entity#inserts}")
    UpdateCount insert(Entity entity);

    // UPDATE entities SET entity_name = :entity.name, code = :entity.code WHERE id = :entity.id
    @Query("UPDATE %{entity#table} SET %{entity#updates} WHERE %{entity#where = @id}")
    UpdateCount update(Entity entity);
}
```

### Field enumeration

After a command, `=` keeps only the listed fields and `-=` excludes them. The `@id` keyword refers to the `@Id` field(s); a bare name refers to a field literally.

```java
// INSERT INTO entities(entity_name, code) VALUES(:entity.name, :entity.code)
@Query("INSERT INTO %{entity#inserts-= @id}")
@Id Long insert(Entity entity);

// INSERT INTO entities(entity_name, code) VALUES(:entity.name, :entity.code)
@Query("INSERT INTO %{entity#inserts = name,code}")
UpdateCount insertPartial(Entity entity);
```

Spaces are allowed only between field names or around the enumeration symbol.

---

## Return types

| Signature | Behavior |
|-----------|----------|
| `T method()` | single row, throws if absent |
| `@Nullable T method()` | optional single row — **preferred** (no allocation) |
| `Optional<T> method()` | optional single row, Optional flavor |
| `List<T> method()` | zero-or-many, empty list never null |
| `UpdateCount method()` | affected-row count for write queries |
| `void method()` | result discarded |
| `@Id Long method()` | database-generated identifier |
| `CompletionStage<T>` / `Mono<T>` | async / reactive (require an `Executor`) |

`UpdateCount` lives in `ru.tinkoff.kora.database.common`; read its count with `.value()`.

---

## Batch queries

`@Batch` sends a set of statements in one round-trip. A batch method returns `void`, `UpdateCount`, or generated identifiers — never arbitrary projected rows.

```java
@Query("INSERT INTO %{entity#inserts}")
UpdateCount insertBatch(@Batch List<Entity> entities);

@Query("INSERT INTO %{entity#inserts-= @id}")
@Id
List<Long> insertBatchReturningIds(@Batch List<Entity> entities);
```

---

## Generated identifiers

When the database assigns the key, put `@Id` on the method and return the id type, or project it with `RETURNING`:

```java
@EntityJdbc
record Entity(@Id Long id, @Column("name") String name) {
    public Entity(String name) { this(null, name); }
}

// @Id on method: works for single and @Batch inserts
@Query("INSERT INTO entities_sequence(name) VALUES (:entity.name)")
@Id
Long insertGenerated(Entity entity);

// explicit RETURNING projection
@Query("INSERT INTO entities_sequence(name) VALUES (:entity.name) RETURNING id")
long insert(Entity entity);
```

---

## Manual query / connection control

When `@Query` is not enough, write a `default` method and use the connection factory directly. Calls inside it still join the surrounding transaction.

```java
@Repository
public interface EntityRepository extends JdbcRepository {

    @EntityJdbc
    record Entity(Long id, String name) {}

    default int insert(Entity entity) {
        return getJdbcConnectionFactory().inTx(connection -> {
            var sql = "INSERT INTO entities(name) VALUES (?) RETURNING id";
            try (var ps = connection.prepareStatement(sql)) {
                ps.setString(1, entity.name());
                try (var rs = ps.executeQuery()) {
                    rs.next();
                    return rs.getInt(1);
                }
            }
        });
    }
}
```

---

## Composite keys

Express a composite key as an `@Embedded` nested record and use `%{id#where}` for lookups.

```java
@Repository
public interface EntityRepository extends JdbcRepository {

    @EntityJdbc
    @Table("entities_composite")
    record Entity(@Id @Embedded EntityId id,
                  @Column("name") String name) {

        public record EntityId(UUID a, UUID b) {}
    }

    @Query("SELECT %{return#selects} FROM %{return#table} WHERE %{id#where}")
    @Nullable
    Entity findById(Entity.EntityId id);

    @Query("INSERT INTO %{entity#inserts}")
    UpdateCount insert(Entity entity);

    @Query("DELETE FROM entities_composite WHERE %{id#where}")
    UpdateCount deleteById(Entity.EntityId id);
}
```

---

## Joins and projections

A repository can return a projection record distinct from the table entity. Alias join columns to match the projection's `@Column`/`@Embedded` names.

```java
@Repository
public interface TaskRepository extends JdbcRepository {

    @EntityJdbc
    @Table("tasks")
    record Task(@Id Long id, @Column("title") String title,
                @Column("user_assignee_id") @Nullable Long userAssigneeId) {}

    @EntityJdbc
    record TaskWithAssignee(@Id @Column("task_id") Long id,
                            @Column("title") String title,
                            @Embedded("assignee_") Assignee assignee) {

        @EntityJdbc
        public record Assignee(@Column("id") Long id, @Column("name") String name) {}
    }

    @Query("""
            SELECT t.id AS task_id, t.title,
                   u.id AS assignee_id, u.name AS assignee_name
            FROM tasks t
            JOIN users u ON u.id = t.user_assignee_id
            WHERE t.id = :id
            """)
    @Nullable
    TaskWithAssignee findWithAssignee(Long id);
}
```

---

## Pessimistic locking

`SELECT ... FOR UPDATE` must run inside a transaction to hold the row lock.

```java
@Query("SELECT %{return#selects} FROM %{return#table} WHERE id = :id FOR UPDATE")
@Nullable
Account findByIdForUpdate(Long id);
```

See [transactions-reference.md](transactions-reference.md) for usage inside `inTx()`.

---

## Generic CRUD base interface

Extract reusable CRUD into a generic interface (no `@Repository`); concrete repositories extend it and supply the `@EntityJdbc` record.

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
}

@Repository
public interface EntityRepository extends AbstractJdbcCrudRepository<String, EntityRepository.Entity> {

    @EntityJdbc
    @Table("entities")
    record Entity(@Id String id, @Column("value1") int field1, String value2) {}

    @Query("DELETE FROM entities WHERE id = :id")
    UpdateCount deleteById(String id);
}
```

---

## Multiple databases

To target a second database, declare a tagged `JdbcDatabaseConfig` + `JdbcDatabase` in `@KoraApp` and reference the tag from the repository. See `database-common.md` ("Multiple databases") for the full factory:

```java
@KoraApp
public interface Application extends JdbcDatabaseModule {

    final class OtherDatabase {}

    @Tag(OtherDatabase.class)
    default JdbcDatabaseConfig otherConfig(Config config,
                                           ConfigValueExtractor<JdbcDatabaseConfig> extractor) {
        return extractor.extract(config.get("db.other"));
    }

    @Tag(OtherDatabase.class)
    default JdbcDatabase otherDatabase(@Tag(OtherDatabase.class) JdbcDatabaseConfig config,
                                       DataBaseTelemetryFactory telemetryFactory,
                                       @Tag(OtherDatabase.class) @Nullable Executor executor) {
        return new JdbcDatabase(config, telemetryFactory, executor);
    }
}

@Repository(executorTag = @Tag(OtherDatabase.class))
public interface OtherRepository extends JdbcRepository { }
```

Repositories using the primary database need no tag.

---

## See also

- [entity-mapping-reference.md](entity-mapping-reference.md)
- [transactions-reference.md](transactions-reference.md)
- [custom-mappers-reference.md](custom-mappers-reference.md)
