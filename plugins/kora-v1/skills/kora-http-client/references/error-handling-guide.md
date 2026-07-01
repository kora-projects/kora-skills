# HTTP Client Error Handling Guide

Reference for [kora-http-client](../SKILL.md).

## Contents

- [How errors surface](#how-errors-surface)
- [HttpClientResponseException](#httpclientresponseexception)
- [HttpClientDecoderException](#httpclientdecoderexception)
- [HttpResponseEntity (avoid exceptions)](#httpresponseentity-avoid-exceptions)
- [Status-aware decoding with @ResponseCodeMapper](#status-aware-decoding-with-responsecodemapper)
- [Resilience](#resilience)
- [Troubleshooting](#troubleshooting)

---

## How errors surface

By default, when no response mapper or converter is specified, decoding is applied for `2xx` status codes. For every other status code Kora throws `HttpClientResponseException`, which carries the HTTP status code, the response body, and the response headers.

The two HTTP-client exceptions provided by Kora are:

| Exception | Import | When |
|-----------|--------|------|
| `HttpClientResponseException` | `ru.tinkoff.kora.http.client.common.HttpClientResponseException` | Response received with a non-2xx status (and no mapper handles it) |
| `HttpClientDecoderException` | `ru.tinkoff.kora.http.client.common.HttpClientDecoderException` | The response body could not be decoded into the target type |

There is no per-status exception subclass hierarchy - branch on `code()` yourself.

---

## HttpClientResponseException

```java
@Component
public final class UserService {

    private static final Logger log = LoggerFactory.getLogger(UserService.class);
    private final UserApiClient client;

    public UserService(UserApiClient client) {
        this.client = client;
    }

    public UserResponse getUser(String id) {
        try {
            return client.getUser(id);
        } catch (HttpClientResponseException e) {
            switch (e.code()) {
                case 404 -> throw new UserNotFoundException(id);
                case 409 -> throw new UserConflictException(id);
                case 503 -> throw new IllegalStateException("user-service unavailable", e);
                default -> {
                    log.error("Unexpected status {} from user-service", e.code(), e);
                    throw new IllegalStateException("user-service error", e);
                }
            }
        }
    }
}
```

`HttpClientResponseException` exposes `code()` plus the standard `getMessage()`. The body and headers from the failed response are available on the exception for diagnostics.

---

## HttpClientDecoderException

Thrown when the body cannot be deserialized (malformed JSON, schema mismatch, empty body where JSON was expected).

```java
try {
    return client.getUser(id);
} catch (HttpClientDecoderException e) {
    log.error("Failed to decode user-service response", e);
    throw new IllegalStateException("Invalid response format", e);
}
```

A custom `HttpClientResponseMapper` may also throw `HttpClientDecoderException` from its `apply` method.

---

## HttpResponseEntity (avoid exceptions)

To branch on status without try/catch, return `HttpResponseEntity<T>`. Non-2xx responses then arrive as a normal value instead of an exception.

```java
@HttpRoute(method = HttpMethod.GET, path = "/users/{id}")
@Json
HttpResponseEntity<UserResponse> getUser(@Path String id);

// Usage:
public UserResponse getUser(String id) {
    HttpResponseEntity<UserResponse> response = client.getUser(id);
    return switch (response.code()) {
        case 200 -> response.body();
        case 404 -> throw new UserNotFoundException(id);
        default -> throw new IllegalStateException("Unexpected status: " + response.code());
    };
}
```

`HttpResponseEntity` exposes `code()`, `body()`, and `headers()`.

---

## Status-aware decoding with @ResponseCodeMapper

When success and error bodies have different shapes, map status codes to dedicated `HttpClientResponseMapper` implementations. `ResponseCodeMapper.DEFAULT` covers all unlisted codes.

```java
sealed interface UserResult permits UserFound, UserError {
    @Json record UserFound(String id, String name) implements UserResult {}
    @Json record UserError(int code, String message) implements UserResult {}
}

@ResponseCodeMapper(code = 200, mapper = UserFoundMapper.class)
@ResponseCodeMapper(code = ResponseCodeMapper.DEFAULT, mapper = UserErrorMapper.class)
@HttpRoute(method = HttpMethod.GET, path = "/users/{id}")
UserResult getUser(@Path String id);
```

The error mapper can read `response.code()` while decoding:

```java
final class UserErrorMapper implements HttpClientResponseMapper<UserResult> {

    private final JsonReader<ErrorPayload> reader;

    public UserErrorMapper(JsonReader<ErrorPayload> reader) {
        this.reader = reader;
    }

    @Override
    public UserResult apply(HttpClientResponse response) throws IOException, HttpClientDecoderException {
        try (var is = response.body().asInputStream()) {
            var payload = reader.read(is.readAllBytes());
            return new UserResult.UserError(response.code(), payload.message());
        }
    }

    @Json record ErrorPayload(String message) {}
}
```

See `assets/CustomMapperClient.java.template` for the full success + error mapper pair.

---

## Resilience

Retries, circuit breakers, timeouts, and fallbacks come from the `resilient-kora` module (`ResilientModule`), applied as aspect annotations on client methods. Each annotation references a named config block; the values live under `resilient.*`. There is no inline `maxAttempts`/`failureThreshold`/`@Backoff`.

```groovy
implementation "ru.tinkoff.kora:resilient-kora"
```

```java
@HttpClient(configPath = "httpClient.itemApi")
public interface ItemApiClient {

    @Retry("itemApi")
    @HttpRoute(method = HttpMethod.GET, path = "/items/{id}")
    @Json
    ItemResponse getItem(@Path String id);

    @CircuitBreaker("itemApi")
    @HttpRoute(method = HttpMethod.POST, path = "/items")
    @Json
    ItemResponse createItem(@Json CreateItemRequest request);

    @Timeout("itemApi")
    @Fallback(value = "itemApi", method = "listItemsFallback()")
    @HttpRoute(method = HttpMethod.GET, path = "/items")
    @Json
    List<ItemResponse> listItems();

    default List<ItemResponse> listItemsFallback() {
        return List.of();
    }
}
```

```hocon
resilient {
  retry { itemApi { delay = "100ms", attempts = 3 } }
  circuitbreaker { itemApi { slidingWindowSize = 20, minimumRequiredCalls = 10, failureRateThreshold = 50 } }
  timeout { itemApi { duration = "5s" } }
}
```

The combination order, exception predicates, and full config schema are covered by the `kora-aop-resilient` skill.

---

## Troubleshooting

### 404 on a URL you believe is valid

Check that `url` (from config) and the `@HttpRoute` `path` concatenate as expected, and that path variables are encoded. Enable logging to see the full request:

```hocon
httpClient {
  itemApi {
    telemetry { logging { enabled = true, pathTemplate = false } }
  }
}
```

### 401/403 on a protected API

Attach an auth interceptor - see [interceptors-reference](interceptors-reference.md).

### Timeout on long requests

Raise `requestTimeout` for the client (or per method):

```hocon
httpClient { itemApi { requestTimeout = "60s" } }
```

---

## See also

- [declarative-client-reference](declarative-client-reference.md)
- [async-client-reference](async-client-reference.md)
- [interceptors-reference](interceptors-reference.md)
