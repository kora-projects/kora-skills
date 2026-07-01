# Context Propagation in Kora HTTP Server

**Kora Version:** 1.2.x

This reference covers passing computed values from HTTP interceptors to controller methods using `ru.tinkoff.kora.common.Context`.

---

## Overview

Kora's `Context` is a request-scoped key-value store for passing data between interceptors, filters, and controllers. Common use cases:

- Auth session or user profile (computed in interceptor, used in controller)
- Request metadata (trace ID, request ID, timing info)
- Computed values (fingerprint, rate limit bucket, tenant ID)

---

## Context.Key Definition

Define a static singleton key for each value type:

```java
package com.example.context;

import ru.tinkoff.kora.common.Context;

public final class RequestContext {
    
    // Mutable key
    public static final Context.Key<String> REQUEST_ID_KEY = Context.Key.of("requestId");
    
    // Immutable key (recommended for records)
    public static final Context.Key<UserProfile> USER_PROFILE_KEY = Context.KeyImmutable.of("userProfile");
    
    private RequestContext() {}
}
```

**Key types:**
- `Context.Key<T>` — mutable key
- `Context.KeyImmutable<T>` — immutable key (recommended for records/immutable types)

**Naming:** Use `Context.KeyImmutable.of("descriptive-name")` for debugging — the name appears in error messages.

---

## Interceptor: Setting Values

Set values in `Context` **BEFORE** calling `chain.process()`:

```java
package com.example.interceptor;

import ru.tinkoff.kora.common.Component;
import ru.tinkoff.kora.common.Context;
import ru.tinkoff.kora.http.server.common.HttpServerInterceptor;
import ru.tinkoff.kora.http.server.common.HttpServerRequest;
import ru.tinkoff.kora.http.server.common.HttpServerResponse;
import ru.tinkoff.kora.http.server.common.InterceptChain;
import ru.tinkoff.kora.http.server.common.annotation.Tag;
import com.example.context.RequestContext;
import com.example.auth.UserProfile;

import java.util.UUID;
import java.util.concurrent.CompletionStage;

@Tag(HttpServerModule.class)  // Global interceptor
@Component
public final class RequestContextInterceptor implements HttpServerInterceptor {
    
    @Override
    public CompletionStage<HttpServerResponse> intercept(Context context,
                                                         HttpServerRequest request,
                                                         InterceptChain chain) {
        // Generate request ID
        String requestId = UUID.randomUUID().toString();
        context.set(RequestContext.REQUEST_ID_KEY, requestId);
        
        // Load user profile (from token, session, etc.)
        UserProfile profile = loadUserProfile(request);
        if (profile != null) {
            context.set(RequestContext.USER_PROFILE_KEY, profile);
        }
        
        // Continue the chain with context populated
        return chain.process(context, request)
            .whenComplete((response, error) -> {
                // Optional: cleanup or logging after request completes
                // Context is request-scoped and will be garbage collected
            });
    }
    
    private UserProfile loadUserProfile(HttpServerRequest request) {
        String token = request.header("Authorization");
        if (token == null || !token.startsWith("Bearer ")) {
            return null;
        }
        // Validate token and extract profile
        return validateToken(token.substring(7));
    }
    
    private UserProfile validateToken(String token) {
        // JWT validation, session lookup, etc.
        // Return null if invalid
    }
}
```

**Critical timing:**
```java
context.set(KEY, value);      // BEFORE
return chain.process(context, request);  // THEN
```

If you set values after `chain.process()`, the controller won't see them.

---

## Controller: Reading Values

Read values from `Context` in controller methods:

```java
package com.example.controller;

import ru.tinkoff.kora.common.Component;
import ru.tinkoff.kora.common.Context;
import ru.tinkoff.kora.http.server.common.annotation.HttpController;
import ru.tinkoff.kora.http.server.common.annotation.HttpRoute;
import ru.tinkoff.kora.http.server.common.HttpMethod;
import com.example.context.RequestContext;
import com.example.auth.UserProfile;

import java.util.Map;

@Component
@HttpController
public final class ProfileController {
    
    @HttpRoute(method = HttpMethod.GET, path = "/profile")
    @Json
    public UserProfileResponse getProfile() {
        UserProfile profile = Context.current().get(RequestContext.USER_PROFILE_KEY);
        
        // NULL-CHECK REQUIRED!
        // Value is null if:
        // - Route is not protected by the interceptor
        // - Interceptor didn't set the value
        // - Request failed before interceptor ran
        if (profile == null) {
            throw HttpServerResponseException.of(401, "Not authenticated");
        }
        
        return mapToResponse(profile);
    }
    
    @HttpRoute(method = HttpMethod.GET, path = "/request-info")
    @Json
    public Map<String, String> getRequestInfo() {
        String requestId = Context.current().get(RequestContext.REQUEST_ID_KEY);
        return Map.of("requestId", requestId != null ? requestId : "unknown");
    }
}
```

**Null safety:** Always add null-checks unless you're certain the route is protected.

---

## Type-Safe Accessor Pattern

For frequently-used context values, create typed accessors:

```java
public final class RequestContext {
    public static final Context.Key<UserProfile> USER_PROFILE_KEY = Context.KeyImmutable.of("userProfile");
    
    private RequestContext() {}
    
    /**
     * Typed accessor with consistent null handling.
     * @throws HttpServerResponseException 401 if not authenticated
     */
    public static UserProfile requireProfile() {
        UserProfile profile = Context.current().get(USER_PROFILE_KEY);
        if (profile == null) {
            throw HttpServerResponseException.of(401, "Not authenticated");
        }
        return profile;
    }
    
    /**
     * Typed accessor returning Optional.
     */
    public static Optional<UserProfile> currentProfile() {
        return Optional.ofNullable(Context.current().get(USER_PROFILE_KEY));
    }
}
```

Usage in controller:
```java
@HttpRoute(method = HttpMethod.GET, path = "/profile")
@Json
public UserProfileResponse getProfile() {
    UserProfile profile = RequestContext.requireProfile();  // Throws 401 if null
    return mapToResponse(profile);
}
```

---

## Important: Use Kora Context, Not gRPC Context

```java
// ✅ CORRECT
import ru.tinkoff.kora.common.Context;

Context.current().get(KEY);

// ❌ WRONG
import io.grpc.Context;

io.grpc.Context.current().get(KEY);  // Different Context!
```

Kora's `ru.tinkoff.kora.common.Context` is **not** the same as `io.grpc.Context`. They are completely unrelated classes with different APIs.

---

## Thread Safety

`Context` is request-scoped and thread-safe:

- Each request gets its own `Context` instance
- Values set in one request are not visible to other requests
- Safe to use in async/reactive handlers

---

## Performance Considerations

`Context` operations are O(1) — implemented as a thread-local map. Overhead is negligible for typical use (a few keys per request).

Avoid:
- Storing large objects in Context (pass references only)
- Too many keys (>10 per request is unusual)
- Using Context as a cache (it's request-scoped, not application-scoped)

---

## Debugging

### Value is null in controller

Checklist:
1. Interceptor has `@Tag(HttpServerModule.class)` and `@Component`
2. Value is set **BEFORE** `chain.process()`
3. Controller route is actually hit by the interceptor (check path, HTTP method)
4. No exception thrown before value is set

### Wrong value in controller

Checklist:
1. Key is a static singleton (not created per-request)
2. Value is not being overwritten by another interceptor
3. Async handlers are using the same `Context` instance

---

## See Also

- [Authentication & Principal](authentication-reference.md) — Storing principal in Context
- [Interceptors](interceptors-reference.md) — Global, controller, and method-level interceptors
