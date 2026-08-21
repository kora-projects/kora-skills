# OpenAPI Controllers Reference

**Generated into:** `$buildDir/generated/<api-name>-server/<apiPackage>/`

## Contents

- [1. Overview](#1-overview)
- [2. What the Generated Controller Does](#2-what-the-generated-controller-does)
- [3. Path Prefix Configuration](#3-path-prefix-configuration)
- [4. Interceptors](#4-interceptors)
- [5. Validation Interceptor](#5-validation-interceptor)
- [6. One Controller per Tag](#6-one-controller-per-tag)
- [7. Avoiding Route Conflicts](#7-avoiding-route-conflicts)
- [8. Common Issues](#8-common-issues)
- [9. Related](#9-related)

---

## 1. Overview

For each OpenAPI tag the `kora` generator emits a `*ApiController` annotated with
`@HttpController`, one `@HttpRoute` method per `operationId`, and the wiring that
calls your `*ApiDelegate`. The controller is **generated and registered
automatically** — never write it by hand and never edit files under
`build/generated/`.

The controller is responsible for:

- registering routes (`@HttpController`, `@HttpRoute`)
- parsing path/query/header parameters and the request body (via the JSON module)
- invoking the matching `*ApiDelegate` method
- turning the returned sealed `*ApiResponses` record into an `HttpServerResponse`
  with the correct status, body, and declared headers

Your code only implements the delegate; everything above stays in generated code.

---

## 2. What the Generated Controller Does

You do not need to read the generated controller line by line. Conceptually, for
`GET /users/{userId}` it:

1. extracts `userId` from the path,
2. calls `delegate.getUser(userId)`,
3. matches the returned record (`GetUser200ApiResponse`, `GetUser404ApiResponse`, ...),
4. serializes that record's body and writes the corresponding HTTP status.

Because the controller is keyed off the contract, the set of routes and the set of
possible responses are exactly what the OpenAPI file declares. To add a route or a
status code, change the contract and regenerate — do not patch the controller.

---

## 3. Path Prefix Configuration

Prefix every route generated from this contract:

```groovy
configOptions = [
    mode: "java-server",
    prefixPath: "/api/v1"
]
```

- Original: `GET /users/{userId}`
- With prefix: `GET /api/v1/users/{userId}`

---

## 4. Interceptors

Attach Kora `HttpServerInterceptor`s to the generated controllers via the
`interceptors` config option. The value is a JSON object whose key is the API tag
(`*` for all tags), and whose value is a list of entries with `type` and/or `tag`:

- `type` — the interceptor implementation class
- `tag` — the interceptor's Kora tag (string, or array of strings)

```groovy
configOptions = [
    mode: "java-server",
    interceptors: """
    {
      "*": [
        { "tag": "com.example.LoggingTag" }
      ],
      "users": [
        { "type": "com.example.RateLimitInterceptor" },
        { "type": "com.example.AuthInterceptor", "tag": "com.example.AuthTag" }
      ]
    }
    """
]
```

### Interceptor Implementation

A Kora HTTP server interceptor implements `HttpServerInterceptor` and continues
the chain with `chain.process(context, request)`:

```java
import java.util.concurrent.CompletionStage;
import ru.tinkoff.kora.common.Component;
import ru.tinkoff.kora.common.Context;
import ru.tinkoff.kora.http.common.body.HttpBody;
import ru.tinkoff.kora.http.server.common.HttpServerInterceptor;
import ru.tinkoff.kora.http.server.common.HttpServerRequest;
import ru.tinkoff.kora.http.server.common.HttpServerResponse;

@Component
public final class RateLimitInterceptor implements HttpServerInterceptor {

    private final RateLimiter rateLimiter;

    public RateLimitInterceptor(RateLimiter rateLimiter) {
        this.rateLimiter = rateLimiter;
    }

    @Override
    public CompletionStage<HttpServerResponse> intercept(
            Context context, HttpServerRequest request, InterceptChain chain) throws Exception {
        if (!rateLimiter.tryAcquire()) {
            return CompletableFuture.completedFuture(
                HttpServerResponse.of(429, HttpBody.plaintext("Too Many Requests")));
        }
        return chain.process(context, request);
    }
}
```

---

## 5. Validation Interceptor

With `enableServerValidation: "true"` the generated DTOs and controller carry Kora
validation annotations. Add `enableServerValidationInterceptor: "true"` to install
an interceptor that maps a Kora `ViolationException` to a separate HTTP response
instead of letting it propagate:

```groovy
configOptions = [
    mode: "java-server",
    enableServerValidation: "true",
    enableServerValidationInterceptor: "true"
]
```

Customize the mapping by providing a `ViolationExceptionHttpServerResponseMapper`
in the application graph (see [Validation Reference](openapi-validation-reference.md)).

---

## 6. One Controller per Tag

Each OpenAPI tag produces a separate controller:

```yaml
tags:
  - name: users
  - name: orders
  - name: products
```

Generated:

- `UsersApiController` (routes for `users`)
- `OrdersApiController` (routes for `orders`)
- `ProductsApiController` (routes for `products`)

Each controller depends on its own `*ApiDelegate`, which you implement separately.

---

## 7. Avoiding Route Conflicts

Give each generator task a unique `outputDir`, and ensure prefixes do not collide:

```groovy
// Correct: distinct output dirs and distinct prefixes
def usersApi = tasks.register("usersApi", GenerateTask) {
    outputDir = "$buildDir/generated/users-api-server"
    configOptions = [mode: "java-server", prefixPath: "/api/users"]
}
def ordersApi = tasks.register("ordersApi", GenerateTask) {
    outputDir = "$buildDir/generated/orders-api-server"
    configOptions = [mode: "java-server", prefixPath: "/api/orders"]
}
```

Reusing one `outputDir` for two tasks makes them overwrite each other and breaks
incremental builds.

---

## 8. Common Issues

### Delegate Not Discovered

The generated controller injects the `*ApiDelegate` from the application graph. If
the graph cannot find it, add `@Component` to your implementation and confirm it
implements the generated delegate from your `apiPackage`.

### Generated Sources Not Compiled

```groovy
// Register generated sources and order generation before compilation
sourceSets.main { java.srcDirs += openApiGenerateHttpServer.get().outputDir }
compileJava.dependsOn openApiGenerateHttpServer
```

### Route Not Registered

The controller is generated only for operations present in the contract. Verify the
operation has a `tag` and an `operationId`, then regenerate.

---

## 9. Related

- [OpenAPI Delegates Reference](openapi-delegates-reference.md) — Delegate interfaces
- [OpenAPI Response Reference](openapi-response-reference.md) — Response records
- [OpenAPI Validation Reference](openapi-validation-reference.md) — Validation interceptor
- [HTTP Server](../../../.kora-agent/kora-docs/mkdocs/docs/en/documentation/http-server.md) — Kora HTTP server, interceptors
