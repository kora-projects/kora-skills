# Custom API-Key Interceptor Reference

When the built-in `ApiKeyHttpClientInterceptor` does not fit (non-standard header
name decided at runtime, extra logic), write your own `HttpClientInterceptor`.

## Contents

- [Built-in first](#built-in-first)
- [Interceptor signature](#interceptor-signature)
- [Custom header interceptor](#custom-header-interceptor)
- [API key in a query parameter](#api-key-in-a-query-parameter)
- [Configuration](#configuration)
- [Security notes](#security-notes)
- [Testing](#testing)

Source of truth: `.kora-agent/kora-examples/guides/java/kora-java-guide-http-client-advanced-app/src/main/java/ru/tinkoff/kora/guide/httpclient/client/ApiKeyAuthInterceptor.java`.

---

## Built-in first

Prefer `ApiKeyHttpClientInterceptor(ApiKeyLocation, name, secret)` for header,
query, or cookie placement. Only hand-write an interceptor when you need behavior
it does not support. See
[http-client-auth-reference.md](http-client-auth-reference.md).

---

## Interceptor signature

`HttpClientInterceptor.processRequest` takes `(Context ctx, InterceptChain chain,
HttpClientRequest request)` and returns `CompletionStage<HttpClientResponse>`. You
must end every path by calling `chain.process(ctx, request)`. `InterceptChain` is a
nested type: `HttpClientInterceptor.InterceptChain`.

Imports:

```java
import ru.tinkoff.kora.common.Component;
import ru.tinkoff.kora.common.Context;
import ru.tinkoff.kora.http.client.common.interceptor.HttpClientInterceptor;
import ru.tinkoff.kora.http.client.common.request.HttpClientRequest;
import ru.tinkoff.kora.http.client.common.response.HttpClientResponse;
```

---

## Custom header interceptor

Adapted from the example app (`ApiKeyAuthInterceptor`):

```java
@Component
public final class CustomApiKeyInterceptor implements HttpClientInterceptor {

    private final ApiKeyAuthConfig config;

    public CustomApiKeyInterceptor(ApiKeyAuthConfig config) {
        this.config = config;
    }

    @Override
    public CompletionStage<HttpClientResponse> processRequest(
            Context ctx, InterceptChain chain, HttpClientRequest request) throws Exception {
        var authorized = request.toBuilder()
                .header("X-Custom-API-Key", config.value())
                .build();
        return chain.process(ctx, authorized);
    }
}
```

```java
@ConfigSource("auth.apiKey")
public interface ApiKeyAuthConfig {
    String value();
}
```

---

## API key in a query parameter

Use the builder's `queryParam(name, value)` — do not concatenate the URL by hand.

```java
@Component
public final class ApiKeyQueryInterceptor implements HttpClientInterceptor {

    private final ApiKeyAuthConfig config;

    public ApiKeyQueryInterceptor(ApiKeyAuthConfig config) {
        this.config = config;
    }

    @Override
    public CompletionStage<HttpClientResponse> processRequest(
            Context ctx, InterceptChain chain, HttpClientRequest request) throws Exception {
        var authorized = request.toBuilder()
                .queryParam("api_key", config.value())
                .build();
        return chain.process(ctx, authorized);
    }
}
```

Attach with `@InterceptWith`:

```java
@InterceptWith(ApiKeyQueryInterceptor.class)
@HttpClient(configPath = "httpClient.externalApi")
public interface ExternalApiClient {

    @HttpRoute(method = HttpMethod.GET, path = "/resource")
    @Json
    Resource getResource();
}
```

---

## Configuration

Several API keys, each as its own `@ConfigSource`:

```hocon
external {
    serviceA { url = "https://api.service-a.com", key = ${SERVICE_A_API_KEY} }
    serviceB { url = "https://api.service-b.com", key = ${SERVICE_B_API_KEY} }
}
httpClient {
    serviceA { url = ${external.serviceA.url} }
    serviceB { url = ${external.serviceB.url} }
}
```

---

## Security notes

- Never hard-code an API key. Bind a `@ConfigSource` interface and reference an
  environment variable in config (`key = ${SERVICE_A_API_KEY}`).
- Rotate keys; always use HTTPS.

---

## Testing

```java
@TestComponent
public final class TestApiKeyInterceptor implements HttpClientInterceptor {
    @Override
    public CompletionStage<HttpClientResponse> processRequest(
            Context ctx, InterceptChain chain, HttpClientRequest request) throws Exception {
        var authorized = request.toBuilder().header("X-API-Key", "test-key-12345").build();
        return chain.process(ctx, authorized);
    }
}
```

```java
@KoraAppTest(Application.class)
class ApiKeyClientTest {

    @Test
    void sendsApiKey(@TestComponent ExternalApiClient client) {
        // Drive the client against a stub server and assert the key reached it.
        assertThat(client.getResource()).isNotNull();
    }
}
```

---

## See also

- [http-client-auth-reference.md](http-client-auth-reference.md)
