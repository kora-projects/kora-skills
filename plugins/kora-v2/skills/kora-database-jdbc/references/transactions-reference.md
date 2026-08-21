# Transactions Reference

**Source:** `.kora-agent/kora-docs/mkdocs/docs/en/documentation/database-jdbc.md` ("Transaction")
**Module:** `ru.tinkoff.kora:database-jdbc`

## Contents

- [Basic transaction](#basic-transaction)
- [Post-commit / post-rollback actions](#transaction-with-post-commit-actions)
- [Custom isolation](#custom-transaction-isolation)
- [Nested transactions](#nested-transactions)
- [Retry on deadlock](#retry-on-deadlock)
- [Pitfalls](#pitfalls)

---

## Basic Transaction

Use `JdbcConnectionFactory.inTx()` for transactional operations:

```java
@Component
public class UserService {
    private final UserRepository userRepository;
    private final JdbcConnectionFactory connectionFactory;
    
    public UserService(UserRepository userRepository, JdbcConnectionFactory connectionFactory) {
        this.userRepository = userRepository;
        this.connectionFactory = connectionFactory;
    }
    
    public User createUser(String email, String name) {
        return connectionFactory.inTx(() -> {
            var user = new User(null, email, name, LocalDateTime.now());
            userRepository.insert(user);
            return user;
        });
    }
}
```

All operations inside `inTx()` block execute in a single transaction. If an exception is thrown, the transaction rolls back.

---

## Transaction with Post-Commit Actions

Execute actions after successful commit or on rollback:

```java
@Component
public class OrderService {
    private final OrderRepository orderRepository;
    private final JdbcConnectionFactory connectionFactory;
    private final EmailService emailService;
    
    public Order createOrder(Order order) {
        return connectionFactory.inTx(() -> {
            var id = orderRepository.insert(order);
            
            var context = connectionFactory.currentConnectionContext();
            context.addPostCommitAction(conn -> emailService.sendOrderConfirmation(id));
            context.addPostRollbackAction((conn, ex) -> logger.error("Order failed", ex));
            
            return new Order(id, order.customerId(), order.items());
        });
    }
}
```

**Use cases:**
- Post-commit: Send notifications, publish events, update cache
- Post-rollback: Log failures, send alerts, cleanup

---

## Custom Transaction Isolation

Set isolation level manually:

```java
public void transferMoney(Long fromId, Long toId, BigDecimal amount) {
    connectionFactory.inTx(connection -> {
        // Set isolation level
        connection.setTransactionIsolation(Connection.TRANSACTION_REPEATABLE_READ);
        
        // Lock accounts for update
        var fromAccount = accountRepository.findByIdForUpdate(fromId);
        var toAccount = accountRepository.findByIdForUpdate(toId);
        
        // Update balances
        accountRepository.updateBalance(fromId, fromAccount.balance().subtract(amount));
        accountRepository.updateBalance(toId, toAccount.balance().add(amount));
    });
}
```

**Isolation levels:**
- `Connection.TRANSACTION_READ_UNCOMMITTED` — dirty reads possible
- `Connection.TRANSACTION_READ_COMMITTED` — PostgreSQL default
- `Connection.TRANSACTION_REPEATABLE_READ` — no non-repeatable reads
- `Connection.TRANSACTION_SERIALIZABLE` — strictest

The default isolation level comes from the Hikari pool `dsProperties`; otherwise set it per transaction via `java.sql.Connection` as shown above.

---

## Configuration via HikariCP

Configure default isolation in `application.conf`:

```hocon
db {
    dsProperties {
        transactionIsolation = "TRANSACTION_READ_COMMITTED"
    }
}
```

Or via environment variable:

```hocon
db {
    dsProperties {
        transactionIsolation = ${TX_ISOLATION:TRANSACTION_READ_COMMITTED}
    }
}
```

---

## Nested transactions

Kora JDBC has no declarative propagation modes — you compose transactions in code. A nested `inTx()` reuses the current connection and joins the outer transaction (it does not start a separate one):

```java
public void processOrder(Order order) {
    connectionFactory.inTx(() -> {
        orderRepository.insert(order);
        
        // Nested transaction (uses same connection)
        connectionFactory.inTx(() -> {
            for (var item : order.items()) {
                inventoryRepository.reserve(item.productId(), item.quantity());
            }
        });
    });
}
```

---

## Common Patterns

### Multi-Repository Transaction

```java
@Component
public class OrderService {
    private final OrderRepository orderRepository;
    private final InventoryRepository inventoryRepository;
    private final JdbcConnectionFactory connectionFactory;
    
    public void createOrderWithItems(Order order, List<OrderItem> items) {
        connectionFactory.inTx(() -> {
            orderRepository.insert(order);
            inventoryRepository.reserveAll(items);
        });
    }
}
```

### Retry on deadlock

Kora's `@Retry` takes a configuration name; attempt count and delays are defined in config under `resilient.retry.<name>`, not as annotation attributes. The retried method must live on a `@Component` so the aspect can wrap it.

```java
@Component
public final class OrderWriter {
    private final OrderRepository repository;
    private final JdbcConnectionFactory connectionFactory;

    public OrderWriter(OrderRepository repository, JdbcConnectionFactory connectionFactory) {
        this.repository = repository;
        this.connectionFactory = connectionFactory;
    }

    @Retry("orderWrite")
    public void updateWithRetry(Order order) {
        connectionFactory.inTx(() -> repository.update(order));
    }
}
```

```hocon
resilient.retry.orderWrite { attempts = 3, delay = "50ms" }
```

`@Retry` requires the resilience module (`ru.tinkoff.kora:resilient-kora`). See the `kora-aop-resilient` skill for the annotation imports and the full configuration surface.

---

## Pitfalls

| Problem | Solution |
|---------|----------|
| Operations outside `inTx()` don't rollback | Wrap all related operations in single `inTx()` |
| Connection leak | Always use try-with-resources or `inTx()` |
| Deadlock on concurrent updates | Use consistent ordering, add retry logic |
| Long-running transactions | Keep transactions short, avoid external calls inside `inTx()` |

---

## See also

- [repository-pattern-reference.md](repository-pattern-reference.md) — `@Repository`, `@Query`, SQL macros
- [connection-pool-reference.md](connection-pool-reference.md) — HikariCP configuration
- `kora-aop-resilient` skill — `@Retry` for deadlock handling
