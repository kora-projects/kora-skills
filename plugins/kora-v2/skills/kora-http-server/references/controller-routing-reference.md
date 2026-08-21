# Controller & Routing Reference

`@HttpController`, `@HttpRoute`, and how the request path is composed.

## Contents

- [@HttpController](#httpcontroller)
- [@HttpRoute](#httproute)
- [Path composition](#path-composition)
- [Path variables](#path-variables)
- [HTTP method patterns](#http-method-patterns)
- [Common pitfalls](#common-pitfalls)
- [Generated code](#generated-code)

---

## @HttpController

Marks a class as an HTTP controller. The class must also be `@Component` so it is registered in
the application graph.

```java
import ru.tinkoff.kora.common.Component;
import ru.tinkoff.kora.http.server.common.annotation.HttpController;

@Component
@HttpController
public final class UserController { /* ... */ }
```

`@HttpController` takes **no** path argument. The full path of each route is the `path` of its
`@HttpRoute`. Group endpoints by sharing the same prefix across each route's `path`.

---

## @HttpRoute

Binds an `HttpMethod` and a path to a handler method.

```java
@HttpRoute(method = HttpMethod.GET, path = "/users/{id}")
public UserResponse getUser(@Path String id) { /* ... */ }
```

| Parameter | Type | Required | Description |
|---|---|---|---|
| `method` | `HttpMethod` | yes | HTTP method |
| `path` | String | yes | Full request path, may contain `{var}` segments |

`HttpMethod` (`ru.tinkoff.kora.http.common.HttpMethod`): `GET`, `POST`, `PUT`, `DELETE`, `PATCH`,
`OPTIONS`, `HEAD`, `TRACE`.

---

## Path composition

Because there is no controller-level prefix, repeat the prefix in each route's `path`:

```java
@Component
@HttpController
public final class UserController {

    @HttpRoute(method = HttpMethod.GET, path = "/users/{id}")          // GET /users/{id}
    public UserResponse getUser(@Path String id) { /* ... */ }

    @HttpRoute(method = HttpMethod.GET, path = "/users/{id}/orders")   // GET /users/{id}/orders
    public List<OrderResponse> getOrders(@Path String id) { /* ... */ }
}
```

`ignoreTrailingSlash` in `httpServer` config controls whether `/users` and `/users/` match the
same route (off by default).

---

## Path variables

```java
@HttpRoute(method = HttpMethod.GET, path = "/users/{userId}/orders/{orderId}")
public OrderResponse getOrder(@Path String userId, @Path String orderId) { /* ... */ }
```

The `@Path` name defaults to the argument name. Use an explicit value only when they differ:
`@Path("orderId") String oid`. The name must match a `{...}` segment exactly, otherwise the route
will not bind.

---

## HTTP method patterns

```java
// GET — read, no side effects
@HttpRoute(method = HttpMethod.GET, path = "/users/{id}")
@Json
public UserResponse getUser(@Path String id) { /* ... */ }

// POST — create; return 201 with a Location header
@HttpRoute(method = HttpMethod.POST, path = "/users")
@Json
public HttpResponseEntity<UserResponse> create(@Json UserRequest request) {
    UserResponse user = userService.createUser(request);
    return HttpResponseEntity.of(201, HttpHeaders.of("Location", "/users/" + user.id()), user);
}

// PUT — full update
@HttpRoute(method = HttpMethod.PUT, path = "/users/{id}")
@Json
public UserResponse update(@Path String id, @Json UserRequest request) {
    return userService.updateUser(id, request);
}

// DELETE — 204 No Content
@HttpRoute(method = HttpMethod.DELETE, path = "/users/{id}")
public HttpServerResponse delete(@Path String id) {
    userService.deleteUser(id);
    return HttpServerResponse.of(204, HttpBody.empty());
}
```

---

## Common pitfalls

### 404 on a valid path

The `{var}` in the route has no matching `@Path` argument, or the prefix was put on
`@HttpController` (unsupported).

```java
// Wrong: route declares {id} but there is no @Path argument
@HttpRoute(method = HttpMethod.GET, path = "/users/{id}")
public UserResponse getUser() { /* ... */ }

// Correct
@HttpRoute(method = HttpMethod.GET, path = "/users/{id}")
public UserResponse getUser(@Path String id) { /* ... */ }
```

### Null `@Path` value

The argument name (or explicit `@Path("...")`) does not match the `{...}` segment.

```java
// Wrong: {id} in path, but the value names "userId"
@HttpRoute(method = HttpMethod.GET, path = "/users/{id}")
public UserResponse getUser(@Path("userId") String userId) { /* ... */ }

// Correct
@HttpRoute(method = HttpMethod.GET, path = "/users/{id}")
public UserResponse getUser(@Path String id) { /* ... */ }
```

---

## Generated code

Kora generates the router at compile time under
`build/generated/sources/annotationProcessor/java/main/` (Java) or `build/generated/ksp/main/`
(Kotlin). Open the generated `*Module`/handler classes to see exactly how your annotations were
turned into request handling — useful when debugging routing.

**See also:** [Request Mapping](request-mapping-reference.md), [Response Types](response-types-reference.md).
