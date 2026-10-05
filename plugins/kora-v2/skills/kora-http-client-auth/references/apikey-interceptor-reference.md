# Hand-written `HttpClientInterceptor` Reference

Writing your own interceptor when `ApiKeyHttpClientInterceptor`,
`BasicAuthHttpClientInterceptor` and `BearerAuthHttpClientInterceptor` do not fit.

## Contents

- [Try the built-in first](#try-the-built-in-first)
- [The contract](#the-contract)
- [Registration](#registration)
- [API key in a header](#api-key-in-a-header)
- [API key in a query parameter](#api-key-in-a-query-parameter)
- [API key in a cookie](#api-key-in-a-cookie)
- [Signing a request](#signing-a-request)
- [Order and composition](#order-and-composition)
- [The response you throw away must be closed](#the-response-you-throw-away-must-be-closed)
- [Kotlin](#kotlin)
- [Testing](#testing)
- [Porting a 1.x interceptor](#porting-a-1x-interceptor)
- [See also](#see-also)

---

## Try the built-in first

`ApiKeyHttpClientInterceptor(location, name, secret)` already covers a static key in a header, a
query parameter or a cookie — see
[http-client-auth-reference.md](http-client-auth-reference.md). Hand-write an interceptor only when
you need something it cannot express:

- a value that depends on the request (a signature over method + path + body);
- two credentials on one request;
- retrying after a `401`;
- a scheme that is not "put this constant somewhere".

---

## The contract

```java
package io.koraframework.http.client.common.interceptor;

public interface HttpClientInterceptor {

    HttpClientResponse processRequest(InterceptChain chain, HttpClientRequest request) throws Exception;

    interface InterceptChain {
        HttpClientResponse process(HttpClientRequest request) throws Exception;
    }
}
```

Synchronous, running on a virtual thread. There is no `Context` parameter — `Context` was removed
from Kora 2.0 entirely — and no `CompletionStage`. `InterceptChain` is nested in
`HttpClientInterceptor`, so Java sees it unqualified inside an implementation while Kotlin needs
`HttpClientInterceptor.InterceptChain`.

Every path must end in `chain.process(...)`; skipping it means the request is never sent.

Imports:

```java
import io.koraframework.common.annotation.Component;
import io.koraframework.http.client.common.interceptor.HttpClientInterceptor;
import io.koraframework.http.client.common.request.HttpClientRequest;
import io.koraframework.http.client.common.response.HttpClientResponse;
```

`HttpClientRequest` is immutable. `request.toBuilder()` gives a
`HttpClientRequestBuilder`; mutate that and `build()`.

| Builder call | Semantics |
|---|---|
| `header(name, value)` | **replaces** every existing value of that header |
| `header(name, List<String>)` | replaces with the whole list |
| `headerRemove(name)` | drops the header |
| `queryParam(name, value)` | **appends** — calling it twice sends the parameter twice |
| `queryParamRemove(name)` | drops every value of that parameter |
| `body(HttpBodyOutput)` / `requestTimeout(...)` / `pathParam(...)` | as named |

Header names are lower-cased when stored, so `request.headers().getFirst("authorization")` finds a
header written as `"Authorization"`.

---

## Registration

`@InterceptWith(X.class)` makes the generated client take `X` as a constructor parameter, so `X`
must be in the graph — with **exactly one** provider:

```java
@Component
public final class ApiKeyClientInterceptor implements HttpClientInterceptor { … }
```

This applies whether or not the class has constructor dependencies. Upstream's migrated examples
annotate interceptors that take no arguments at all
(`InterceptedHttpClient.ClientInterceptor`, `DataApiClient.MethodLoggingInterceptor`). The
"dependency-free ⇒ no `@Component`" rule belongs to **mappers**, which have generated module
factories; interceptors have none.

Adding a `@Module` factory on top of `@Component` produces
`Multiple components match dependency:`. Providing neither produces
`No component found for dependency:`.

An interceptor nested inside the client interface is a normal component and is the tidiest place
for a single-client one:

```java
@InterceptWith(ExternalApiClient.SignatureInterceptor.class)
@HttpClient("httpClient.externalApi")
public interface ExternalApiClient {

    @Component
    final class SignatureInterceptor implements HttpClientInterceptor { … }

    @HttpRoute(method = HttpMethod.GET, path = "/resource")
    @Json
    Resource getResource();
}
```

---

## API key in a header

```java
@ConfigSource("auth.externalApi")
public interface ExternalApiAuthConfig {

    String key();
}
```

```java
@Component
public final class ApiKeyClientInterceptor implements HttpClientInterceptor {

    private final ExternalApiAuthConfig config;

    public ApiKeyClientInterceptor(ExternalApiAuthConfig config) {
        this.config = config;
    }

    @Override
    public HttpClientResponse processRequest(InterceptChain chain, HttpClientRequest request) throws Exception {
        var authorized = request.toBuilder()
                .header("X-Custom-API-Key", config.key())
                .build();
        return chain.process(authorized);
    }
}
```

---

## API key in a query parameter

`queryParam` appends, so remove before adding if the interceptor can run more than once on the
same request (a retry, or the same interceptor attached at class **and** method level):

```java
@Override
public HttpClientResponse processRequest(InterceptChain chain, HttpClientRequest request) throws Exception {
    var authorized = request.toBuilder()
            .queryParamRemove("api_key")
            .queryParam("api_key", config.key())
            .build();
    return chain.process(authorized);
}
```

A key in the URL is logged by every proxy on the path. If you enable client logging, add the
parameter name to `telemetry.logging.maskQueries` — nothing is masked there by default.

---

## API key in a cookie

`header("Cookie", …)` replaces the whole header, so preserve what the request already carries:

```java
@Override
public HttpClientResponse processRequest(InterceptChain chain, HttpClientRequest request) throws Exception {
    var apiKeyCookie = Cookie.of("api_key", config.key()).toValue();
    var existing = request.headers().getFirst("cookie");
    var cookieHeader = (existing == null || existing.isBlank())
            ? apiKeyCookie
            : existing + "; " + apiKeyCookie;

    return chain.process(request.toBuilder().header("Cookie", cookieHeader).build());
}
```

`io.koraframework.http.common.cookie.Cookie`. The built-in `ApiKeyHttpClientInterceptor` with
`ApiKeyLocation.COOKIE` performs the same merge, so hand-write this only when the cookie needs
something the built-in cannot express.

---

## Signing a request

Values derived from the request are exactly what the built-ins cannot do:

```java
@Component
public final class SignatureInterceptor implements HttpClientInterceptor {

    private final SigningConfig config;

    public SignatureInterceptor(SigningConfig config) {
        this.config = config;
    }

    @Override
    public HttpClientResponse processRequest(InterceptChain chain, HttpClientRequest request) throws Exception {
        var timestamp = Long.toString(Instant.now().getEpochSecond());
        var canonical = request.method() + "\n" + request.uri().getRawPath() + "\n" + timestamp;

        var mac = Mac.getInstance("HmacSHA256");
        mac.init(new SecretKeySpec(config.secret().getBytes(StandardCharsets.UTF_8), "HmacSHA256"));
        var signature = HexFormat.of().formatHex(mac.doFinal(canonical.getBytes(StandardCharsets.UTF_8)));

        var signed = request.toBuilder()
                .header("X-Timestamp", timestamp)
                .header("X-Signature", signature)
                .build();
        return chain.process(signed);
    }
}
```

Signing the **body** is not generally possible here: `HttpBodyOutput` is a write-once stream, not a
buffer you can read and re-attach. Sign the method, path, query and timestamp, or produce the body
yourself in a `HttpClientRequestMapper` where you still hold the bytes.

---

## Order and composition

- Class-level `@InterceptWith` runs **before** method-level.
- Several class-level annotations run in declaration order (`@InterceptWith` is `@Repeatable`).
- Kora's own `TelemetryInterceptor` is applied by the generated client around your interceptors, so
  the request your interceptor produces is the one that gets logged and traced. Anything you add
  there is subject to the masking rules.
- Duplicates are collapsed: the same interceptor class (with the same tag) named at both class and
  method level is injected and applied once.

---

## The response you throw away must be closed

`HttpClientResponse extends Closeable`. The generated client wraps the response it finally gets in
`try (var _response = _client.execute(_request))`, so the **last** response is closed for you. A
response your interceptor discards — a `401` you are about to retry, a redirect you follow by hand
— is not:

```java
@Override
public HttpClientResponse processRequest(InterceptChain chain, HttpClientRequest request) throws Exception {
    var response = chain.process(withCredential(request));
    if (response.code() != 401) {
        return response;
    }
    response.close();                       // required — nothing else will close it
    tokens.invalidate();
    return chain.process(withCredential(request));
}
```

Never return the same `HttpClientResponse` twice, and never read its body and then return it — the
body is a one-shot `InputStream`.

---

## Kotlin

```kotlin
package com.example.client

import io.koraframework.common.annotation.Component
import io.koraframework.http.client.common.interceptor.HttpClientInterceptor
import io.koraframework.http.client.common.request.HttpClientRequest
import io.koraframework.http.client.common.response.HttpClientResponse

@Component
class ApiKeyClientInterceptor(
    private val config: ExternalApiAuthConfig
) : HttpClientInterceptor {

    override fun processRequest(
        chain: HttpClientInterceptor.InterceptChain,
        request: HttpClientRequest
    ): HttpClientResponse {
        val authorized = request.toBuilder()
            .header("X-Custom-API-Key", config.key())
            .build()
        return chain.process(authorized)
    }
}
```

- Qualify the nested type: `HttpClientInterceptor.InterceptChain`. An unqualified `InterceptChain`
  does not resolve, and a wrong signature is reported as `'processRequest' overrides nothing`
  without saying why.
- No `@Throws` is needed; Kotlin has no checked exceptions.
- Do **not** make it `suspend`, and do not wrap `chain.process` in `runBlocking` or
  `withContext(Dispatchers.IO)`. `suspend` is not a Kora contract, and the call is already on a
  virtual thread — the dispatcher hop is pure overhead.

---

## Testing

Interceptors are plain objects: the chain is a lambda.

```java
@Test
void addsTheApiKeyHeader() throws Exception {
    var interceptor = new ApiKeyClientInterceptor(() -> "secret-key");   // ExternalApiAuthConfig is a SAM
    var seen = new AtomicReference<HttpClientRequest>();

    interceptor.processRequest(
            request -> { seen.set(request); return new SimpleHttpClientResponse(200); },
            HttpClientRequest.get("https://api.example.test/resource").build());

    assertThat(seen.get().headers().getFirst("x-custom-api-key")).isEqualTo("secret-key");
}
```

`HttpClientRequest.get/post/put/…(uriTemplate)` builds a request without a client;
`io.koraframework.http.client.common.response.SimpleHttpClientResponse` has a
`SimpleHttpClientResponse(int code)` constructor for the stub response; and `headers().getFirst(...)`
matches against the lower-cased name. For the wired-up path, use `@KoraAppTest` against a stub
upstream — see [kora-testing-junit-java](../../kora-testing-junit-java/SKILL.md).

---

## Porting a 1.x interceptor

```java
// Kora 1.x
@Override
public CompletionStage<HttpClientResponse> processRequest(
        Context ctx, InterceptChain chain, HttpClientRequest request) throws Exception {
    var authorized = request.toBuilder().header("X-Api-Key", key).build();
    return chain.process(ctx, authorized);
}
```

```java
// Kora 2.0
@Override
public HttpClientResponse processRequest(InterceptChain chain, HttpClientRequest request) throws Exception {
    var authorized = request.toBuilder().header("X-Api-Key", key).build();
    return chain.process(authorized);
}
```

Four edits, none of them mechanical enough to trust to search-and-replace:

1. Drop the `Context` parameter — the type no longer exists, and nothing replaces it.
2. `CompletionStage<HttpClientResponse>` → `HttpClientResponse`.
3. `chain.process(ctx, request)` → `chain.process(request)`.
4. Check the argument order: 1.x was `(ctx, chain, request)`, 2.0 is `(chain, request)`. Deleting
   `ctx` happens to leave them correct — reorderings done by hand often do not.

A `thenApply`/`thenCompose` chain around the call becomes straight-line code. If it ran work on an
executor to avoid blocking a Netty thread, delete the executor: blocking a virtual thread is the
intended model in 2.0.

---

## See also

- [http-client-auth-reference.md](http-client-auth-reference.md) — the built-in interceptors
- [jwt-token-provider-reference.md](jwt-token-provider-reference.md) — 401 retry with a real token store
- [token-cache-reference.md](token-cache-reference.md) — the cache behind `tokens.invalidate()`
