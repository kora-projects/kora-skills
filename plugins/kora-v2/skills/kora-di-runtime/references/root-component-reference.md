# Kora @Root Component Reference

**Source:** [Kora Container Documentation](../../../.kora-agent/kora-docs/mkdocs/docs/en/documentation/container.md)

Complete reference for `@Root` components — auto-starting components in Kora applications.

---

## Table of Contents

1. [@Root Annotation](#root-annotation)
2. [When to Use @Root](#when-to-use-root)
3. [How @Root Works](#how-root-works)
4. [Common Patterns](#common-patterns)
5. [Troubleshooting](#troubleshooting)

---

## @Root Annotation

`@Root` marks a component that must be instantiated at application startup, even if nothing depends on it.

```java
@Root
@Component
public final class HttpServer implements Lifecycle {
    // This component will be created and init() called
}
```

**Without @Root:** Component is only created if another component depends on it.

**With @Root:** Component is always created and started.

---

## When to Use @Root

| Component Type | Needs @Root? | Why |
|----------------|--------------|-----|
| HTTP/GRPC Server | Yes | Must start listening |
| Kafka Consumer | Yes | Must begin polling |
| Cache Warmer | Yes | Must pre-load data |
| Health Checker | Yes | Must register checks |
| Background Scheduler | Yes | Must start scheduling |
| Metrics Reporter | Yes | Must start reporting |
| Service/Repository | No | Only needed if depended upon |
| DTO/Entity | No | Not a component |

### HTTP Server Example

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
    }

    @Override
    public void release() throws Exception {
        System.out.println("Stopping HTTP server");
        server.stop();
    }
}
```

### Kafka Consumer Example

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

### Cache Warmer Example

```java
@Root
@Component
public final class CacheWarmer implements Lifecycle {
    private final Cache cache;
    private final Database db;

    public CacheWarmer(Cache cache, Database db) {
        this.cache = cache;
        this.db = db;
    }

    @Override
    public void init() {
        System.out.println("Warming up cache");
        var data = db.loadAll();
        data.forEach(item -> cache.put(item.getId(), item));
        System.out.println("Cache warmed with " + data.size() + " items");
    }

    @Override
    public void release() {
        System.out.println("Clearing cache");
        cache.invalidateAll();
    }
}
```

### Health Checker Example

```java
@Root
@Component
public final class HealthChecker implements Lifecycle {
    private final ScheduledExecutorService scheduler;
    private final All<HealthCheck> healthChecks;

    public HealthChecker(All<HealthCheck> healthChecks) {
        this.healthChecks = healthChecks;
        this.scheduler = Executors.newSingleThreadScheduledExecutor();
    }

    @Override
    public void init() {
        // Initial check
        checkAll();
        // Schedule periodic checks
        scheduler.scheduleAtFixedRate(
            this::checkAll,
            1, 1, TimeUnit.MINUTES
        );
    }

    @Override
    public void release() {
        scheduler.shutdown();
    }

    private void checkAll() {
        for (HealthCheck check : healthChecks) {
            try {
                check.run();
            } catch (Exception e) {
                System.err.println("Health check failed: " + check.name());
            }
        }
    }
}
```

---

## How @Root Works

```
Application Start
    ↓
KoraApplication.run(graphFactory)
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

**Key points:**

1. `@Root` components are instantiated **after** their dependencies
2. `init()` is called on all `Lifecycle` components in dependency order
3. `release()` is called in **reverse order** of creation
4. Application stays alive as long as `@Root` components are running

---

## Common Patterns

### Pattern 1: Server with All Handlers

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

### Pattern 2: Scheduler with Periodic Task

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

### Pattern 3: Multiple @Root Components

```java
// All three components will start
@Root
@Component
public final class HttpServer implements Lifecycle { /* ... */ }

@Root
@Component
public final class KafkaConsumer implements Lifecycle { /* ... */ }

@Root
@Component
public final class GrpcServer implements Lifecycle { /* ... */ }
```

**Note:** All `@Root` components initialize in parallel (as much as dependencies allow).

---

## Troubleshooting

### Application Exits Immediately

**Problem:** Application starts and exits without doing anything

**Check:**
1. Is your HTTP/Kafka/gRPC server marked with `@Root`?
2. Is the server component implementing `Lifecycle`?
3. Is `init()` starting the server?

```java
// WRONG: App exits immediately
@Component
public final class HttpServer implements Lifecycle { /* ... */ }

// CORRECT: App stays alive
@Root
@Component
public final class HttpServer implements Lifecycle { /* ... */ }
```

### @Root Component Not Initialized

**Problem:** `init()` not called

**Check:**
1. Is component annotated with both `@Root` AND `@Component`?
2. Is component in a scanned package?
3. Are all dependencies satisfied?

### Wrong Init Order

**Problem:** Component tries to use dependency before it's ready

**Solution:** Add explicit dependency in constructor:

```java
@Root
@Component
public final class CacheWarmer implements Lifecycle {
    private final Cache cache;
    private final Database db;

    // Database will be init'd first (dependency)
    public CacheWarmer(Cache cache, Database db) {
        this.cache = cache;
        this.db = db;
    }
}
```

### Shutdown Not Graceful

**Problem:** Resources not released on shutdown

**Solution:** Implement `release()` properly:

```java
@Override
public void release() {
    // 1. Stop accepting new work
    // 2. Wait for in-flight work to complete
    // 3. Close resources
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
```

---

## See Also

- [SKILL.md](../SKILL.md) — Runtime DI overview
- [Lifecycle Reference](lifecycle-reference.md) — Lifecycle interface, init/release
- [Container Documentation](../../../.kora-agent/kora-docs/mkdocs/docs/en/documentation/container.md) — Official docs
