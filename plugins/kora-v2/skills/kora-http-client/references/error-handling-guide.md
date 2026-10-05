# HTTP Client Error Handling Guide (Kora 2.x)

Reference for [kora-http-client](../SKILL.md). Verified against the framework source at tag
**`2.0.0.RC2`**.

## Contents

- [Exception hierarchy](#exception-hierarchy)
- [HttpClientResponseException](#httpclientresponseexception)
- [Decoding and encoding failures](#decoding-and-encoding-failures)
- [Connection and timeout failures](#connection-and-timeout-failures)
- [HttpResponseEntity — status without exceptions](#httpresponseentity--status-without-exceptions)
- [Either — typed success or error](#either--typed-success-or-error)
- [@ResponseCodeMapper — a different shape per status](#responsecodemapper--a-different-shape-per-status)
- [Resilience](#resilience)
- [Troubleshooting](#troubleshooting)

---

## Exception hierarchy

All in `io.koraframework.http.client.common.exception` — the 1.x package
`http.client.common` no longer holds them.

```
RuntimeException
└── HttpClientException                (abstract; catch this to catch everything)
    ├── HttpClientResponseException    non-2xx response with no mapper for that status
    ├── HttpClientDecoderException     response body could not be turned into the result type
    ├── HttpClientEncoderException     request body mapper threw
    ├── HttpClientConnectionException  connection could not be used: refused, connect timeout, I/O
    ├── HttpClientTimeoutException     request timed out
    └── HttpClientUnknownException     anything else
```

Every one of them is **unchecked**, so nothing forces a `catch`. There is no per-status subclass —
branch on the code yourself.

Client methods declare `throws HttpClientException` on the generated implementation, which is the
useful thing to catch at a service boundary when you do not care which failure it was.

---

## HttpClientResponseException

Thrown when a response arrives with a status outside `200..299` and no `@Mapping` /
`@ResponseCodeMapper` claims it, and the return type is not `Either`.

```java
public class HttpClientResponseException extends HttpClientException {
    public int getCode();
    public HttpHeaders getHeaders();
    public byte[] getBytes();
}
```

**The accessors are `getCode()` / `getHeaders()` / `getBytes()`** — the 1.x `code()` form does not
exist. The message is built eagerly as
`"HTTP response with status code %d:\n%s"` with the body decoded as UTF-8, and the captured body is
truncated to the first **4096 bytes** when the transport cannot hand over the full content at once.
It is a diagnostic snapshot, not a reliable payload — decode structured errors with a
`@ResponseCodeMapper` instead of parsing `getBytes()`.

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
            return this.client.getUser(id);
        } catch (HttpClientResponseException e) {
            throw switch (e.getCode()) {
                case 404 -> new UserNotFoundException(id);
                case 409 -> new UserConflictException(id);
                default -> {
                    log.error("user-service returned {}", e.getCode(), e);
                    yield new IllegalStateException("user-service error", e);
                }
            };
        }
    }
}
```

```kotlin
fun getUser(id: String): UserResponse =
    try {
        client.getUser(id)
    } catch (e: HttpClientResponseException) {
        when (e.code) {
            404 -> throw UserNotFoundException(id)
            409 -> throw UserConflictException(id)
            else -> throw IllegalStateException("user-service error", e)
        }
    }
```

Kotlin sees `getCode()` as the synthetic property `e.code`.

---

## Decoding and encoding failures

**Request side.** The generated client wraps the request-body mapper:

```java
try {
    _body = this.createUserRequestMapper.apply(request);
} catch (Exception _e) {
    throw new HttpClientEncoderException(_e);
}
```

So a `JsonWriter` failure or a throwing custom `HttpClientRequestMapper` always surfaces as
`HttpClientEncoderException`.

**Response side — symmetric.** The generated client wraps every response-mapper call the same way:

```java
try {
    return this.getUserResponseMapper.apply(_response);
} catch (Exception _e) {
    throw new HttpClientDecoderException(_e);
}
```

So a `JsonReader` failure, an `IOException` while reading the body, or any `RuntimeException` from a
custom `HttpClientResponseMapper` surfaces as `HttpClientDecoderException` — for the method-level
mapper, for every `@ResponseCodeMapper` arm whose mapper returns the result type, and for the
default 2xx mapping. The exception is: a `@ResponseCodeMapper` arm whose mapper produces an
*exception* (`throw mapper.apply(_response)`) throws that exception as is.

A mapper may still reject a payload itself, e.g. an empty body. A `HttpClientDecoderException`
thrown inside `apply` arrives wrapped in another one, so read `getCause()` for the original:

```java
@Override
public UserResponse apply(HttpClientResponse response) throws IOException {
    try (var is = response.body().asInputStream()) {
        var payload = this.reader.read(is.readAllBytes());
        if (payload == null) {
            throw new HttpClientDecoderException(new IllegalStateException("empty body"));
        }
        return payload;
    }
}
```

`JsonReader<T>.read(...)` returns `@Nullable T` in 2.0 — in Kotlin that is
`requireNotNull(reader.read(bytes)) { "empty body" }`.

---

## Connection and timeout failures

Mapped by each transport, before any decoding happens. **A failure to connect — refused
connection or `connectTimeout` elapsed — is `HttpClientConnectionException` on all three
transports**, never `HttpClientTimeoutException`:

| Transport | `HttpClientConnectionException` | `HttpClientTimeoutException` | `HttpClientUnknownException` |
|---|---|---|---|
| OkHttp | any `IOException` except the one below — refused, connect timeout, DNS, reset, TLS | `InterruptedIOException` with message `"timeout"` (`requestTimeout`, `readTimeout`) | any non-I/O `Throwable` |
| JDK | `ConnectException`, `HttpConnectTimeoutException`, `ProtocolException` | `HttpTimeoutException` (`requestTimeout`, else `readTimeout`) | `InterruptedException`; any other `IOException` after the transport's single retry (or at once when the request body was already streamed) |
| Apache | `ConnectTimeoutException`, and any other `IOException` | `SocketTimeoutException` (`readTimeout`, `requestTimeout`) | any non-I/O `Throwable` |

A timeout is a `HttpClientTimeoutException`, not a response — there is no status code to branch on.
On the JDK transport a reset mid-exchange can surface as `HttpClientUnknownException`, so catch
`HttpClientException` as the last branch:

```java
try {
    return this.client.getItem(id);
} catch (HttpClientTimeoutException e) {
    return ItemResponse.unavailable(id);
} catch (HttpClientConnectionException e) {
    log.warn("items-service unreachable", e);
    return ItemResponse.unavailable(id);
} catch (HttpClientException e) {
    log.warn("items-service call failed", e);
    return ItemResponse.unavailable(id);
}
```

---

## HttpResponseEntity — status without exceptions

Returning `HttpResponseEntity<T>` gives access to `code()`, `headers()` and a `@Nullable body()`.
It does **not** by itself stop non-2xx from throwing: the generated client still checks the status
before mapping, and only the `Either` payload disables that check.

```java
@HttpRoute(method = HttpMethod.GET, path = "/users/{userId}")
@Json
HttpResponseEntity<UserResponse> getUser(@Path String userId);
```

```java
var response = client.getUser(id);        // throws on 404
if (response.code() == 201) {
    var location = response.headers().getFirst("location");
}
```

Use it to read the status/headers of **successful** responses (`201` vs `200`, `Location`, ETags).
For "do not throw on 404", use `Either` or `@ResponseCodeMapper`.

`HttpResponseEntity<Void>` needs its own `HttpClientResponseMapper<Void>` component — see
[SKILL.md](../SKILL.md#httpresponseentityvoid-needs-its-own-payload-mapper).

---

## Either — typed success or error

`io.koraframework.common.Either<A, B>` is the only return shape that **suppresses the status check
entirely**: 2xx becomes `Either.Left`, everything else `Either.Right`, and nothing throws.

```java
@HttpRoute(method = HttpMethod.GET, path = "/users/{userId}")
@Json
Either<UserResponse, ApiError> getUser(@Path String userId);
```

```java
switch (client.getUser(id)) {
    case Either.Left<UserResponse, ApiError> ok  -> return ok.value();
    case Either.Right<UserResponse, ApiError> err -> throw new UserApiException(err.value());
}
```

`Either` is a sealed interface with `Left`/`Right` records plus `isLeft()`, `isRight()`, and
`@Nullable left()` / `right()` accessors. `HttpResponseEntity<Either<T, E>>` works too and adds the
status code.

The framework supplies the mappers as templates: `Either<T, E>` needs an
`HttpClientResponseMapper` for both `T` and `E` (the `@Json` variants need `JsonReader<T>` and
`JsonReader<E>`), so both types must be resolvable. `@Json` can be placed on the method for both
sides, or per type argument: `HttpResponseEntity<Either<@Json String, @Json String>>`.

---

## @ResponseCodeMapper — a different shape per status

When success and error bodies differ, map status codes to dedicated mappers. The generated body is
a `switch` on the code; unlisted codes without a `DEFAULT` entry still throw
`HttpClientResponseException`.

```java
@InterceptWith(MethodLoggingInterceptor.class)
@ResponseCodeMapper(code = ResponseCodeMapper.DEFAULT, mapper = MappedResponseErrorMapper.class)
@ResponseCodeMapper(code = 200, mapper = MappedResponseSuccessMapper.class)
@HttpRoute(method = HttpMethod.GET, path = "/data/mapping-by-code/{code}")
MappedResponse getMappedByCode(@Path int code);
```

```java
sealed interface MappedResponse permits Payload, Error {
    @Json record Payload(String message) implements MappedResponse {}
    @Json record Error(int code, String message) implements MappedResponse {}
    @Json record ErrorPayload(String message) {}
}

@Component
final class MappedResponseErrorMapper implements HttpClientResponseMapper<MappedResponse> {

    private final JsonReader<ErrorPayload> jsonReader;

    public MappedResponseErrorMapper(JsonReader<ErrorPayload> jsonReader) {
        this.jsonReader = jsonReader;
    }

    @Override
    public MappedResponse apply(HttpClientResponse response) throws IOException {
        try (var is = response.body().asInputStream()) {
            var payload = this.jsonReader.read(is.readAllBytes());
            return new Error(response.code(), payload.message());
        }
    }
}
```

`@Component` is needed here because the mapper takes a `JsonReader` — see the component rule in
[SKILL.md](../SKILL.md#which-mappers-and-interceptors-need-component).

**Mapping a status to an exception** works too: give the `mapper` a type argument that is *not*
assignable to the method's return type and the generated `switch` arm becomes `throw
mapper.apply(_response)` instead of a `yield`.

```java
@ResponseCodeMapper(code = 404, mapper = NotFoundExceptionMapper.class)
@ResponseCodeMapper(code = 200, mapper = UserMapper.class)
@HttpRoute(method = HttpMethod.GET, path = "/users/{userId}")
UserResponse getUser(@Path String userId);

final class NotFoundExceptionMapper implements HttpClientResponseMapper<UserNotFoundException> {
    @Override
    public UserNotFoundException apply(HttpClientResponse response) {
        return new UserNotFoundException(response.code());
    }
}
```

Full walk-through: `assets/CustomMapperClient.java.template` and `.kt.template`.

---

## Resilience

Resilience is the separate `resilient-kora` module (`io.koraframework.resilient.ResilientModule`),
applied as AOP annotations. Kora 2.0 replaced the 1.x **string names** with **typed specification
interfaces** — `@Retry("itemApi")` no longer compiles.

```groovy
implementation "io.koraframework:resilient-kora"
```

```java
@RetrySpec("resilient.retry.itemApi")
public interface ItemApiRetry extends Retry {}

@CircuitBreakerSpec("resilient.circuitbreaker.itemApi")
public interface ItemApiCircuitBreaker extends CircuitBreaker {}

@TimeoutSpec("resilient.timeout.itemApi")
public interface ItemApiTimeouter extends Timeouter {}
```

```java
@HttpClient("httpClient.itemApi")
public interface ItemApiClient {

    @Retryable(ItemApiRetry.class)
    @HttpRoute(method = HttpMethod.GET, path = "/items/{id}")
    @Json
    ItemResponse getItem(@Path String id);

    @Fallback(method = "listItemsFallback()")
    @Timeout(ItemApiTimeouter.class)
    @CircuitBreakable(ItemApiCircuitBreaker.class)
    @HttpRoute(method = HttpMethod.GET, path = "/items")
    @Json
    List<ItemResponse> listItems();

    default List<ItemResponse> listItemsFallback() {
        return List.of();
    }
}
```

`@Fallback` lost its `value` attribute — only `method` remains. AOP annotations on the interface
methods are copied onto the generated `$ItemApiClient_ClientImpl`, which the processor leaves
non-`final` so the aspect can subclass it.

```hocon
resilient {
  retry.itemApi { delay = 100ms, attempts = 3 }
  timeout.itemApi { duration = 5s }
  circuitbreaker.itemApi {
    type = FIXED_WINDOW
    countBased.windowSize = 20
    minimumRequiredCalls = 10
    failureRateThreshold = 50
    permittedCallsInHalfOpenState = 1
    waitDurationInOpenState = 10s
  }
}
```

Two traps carried over from the 1.x config: `slidingWindowSize` became `countBased.windowSize`,
and a circuit breaker section without `countBased` fails at graph init with
`IllegalArgumentException: CircuitBreaker '<name>' property 'countBased' is not configured`.
The `type` key is optional — it defaults to `STRIPED_APPROX`, which is itself count-based, so the
block is required whether or not you name a type. Named sections no longer inherit from `default`, so
every required value must be present in each section. Full reference:
[`kora-aop-resilient`](../../kora-aop-resilient/SKILL.md).

---

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `cannot find symbol: method code()` on the exception | It is `getCode()` in 2.0 (Kotlin: `e.code`) |
| `HttpClientResponseException` cannot be imported | Moved to `…http.client.common.exception` |
| Non-2xx silently returns instead of throwing | The method returns `Either` (status check disabled), or a `@Mapping` response mapper is attached (it is called for every status) |
| A malformed body throws `HttpClientDecoderException` whose cause is another `HttpClientDecoderException` | Your mapper threw `HttpClientDecoderException` itself; the generated client wraps every mapper failure once more — read `getCause()` |
| Connect timeout arrives as `HttpClientConnectionException`, not `HttpClientTimeoutException` | By design on every transport: timeouts are about an established call; failing to connect is a connection error |
| `HttpClientEncoderException` on every call | The request-body mapper throws — usually a `JsonWriter` for a type without `@Json` |
| `HttpClientTimeoutException` with no server log | `requestTimeout` fired before the server answered; it covers DNS, connect, write, processing and read |
| 404 on a URL that looks right | `url` + route `path` are concatenated verbatim — check for a doubled or missing `/`, and enable `telemetry.logging.enabled` with `pathFull = true` to see the real URI |
| `@Retry("name")` does not compile | 2.0 uses `@Retryable(Spec.class)` with a `@RetrySpec` interface |
| `IllegalArgumentException: CircuitBreaker 'X' property 'countBased' is not configured` | `countBased` is missing from that `resilient.circuitbreaker.<name>` section |

---

## See also

- [declarative-client-reference](declarative-client-reference.md)
- [execution-model-reference](execution-model-reference.md)
- [interceptors-reference](interceptors-reference.md)
- [transports-reference](transports-reference.md)
