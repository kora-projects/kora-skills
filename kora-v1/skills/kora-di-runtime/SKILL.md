---
name: kora-di-runtime
description: "Covers Kora runtime dependency-injection behavior - the Graph lifecycle, component init/release, disambiguation, collection injection, lazy/optional wrappers, and interception. Use when a component must start without being a dependency (@Root from ru.tinkoff.kora.common.annotation), when implementing init()/release() via Lifecycle or LifecycleWrapper, when disambiguating multiple beans of one interface with @Tag (tag marker class, @Tag(Tag.Any.class)), when collecting every implementation with All<T>, when breaking refresh chains or cycles with ValueOf<T>, when an optional dependency needs @Nullable, or when wrapping a component during graph build with GraphInterceptor. Does not cover compile-time @KoraApp/@Module/@Component wiring (see kora-di-compile)."
---

# Kora DI Runtime — Runtime Injection Behavior

**Kora Version:** 1.x  
**Focus:** Runtime DI — lifecycle, tags, collections, lazy dependencies, interception.

**Read this first when:**
- Marking components as `@Root` for automatic startup
- Implementing `Lifecycle` for init/release logic
- Disambiguating with `@Tag`, collecting with `All<T>`
- Using `ValueOf<T>` for lazy dependencies
- Wrapping components with `GraphInterceptor`

**References:** See `references/` for detailed guides on each topic.

---

## Quick Start

### @Root — Self-Starting Components

Only components that are dependencies of other components, or marked `@Root` (`ru.tinkoff.kora.common.annotation.Root`), are instantiated at runtime. `@Root` goes on a `@Component` class or on a `@KoraApp`/`@Module` factory method.

**When to use @Root:** HTTP/gRPC servers, Kafka consumers, cache warmers, schedulers, startup tasks — anything that must run even though nothing depends on it.

A self-starting worker:
```java
import ru.tinkoff.kora.application.graph.Lifecycle;
import ru.tinkoff.kora.common.Component;
import ru.tinkoff.kora.common.annotation.Root;

@Root
@Component
public final class ServerRunner implements Lifecycle {
    private final ServerConfig config; // a @ConfigSource interface, injected as a component

    public ServerRunner(ServerConfig config) {
        this.config = config;
    }

    @Override
    public void init() throws Exception {
        System.out.println("Starting server on port " + config.port());
        // Bind socket, start accepting traffic
    }

    @Override
    public void release() throws Exception {
        System.out.println("Stopping server");
        // Stop server, release connections
    }
}
```

Config is supplied as a separate `@ConfigSource` component (see `kora-config-hocon`), never as a constructor-parameter annotation:
```java
@ConfigSource("server")
public interface ServerConfig {
    int port();
}
```

**Warning:** Forget `@Root` and a non-dependency worker won't start — the application exits silently after the Graph is built.

> **Learn more:** [`references/root-component-reference.md`](references/root-component-reference.md) — Complete @Root guide with patterns and troubleshooting.

---

## Component Lifecycle

Components with initialization/cleanup logic implement `Lifecycle` (`ru.tinkoff.kora.application.graph.Lifecycle`):

```java
@Root
@Component
public final class DatabasePool implements Lifecycle {
    private final DataSource dataSource;
    private final ScheduledExecutorService scheduler;
    
    public DatabasePool(DataSource dataSource) {
        this.dataSource = dataSource;
        this.scheduler = Executors.newSingleThreadScheduledExecutor();
    }
    
    @Override
    public void init() throws Exception {
        try (Connection conn = dataSource.getConnection()) {
            System.out.println("Database connection OK");
        }
        scheduler.scheduleAtFixedRate(this::cleanup, 5, 5, TimeUnit.MINUTES);
    }
    
    @Override
    public void release() throws Exception {
        scheduler.shutdown();
        if (!scheduler.awaitTermination(30, TimeUnit.SECONDS)) {
            scheduler.shutdownNow();
        }
        if (dataSource instanceof AutoCloseable) {
            ((AutoCloseable) dataSource).close();
        }
    }
}
```

**Key points:**
- `init()` is called after component creation, before use; `release()` during graceful shutdown (SIGTERM)
- Release order is the **reverse** of init order
- Components are initialized as parallel as the dependency Graph allows
- For factory methods, wrap with `LifecycleWrapper` — see [Advanced DI Patterns](references/advanced-di-reference.md) for exact signature

---

## Generic Factories

Generic methods in `@Module` interfaces become "generic factories" usable for ANY matching type. Use deliberately, or move helpers to top-level `private static` methods. See [Advanced DI Patterns](references/advanced-di-reference.md).

> **Learn more:** [`references/lifecycle-reference.md`](references/lifecycle-reference.md) — LifecycleWrapper, graceful shutdown, post-commit actions.

---

## Tags and Collections

### @Tag for Disambiguation

When multiple implementations of one interface exist, use `@Tag` (`ru.tinkoff.kora.common.Tag`) to select which one to inject. The tag is a marker **class**, not a string literal, so navigation and refactoring stay safe:

```java
public final class RedisTag {}
public final class CaffeineTag {}

@Tag(RedisTag.class)
@Component
public final class RedisCache implements Cache {}

@Tag(CaffeineTag.class)
@Component
public final class CaffeineCache implements Cache {}

@Component
public final class UserService {
    private final Cache redisCache;
    private final Cache localCache;
    
    public UserService(
        @Tag(RedisTag.class) Cache redisCache,
        @Tag(CaffeineTag.class) Cache localCache
    ) {
        this.redisCache = redisCache;
        this.localCache = localCache;
    }
}
```

### All<T> for Collections

Inject every untagged implementation of a type. `All<T>` (`ru.tinkoff.kora.application.graph.All`) extends `List<T>`:

```java
import ru.tinkoff.kora.application.graph.All;

@Component
public final class NotificationService {
    private final List<Notifier> notifiers;

    public NotificationService(All<Notifier> notifiers) {
        this.notifiers = List.copyOf(notifiers);
    }

    public void notify(String message) {
        notifiers.forEach(n -> n.send(message));
    }
}
```

To collect **every** implementation including tagged ones, request `@Tag(Tag.Any.class)`:

```java
public NotificationService(@Tag(Tag.Any.class) All<Notifier> notifiers) { ... }
```

`@Tag(SomeTag.class) All<T>` collects only the components registered under `SomeTag`.

> **Learn more:** 
> - [`references/tag-injection-reference.md`](references/tag-injection-reference.md) — @Tag patterns
> - [`references/collection-injection-reference.md`](references/collection-injection-reference.md) — All<T>, Tag.Any patterns

---

## ValueOf<T> — Lazy Dependencies

`ValueOf<T>` (`ru.tinkoff.kora.application.graph.ValueOf`) provides lazy access via `get()` and **decouples lifecycles**: depending on `ValueOf<B>` tells the Graph that this component is NOT refreshed when `B` changes. `ValueOf` also exposes `refresh()`.

```java
import ru.tinkoff.kora.application.graph.ValueOf;

@Component
public final class ApiClient {
    private final ValueOf<AuthConfig> config;

    public ApiClient(ValueOf<AuthConfig> config) {
        this.config = config;
    }

    public Response get(String url) {
        var currentConfig = config.get(); // always the latest instance
        // ApiClient is NOT recreated when AuthConfig refreshes
        return doGet(url, currentConfig);
    }
}
```

**Use cases:** breaking refresh cascades, breaking circular dependencies, lazy access to a component that may not be ready at construction.

Optional dependencies use a `@Nullable` constructor parameter (any `@Nullable`: `jakarta.annotation.Nullable`, `javax.annotation.Nullable`, or `org.jetbrains.annotations.Nullable`); the Graph then tolerates the absence of that component instead of failing the build.

> **Learn more:** [`references/optional-dependency-reference.md`](references/optional-dependency-reference.md) — @Nullable and ValueOf patterns.

---

## GraphInterceptor — Component Wrapping

`GraphInterceptor<T>` (`ru.tinkoff.kora.application.graph.GraphInterceptor`) wraps or modifies a component during graph construction. Its contract mirrors `Lifecycle` except `init`/`release` return the (possibly replaced) instance that other components will then receive:

```java
@Component
public final class MetricsInterceptor implements GraphInterceptor<HttpClient> {
    private final MeterRegistry meterRegistry;
    
    public MetricsInterceptor(MeterRegistry meterRegistry) {
        this.meterRegistry = meterRegistry;
    }
    
    @Override
    public HttpClient init(HttpClient client) {
        return new MetricsHttpClient(client, meterRegistry);
    }
    
    @Override
    public HttpClient release(HttpClient client) {
        return client;
    }
}
```

**Use cases:** Metrics, tracing, circuit breakers, logging proxies.

> **Learn more:** [`references/graph-interceptor-reference.md`](references/graph-interceptor-reference.md) — Complete interceptor patterns.

---

## Common Pitfalls

| Problem | Solution |
|---------|----------|
| HTTP/GRPC server doesn't start | Mark server component with `@Root` |
| Kafka consumer not polling | Mark consumer with `@Root` |
| Component silently not created | Check it's used by `@Root` or marked `@Root` itself |
| Component restarted on config change | Use `ValueOf<T>` for lazy dependency |
| Ambiguous dependency error | Use `@Tag` to disambiguate |
| LifecycleWrapper factory returns wrong type | Return `Wrapped<T>`, use constructor (see [Advanced DI](references/advanced-di-reference.md)) |
| Generic method in @Module causes implicit bindings | Move helpers to top-level `private static` methods (see [Advanced DI](references/advanced-di-reference.md)) |

---

## Checklist

```
- [ ] Component marked @Root if it must start automatically?
- [ ] Implements Lifecycle for init/release logic?
- [ ] Resources properly released in release()?
- [ ] Using @Tag to disambiguate multiple implementations?
- [ ] Using All<T> for untagged collections, @Tag(Tag.Any.class) List<T> for all components?
- [ ] Using ValueOf<T> for lazy dependencies?
- [ ] Using GraphInterceptor for component wrapping?
```

---

## Assets

Templates in `assets/`: `Application`, `RootComponent`, `LifecycleComponent`, `LifecycleFactory`, `TaggedComponent`, `CollectionComponent`, `GraphInterceptor`, `ValueOfComponent`, build configs.
