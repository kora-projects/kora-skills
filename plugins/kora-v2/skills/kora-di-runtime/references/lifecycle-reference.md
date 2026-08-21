# Kora Lifecycle Reference

**Source:** [Kora Container Documentation](../../../.kora-agent/kora-docs/mkdocs/docs/en/documentation/container.md)

Complete reference for component lifecycle management in Kora applications.

---

## Table of Contents

1. [Lifecycle Interface](#lifecycle-interface)
2. [LifecycleWrapper for Factories](#lifecyclewrapper-for-factories)
3. [@Root Components](#root-components)
4. [Graceful Shutdown](#graceful-shutdown)
5. [Post-Commit/Rollback Actions](#post-commitrollback-actions)
6. [Common Patterns](#common-patterns)
7. [Troubleshooting](#troubleshooting)

---

## Lifecycle Interface

### Contract

```java
public interface Lifecycle {
    void init() throws Exception;
    void release() throws Exception;
}
```

### Method Timing

| Method | When Called | Purpose |
|--------|-------------|---------|
| `init()` | After component creation, before use | Initialize resources, warm caches, start background tasks |
| `release()` | During shutdown (SIGTERM) | Cleanup resources, stop tasks, close connections |

### Order Guarantees

- **Init order**: Topological (dependencies initialized first)
- **Release order**: Reverse of creation order

### Example: HTTP Server

```java
@Root
@Component
public final class HttpServer implements Lifecycle {
    private final Server server;
    private final int port;

    public HttpServer(
        HttpServerConfig config, // a @ConfigSource("http") interface, injected as a component
        Handler handler
    ) {
        this.port = config.port();
        this.server = new Server(port, handler);
    }

    @Override
    public void init() throws Exception {
        System.out.println("Starting HTTP server on port " + port);
        server.start();
        System.out.println("HTTP server started");
    }

    @Override
    public void release() throws Exception {
        System.out.println("Stopping HTTP server");
        server.stop();
        System.out.println("HTTP server stopped");
    }
}
```

### Example: Kafka Consumer

```java
@Root
@Component
public final class KafkaConsumer implements Lifecycle {
    private final KafkaListener listener;
    private final ExecutorService executor;

    public KafkaConsumer(KafkaListener listener) {
        this.listener = listener;
        this.executor = Executors.newSingleThreadExecutor();
    }

    @Override
    public void init() {
        System.out.println("Starting Kafka consumer");
        executor.submit(() -> {
            while (!executor.isShutdown()) {
                var records = listener.poll(Duration.ofMillis(100));
                records.forEach(this::process);
            }
        });
    }

    @Override
    public void release() {
        System.out.println("Stopping Kafka consumer");
        executor.shutdown();
        try {
            if (!executor.awaitTermination(30, TimeUnit.SECONDS)) {
                executor.shutdownNow();
            }
        } catch (InterruptedException e) {
            executor.shutdownNow();
            Thread.currentThread().interrupt();
        }
    }

    private void process(ConsumerRecord<String, String> record) {
        // Process message
    }
}
```

---

## LifecycleWrapper for Factories

When factory methods need to provide lifecycle for components that don't implement `Lifecycle`:

### Basic Usage

```java
@Module
public interface CacheModule {

    default Wrapped<Cache> cache(Config config) {
        var cacheConfig = config.getConfig("cache");
        var cache = new CaffeineCache(cacheConfig);

        return new LifecycleWrapper<>(
            cache,
            c -> c.warmup(),           // Init hook
            c -> c.invalidateAll()     // Release hook
        );
    }
}
```

### Async Lifecycle

```java
@Module
public interface SchedulerModule {

    default Wrapped<ScheduledExecutorService> scheduler() {
        return new LifecycleWrapper<>(
            Executors.newSingleThreadScheduledExecutor(),
            scheduler -> {
                // Schedule periodic task
                scheduler.scheduleAtFixedRate(
                    this::cleanupTask,
                    0, 1, TimeUnit.HOURS
                );
            },
            scheduler -> {
                // Graceful shutdown
                scheduler.shutdown();
                if (!scheduler.awaitTermination(30, TimeUnit.SECONDS)) {
                    scheduler.shutdownNow();
                }
            }
        );
    }

    private void cleanupTask() {
        // Cleanup logic
    }
}
```

### DataSource with Connection Test

```java
@Module
public interface DatabaseModule {

    default Wrapped<DataSource> dataSource(DatabaseConfig config) {
        var ds = new DriverManagerDataSource(
            config.url(),
            config.username(),
            config.password()
        );

        return new LifecycleWrapper<>(
            ds,
            dataSource -> {
                // Init: test connection
                try (Connection conn = dataSource.getConnection()) {
                    System.out.println("Database connection OK");
                }
            },
            dataSource -> {
                // Release: close connections
                if (dataSource instanceof AutoCloseable) {
                    ((AutoCloseable) dataSource).close();
                }
            }
        );
    }
}
```

---

## @Root Components

### When to Use @Root

Mark a component with `@Root` when it must be instantiated at runtime even if nothing depends on it:

| Component Type | Needs @Root? | Why |
|----------------|--------------|-----|
| HTTP/GRPC Server | Yes | Must start listening |
| Kafka Consumer | Yes | Must begin polling |
| Cache Warmer | Yes | Must pre-load data |
| Health Checker | Yes | Must register checks |
| Background Scheduler | Yes | Must start scheduling |
| Service/Repository | No | Only needed if depended upon |

### How @Root Works

```
Application Start
    ↓
Build Dependency Graph
    ↓
Instantiate Components
    ├── Dependencies of @Root components
    └── @Root components themselves
    ↓
Call init() on all Lifecycle components
    ↓
Application Running
    ↓
[SIGTERM received]
    ↓
Call release() in reverse order
    ↓
Application Exit
```

### Common Mistake

```java
// WRONG: Server won't start without @Root
@Component
public final class HttpServer implements Lifecycle {
    // ... never instantiated, app exits immediately
}

// CORRECT
@Root
@Component
public final class HttpServer implements Lifecycle {
    // ... instantiated and started
}
```

---

## Graceful Shutdown

Kora supports graceful shutdown via SIGTERM:

### Shutdown Sequence

1. SIGTERM signal received
2. `release()` called on all `Lifecycle` components
3. Release order: reverse of creation order
4. Exceptions in `release()` are logged but don't stop shutdown
5. After all `release()` complete, JVM exits

### Best Practices

```java
@Root
@Component
public final class MessageProcessor implements Lifecycle {
    private final ExecutorService executor;
    private final MessageQueue queue;

    public MessageProcessor(MessageQueue queue) {
        this.queue = queue;
        this.executor = Executors.newFixedThreadPool(10);
    }

    @Override
    public void init() {
        // Start processing
        executor.submit(this::processMessages);
    }

    @Override
    public void release() {
        // 1. Stop accepting new messages
        queue.close();

        // 2. Shutdown executor gracefully
        executor.shutdown();
        try {
            // Wait for in-flight messages
            if (!executor.awaitTermination(30, TimeUnit.SECONDS)) {
                executor.shutdownNow();
            }
        } catch (InterruptedException e) {
            executor.shutdownNow();
            Thread.currentThread().interrupt();
        }
    }

    private void processMessages() {
        while (!executor.isShutdown()) {
            var msg = queue.poll();
            if (msg != null) {
                process(msg);
            }
        }
    }
}
```

---

## Post-Commit/Rollback Actions

For JDBC transactions, register actions to run after commit or rollback:

### Basic Usage

```java
@Inject
private JdbcConnectionFactory connectionFactory;
@Inject
private EmailService emailService;

public void createUser(User user) {
    connectionFactory.inTx(() -> {
        // Insert user
        userRepository.insert(user);

        // Register post-commit action
        var context = connectionFactory.currentConnectionContext();
        context.addPostCommitAction(() ->
            emailService.sendWelcomeEmail(user)
        );

        // Register post-rollback action
        context.addPostRollbackAction(() ->
            log.error("Failed to create user: {}", user.getId())
        );
    });
}
```

### Use Cases

| Scenario | Post-Commit | Post-Rollback |
|----------|-------------|---------------|
| User registration | Send welcome email | Log failure |
| Order placement | Send confirmation | Notify customer service |
| Payment processing | Send receipt | Alert fraud team |
| Cache invalidation | Invalidate related caches | Log for debugging |

---

## Common Patterns

### Pattern 1: Server with Dependencies

```java
@Root
@Component
public final class GrpcServer implements Lifecycle {
    private final Server server;

    public GrpcServer(
        GrpcServerConfig config, // a @ConfigSource("grpc") interface, injected as a component
        All<BindableService> services
    ) {
        var builder = ServerBuilder.forPort(config.port());
        services.forEach(builder::addService);
        this.server = builder.build();
    }

    @Override
    public void init() throws Exception {
        server.start();
        System.out.println("gRPC server started");
    }

    @Override
    public void release() throws Exception {
        server.shutdown();
        server.awaitTermination();
    }
}
```

### Pattern 2: Periodic Task

```java
@Root
@Component
public final class DataSyncer implements Lifecycle {
    private final ScheduledExecutorService scheduler;
    private final DataSyncService syncService;

    public DataSyncer(DataSyncService syncService) {
        this.syncService = syncService;
        this.scheduler = Executors.newSingleThreadScheduledExecutor();
    }

    @Override
    public void init() {
        // Sync immediately
        syncService.sync();

        // Then every hour
        scheduler.scheduleAtFixedRate(
            syncService::sync,
            1, 1, TimeUnit.HOURS
        );
    }

    @Override
    public void release() {
        scheduler.shutdown();
        try {
            if (!scheduler.awaitTermination(30, TimeUnit.SECONDS)) {
                scheduler.shutdownNow();
            }
        } catch (InterruptedException e) {
            scheduler.shutdownNow();
            Thread.currentThread().interrupt();
        }
    }
}
```

### Pattern 3: Resource Pool

```java
@Root
@Component
public final class ConnectionPool implements Lifecycle {
    private final Pool<Connection> pool;

    public ConnectionPool(PoolConfig config) {
        this.pool = createPool(config);
    }

    @Override
    public void init() throws Exception {
        // Warm up pool
        for (int i = 0; i < pool.getMinSize(); i++) {
            pool.add(createConnection());
        }
        System.out.println("Connection pool warmed up");
    }

    @Override
    public void release() throws Exception {
        // Close all connections
        pool.clear();
        System.out.println("Connection pool closed");
    }

    public Connection acquire() {
        return pool.acquire();
    }

    public void release(Connection conn) {
        pool.release(conn);
    }
}
```

---

## Troubleshooting

### Component Not Starting

**Problem:** HTTP server/Kafka consumer not starting

**Check:**
1. Is it marked with `@Root`?
2. Does it implement `Lifecycle`?
3. Is `init()` being called (add logging)?

### Resource Leak

**Problem:** Connections/threads not closed on shutdown

**Check:**
1. Is `release()` implemented?
2. Are all resources closed in `release()`?
3. Is shutdown graceful (awaitTermination)?

### Wrong Init Order

**Problem:** Component tries to use dependency before it's ready

**Solution:** Add explicit dependency in constructor:
```java
public MyComponent(Dependency dep) {  // Dep will be init'd first
    // ...
}
```

### Release Order Issue

**Problem:** Component tries to use dependency that's already released

**Solution:** Remember: release order is reverse of creation. If A depends on B:
- Init: B first, then A
- Release: A first, then B

### Transaction Hook Not Called

**Problem:** Post-commit action not executing

**Check:**
1. Is transaction committed (not rolled back)?
2. Is hook registered inside `inTx()`?
3. Is exception in hook handled?

---

## See Also

- [SKILL.md](../SKILL.md) — Runtime DI overview
- [Tag Injection Reference](tag-injection-reference.md) — @Tag disambiguation patterns
- [Collection Injection Reference](collection-injection-reference.md) — All<T> and @Tag(Tag.Any.class)
- [Container Documentation](../../../.kora-agent/kora-docs/mkdocs/docs/en/documentation/container.md) — Official docs
