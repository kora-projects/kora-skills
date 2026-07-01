# Authentication & Principal in Kora HTTP Server

**Kora Version:** 1.2.x

This reference covers custom authentication patterns for Kora HTTP server, including the recommended interceptor-based approach and the limitations of `HttpServerPrincipalExtractor` in Kora 1.2.x.

---

## Overview

Kora 1.2.x does **NOT** auto-bridge `HttpServerPrincipalExtractor` to controller method parameters. Using `Principal` as a controller parameter causes:

1. The HTTP-server KSP to treat it as a request body
2. Required dependency type errors during graph build
3. 401 errors downgraded to 400 (because extractor exceptions are wrapped)

**Recommended pattern:** Authenticate in a global `@Tag(HttpServerModule)` interceptor, store the principal in `Context`, and read it in controllers via `Principal.current()`.

---

## Principal Pattern via Interceptor

### Step 1: Define Your Principal Type

Use an immutable record for the principal:

```java
package com.example.auth;

import ru.tinkoff.kora.common.Principal;

public record ClientPrincipal(String clientId, String apiKeyId) implements Principal {
    @Override
    public String name() {
        return clientId;
    }
    
    /**
     * Typed accessor to avoid casting at call sites.
     * Returns null if not authenticated — add null-checks.
     */
    public static ClientPrincipal current() {
        return (ClientPrincipal) Principal.current();
    }
}
```

### Step 2: Global Auth Interceptor

```java
package com.example.auth;

import ru.tinkoff.kora.common.Component;
import ru.tinkoff.kora.common.Context;
import ru.tinkoff.kora.http.server.common.HttpServerInterceptor;
import ru.tinkoff.kora.http.server.common.HttpServerRequest;
import ru.tinkoff.kora.http.server.common.HttpServerResponse;
import ru.tinkoff.kora.http.server.common.HttpServerResponseException;
import ru.tinkoff.kora.http.server.common.InterceptChain;
import ru.tinkoff.kora.http.server.common.annotation.Tag;
import ru.tinkoff.kora.http.server.common.auth.Principal;

import java.util.concurrent.CompletableFuture;
import java.util.concurrent.CompletionStage;

@Tag(HttpServerModule.class)  // Makes it global — only ONE global interceptor allowed
@Component
public final class ApiKeyAuthInterceptor implements HttpServerInterceptor {
    
    @Override
    public CompletionStage<HttpServerResponse> intercept(Context context,
                                                         HttpServerRequest request,
                                                         InterceptChain chain) {
        String apiKey = request.header("X-API-Key");
        
        if (apiKey == null || !isValid(apiKey)) {
            // Return 401 immediately — don't continue the chain
            return CompletableFuture.completedFuture(
                HttpServerResponseException.of(401, "Invalid or missing API key")
            );
        }
        
        // Extract principal from API key
        ClientPrincipal principal = new ClientPrincipal(
            extractClientId(apiKey),
            extractKeyId(apiKey)
        );
        
        // Store principal in context BEFORE continuing the chain
        Principal.set(context, principal);
        
        return chain.process(context, request);
    }
    
    private boolean isValid(String apiKey) {
        // Validate against database, cache, or HMAC signature
        // Return true if valid, false otherwise
    }
    
    private String extractClientId(String apiKey) {
        // Extract client identifier from API key
    }
    
    private String extractKeyId(String apiKey) {
        // Extract key identifier from API key
    }
}
```

### Step 3: Controller Reads Principal

```java
package com.example.controller;

import ru.tinkoff.kora.common.Component;
import ru.tinkoff.kora.http.server.common.annotation.HttpController;
import ru.tinkoff.kora.http.server.common.annotation.HttpRoute;
import ru.tinkoff.kora.http.server.common.HttpMethod;
import com.example.auth.ClientPrincipal;
import com.example.service.OrderService;
import com.example.dto.OrderResponse;

import java.util.List;

@Component
@HttpController
public final class OrdersController {
    
    private final OrderService orderService;
    
    public OrdersController(OrderService orderService) {
        this.orderService = orderService;
    }
    
    @HttpRoute(method = HttpMethod.GET, path = "/orders")
    @Json
    public List<OrderResponse> getOrders() {
        // Typed accessor — no casting needed
        ClientPrincipal principal = ClientPrincipal.current();
        
        // Null-check if route might not be protected
        if (principal == null) {
            throw HttpServerResponseException.of(401, "Not authenticated");
        }
        
        // Use principal for filtering, auditing, etc.
        return orderService.findByClient(principal.clientId());
    }
}
```

---

## Key Points

### Context.Key for Custom Values

For passing non-principal values (e.g., auth session, user profile, request metadata):

```java
public final class RequestContext {
    public static final Context.Key<UserProfile> USER_PROFILE_KEY = Context.KeyImmutable.of("userProfile");
    private RequestContext() {}
}
```

- `Context.Key<T>` — mutable key
- `Context.KeyImmutable<T>` — immutable key (recommended for records)
- Static singleton — one key per value type

### Interceptor Timing

**Critical:** Set values in `Context` **BEFORE** calling `chain.process()`:

```java
context.set(PRINCIPAL_KEY, principal);  // BEFORE
return chain.process(context, request);  // THEN
```

### Null Safety

`Principal.current()` and `Context.current().get(KEY)` return `null` if:
- The route is not protected by the interceptor
- The interceptor didn't set the value
- The request failed before the interceptor ran

**Always add null-checks** in controllers unless you're certain the route is protected.

### Status Code Preservation

The interceptor pattern preserves correct status codes because the interceptor maps failures directly:

```java
// In interceptor — returns 401
return CompletableFuture.completedFuture(
    HttpServerResponseException.of(401, "Invalid API key")
);

// NOT this — would be wrapped to 400 by generated handler
throw new AuthException("Invalid API key");  // Becomes 400!
```

---

## HttpServerPrincipalExtractor (Kora 1.2.x Limitation)

`ru.tinkoff.kora.http.server.common.auth.HttpServerPrincipalExtractor` exists but has **no auto-wiring** to controller parameters in Kora 1.2.x.

### Why It Doesn't Work

1. The HTTP-server KSP treats `Principal` parameters as request bodies
2. Requires `HttpServerRequestMapper<CompletionStage<ClientPrincipal>>`
3. Mapper failures are wrapped as `HttpServerResponseException.of(400, ...)`
4. Custom 401 exceptions get downgraded to 400

### Potential Workaround (Not Recommended)

To make 401 survive, your exception must implement `HttpServerResponse`:

```java
// Hack — not recommended
public class ApiException extends RuntimeException implements HttpServerResponse {
    @Override
    public int code() { return 401; }
    @Override
    public HttpBody body() { return HttpBody.plaintext(getMessage()); }
    @Override
    public HttpHeaders headers() { return HttpHeaders.of(); }
}
```

This is fragile and not worth the complexity. Use the interceptor pattern instead.

---

## Comparison: Interceptor vs Extractor

| Aspect | Interceptor Pattern | HttpServerPrincipalExtractor |
|--------|---------------------|------------------------------|
| **Status codes** | Correct (401/403) | Downgraded to 400 |
| **Graph build** | No issues | Requires custom mapper |
| **Controller params** | Read via `Principal.current()` | Would be direct param (doesn't work in 1.2.x) |
| **Null handling** | Explicit null-check needed | N/A |
| **Complexity** | Low | High (custom mapper, exception hacks) |
| **Recommended** | ✅ Yes | ❌ No (in 1.2.x) |

---

## Future Versions

Check newer Kora versions (1.3+) for first-class `@Principal` parameter support. The Kora maintainers may add auto-bridging of `HttpServerPrincipalExtractor` to controller parameters in future releases.

---

## See Also

- [Context Propagation](context-propagation-reference.md) — Passing values from interceptor to controller
- [Interceptors](interceptors-reference.md) — Global, controller, and method-level interceptors
- [Error Handling](error-handling-reference.md) — `HttpServerResponseException` and error mapping
