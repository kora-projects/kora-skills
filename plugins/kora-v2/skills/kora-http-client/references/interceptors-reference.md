# HTTP Client Interceptors Reference (Kora 2.x)

Reference for [kora-http-client](../SKILL.md). Verified against the framework source at tag
**`2.0.0.RC2`**.

## Contents

- [The contract](#the-contract)
- [@InterceptWith](#interceptwith)
- [Every interceptor must be a graph component](#every-interceptor-must-be-a-graph-component)
- [Interceptor with dependencies](#interceptor-with-dependencies)
- [Chain order](#chain-order)
- [Modifying the request](#modifying-the-request)
- [Reading or replacing the response](#reading-or-replacing-the-response)
- [Built-in auth interceptors](#built-in-auth-interceptors)
- [Applying an interceptor imperatively](#applying-an-interceptor-imperatively)
- [Testing](#testing)
- [Troubleshooting](#troubleshooting)

---

## The contract

`io.koraframework.http.client.common.interceptor.HttpClientInterceptor`:

```java
public interface HttpClientInterceptor {

    HttpClientResponse processRequest(InterceptChain chain, HttpClientRequest request) throws Exception;

    interface InterceptChain {
        HttpClientResponse process(HttpClientRequest request) throws Exception;
    }

    static HttpClientInterceptor noop() {
        return InterceptChain::process;
    }
}
```

Three changes from Kora 1.x, all breaking:

| 1.x | 2.0 |
|---|---|
| `CompletionStage<HttpClientResponse> processRequest(Context, InterceptChain, HttpClientRequest)` | `HttpClientResponse processRequest(InterceptChain, HttpClientRequest)` |
| `chain.process(ctx, request)` | `chain.process(request)` |
| chain argument came second | **chain argument comes first** |

`Context` was removed from the framework entirely, so there is nothing to migrate it to. Tracing
and logging context is carried by the built-in `TelemetryInterceptor`, which the generated client
installs as the innermost interceptor.

The method may throw any `Exception`. Anything that is not an `HttpClientException` is wrapped in
`HttpClientUnknownException` by the generated client.

---

## @InterceptWith

`io.koraframework.http.common.annotation.InterceptWith` — the same annotation the HTTP **server**
uses. Repeatable, `@Target({METHOD, TYPE})`.

| Attribute | Type | Default | Meaning |
|---|---|---|---|
| `value` | `Class<?>` | — | The interceptor implementation |
| `tag` | `Class<?>` | `Tag.class` | Resolve the interceptor component under this `@Tag` |

```java
@InterceptWith(ApiKeyAuthInterceptor.class)
@HttpClient("httpClient.dataApi")
public interface DataApiClient {

    @InterceptWith(MethodLoggingInterceptor.class)
    @HttpRoute(method = HttpMethod.GET, path = "/items/{id}")
    @Json
    ItemResponse getItem(@Path String id);
}
```

An interface-level `@InterceptWith` applies to every method; a method-level one applies to that
method only. The generator de-duplicates: an interceptor declared on both the interface and a
method is installed once for that method.

`tag` is how two configurations of the same interceptor class coexist:

```java
@InterceptWith(value = BearerAuthHttpClientInterceptor.class, tag = PartnerApi.class)
@HttpClient("httpClient.partnerApi")
public interface PartnerApiClient { }
```

---

## Every interceptor must be a graph component

Unlike some response mappers, an `@InterceptWith` class is **always** a constructor parameter of
the generated client — the generator never instantiates it. It therefore always needs `@Component`
(or a `default` method in a `@Module`).

```java
@InterceptWith(InterceptedHttpClient.ClientInterceptor.class)
@HttpClient("httpClient.default")
public interface InterceptedHttpClient {

    @Component
    final class ClientInterceptor implements HttpClientInterceptor {

        private static final Logger logger = LoggerFactory.getLogger(ClientInterceptor.class);

        @Override
        public HttpClientResponse processRequest(InterceptChain chain, HttpClientRequest request) throws Exception {
            logger.info("Client Level Interceptor");
            return chain.process(request);
        }
    }

    @Component
    final class MethodInterceptor implements HttpClientInterceptor {

        private static final Logger logger = LoggerFactory.getLogger(MethodInterceptor.class);

        @Override
        public HttpClientResponse processRequest(InterceptChain chain, HttpClientRequest request) throws Exception {
            logger.info("Method Level Interceptor");
            return chain.process(request);
        }
    }

    @InterceptWith(MethodInterceptor.class)
    @HttpRoute(method = HttpMethod.GET, path = "/intercepted")
    HttpResponseEntity<String> get();
}
```

```kotlin
@InterceptWith(InterceptedHttpClient.ClientInterceptor::class)
@HttpClient("httpClient.default")
interface InterceptedHttpClient {

    @Component
    class ClientInterceptor : HttpClientInterceptor {
        private val logger = LoggerFactory.getLogger(ClientInterceptor::class.java)

        override fun processRequest(
            chain: HttpClientInterceptor.InterceptChain,
            request: HttpClientRequest
        ): HttpClientResponse {
            logger.info("Client Level Interceptor")
            return chain.process(request)
        }
    }

    @InterceptWith(ClientInterceptor::class)
    @HttpRoute(method = HttpMethod.GET, path = "/intercepted")
    fun get(): HttpResponseEntity<String>
}
```

Nested classes inside the client interface are fine — that is what the reference example does.
Missing `@Component` gives:

```
No component found for dependency: InterceptedHttpClient.ClientInterceptor (no tags)
```

---

## Interceptor with dependencies

Constructor injection, like any component. Typed config comes from a `@ConfigSource` interface —
Kora has no `@ConfigValue`-style annotation.

```java
@ConfigSource("auth.apiKey")
public interface ApiKeyAuthConfig {
    String value();
}

@Component
public final class ApiKeyAuthInterceptor implements HttpClientInterceptor {

    private final ApiKeyAuthConfig config;

    public ApiKeyAuthInterceptor(ApiKeyAuthConfig config) {
        this.config = config;
    }

    @Override
    public HttpClientResponse processRequest(InterceptChain chain, HttpClientRequest request) throws Exception {
        var authorizedRequest = request.toBuilder()
                .header("Authorization", this.config.value())
                .build();
        return chain.process(authorizedRequest);
    }
}
```

```hocon
auth.apiKey {
  value = "MySecuredApiKey"
  value = ${?HTTP_API_KEY}
}
```

---

## Chain order

The generated constructor builds the chain as

```java
this.getClient = get.client()
  .with($interceptorMethodN) … .with($interceptorMethod1)
  .with($interceptorClassN)  … .with($interceptorClass1);
```

`HttpClient.with(i)` wraps the receiver, so the **last** `with` is the outermost. Net effect,
outermost first:

```
class interceptors, in declaration order
  → method interceptors, in declaration order
    → TelemetryInterceptor (logging / metrics / tracing)
      → the transport
```

So with

```java
@InterceptWith(LoggingInterceptor.class)
@InterceptWith(ApiKeyAuthInterceptor.class)
@HttpClient("httpClient.someApi")
public interface SomeApiClient {

    @InterceptWith(RetryHeaderInterceptor.class)
    @HttpRoute(method = HttpMethod.GET, path = "/x")
    String x();
}
```

`x()` runs `LoggingInterceptor` → `ApiKeyAuthInterceptor` → `RetryHeaderInterceptor` → telemetry →
transport, and responses unwind in reverse. Identical in the Java processor and in KSP.

Because telemetry is innermost, a header added by an interceptor **is** visible in the request log
(and is masked by `telemetry.logging.maskHeaders`, which covers `authorization` by default — see
[transports-reference → Log masking](transports-reference.md#log-masking)).

---

## Modifying the request

`HttpClientRequest` is immutable. `toBuilder()` returns an `HttpClientRequestBuilder`; mutating
attempts on the original are simply not available.

```java
var modified = request.toBuilder()
        .header("X-Request-ID", UUID.randomUUID().toString())
        .headerRemove("x-internal")
        .queryParam("trace", true)
        .requestTimeout(Duration.ofSeconds(3))
        .build();
return chain.process(modified);
```

Builder methods: `pathParam`, `queryParam`, `queryParamRemove`, `header`, `headerRemove`,
`requestTimeout`, `body`, `build`. `header(String, String)` **replaces**; `header(String,
List<String>)` sets a multi-value header.

Read-only inspection of the incoming request: `method()`, `uri()`, `uriTemplate()`, `headers()`,
`body()`, `requestTimeout()`. `uriTemplate()` is the un-substituted route path — the right thing to
key metrics or routing decisions on, since `uri()` has path parameters baked in.

```java
if (HttpMethod.POST.equals(request.method())) {
    log.info("POST {}", request.uriTemplate());
}
```

---

## Reading or replacing the response

`chain.process(...)` returns the response synchronously, so post-processing is ordinary code.

```java
@Override
public HttpClientResponse processRequest(InterceptChain chain, HttpClientRequest request) throws Exception {
    var started = System.nanoTime();
    try {
        var response = chain.process(request);
        log.info("{} {} -> {} in {}ms", request.method(), request.uriTemplate(),
                response.code(), (System.nanoTime() - started) / 1_000_000);
        return response;
    } catch (HttpClientException e) {
        log.warn("{} {} failed", request.method(), request.uriTemplate(), e);
        throw e;
    }
}
```

**Do not consume the body in an interceptor.** `HttpClientResponse.body()` is an `HttpBodyInput`
backed by the live connection; reading it leaves nothing for the response mapper. If a value is
genuinely needed, read `getFullContentIfAvailable()` (returns `null` when the body is streamed) and
never `asInputStream()`.

An interceptor may also short-circuit by returning a response without calling `chain.process` —
useful for a cache or a circuit-breaker style guard.

---

## Built-in auth interceptors

Three ship in `io.koraframework.http.client.common.interceptor`. None is registered by any module,
so expose the one you need as a component with the credentials it needs.

### Basic

```java
public class BasicAuthHttpClientInterceptor implements HttpClientInterceptor {
    public BasicAuthHttpClientInterceptor(HttpClientTokenProvider tokenProvider);
    public BasicAuthHttpClientInterceptor(String username, String password);
}
```

Sets `authorization: Basic <base64(user:password)>`, with `user:password` encoded as UTF-8.
`BasicAuthHttpClientTokenProvider` returns `null` when either credential is `null`, and a `null` or
blank token means the request passes through **unmodified** — a silent no-auth call rather than an
error.

```java
@Module
public interface BasicAuthModule {

    @ConfigSource("auth.basic")
    interface BasicAuthConfig {
        String username();
        String password();
    }

    default BasicAuthHttpClientInterceptor basicAuthInterceptor(BasicAuthConfig config) {
        return new BasicAuthHttpClientInterceptor(config.username(), config.password());
    }
}

@InterceptWith(BasicAuthHttpClientInterceptor.class)
@HttpClient("httpClient.someApi")
public interface SomeApiClient { }
```

### API key

```java
public final class ApiKeyHttpClientInterceptor implements HttpClientInterceptor {
    public enum ApiKeyLocation { HEADER, QUERY, COOKIE }
    public ApiKeyHttpClientInterceptor(ApiKeyLocation location, String parameterName, HttpClientTokenProvider tokenProvider);
    public ApiKeyHttpClientInterceptor(ApiKeyLocation location, String parameterName, String secret);
}
```

`HEADER` adds `parameterName: secret`, `QUERY` appends `?parameterName=secret`, `COOKIE` appends
`parameterName=secret` to the request's existing `Cookie` header (or creates it). The value is read
per request; the `HttpClientTokenProvider` form rotates keys without rebuilding the interceptor.
Like Basic and Bearer, a `null` or blank value **skips** the parameter and sends the request
unauthenticated — a missing key is not caught at graph build, so test the header's presence.

```java
@Module
public interface ApiKeyAuthModule {

    @ConfigSource("auth.apiKey")
    interface ApiKeyConfig {
        String apiKey();
    }

    default ApiKeyHttpClientInterceptor apiKeyInterceptor(ApiKeyConfig config) {
        return new ApiKeyHttpClientInterceptor(
                ApiKeyHttpClientInterceptor.ApiKeyLocation.HEADER, "X-API-KEY", config.apiKey());
    }
}
```

### Bearer / OAuth

```java
public class BearerAuthHttpClientInterceptor implements HttpClientInterceptor {
    public BearerAuthHttpClientInterceptor(HttpClientTokenProvider tokenProvider);
    public BearerAuthHttpClientInterceptor(String token);
}
```

Sets `authorization: Bearer <token>`; a `null` or blank token again passes the request through
unmodified.

The token provider is synchronous in 2.0:

```java
public interface HttpClientTokenProvider {
    @Nullable String getToken(HttpClientRequest request);
}
```

```java
@Component
public final class CachingTokenProvider implements HttpClientTokenProvider {

    private final OAuthTokenClient tokenClient;
    private final AtomicReference<CachedToken> cache = new AtomicReference<>();

    public CachingTokenProvider(OAuthTokenClient tokenClient) {
        this.tokenClient = tokenClient;
    }

    @Override
    public String getToken(HttpClientRequest request) {
        var cached = this.cache.get();
        if (cached != null && cached.isValid()) {
            return cached.token();
        }
        var fresh = this.tokenClient.issueToken();   // a blocking Kora HTTP client call
        this.cache.set(CachedToken.of(fresh));
        return fresh.accessToken();
    }
}
```

```kotlin
@Component
class CachingTokenProvider(private val tokenClient: OAuthTokenClient) : HttpClientTokenProvider {
    override fun getToken(request: HttpClientRequest): String? = /* … */
}
```

The `String?` return type is required in Kotlin — the contract is `@NullMarked` with `@Nullable` on
the result. Token-refresh strategies in depth:
[`kora-http-client-auth`](../../kora-http-client-auth/SKILL.md).

---

## Applying an interceptor imperatively

`HttpClient.with(interceptor)` returns a decorated client and leaves the injected one untouched —
this is how the base `HttpClient` reuses a declarative client's interceptor:

```java
var response = this.httpClient.with(this.apiKeyAuthInterceptor).execute(request);
```

Interceptors compose the same way here: the last `with` is the outermost.

---

## Testing

The synchronous contract makes an interceptor a plain unit under test — the chain is a lambda:

```java
@Test
void addsApiKeyHeader() throws Exception {
    var interceptor = new ApiKeyAuthInterceptor(() -> "secret");
    var request = HttpClientRequest.get("http://localhost/x").build();
    var captured = new AtomicReference<HttpClientRequest>();

    interceptor.processRequest(rq -> { captured.set(rq); return stubResponse; }, request);

    assertThat(captured.get().headers().getFirst("Authorization")).isEqualTo("secret");
}
```

No `Context`, no `CompletionStage`, no `runBlocking`.

---

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `No component found for dependency: <Interceptor>` | `@InterceptWith` classes are always injected — add `@Component` or a `@Module` factory method |
| `'processRequest' overrides nothing` (Kotlin) | The chain is now the **first** parameter: `processRequest(chain: HttpClientInterceptor.InterceptChain, request: HttpClientRequest)` |
| `processRequest` will not compile in Java | Drop the `Context` parameter and return `HttpClientResponse`, not `CompletionStage` |
| Header change has no effect | `request.toBuilder().header(…).build()` and pass the **new** request to `chain.process` |
| Auth silently missing, no error | `BasicAuth`/`BearerAuth`/`ApiKey` interceptors pass the request through unchanged when the token (or key) is `null` or blank |
| Interceptor runs but the body is empty downstream | The body was consumed in the interceptor — use `getFullContentIfAvailable()` or do not read it |
| Wrong `@InterceptWith` import | `io.koraframework.http.common.annotation.InterceptWith` — the same one the server uses |
| Two interceptors of the same class, one config wins | Give each a distinct `@Tag` and select it with `@InterceptWith(value = X.class, tag = Y.class)` |

---

## See also

- [declarative-client-reference](declarative-client-reference.md)
- [error-handling-guide](error-handling-guide.md)
- [execution-model-reference](execution-model-reference.md)
- [transports-reference](transports-reference.md)
