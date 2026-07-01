# Kora Optional Dependency Reference

**Source:** [Kora Container Documentation](../../../.kora-agent/kora-docs/mkdocs/docs/en/documentation/container.md)

Complete reference for optional dependencies using `@Nullable` and `ValueOf<T>` in Kora applications.

---

## Table of Contents

1. [@Nullable Optional Dependencies](#nullable-optional-dependencies)
2. [ValueOf<T> for Lazy Dependencies](#valueoft-for-lazy-dependencies)
3. [When to Use Each](#when-to-use-each)
4. [Common Patterns](#common-patterns)
5. [Troubleshooting](#troubleshooting)

---

## @Nullable Optional Dependencies

### Basic Usage

Use `@Nullable` when a dependency may not exist in the container.

```java
@Component
public final class UserService {
    private final EmailService emailService;

    public UserService(@Nullable EmailService emailService) {
        this.emailService = emailService;  // May be null
    }

    public void createUser(User user) {
        // Save user
        userRepository.insert(user);

        // Send email if service is available
        if (emailService != null) {
            emailService.sendWelcomeEmail(user);
        }
    }
}
```

### Supported Nullable Annotations

Any of these annotations work:

```java
import javax.annotation.Nullable;
import jakarta.annotation.Nullable;
import org.jetbrains.annotations.Nullable;
import jakarta.annotation.Nullable;
```

### Kotlin Nullability

In Kotlin, use nullable type syntax:

```kotlin
@Component
class UserService(
    private val emailService: EmailService?  // Nullable type
) {
    fun createUser(user: User) {
        userRepository.insert(user)
        emailService?.sendWelcomeEmail(user)  // Safe call
    }
}
```

---

## ValueOf<T> for Lazy Dependencies

### Purpose

`ValueOf<T>` provides lazy access to dependencies with two key benefits:

1. **Breaking circular dependencies** — Lazy reference avoids cycle detection
2. **Preventing cascading refreshes** — Dependency changes don't trigger refresh of dependent component

### API

```java
public interface ValueOf<T> {
    T get();           // Get current instance
    void refresh();    // Force refresh (if refreshable)
}
```

### Basic Usage

```java
@Component
public final class HttpClient {
    private final ValueOf<AuthConfig> config;

    public HttpClient(ValueOf<AuthConfig> config) {
        this.config = config;
        // Config NOT yet accessed
    }

    public Response get(String url) {
        // Access config when needed
        AuthConfig currentConfig = config.get();
        return httpClient.execute(url, currentConfig.getToken());
    }
}
```

---

## Use Case 1: Breaking Circular Dependencies

### Problem

```
ServiceA → ServiceB
    ↑          ↓
    └──────────┘
(Circular dependency error!)
```

### Solution

Use `ValueOf` in one direction:

```java
@Component
public final class ServiceA {
    private final ValueOf<ServiceB> serviceB;

    public ServiceA(ValueOf<ServiceB> serviceB) {
        this.serviceB = serviceB;
    }

    public void doSomething() {
        // Lazy access — cycle avoided
        serviceB.get().doOther();
    }
}

@Component
public final class ServiceB {
    private final ServiceA serviceA;  // Direct dependency

    public ServiceB(ServiceA serviceA) {
        this.serviceA = serviceA;
    }

    public void doOther() {
        serviceA.doSomething();
    }
}
```

**How it works:**
- `ValueOf<ServiceB>` is a lazy reference
- Kora doesn't need ServiceB to create ServiceA
- ServiceB is accessed only when `get()` is called

---

## Use Case 2: Preventing Cascading Refreshes

### Scenario

Config changes at runtime, but you don't want dependent components to refresh.

### Without ValueOf (cascades)

```java
@Component
public final class HttpClient {
    private final AuthConfig config;

    public HttpClient(AuthConfig config) {
        this.config = config;
    }

    // When config refreshes, HttpClient also refreshes
    // This may cause connection pool reset, etc.
}
```

### With ValueOf (no cascade)

```java
@Component
public final class HttpClient {
    private final ValueOf<AuthConfig> config;

    public HttpClient(ValueOf<AuthConfig> config) {
        this.config = config;
    }

    // When config refreshes:
    // - Config is refreshed
    // - HttpClient survives (not refreshed)
    // - HttpClient uses new config via get()
}
```

### When to Use ValueOf

| Scenario | Use ValueOf? | Reason |
|----------|--------------|--------|
| HTTP request handlers | Yes | Handler may refresh, server should survive |
| Config dependencies | Yes | Config changes shouldn't cascade |
| Cache dependencies | Yes | Cache refresh shouldn't cascade |
| Database connections | No | Connection changes should propagate |
| Core services | No | Service changes should be consistent |

---

## Use Case 3: HTTP Server with Request Handlers

Kora HTTP servers use `ValueOf` for request handlers:

```java
@Root
@Component
public final class HttpServer implements Lifecycle {
    private final ValueOf<UserHandler> userHandler;
    private final ValueOf<OrderHandler> orderHandler;

    public HttpServer(
        ValueOf<UserHandler> userHandler,
        ValueOf<OrderHandler> orderHandler
    ) {
        this.userHandler = userHandler;
        this.orderHandler = orderHandler;
    }

    @Override
    public void init() {
        // Start server with current handler versions
        // If handlers are refreshed, server picks up new versions
        router.get("/users", req -> userHandler.get().handle(req));
        router.post("/orders", req -> orderHandler.get().handle(req));
    }

    @Override
    public void release() {
        // Stop server
    }
}
```

**Benefit:** Handler refreshes don't require server restart.

---

## Use Case 4: Lazy Initialization

Delay expensive initialization until first use:

```java
@Component
public final class ReportGenerator {
    private final ValueOf<ExpensiveResource> resource;

    public ReportGenerator(ValueOf<ExpensiveResource> resource) {
        this.resource = resource;
    }

    public Report generate() {
        // Resource only initialized when first report is generated
        ExpensiveResource r = resource.get();
        return r.generateReport();
    }
}
```

---

## Common Patterns

### Pattern 1: Optional Feature Toggle

```java
@Component
public final class AnalyticsService {
    private final AnalyticsTracker tracker;

    public AnalyticsService(@Nullable AnalyticsTracker tracker) {
        this.tracker = tracker;
    }

    public void trackEvent(String event, Map<String, Object> data) {
        if (tracker != null) {
            tracker.track(event, data);
        }
        // Silently skip if tracker not configured
    }
}
```

### Pattern 2: Fallback Implementation

```java
@Component
public final class CacheService {
    private final Cache primaryCache;
    private final Cache fallbackCache;

    public CacheService(
        @Tag(PrimaryTag.class) Cache primaryCache,
        @Nullable @Tag(FallbackTag.class) Cache fallbackCache
    ) {
        this.primaryCache = primaryCache;
        this.fallbackCache = fallbackCache;
    }

    public Object get(String key) {
        // Try primary first
        Object value = primaryCache.get(key);
        if (value != null) {
            return value;
        }

        // Fall back to secondary if available
        if (fallbackCache != null) {
            value = fallbackCache.get(key);
            if (value != null) {
                primaryCache.put(key, value);  // Populate primary
                return value;
            }
        }

        return null;
    }
}
```

### Pattern 3: Configurable Notifications

```java
@Component
public final class OrderService {
    private final OrderRepository repository;
    private final ValueOf<NotificationConfig> config;

    public OrderService(
        OrderRepository repository,
        ValueOf<NotificationConfig> config
    ) {
        this.repository = repository;
        this.config = config;
    }

    public Order createOrder(Order order) {
        Order saved = repository.insert(order);

        // Check config at runtime
        NotificationConfig currentConfig = config.get();
        if (currentConfig.shouldSendConfirmation()) {
            sendConfirmation(saved);
        }

        return saved;
    }

    private void sendConfirmation(Order order) {
        // Send confirmation email/SMS
    }
}
```

### Pattern 4: Optional Metrics

```java
@Component
public final class PaymentProcessor {
    private final PaymentGateway gateway;
    private final MeterRegistry meterRegistry;

    public PaymentProcessor(
        PaymentGateway gateway,
        @Nullable MeterRegistry meterRegistry
    ) {
        this.gateway = gateway;
        this.meterRegistry = meterRegistry;
    }

    public PaymentResult process(Payment payment) {
        long start = System.nanoTime();

        PaymentResult result;
        try {
            result = gateway.process(payment);
        } finally {
            // Record metrics if available
            if (meterRegistry != null) {
                long duration = System.nanoTime() - start;
                meterRegistry.timer("payment.process")
                    .record(duration, TimeUnit.NANOSECONDS);
            }
        }

        return result;
    }
}
```

---

## Troubleshooting

### Null Pointer Exception

**Problem:** `NullPointerException` when using optional dependency

**Solution:** Always check for null before use:

```java
// WRONG: Assuming non-null
public UserService(EmailService emailService) {
    emailService.send();  // May throw NPE!
}

// CORRECT: Null check
public UserService(@Nullable EmailService emailService) {
    if (emailService != null) {
        emailService.send();
    }
}
```

### ValueOf.get() Returns Null

**Problem:** `ValueOf.get()` returns null or throws exception

**Check:**
1. Is the dependency a valid `@Component`?
2. Are all its dependencies satisfied?
3. Is it in a scanned package?

### Circular Dependency Not Resolved

**Problem:** Still getting circular dependency error with ValueOf

**Check:**
1. Is `ValueOf` used in **one direction only**?
2. Is the other direction a direct dependency?
3. Are both components `@Component` annotated?

### Kotlin Null Safety

**Problem:** Kotlin complains about nullable types

**Solution:** Use safe call operator or explicit null check:

```kotlin
// Safe call
emailService?.sendWelcomeEmail(user)

// Or explicit check
if (emailService != null) {
    emailService.sendWelcomeEmail(user)
}
```

---

## See Also

- [SKILL.md](../SKILL.md) — Runtime DI overview
- [GraphInterceptor Reference](graph-interceptor-reference.md) — Component wrapping during graph build
- [Container Documentation](../../../.kora-agent/kora-docs/mkdocs/docs/en/documentation/container.md) — Official docs
