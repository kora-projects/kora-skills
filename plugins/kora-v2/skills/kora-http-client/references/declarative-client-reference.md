# Declarative HTTP Client Reference (Kora 2.x)

Reference for [kora-http-client](../SKILL.md). Every API below is `io.koraframework.*`.

## Contents

- [What the processor generates](#what-the-processor-generates)
- [@HttpClient](#httpclient)
- [@HttpRoute](#httproute)
- [Path parameter: @Path](#path-parameter-path)
- [Query parameter: @Query](#query-parameter-query)
- [Header: @Header](#header-header)
- [Cookie: @Cookie](#cookie-cookie)
- [Body parameters](#body-parameters)
- [Form bodies](#form-bodies)
- [Custom request mapper: @Mapping](#custom-request-mapper-mapping)
- [Response mapping](#response-mapping)
- [Status-aware decoding: @ResponseCodeMapper](#status-aware-decoding-responsecodemapper)
- [Return types](#return-types)
- [Client configuration](#client-configuration)
- [The imperative HttpClient](#the-imperative-httpclient)

---

## What the processor generates

For `interface UserApiClient` in package `com.example`, the annotation processor / KSP emits three
types into the same package:

| Generated type | Role |
|---|---|
| `$UserApiClient_ClientImpl` | The implementation. Registered in the graph; carries `@Root`/`@Component` if the interface had them |
| `$UserApiClient_Config` | A `@ConfigMapper` interface extending `DeclarativeHttpClientConfig` — `url()`, `telemetry()`, `requestTimeout()`, plus one `HttpClientOperationConfig` method per client method |
| `$UserApiClient_Module` | A `@Module` that maps the config path onto `$UserApiClient_Config` |

The impl is left non-`final` when the interface carries AOP annotations, so resilience aspects
(`@Retryable`, `@CircuitBreakable`, `@Timeout`, `@Fallback`) can proxy it. AOP annotations declared
on interface methods are copied onto the generated overrides.

`$UserApiClient_Config` is injectable — inject it to read `url()` when hand-building a request.
In Kotlin the generated name must be back-quoted because of the leading `$`:

```kotlin
@Component
class ManualDataHttpClient(
    private val httpClient: HttpClient,
    private val dataApiConfig: `$DataApiClient_Config`
)
```

---

## @HttpClient

`io.koraframework.http.client.common.annotation.HttpClient`, `@Target(TYPE)`.

| Attribute | Type | Default | Meaning |
|---|---|---|---|
| `value` | `String` | `""` | Full config path for this client |
| `telemetryTag` | `Class<?>` | `Tag.class` | Tag used to resolve the `HttpClientTelemetryFactory` constructor parameter |
| `httpClientTag` | `Class<?>` | `Tag.class` | Tag used to resolve the base `HttpClient` constructor parameter |

There is **no** `configPath` and **no** `baseUrl`.

```java
@HttpClient("httpClient.externalApi")   // resolves httpClient.externalApi
public interface ExternalApiClient { }

@HttpClient                             // resolves httpClient.myApiClient
public interface MyApiClient { }
```

An empty `value` falls back to `"httpClient." + <interface name with the first letter lower-cased>`.

`telemetryTag` / `httpClientTag` exist for the case where several transports or telemetry
factories coexist in one graph: tag the alternative component and point the client at it. With a
single transport module both stay at their default and nothing has to be tagged.

---

## @HttpRoute

`io.koraframework.http.common.annotation.HttpRoute`, `@Target(METHOD)`.

| Attribute | Type | Meaning |
|---|---|---|
| `method` | `String` | Use the constants on `io.koraframework.http.common.HttpMethod` |
| `path` | `String` | Path appended to `url`; `{name}` placeholders bind to `@Path` parameters |

`HttpMethod` is a constant holder, not an enum: `GET`, `HEAD`, `POST`, `PUT`, `DELETE`, `CONNECT`,
`OPTIONS`, `TRACE`, `PATCH`, `QUERY`.

```java
@HttpRoute(method = HttpMethod.PUT, path = "/items/{id}")
@Json
Item updateItem(@Path String id, @Json UpdateItemRequest request);
```

A `{placeholder}` with no matching `@Path` parameter is a compile error:
`Path template contains parameters that have no matching @Path method parameter: [{id}]`.

---

## Path parameter: @Path

`io.koraframework.http.common.annotation.Path`. The placeholder name defaults to the argument
name; `@Path("userId")` overrides it. Values are URL-encoded, with `+` normalised to `%20`.

```java
@HttpRoute(method = HttpMethod.GET, path = "/users/{userId}/orders/{orderId}")
@Json
OrderResponse getOrder(@Path String userId, @Path String orderId);
```

Non-`String` types are converted by an `HttpClientParameterWriter<T>`. Writers ship for `Boolean`,
`Short`, `Integer`, `Long`, `Double`, `Float`, `UUID`, `BigDecimal`, `BigInteger`, `Duration`,
`Instant`, `LocalDate`, `LocalTime`, `LocalDateTime`, `OffsetTime`, `OffsetDateTime`,
`ZonedDateTime` (ISO-8601 for the temporal types). Anything else needs a `@Component`
`HttpClientParameterWriter<T>` or `@Mapping`.

---

## Query parameter: @Query

`io.koraframework.http.common.annotation.Query`.

```java
@HttpRoute(method = HttpMethod.GET, path = "/items")
@Json
List<Item> searchItems(@Query("category") String category,
                       @Nullable @Query("page") Integer page);
```

- Parameters are required unless marked `@Nullable` (Kotlin: `T?`); a `null` value is skipped.
- `Collection<T>` emits a repeated parameter — `List.of("1","2")` → `?ids=1&ids=2`. An **empty**
  collection emits the bare name with no value.
- `Map<String, ?>` emits one parameter per entry; a `null` entry value emits the bare name. The map
  key must be `String` — anything else is a compile error
  (`@Query map parameter has unsupported key type`).

---

## Header: @Header

`io.koraframework.http.common.annotation.Header`. Same naming, nullability, collection and map
rules as `@Query`.

```java
@HttpRoute(method = HttpMethod.GET, path = "/users/{id}")
@Json
UserResponse getUser(@Path String id,
                     @Nullable @Header("X-Request-ID") String requestId,
                     @Nullable @Header("headers") List<String> extra);
```

---

## Cookie: @Cookie

`io.koraframework.http.common.annotation.Cookie` (distinct from the value type
`io.koraframework.http.common.cookie.Cookie`).

```java
@HttpRoute(method = HttpMethod.GET, path = "/profile")
@Json
ProfileResponse getProfile(@Nullable @Cookie("sessionId") String sessionId);
```

---

## Body parameters

**Any parameter without `@Path`/`@Query`/`@Header`/`@Cookie` is the request body.** At most one.
The generator resolves an `HttpClientRequestMapper<T>` for its type; `HttpClientRequestMapperModule`
ships mappers for:

| Body type | Content-Type |
|---|---|
| `String` | `text/plain;charset=utf-8` |
| `byte[]`, `ByteBuffer` | `application/octet-stream` |
| `HttpBodyOutput` | passed through as-is |
| `FormUrlEncoded` | `application/x-www-form-urlencoded` |
| `FormMultipart` | `multipart/form-data` |
| `@Json T` | `application/json`, via `JsonWriter<T>` |

`@Json` on the parameter selects the JSON mapper; `@Json` on the **method** selects the JSON
response mapper. The DTO itself must be `@Json`-annotated so `json-common` generates its
reader/writer.

```java
@HttpRoute(method = HttpMethod.POST, path = "/users")
@Json
UserResponse createUser(@Json CreateUserRequest request);

@Json record CreateUserRequest(String email, String name) {}
@Json record UserResponse(String id, String email, String name) {}
```

Anything a mapper cannot be found for fails the graph build with the module hint
*"HttpClientRequestMapper<T> was not found …"*.

---

## Form bodies

`io.koraframework.http.common.form.FormUrlEncoded` / `FormMultipart`.

```java
@HttpRoute(method = HttpMethod.POST, path = "/data/form")
String processForm(FormUrlEncoded body);

@HttpRoute(method = HttpMethod.POST, path = "/data/upload")
@Json
UploadResponse processUpload(FormMultipart body);
```

```java
var form = new FormUrlEncoded(
        new FormUrlEncoded.FormPart("name", "kora"),
        new FormUrlEncoded.FormPart("tags", List.of("a", "b")));

var multipart = new FormMultipart(List.of(
        FormMultipart.data("field1", "some data content"),
        FormMultipart.file("field2", "example1.txt", "text/plain",
                "some file content".getBytes(StandardCharsets.UTF_8))));
```

`FormMultipart.file` also has an `HttpBodyOutput` overload for streaming uploads.

---

## Custom request mapper: @Mapping

Implement `io.koraframework.http.client.common.request.HttpClientRequestMapper<T>` and reference it
with `io.koraframework.common.annotation.Mapping` on the body parameter.

```java
record PlainTextGreetingBody(String name) {}

@Component
final class GreetingRequestMapper implements HttpClientRequestMapper<PlainTextGreetingBody> {

    @Override
    public HttpBodyOutput apply(PlainTextGreetingBody value) {
        return HttpBody.plaintext("Hello " + value.name());
    }
}

@HttpRoute(method = HttpMethod.POST, path = "/data/mapping-request")
String processMappedRequest(@Mapping(GreetingRequestMapper.class) PlainTextGreetingBody body);
```

`apply(T)` takes a single argument — the 1.x `apply(Context, T)` signature is gone.

**A `@Mapping` request mapper is always a constructor parameter of the generated client, so it
always needs `@Component`** (or a `@Module` factory method). Without it:
`No component found for dependency: … (no tags)`.

---

## Response mapping

`io.koraframework.http.client.common.response.HttpClientResponseMapper<T>`:

```java
public interface HttpClientResponseMapper<T> extends Mapping.MappingFunction {
    @Nullable T apply(HttpClientResponse response) throws IOException, HttpClientDecoderException;
}
```

`HttpClientResponse` is `Closeable` and exposes `code()`, `headers()`, `body()` (an
`HttpBodyInput` with `asInputStream()` and `getFullContentIfAvailable()`). The generated client
already closes the response in a try-with-resources — read the body inside `apply`, never after it
returns.

### What ships out of the box

`HttpClientResponseMapperModule` supplies, all as `@DefaultComponent`:

| Result type | Note |
|---|---|
| `String`, `byte[]`, `ByteBuffer`, `HttpBodyInput` | concrete mappers |
| `HttpResponseEntity<T>` | **template** — needs an `HttpClientResponseMapper<T>` for the payload |
| `HttpResponseEntity<T>` with `@Json` | template — needs a `JsonReader<T>` |
| `Either<T, E>` and `HttpResponseEntity<Either<T, E>>` | templates over the success/error mappers |
| `T` with `@Json` | via `JsonReader<T>` |

Because the entity form is a template, `HttpResponseEntity<Void>` needs an explicit
`HttpClientResponseMapper<Void>` component — see [SKILL.md](../SKILL.md#httpresponseentityvoid-needs-its-own-payload-mapper).

### Attaching your own with @Mapping

```java
final class TextResponseMapper implements HttpClientResponseMapper<String> {

    @Override
    public String apply(HttpClientResponse response) throws IOException {
        try (var is = response.body().asInputStream()) {
            return new String(is.readAllBytes(), StandardCharsets.UTF_8);
        }
    }
}

@Mapping(TextResponseMapper.class)
@HttpRoute(method = HttpMethod.GET, path = "/text")
String getText();
```

A `@Mapping` response mapper **bypasses the status check**: the mapper is called for every status
code, and a non-2xx response no longer throws `HttpClientResponseException` on its own.

`@Component` on it is required only when the generator cannot construct it — i.e. when the class is
not `final` (Kotlin: `open`) or its constructor takes arguments.

---

## Status-aware decoding: @ResponseCodeMapper

`io.koraframework.http.client.common.annotation.ResponseCodeMapper`, repeatable, `@Target(METHOD)`.

| Attribute | Type | Meaning |
|---|---|---|
| `code` | `int` | HTTP status this handler covers; `ResponseCodeMapper.DEFAULT` (`-1`) covers everything else |
| `type` | `Class<?>` | Payload type when it differs from the method return type |
| `mapper` | `Class<? extends HttpClientResponseMapper>` | The handler implementation |

```java
@ResponseCodeMapper(code = DEFAULT, mapper = ResponseErrorMapper.class)
@ResponseCodeMapper(code = 200, mapper = ResponseSuccessMapper.class)
@HttpRoute(method = HttpMethod.GET, path = "/mapping_by_code/{code}")
UserResponse get(@Path String code);
```

The generated body becomes a `switch (_code)`. Codes without a mapper and no `DEFAULT` entry throw
`HttpClientResponseException`. If the mapper's type argument is **not** assignable to the method's
return type, the generated code `throw`s the mapper result instead of returning it — that is how a
mapper producing an exception type is wired.

`@Component` follows the same constructor rule as `@Mapping`: the two dependency-free `final`
mappers above are built by the generated code, whereas a mapper taking a `JsonReader<T>` must be a
component:

```java
@Component
final class MappedResponseSuccessMapper implements HttpClientResponseMapper<MappedResponse> {

    private final JsonReader<Payload> jsonReader;

    public MappedResponseSuccessMapper(JsonReader<Payload> jsonReader) {
        this.jsonReader = jsonReader;
    }

    @Override
    public MappedResponse apply(HttpClientResponse response) throws IOException {
        try (var is = response.body().asInputStream()) {
            return this.jsonReader.read(is.readAllBytes());
        }
    }
}
```

---

## Return types

| Return type | Behaviour |
|---|---|
| `void` (Kotlin `Unit`) | 2xx returns, non-2xx throws `HttpClientResponseException`. No mapper needed |
| `Void` | Same, and returns `null` — still no mapper needed |
| `T` | Decoded on 2xx; non-2xx throws `HttpClientResponseException` |
| `HttpResponseEntity<T>` | Body plus `code()` and `headers()`; still throws on non-2xx unless `T` is `Either` |
| `Either<T, E>` and `HttpResponseEntity<Either<T, E>>` | **No status check at all** — 2xx becomes `Either.left`, everything else `Either.right` |

`CompletionStage<T>` and `Mono<T>` are not supported contracts: the processor prints
*"Method has async signature, this might not work correctly"* and then fails to resolve
`HttpClientResponseMapper<CompletionStage<T>>`. A Kotlin `suspend` method is a hard KSP error. See
[execution-model-reference](execution-model-reference.md).

---

## Client configuration

The client config type extends `DeclarativeHttpClientConfig`:

| Key | Type | Required | Meaning |
|---|---|---|---|
| `url` | `String` | **yes** | Base URL; the route path is appended |
| `requestTimeout` | `Duration` | no | Whole-call budget: DNS, connect, write, server processing, read |
| `telemetry.logging.*` | object | no | `enabled` (**false** by default), `maskQueries`, `maskHeaders`, `pathFull`, `maxRequestBodyLogSize`, `maxResponseBodyLogSize` — no `mask` key, see [Log masking](transports-reference.md#log-masking) |
| `telemetry.metrics.*` | object | no | `enabled` (**false** by default), `slo`, `tags` |
| `telemetry.tracing.*` | object | no | `enabled` (**true** by default), `attributes`, `pathFull` (default `true`) |
| `<methodName>` | object | no | Per-operation override: `requestTimeout` and the same three telemetry sections |

```hocon
httpClient {
  userApi {
    url = "http://users-service:8080"
    url = ${?USERS_API_URL}
    requestTimeout = 10s

    telemetry {
      logging {
        enabled = true
        maskQueries = ["token"]
        maskHeaders = ["authorization", "cookie", "set-cookie"]
        pathFull = false
        maxResponseBodyLogSize = "2MiB"
      }
      metrics.enabled = true
      tracing.attributes = { "peer.service" = "users-service" }
    }

    getUser { requestTimeout = 3s }
    listUsers { telemetry.logging.enabled = false }
  }
}
```

Per-operation keys are the **method names** of the client interface. Every operation-level
telemetry field is nullable and falls back to the client-level value when absent.

The `slo` list is in milliseconds when written as bare numbers
(`slo = [1, 10, 50, 100, 200, 500, 1000, 2000, 5000]`); size values accept `"2MiB"`, `"512KiB"`,
`"1MB"` or a bare byte count.

Transport-wide keys (`connectTimeout`, `readTimeout`, `proxy`, `useEnvProxy`) live at `httpClient`,
not inside the per-client block — see [transports-reference](transports-reference.md).

---

## The imperative HttpClient

Inject `io.koraframework.http.client.common.HttpClient` when a declarative interface does not fit.
`execute` is synchronous and returns a `Closeable` response.

```java
@Component
public final class ManualDataHttpClient {

    private final HttpClient httpClient;
    private final $DataApiClient_Config dataApiConfig;
    private final ApiKeyAuthInterceptor apiKeyAuthInterceptor;

    public ManualDataHttpClient(HttpClient httpClient,
                                $DataApiClient_Config dataApiConfig,
                                ApiKeyAuthInterceptor apiKeyAuthInterceptor) {
        this.httpClient = httpClient;
        this.dataApiConfig = dataApiConfig;
        this.apiKeyAuthInterceptor = apiKeyAuthInterceptor;
    }

    public String ping() {
        var request = HttpClientRequest.get(this.dataApiConfig.url() + "/manual/data/ping")
                .header("x-trace-id", UUID.randomUUID().toString())
                .queryParam("verbose", true)
                .requestTimeout(Duration.ofSeconds(5))
                .build();

        try (var response = this.httpClient.with(this.apiKeyAuthInterceptor).execute(request)) {
            if (response.code() != 200) {
                throw new IllegalStateException("Manual HTTP call failed with " + response.code());
            }
            try (var body = response.body().asInputStream()) {
                return new String(body.readAllBytes(), StandardCharsets.UTF_8);
            }
        } catch (IOException e) {
            throw new IllegalStateException("Failed to read manual HTTP response body", e);
        }
    }
}
```

`HttpClientRequest` has per-method builders (`get`, `head`, `post`, `put`, `delete`, `connect`,
`options`, `trace`, `patch`) plus `of(method, uriTemplate)`. Builder methods:
`pathParam`, `queryParam`, `queryParamRemove`, `header`, `headerRemove`, `requestTimeout`, `body`.
`pathParam` replaces the 1.x `templateParam`.

`httpClient.with(interceptor)` returns a decorated `HttpClient` — it does not mutate the injected one.

---

## See also

- [execution-model-reference](execution-model-reference.md)
- [error-handling-guide](error-handling-guide.md)
- [interceptors-reference](interceptors-reference.md)
- [transports-reference](transports-reference.md)
