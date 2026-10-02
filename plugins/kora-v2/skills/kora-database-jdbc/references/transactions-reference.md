# Transactions Reference

**Applies to:** Kora 2.x (`io.koraframework:database-jdbc`)

## Contents

- [Getting the executor](#getting-the-executor)
- [Basic transaction](#basic-transaction)
- [Kotlin needs an explicit SAM constructor](#kotlin-needs-an-explicit-sam-constructor)
- [The inTx overload set](#the-intx-overload-set)
- [Isolation levels](#isolation-levels)
- [Post-commit and post-rollback actions](#post-commit-and-post-rollback-actions)
- [Nested transactions](#nested-transactions)
- [Pessimistic locking](#pessimistic-locking)
- [Non-transactional connection access](#non-transactional-connection-access)
- [Retry on deadlock](#retry-on-deadlock)
- [Kotlin: removing suspend](#kotlin-removing-suspend)
- [Pitfalls](#pitfalls)

---

## Getting the executor

`JdbcRepository` exposes one method:

```java
JdbcExecutor executor();
```

This **replaces** the 1.x `getJdbcConnectionFactory()`. `JdbcExecutor` lives in
`io.koraframework.database.jdbc`; the graph implementation is `JdbcDataSource`, so
`JdbcExecutor` can also be injected directly into any `@Component`:

```java
@Component
public final class LedgerService {

    private final AccountRepository accounts;
    private final JdbcExecutor executor;

    public LedgerService(AccountRepository accounts, JdbcExecutor executor) {
        this.accounts = accounts;
        this.executor = executor;
    }
}
```

Reaching it through a repository (`accounts.executor()`) is the shorter form and is what the
migrated examples use.

---

## Basic transaction

```java
@Component
public final class TaskService {

    private final TaskRepository taskRepository;
    private final AuditRepository auditRepository;

    public TaskService(TaskRepository taskRepository, AuditRepository auditRepository) {
        this.taskRepository = taskRepository;
        this.auditRepository = auditRepository;
    }

    public List<Long> createTasks(List<TaskDAO> tasks) {
        return taskRepository.executor().inTx(() -> {
            var ids = taskRepository.insert(tasks);
            auditRepository.recordCreated(ids);
            return ids;
        });
    }

    public void assign(long taskId, long userId) {
        taskRepository.executor().inTx(() -> {
            var updated = taskRepository.updateAssignee(taskId, userId);
            if (updated.value() < 1) {
                throw HttpServerResponseException.of(404, "Task not found");
            }
        });
    }
}
```

Every repository call made inside the lambda joins the same transaction, whichever repository it
belongs to, as long as they share the same `JdbcExecutor`. Any exception rolls the whole block
back and is rethrown.

There is no `@Transactional` annotation and no declarative propagation in Kora — transaction
boundaries are the `inTx` lambda, written in code.

---

## Kotlin needs an explicit SAM constructor

`inTx` has eight overloads, and Kotlin no longer picks one from a bare lambda. Name the functional
interface:

```kotlin
// returns a value
val ids = taskRepository.executor().inTx(JdbcExecutor.SqlSupplier {
    taskRepository.insert(tasks)
})

// returns nothing
taskRepository.executor().inTx(JdbcExecutor.SqlRunnable {
    val updated = taskRepository.updateAssignee(taskId, userId)
    if (updated.value() < 1) {
        throw HttpServerResponseException.of(404, "Task not found")
    }
})
```

Without the SAM constructor the compiler reports `Cannot infer type for type parameter T` or
`Overload resolution ambiguity` — neither error mentions transactions, which makes this an easy
half-hour to lose during a migration.

Java infers correctly from a bare lambda: a zero-argument lambda that returns a value binds to
`SqlSupplier<T>`, one that returns nothing binds to `SqlRunnable`.

---

## The inTx overload set

The nested functional interfaces are declared on `JdbcExecutor`:

```java
@FunctionalInterface interface SqlSupplier<T>    { T apply() throws SQLException; }
@FunctionalInterface interface SqlFunction<T, R> { R apply(T t) throws SQLException; }
@FunctionalInterface interface SqlConsumer<T>    { void accept(T t) throws SQLException; }
@FunctionalInterface interface SqlRunnable       { void run() throws SQLException; }
```

`inTx` accepts each of them, with and without an isolation level:

| Overload | Callback receives | Returns |
|----------|-------------------|---------|
| `inTx(SqlSupplier<T>)` | nothing | `T` |
| `inTx(SqlRunnable)` | nothing | `void` |
| `inTx(SqlFunction<ConnectionContext, T>)` | the `ConnectionContext` | `T` |
| `inTx(SqlConsumer<ConnectionContext>)` | the `ConnectionContext` | `void` |
| `inTx(TxIsolation, SqlSupplier<T>)` | nothing | `T` |
| `inTx(TxIsolation, SqlRunnable)` | nothing | `void` |
| `inTx(TxIsolation, SqlFunction<ConnectionContext, T>)` | the `ConnectionContext` | `T` |
| `inTx(TxIsolation, SqlConsumer<ConnectionContext>)` | the `ConnectionContext` | `void` |

Callbacks may throw `SQLException` directly; `JdbcExecutor` wraps failures in
`io.koraframework.database.jdbc.exception.UncheckedSqlException`.

---

## Isolation levels

The isolation level is an overload argument, not a manual `Connection` call.
`JdbcExecutor.TxIsolation` has `READ_UNCOMMITTED`, `READ_COMMITTED`, `REPEATABLE_READ` and
`SERIALIZABLE`.

```java
public void transfer(long fromId, long toId, BigDecimal amount) {
    accounts.executor().inTx(JdbcExecutor.TxIsolation.REPEATABLE_READ, () -> {
        var from = accounts.findByIdForUpdate(fromId);
        var to = accounts.findByIdForUpdate(toId);
        // ...
    });
}
```

```kotlin
accounts.executor().inTx(JdbcExecutor.TxIsolation.REPEATABLE_READ, JdbcExecutor.SqlRunnable {
    // ...
})
```

The executor restores the connection's previous isolation level afterwards. The default comes from
the driver and the database (usually `READ_COMMITTED`); a pool-wide default can be set through
`jdbc.dsProperties`, which is passed to Hikari as `dataSourceProperties`.

---

## Post-commit and post-rollback actions

`ConnectionContext` registers callbacks that run **after** the outer transaction resolves. Take the
context from the `SqlFunction`/`SqlConsumer` overload rather than reaching for
`executor().currentContext()`, which is nullable.

```java
public long createOrder(Order order) {
    return orders.executor().inTx(ctx -> {
        var id = orders.insert(order);

        ctx.afterCommit(connection -> eventPublisher.orderCreated(id));
        ctx.afterRollback((connection, e) -> log.error("order {} rolled back", id, e));

        return id;
    });
}
```

- `ConnectionContext.afterCommit(PostCommitAction)` — `void run(Connection connection)`.
- `ConnectionContext.afterRollback(PostRollbackAction)` — `void run(Connection connection, Exception e)`.
- Both return the context, so they chain.
- Both throw `IllegalStateException` when there is no active transaction: *"Cannot add JDBC
  post-commit action because transaction is not active; register it inside a transactional
  repository/service method"*.

Actions belong to the outer transaction: a nested `inTx` joins it, so what it registers runs only
when the outer one commits or rolls back.

Post-rollback actions run inside the rollback handling; anything they throw is attached to the
original exception as a suppressed exception. Post-commit actions run after `commit()` and after
auto-commit is restored — a failure there does **not** undo the commit, but it **does** propagate
out of `inTx`: the caller sees an exception for work that is already committed (an HTTP endpoint
answers 500 and the client retries). Catch inside the action whatever the caller must not see:

```java
ctx.afterCommit(connection -> {
    try {
        cache.put(id, value);
    } catch (RuntimeException e) {
        log.warn("cache write-through failed for {}", id, e);
    }
});
```

On `2.0.0.RC1` three more defects apply (fixed in `2.0.0.RC2`, kora-projects/kora PR #967 — only RC1 is affected):

1. The first post-commit action that throws skips the remaining ones; a post-rollback action
   throwing a `RuntimeException` (not an `SQLException`) skips the remaining rollback actions.
2. Actions are never cleared from the `ConnectionContext`, so inside one `withConnection` /
   `withContext` scope every later `inTx` runs them again: the `afterCommit` of a rolled-back
   transaction fires when the next one commits, the `afterRollback` of a committed one fires when
   the next one rolls back.
3. An `afterCommit` action that opens another `inTx` re-runs itself until `StackOverflowError`.

On RC1: catch inside every action, keep to one `inTx` per `withConnection` scope when it
registers actions, and run follow-up transactional work after `inTx` returns rather than from an
action.

Use post-commit for notifications, event publishing and cache invalidation; post-rollback for
alerting and cleanup.

---

## Nested transactions

There are no propagation modes. `inTx` inspects the current connection: if auto-commit is already
off, it simply runs the callback on the open transaction instead of starting a new one. So a nested
`inTx` joins the outer transaction, and an inner rollback rolls the outer one back too.

```java
public void processOrder(Order order) {
    orders.executor().inTx(() -> {
        orders.insert(order);

        // joins the transaction above — not a savepoint, not a separate transaction
        inventory.executor().inTx(() -> inventory.reserveAll(order.items()));
    });
}
```

Savepoints are not exposed; use `executor().withConnection(...)` and the JDBC API if you need them.

---

## Pessimistic locking

```java
@Query("SELECT %{return#selects} FROM %{return#table} WHERE id = :id FOR UPDATE")
@Nullable
Account findByIdForUpdate(Long id);
```

`FOR UPDATE` only holds the lock for the life of the transaction, so the call must sit inside
`inTx`. Called outside one it runs in its own auto-commit statement and the lock is released
immediately — a silent correctness bug rather than an error.

---

## Non-transactional connection access

`withConnection` / `withContext` reuse the current connection (and therefore the current
transaction, if any) without opening one of their own:

```java
default long insertReturning(Entity entity) {
    return executor().withConnection(connection -> {
        try (var ps = connection.prepareStatement(
                "INSERT INTO entities(name) VALUES (?) RETURNING id")) {
            ps.setString(1, entity.name());
            try (var rs = ps.executeQuery()) {
                rs.next();
                return rs.getLong(1);
            }
        }
    });
}
```

`acquireConnection()` hands out a raw connection you own — close it yourself, in
try-with-resources. `currentConnection()` and `currentContext()` return `null` when no connection
is bound to the current scope.

---

## Retry on deadlock

Resilience in 2.0 is typed: `@Retryable(Spec.class)` where the spec interface extends `Retry` and
carries `@RetrySpec("<config path>")`. The retried method must live on a `@Component` so the AOP
aspect can wrap it, and the retried block must include the whole transaction — retrying a
half-rolled-back transaction is not meaningful.

```java
@RetrySpec("resilient.retry.orderWrite")
public interface OrderWriteRetry extends Retry {}

@Component
public final class OrderWriter {

    private final OrderRepository repository;

    public OrderWriter(OrderRepository repository) {
        this.repository = repository;
    }

    @Retryable(OrderWriteRetry.class)
    public void updateWithRetry(Order order) {
        repository.executor().inTx(() -> repository.update(order));
    }
}
```

```hocon
resilient.retry.orderWrite {
    attempts = 3
    delay = "50ms"
    delayStep = "100ms"
}
```

`attempts` and `delay` are required; `delayStep` defaults to zero. Annotations come from
`io.koraframework.resilient.retry.annotation`, the base type from
`io.koraframework.resilient.retry.Retry`, artifact `io.koraframework:resilient-kora`. The 1.x
string form `@Retry("orderWrite")` no longer exists. See the `kora-aop-resilient` skill for the
full surface.

---

## Kotlin: removing suspend

Repository contracts are synchronous, so a 1.x `suspend fun findById(...)` becomes
`fun findById(...)`. **This is not a mechanical keyword deletion.** Dropping `suspend` propagates
up the call chain into services, controllers and tests, and it changes behaviour:

- **Cancellation.** Structured concurrency no longer cancels the database call; a coroutine
  cancellation cannot interrupt a blocking JDBC statement. Bound the work with a query timeout or a
  statement-level limit instead.
- **Transaction boundaries.** A transaction is now tied to the calling thread's scope for the
  duration of the `inTx` lambda, not to a coroutine context. Do not launch coroutines inside `inTx`
  and expect them to share the transaction — they will not.
- **Exception propagation.** Failures surface as ordinary thrown exceptions rather than through
  coroutine machinery; `CancellationException` handling around repository calls becomes dead code.
- **Tests.** `runTest` / `runBlocking` wrappers around what are now synchronous calls are
  unnecessary and should be removed.

If a suspend repository existed only as a duplicate of an already-synchronous one, delete it
outright together with its DI references and coroutine tests instead of keeping two interfaces.
Once the last coroutine usage is gone, drop the module's direct
`kotlinx-coroutines-core` / `kotlinx-coroutines-jdk8` dependencies.

For genuine parallel fan-out, Java `StructuredTaskScope` replaces coroutine concurrency — it is a
preview API, so it needs `--enable-preview` (and the matching Kotlin flags) on every compile, test
and run task.

---

## Pitfalls

| Problem | Cause | Fix |
|---------|-------|-----|
| `Cannot infer type for type parameter T` on `inTx` | Kotlin bare lambda against overloads | `JdbcExecutor.SqlSupplier { … }` / `SqlRunnable { … }` |
| `getJdbcConnectionFactory()` does not resolve | renamed in 2.0 | `executor()` |
| `currentConnectionContext()` / `addPostCommitAction` do not resolve | renamed in 2.0 | `currentContext()` / `ConnectionContext.afterCommit` |
| `IllegalStateException: Cannot add JDBC post-commit action…` | registered outside an active transaction | move the registration inside `inTx` |
| Writes outside the lambda are not rolled back | they ran in their own auto-commit statement | move every related call into one `inTx` |
| `FOR UPDATE` does not block a concurrent writer | the query ran outside a transaction | call it inside `inTx` |
| Caller gets an exception although the data is committed | a post-commit action threw; the error propagates out of `inTx` | catch inside the action |
| `afterCommit` fired for a transaction that rolled back, or `afterRollback` for one that committed | on RC1 (fixed in RC2 by kora-projects/kora PR #967) actions stay in the context, and a later `inTx` in the same `withConnection` scope ran them | one `inTx` per `withConnection` scope when it registers actions |
| `StackOverflowError` through `JdbcExecutor.doInTx` | on RC1 (fixed in RC2 by kora-projects/kora PR #967) an `afterCommit` action that opens another `inTx` re-runs itself | run the follow-up after `inTx` returns |
| Long transaction exhausts the pool | remote calls inside `inTx` | keep external I/O outside the transaction |

---

## See also

- [repository-pattern-reference.md](repository-pattern-reference.md) — `@Repository`, `@Query`, macros
- [connection-pool-reference.md](connection-pool-reference.md) — HikariCP sizing and leak detection
- [database-jdbc-config-reference.md](database-jdbc-config-reference.md) — the `jdbc` config section
- `kora-aop-resilient` skill — `@Retryable`, `@CircuitBreakable`, `@Timeout`
