# Kora GraphInterceptor Reference

**Source:** [Kora Container Documentation](../../../.kora-agent/kora-docs/mkdocs/docs/en/documentation/container.md)

Complete reference for component wrapping and modification using `GraphInterceptor` in Kora applications.

---

## Table of Contents

1. [GraphInterceptor Interface](#graphinterceptor-interface)
2. [Basic Usage](#basic-usage)
3. [Common Patterns](#common-patterns)
4. [Lifecycle vs GraphInterceptor](#lifecycle-vs-graphinterceptor)
5. [Troubleshooting](#troubleshooting)

---

## GraphInterceptor Interface

### Purpose

`GraphInterceptor<T>` wraps/modifies components during graph construction.

```java
public interface GraphInterceptor<T> {
    T init(T value) throws Exception;      // Called on component init
    T release(T value) throws Exception;   // Called on component release
}
```

**Key capability:** `init()` may return a **different instance** (proxy, wrapper, decorator).

### How It Works

```
Component Created
       ↓
GraphInterceptor.init() called
       ↓
Interceptor may return:
  - Same instance (after modification)
  - Wrapped instance (proxy, decorator)
  - Completely different instance
       ↓
Returned instance used by downstream components
       ↓
[Shutdown]
       ↓
GraphInterceptor.release() called
```

---

## Basic Usage

### Cache Warmup Interceptor

```java
@Component
public final class CacheWarmupInterceptor implements GraphInterceptor<JdbcDatabase> {

    @Override
    public JdbcDatabase init(JdbcDatabase db) {
        // Warm cache on init
        warmupCache(db);
        return db;  // Return same instance
    }

    @Override
    public JdbcDatabase release(JdbcDatabase db) {
        // Cleanup on release
        return db;
    }

    private void warmupCache(JdbcDatabase db) {
        // Pre-load frequently used data
        var热门数据 = db.query("SELECT * FROM popular_items LIMIT 100");
        // Cache the results...
    }
}
```

---

## Common Patterns

### Pattern 1: Metrics Wrapper

Wrap component with timing/metrics:

```java
@Component
public final class MetricsInterceptor implements GraphInterceptor<HttpClient> {
    private final MeterRegistry meterRegistry;

    public MetricsInterceptor(MeterRegistry meterRegistry) {
        this.meterRegistry = meterRegistry;
    }

    @Override
    public HttpClient init(HttpClient client) {
        // Return wrapped client with metrics
        return new MetricsHttpClient(client, meterRegistry);
    }

    @Override
    public HttpClient release(HttpClient client) {
        return client;
    }
}

// Wrapper implementation
public final class MetricsHttpClient implements HttpClient {
    private final HttpClient delegate;
    private final MeterRegistry registry;

    public MetricsHttpClient(HttpClient delegate, MeterRegistry registry) {
        this.delegate = delegate;
        this.registry = registry;
    }

    @Override
    public Response get(String url) {
        var timer = registry.timer("http.client.get");
        return timer.record(() -> delegate.get(url));
    }

    @Override
    public Response post(String url, String body) {
        var timer = registry.timer("http.client.post");
        return timer.record(() -> delegate.post(url, body));
    }
}
```

### Pattern 2: Circuit Breaker

Add fault tolerance wrapper:

```java
@Component
public final class CircuitBreakerInterceptor implements GraphInterceptor<ExternalService> {
    private final ResilienceRegistry registry;

    public CircuitBreakerInterceptor(ResilienceRegistry registry) {
        this.registry = registry;
    }

    @Override
    public ExternalService init(ExternalService service) {
        // Wrap with circuit breaker
        return registry.circuitBreaker(service, "external-service");
    }

    @Override
    public ExternalService release(ExternalService service) {
        return service;
    }
}
```

### Pattern 3: Logging Proxy

Add method call logging:

```java
@Component
public final class LoggingInterceptor implements GraphInterceptor<PaymentService> {
    private static final Logger log = LoggerFactory.getLogger(PaymentService.class);

    @Override
    public PaymentService init(PaymentService service) {
        return new PaymentServiceProxy(service);
    }

    @Override
    public PaymentService release(PaymentService service) {
        return service;
    }

    // Proxy implementation
    private static class PaymentServiceProxy implements PaymentService {
        private final PaymentService delegate;

        PaymentServiceProxy(PaymentService delegate) {
            this.delegate = delegate;
        }

        @Override
        public PaymentResult process(PaymentRequest request) {
            log.info("Processing payment: {}", request.getId());
            try {
                var result = delegate.process(request);
                log.info("Payment processed: {}", request.getId());
                return result;
            } catch (Exception e) {
                log.error("Payment failed: {}", request.getId(), e);
                throw e;
            }
        }
    }
}
```

### Pattern 4: Distributed Tracing

Add tracing to all components:

```java
@Component
public final class TracingInterceptor implements GraphInterceptor<EventHandler> {
    private final Tracer tracer;

    public TracingInterceptor(Tracer tracer) {
        this.tracer = tracer;
    }

    @Override
    public EventHandler init(EventHandler handler) {
        return new TracingEventHandler(handler, tracer);
    }

    @Override
    public EventHandler release(EventHandler handler) {
        return handler;
    }

    // Tracing wrapper
    private static final class TracingEventHandler implements EventHandler {
        private final EventHandler delegate;
        private final Tracer tracer;

        TracingEventHandler(EventHandler delegate, Tracer tracer) {
            this.delegate = delegate;
            this.tracer = tracer;
        }

        @Override
        public void handle(Event event) {
            var span = tracer.startSpan("event.handle");
            span.setTag("event.type", event.getType());
            try {
                delegate.handle(event);
            } finally {
                span.end();
            }
        }
    }
}
```

### Pattern 5: Validation Wrapper

Add pre/post validation:

```java
@Component
public final class ValidationInterceptor implements GraphInterceptor<UserService> {
    private final Validator validator;

    public ValidationInterceptor(Validator validator) {
        this.validator = validator;
    }

    @Override
    public UserService init(UserService service) {
        return new ValidatingUserService(service, validator);
    }

    @Override
    public UserService release(UserService service) {
        return service;
    }

    // Validation wrapper
    private static final class ValidatingUserService implements UserService {
        private final UserService delegate;
        private final Validator validator;

        ValidatingUserService(UserService delegate, Validator validator) {
            this.delegate = delegate;
            this.validator = validator;
        }

        @Override
        public User create(CreateUserRequest request) {
            // Validate request
            validator.validate(request);
            return delegate.create(request);
        }

        @Override
        public User update(UpdateUserRequest request) {
            // Validate request
            validator.validate(request);
            return delegate.update(request);
        }
    }
}
```

### Pattern 6: Retry Wrapper

Add retry logic:

```java
@Component
public final class RetryInterceptor implements GraphInterceptor<DatabaseService> {
    private final int maxRetries;
    private final Duration delay;

    public RetryInterceptor(RetryConfig config) { // a @ConfigSource("retry") interface
        this.maxRetries = config.maxAttempts();
        this.delay = Duration.ofMillis(config.delayMs());
    }

    @Override
    public DatabaseService init(DatabaseService service) {
        return new RetryDatabaseService(service, maxRetries, delay);
    }

    @Override
    public DatabaseService release(DatabaseService service) {
        return service;
    }

    // Retry wrapper
    private static final class RetryDatabaseService implements DatabaseService {
        private final DatabaseService delegate;
        private final int maxRetries;
        private final Duration delay;

        RetryDatabaseService(DatabaseService delegate, int maxRetries, Duration delay) {
            this.delegate = delegate;
            this.maxRetries = maxRetries;
            this.delay = delay;
        }

        @Override
        public <T> T execute(Query<T> query) {
            int attempts = 0;
            Exception lastException = null;

            while (attempts < maxRetries) {
                try {
                    return delegate.execute(query);
                } catch (TransientException e) {
                    lastException = e;
                    attempts++;
                    try {
                        Thread.sleep(delay.toMillis());
                    } catch (InterruptedException ie) {
                        Thread.currentThread().interrupt();
                        throw new RuntimeException("Retry interrupted", ie);
                    }
                }
            }

            throw new RuntimeException("Query failed after " + maxRetries + " attempts", lastException);
        }
    }
}
```

### Pattern 7: Async Interceptor

Add async behavior:

```java
@Component
public final class AsyncInterceptor implements GraphInterceptor<EventHandler> {
    private final ExecutorService executor;

    public AsyncInterceptor() {
        this.executor = Executors.newFixedThreadPool(10);
    }

    @Override
    public EventHandler init(EventHandler handler) {
        return new AsyncEventHandler(handler, executor);
    }

    @Override
    public EventHandler release(EventHandler handler) {
        return handler;
    }

    // Async wrapper
    private static final class AsyncEventHandler implements EventHandler {
        private final EventHandler delegate;
        private final ExecutorService executor;

        AsyncEventHandler(EventHandler delegate, ExecutorService executor) {
            this.delegate = delegate;
            this.executor = executor;
        }

        @Override
        public void handle(Event event) {
            executor.submit(() -> delegate.handle(event));
        }
    }
}
```

### Pattern 8: Composite Interceptor Chain

Multiple interceptors are applied automatically:

```java
// All interceptors for HttpClient
@Component
public class MetricsInterceptor implements GraphInterceptor<HttpClient> { /* ... */ }

@Component
public class TracingInterceptor implements GraphInterceptor<HttpClient> { /* ... */ }

@Component
public class CircuitBreakerInterceptor implements GraphInterceptor<HttpClient> { /* ... */ }

// Result: HttpClient is wrapped with metrics → tracing → circuit breaker
// Order is determined by Kora's graph construction
```

---

## Lifecycle vs GraphInterceptor

| Aspect | Lifecycle | GraphInterceptor |
|--------|-----------|------------------|
| Purpose | Init/release hooks | Component wrapping/modification |
| Can modify instance | No | Yes (return different instance) |
| Use case | Resource management | Cross-cutting concerns |
| Example | Start/stop server | Add metrics, tracing, circuit breaker |
| Applied to | Component itself | External interceptor |

### When to Use Which

| Scenario | Use |
|----------|-----|
| Component needs init/release logic | `Lifecycle` |
| Factory method needs lifecycle | `LifecycleWrapper` |
| Wrap/modify component instance | `GraphInterceptor` |
| Add cross-cutting concern (metrics, tracing) | `GraphInterceptor` |
| Component-specific initialization | `Lifecycle` (on component) |
| External modification of component | `GraphInterceptor` |

---

## Troubleshooting

### Interceptor Not Applied

**Problem:** Component not wrapped by interceptor

**Check:**
1. Is interceptor marked with `@Component`?
2. Does generic type match component type exactly?
3. Is interceptor in a scanned package?

### Wrapper Breaking Component

**Problem:** Wrapped component doesn't work correctly

**Check:**
1. Does wrapper delegate all methods correctly?
2. Are interfaces properly implemented?
3. Is state properly transferred?

### Circular Dependency in Interceptor

**Problem:** Interceptor creates circular dependency

**Solution:** Use `ValueOf` for dependencies in interceptor:

```java
@Component
public final class MetricsInterceptor implements GraphInterceptor<HttpClient> {
    private final ValueOf<MeterRegistry> meterRegistry;

    public MetricsInterceptor(ValueOf<MeterRegistry> meterRegistry) {
        this.meterRegistry = meterRegistry;
    }

    @Override
    public HttpClient init(HttpClient client) {
        return new MetricsHttpClient(client, meterRegistry.get());
    }

    @Override
    public HttpClient release(HttpClient client) {
        return client;
    }
}
```

### Performance Overhead

**Problem:** Interceptor causing latency

**Solutions:**
1. Minimize work in `init()`/`release()`
2. Use async processing for heavy operations
3. Consider sampling for high-frequency operations

### Multiple Interceptors Order

**Problem:** Need specific order of interceptor application

**Solution:** Kora applies interceptors in deterministic order, but if you need specific ordering, consider:

1. Combining interceptors into one
2. Using a single composite interceptor
3. Documenting expected order in code comments

---

## See Also

- [SKILL.md](../SKILL.md) — Runtime DI overview
- [Lifecycle Reference](lifecycle-reference.md) — Lifecycle interface patterns
- [Optional Dependency Reference](optional-dependency-reference.md) — @Nullable and ValueOf lazy dependencies
- [Container Documentation](../../../.kora-agent/kora-docs/mkdocs/docs/en/documentation/container.md) — Official docs
