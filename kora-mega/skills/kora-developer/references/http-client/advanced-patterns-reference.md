# Advanced Patterns Reference

**Source:** [.kora-agent/kora-docs/mkdocs/docs/en/documentation/http-client.md](.kora-agent/kora-docs/mkdocs/docs/en/documentation/http-client.md)  
**Examples:** `.kora-agent/kora-examples/kora-java-http-client/`

## @ResponseCodeMapper for Custom Responses

Type-safe handling of different HTTP status codes via sealed interfaces:

```java
@HttpClient("user-api")
public interface UserApiClient {
    @HttpRoute(method = HttpMethod.PUT, path = "/users/{id}")
    @ResponseCodeMapper(code = 200, mapper = UpdateSuccessMapper.class)
    @ResponseCodeMapper(code = ResponseCodeMapper.DEFAULT, mapper = UpdateErrorMapper.class)
    UpdateUserResult updateUser(@Path String id, @Json UserRequest request);
}

@Json
public sealed interface UpdateUserResult permits UpdateUserResult.Success, UpdateUserResult.Error {
    @JsonDiscriminatorValue("SUCCESS")
    record Success(UserResponse user) implements UpdateUserResult {}
    
    @JsonDiscriminatorValue("ERROR")
    record Error(ErrorResponse error) implements UpdateUserResult {}
    
    // Custom mapper for 200 OK
    class UpdateSuccessMapper implements HttpClientResponseMapper<Success> {
        private final JsonReader<UserResponse> reader;
        public UpdateSuccessMapper(JsonReader<UserResponse> reader) { this.reader = reader; }
        @Override
        public Success apply(HttpResponseEntity<byte[]> response) { return new Success(reader.read(response.body())); }
    }
    
    // Custom mapper for errors (4xx, 5xx)
    class UpdateErrorMapper implements HttpClientResponseMapper<Error> {
        private final JsonReader<ErrorResponse> reader;
        public UpdateErrorMapper(JsonReader<ErrorResponse> reader) { this.reader = reader; }
        @Override
        public Error apply(HttpResponseEntity<byte[]> response) { return new Error(reader.read(response.body())); }
    }
}
```

**Advantages:** type-safe error handling, compile-time exhaustiveness check, avoiding exceptions for expected error cases.

## Custom Request Mapper

Custom request body formats (XML, CSV, protobuf):

```java
@HttpClient("xml-api")
public interface XmlApiClient {
    record XmlRequest(String data) {}
    
    class XmlRequestMapper implements HttpClientRequestMapper<XmlRequest> {
        @Override
        public HttpBodyOutput apply(Context ctx, XmlRequest value) {
            String xml = "<request><data>" + value.data() + "</data></request>";
            return HttpBody.of("application/xml", xml.getBytes(StandardCharsets.UTF_8));
        }
    }
    
    @HttpRoute(method = HttpMethod.POST, path = "/xml")
    @Mapping(XmlRequestMapper.class)
    XmlResponse sendXml(@Mapping(XmlRequestMapper.class) XmlRequest request);
}
```

## Custom Response Mapper

Custom response formats (CSV, XML, plain text):

```java
@HttpClient("csv-api")
public interface CsvApiClient {
    class CsvResponseMapper implements HttpClientResponseMapper<List<String>> {
        @Override
        public List<String> apply(HttpResponseEntity<byte[]> response) {
            String csv = response.body().asString();
            return Arrays.asList(csv.split("\n"));
        }
    }
    @HttpRoute(method = HttpMethod.GET, path = "/data.csv")
    @Mapping(CsvResponseMapper.class)
    List<String> getCsvData();
}
```

## HttpClientInterceptor for Methods

Interceptors for specific methods:

```java
@HttpClient("api")
public interface ApiClient {
    @InterceptWith(LoggingInterceptor.class)
    @HttpRoute(method = HttpMethod.POST, path = "/sensitive")
    @Json
    SensitiveResponse processSensitive(@Json SensitiveRequest request);
    
    class LoggingInterceptor implements HttpClientInterceptor {
        @Override
        public CompletionStage<HttpClientResponse> intercept(Context ctx, HttpClientRequest request, InterceptChain chain) {
            System.out.println("Request: " + request.method() + " " + request.uri());
            return chain.process(ctx, request);
        }
    }
}
```

## Authentication Patterns

### Basic Authentication

```java
@Module
public interface BasicAuthModule {
    @ConfigSource("auth.basic")
    interface BasicAuthConfig { String username(); String password(); }
    
    @DefaultComponent
    default BasicAuthHttpClientInterceptor basicAuthInterceptor(BasicAuthConfig config) {
        return new BasicAuthHttpClientInterceptor(config.username(), config.password());
    }
}

@HttpClient("secure-api")
@InterceptWith(BasicAuthHttpClientInterceptor.class)
public interface SecureApiClient {
    @HttpRoute(method = HttpMethod.GET, path = "/protected")
    @Json ProtectedResource getProtected();
}
```

### API Key Authentication

```java
@Module
public interface ApiKeyAuthModule {
    @ConfigSource("auth.apiKey")
    interface ApiKeyAuthConfig { String apiKey(); }
    
    @DefaultComponent
    default ApiKeyHttpClientInterceptor apiKeyInterceptor(ApiKeyAuthConfig config) {
        return new ApiKeyHttpClientInterceptor(ApiKeyLocation.HEADER, "X-API-KEY", config.apiKey());
    }
}
```

### Bearer Token Authentication

```java
@Module
public interface BearerAuthModule {
    @DefaultComponent
    default BearerAuthHttpClientInterceptor bearerAuthInterceptor(HttpClientTokenProvider tokenProvider) {
        return new BearerAuthHttpClientInterceptor(tokenProvider);
    }
}

@Component
public class MyTokenProvider implements HttpClientTokenProvider {
    @Override
    public String getToken(HttpClientRequest request) { return getCachedToken(); }  // From cache, OAuth flow, etc.
}
```

## Assets Templates

Ready-to-use templates in `assets/`:

**Java:** `declarative-client.java.template` (declarative client with CRUD), `imperative-client.java.template` (imperative client), `request-dto.java.template` / `response-dto.java.template` (DTO records), `sealed-response.java.template` (polymorphic responses), `basic-auth-interceptor.java.template` / `api-key-auth-interceptor.java.template` / `bearer-auth-interceptor.java.template` (auth), `custom-response-mapper.java.template` (custom mapper).

**Kotlin:** `declarative-client.kt.template`, `imperative-client.kt.template`, `request-dto.kt.template` / `response-dto.kt.template`, `sealed-response.kt.template`, `basic-auth-interceptor.kt.template` / `api-key-auth-interceptor.kt.template` / `bearer-auth-interceptor.kt.template`, `custom-response-mapper.kt.template`.

**Configuration:** `application.conf.template` (HOCON), `application.yaml.template` (YAML).

**Usage:** Copy the template into your project and replace the placeholders (`${package}`, `${client_name}`, etc.).

## Related

- [Client Annotation Reference](client-annotation-reference.md) — @HttpClient, @HttpRoute, parameters
- [Interceptors Reference](interceptors-reference.md) — HttpClientInterceptor, auth patterns
- [Configuration Reference](configuration-reference.md) — OkHttp configuration
