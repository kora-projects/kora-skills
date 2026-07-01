# Kora Runtime Graph API Reference

**Source:** [Kora Container Documentation](../../../.kora-agent/kora-docs/mkdocs/docs/en/documentation/container.md)

Complete reference for dynamic graph creation and runtime component management in Kora applications.

---

## Table of Contents

1. [KoraApplication Entry Point](#koraapplication-entry-point)
2. [Dynamic Graph Creation](#dynamic-graph-creation)
3. [Graph Refresh Mechanism](#graph-refresh-mechanism)
4. [Runtime Component Updates](#runtime-component-updates)
5. [Common Patterns](#common-patterns)
6. [Troubleshooting](#troubleshooting)

---

## KoraApplication Entry Point

### Basic Application Entry Point

The application entry point calls `KoraApplication.run()` with the graph factory.

```java
@KoraApp
public interface Application {

    static void main(String[] args) {
        KoraApplication.run(ApplicationGraph::graph);
    }
}
```

### Kotlin Entry Point

```kotlin
@KoraApp
interface Application

fun main() {
    KoraApplication.run { ApplicationGraph.graph() }
}
```

### Generated Graph Class

At compile time, Kora generates:
- `ApplicationGraph` class in the same package as `Application`
- `graph()` method returning the dependency graph

---

## Graph Construction

The Graph is constructed at compile time from the `@KoraApp` interface; there is no runtime builder API. `KoraApplication.run` accepts a `Supplier` of the generated graph (`ApplicationGraph::graph`). Configuration is supplied through config sources (HOCON/YAML, environment variables, system properties) declared on the `@KoraApp` via modules such as `HoconConfigModule` — not by setting values programmatically.

### Graph with Modules

```java
@KoraApp
public interface Application extends JsonModule, LogbackModule {

    static void main(String[] args) {
        KoraApplication.run(ApplicationGraph::graph);
    }
}
```

---

## Graph Refresh Mechanism

### ValueOf Refresh

Components using `ValueOf<T>` can be refreshed at runtime:

```java
public interface ValueOf<T> {
    T get();           // Get current instance
    void refresh();    // Force refresh (if refreshable)
}
```

### Config-Driven Refresh

```java
@Component
public final class ConfigReloader implements Lifecycle {
    private final ValueOf<AppConfig> config;
    private final ScheduledExecutorService scheduler;

    public ConfigReloader(ValueOf<AppConfig> config) {
        this.config = config;
        this.scheduler = Executors.newSingleThreadScheduledExecutor();
    }

    @Override
    public void init() {
        // Check for config changes every minute
        scheduler.scheduleAtFixedRate(
            this::checkAndRefresh,
            1, 1, TimeUnit.MINUTES
        );
    }

    @Override
    public void release() {
        scheduler.shutdown();
    }

    private void checkAndRefresh() {
        if (configFileChanged()) {
            config.refresh();  // Trigger refresh chain
        }
    }

    private boolean configFileChanged() {
        // Check file modification time
        return true;
    }
}
```

---

## Runtime Component Updates

### Atomic Graph Updates

Kora updates components atomically:

1. Transaction begins
2. All affected components are refreshed
3. If all succeed, transaction commits
4. If any fail, transaction rolls back

### Update Propagation

```
Config Changed
      ↓
ValueOf<Config>.refresh()
      ↓
Components depending on Config (via direct dependency)
      ↓
Components depending on those components
      ↓
...propagates through dependency graph
```

**Note:** Components using `ValueOf<T>` do NOT cascade refreshes.

---

## Common Patterns

### Pattern 1: File Watcher for Hot Reload

```java
@Root
@Component
public final class FileWatcher implements Lifecycle {
    private final WatchService watchService;
    private final ValueOf<AppConfig> config;
    private final ExecutorService executor;

    public FileWatcher(ValueOf<AppConfig> config) throws IOException {
        this.config = config;
        this.watchService = FileSystems.getDefault().newWatchService();
        this.executor = Executors.newSingleThreadExecutor();

        Path path = Paths.get(config.get().path()).getParent();
        path.register(watchService, StandardWatchEventKinds.ENTRY_MODIFY);
    }

    @Override
    public void init() {
        executor.submit(this::watchForChanges);
    }

    @Override
    public void release() throws Exception {
        executor.shutdown();
        watchService.close();
    }

    private void watchForChanges() {
        while (!executor.isShutdown()) {
            try {
                WatchKey key = watchService.take();
                for (WatchEvent<?> event : key.pollEvents()) {
                    if (event.context().toString().equals("app.conf")) {
                        config.refresh();  // Refresh config
                    }
                }
                key.reset();
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                break;
            }
        }
    }
}
```

### Pattern 2: Admin Endpoint for Refresh

```java
@Component
public final class AdminHandler {
    private final Map<String, Runnable> refreshActions = new ConcurrentHashMap<>();

    public AdminHandler(All<Refreshable> refreshables) {
        for (Refreshable r : refreshables) {
            refreshActions.put(r.getName(), r::refresh);
        }
    }

    public Response refresh(String component) {
        Runnable action = refreshActions.get(component);
        if (action == null) {
            return Response.notFound("Component not found: " + component);
        }
        action.run();
        return Response.ok("Refreshed: " + component);
    }
}

public interface Refreshable {
    String getName();
    void refresh();
}
```

### Pattern 3: Feature Toggle Refresh

```java
@Component
public final class FeatureToggleService implements Refreshable {
    private volatile Map<String, Boolean> toggles = new HashMap<>();

    public FeatureToggleService() {
        loadToggles();
    }

    @Override
    public String getName() {
        return "feature-toggles";
    }

    @Override
    public void refresh() {
        loadToggles();
    }

    public boolean isEnabled(String feature) {
        return toggles.getOrDefault(feature, false);
    }

    private void loadToggles() {
        // Load from config file, database, or remote service
        toggles = loadFromRemote();
    }
}
```

---

## Troubleshooting

### Refresh Not Propagating

**Problem:** Component not updating after refresh

**Check:**
1. Is dependency injected via `ValueOf<T>`? (won't cascade)
2. Is direct dependency used? (will cascade)
3. Is refresh being called?

### Refresh Causing Downtime

**Problem:** Service interruption during refresh

**Solution:** Use graceful refresh pattern:

```java
@Component
public final class GracefulHandler implements Refreshable {
    private volatile Handler current;
    private volatile Handler next;

    @Override
    public void refresh() {
        // Create new handler
        next = createNewHandler();

        // Switch atomically
        Handler old = current;
        current = next;

        // Cleanup old handler after drain period
        scheduleCleanup(old);
    }
}
```

### Circular Refresh

**Problem:** Infinite refresh loop

**Solution:** Break cycle with `ValueOf`:

```java
// WRONG: Circular refresh
@Component
public class A { ValueOf<B> b; }  // B refreshes A
@Component
public class B { ValueOf<A> a; }  // A refreshes B

// CORRECT: One direction only
@Component
public class A { ValueOf<B> b; }  // B refreshes A
@Component
public class B { /* no ValueOf<A> */ }
```

---

## See Also

- [SKILL.md](../SKILL.md) — Runtime DI overview
- [Optional Dependency Reference](optional-dependency-reference.md) — @Nullable and ValueOf lazy dependencies
- [Container Documentation](../../../.kora-agent/kora-docs/mkdocs/docs/en/documentation/container.md) — Official docs
