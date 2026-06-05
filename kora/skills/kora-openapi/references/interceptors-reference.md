# OpenAPI Interceptors Reference

**Source:** [.kora-agent/kora-docs/mkdocs/docs/en/documentation/openapi-codegen.md](.kora-agent/kora-docs/mkdocs/docs/en/documentation/openapi-codegen.md)  
**Examples:** `.kora-agent/kora-examples/kora-java-openapi-generator-http-server/`

## 1. Overview

Kora OpenAPI Generator supports interceptors for both HTTP clients and servers. Interceptors are configured via JSON in `configOptions.interceptors` and applied to generated code.

## 2. Client Interceptors

### Configuration Pattern

```groovy
configOptions = [
    mode: "java-client",
    interceptors: """
        {
          "*": [
            {
              "tag": "com.example.MyTag"
            }
          ],
          "pet": [
            {
              "type": "com.example.MyInterceptor"
            }
          ],
          "shop": [
            {
              "type": "com.example.MyInterceptor",
              "tag": "com.example.MyTag"
            }
          ]
        }
        """
]
```

### Configuration Keys

| Key | Description |
|-----|-------------|
| `*` | Global interceptors applied to all operations |
| `<tag>` | Tag-specific interceptors (OpenAPI tag name) |
| `type` | Interceptor class type |
| `tag` | Interceptor tag for DI resolution |

### Interceptor Implementation

```java
@Component
@Tag(MyTag.class)
public final class MyInterceptor implements HttpClientInterceptor {
    @Override
    public <T> T handle(HttpClientRequest request, HttpClientRequest.BodyProvider body,
                        HttpClientResponseHandler<T> responseHandler,
                        Chain chain) throws IOException, InterruptedException {
        // Pre-request logic
        request.headers().put("X-Request-Id", generateRequestId());
        
        var response = chain.proceed(request, body, responseHandler);
        
        // Post-response logic
        logResponse(response);
        
        return response;
    }
}
```

### Tag-Based Interceptors

```java
public final class LoggingTag {}

@Component
@Tag(LoggingTag.class)
public final class LoggingInterceptor implements HttpClientInterceptor {
    private static final Logger log = LoggerFactory.getLogger(LoggingInterceptor.class);
    
    @Override
    public <T> T handle(HttpClientRequest request, HttpClientRequest.BodyProvider body,
                        HttpClientResponseHandler<T> responseHandler,
                        Chain chain) throws IOException, InterruptedException {
        log.info("Request: {} {}", request.method(), request.uri());
        return chain.proceed(request, body, responseHandler);
    }
}
```

## 3. Server Interceptors

### Configuration Pattern

```groovy
configOptions = [
    mode: "java-server",
    interceptors: """
        {
          "*": [
            {
              "tag": "com.example.GlobalTag"
            }
          ],
          "pet": [
            {
              "type": "com.example.PetMetricsInterceptor"
            }
          ],
          "admin": [
            {
              "type": "com.example.AdminAuthInterceptor",
              "tag": "com.example.AdminTag"
            }
          ]
        }
        """
]
```

### Server Interceptor Implementation

```java
@Component
@Tag(PetMetricsTag.class)
public final class PetMetricsInterceptor implements HttpServerInterceptor {
    private final Timer requestTimer;
    
    public PetMetricsInterceptor(MeterRegistry registry) {
        this.requestTimer = Timer.builder("pet.api.requests")
            .register(registry);
    }
    
    @Override
    public <T> Mono<T> handle(HttpServerRequest request,
                              HttpServerResponse response,
                              Chain chain) {
        return requestTimer.record(() -> chain.proceed(request, response));
    }
}
```

### Reactive Server Interceptor

```java
@Component
public final class ValidationInterceptor implements HttpServerInterceptor {
    @Override
    public <T> Mono<T> handle(HttpServerRequest request,
                              HttpServerResponse response,
                              Chain chain) {
        // Pre-validation
        if (!hasValidHeader(request)) {
            return Mono.error(new BadRequestException("Invalid header"));
        }
        
        return chain.proceed(request, response)
            .doOnNext(result -> {
                // Post-processing
                response.headers().put("X-Validated", "true");
            });
    }
}
```

## 4. Interceptor Tags

### Client Tags

```java
public final class HttpClientTag {}
public final class TelemetryTag {}
public final class AuthTag {}
```

### Server Tags

```java
public final class HttpServerTag {}
public final class MetricsTag {}
public final class SecurityTag {}
```

## 5. Advanced Patterns

### Chained Interceptors

Multiple interceptors are applied in order:

```groovy
interceptors: """
    {
      "*": [
        {
          "type": "com.example.LoggingInterceptor"
        },
        {
          "type": "com.example.MetricsInterceptor"
        },
        {
          "type": "com.example.TracingInterceptor"
        }
      ]
    }
    """
```

### Conditional Interceptors

Apply interceptors based on operation tags:

```groovy
interceptors: """
    {
      "admin": [
        {
          "type": "com.example.AdminAuthInterceptor"
        }
      ],
      "public": [
        {
          "type": "com.example.RateLimitInterceptor"
        }
      ]
    }
    """
```

### Interceptor with Dependencies

```java
@Component
public final class CacheInterceptor implements HttpClientInterceptor {
    private final CacheService cache;
    private final ObjectMapper mapper;
    
    public CacheInterceptor(CacheService cache, ObjectMapper mapper) {
        this.cache = cache;
        this.mapper = mapper;
    }
    
    @Override
    public <T> T handle(HttpClientRequest request, HttpClientRequest.BodyProvider body,
                        HttpClientResponseHandler<T> responseHandler,
                        Chain chain) throws IOException, InterruptedException {
        String cacheKey = generateCacheKey(request);
        
        // Try cache first
        Optional<String> cached = cache.get(cacheKey);
        if (cached.isPresent()) {
            return mapper.readValue(cached.get(), responseHandler.responseType());
        }
        
        // Proceed with request
        T response = chain.proceed(request, body, responseHandler);
        
        // Cache response
        cache.put(cacheKey, mapper.writeValueAsString(response));
        
        return response;
    }
}
```

## 6. Tags Configuration (Client Only)

Configure HTTP client and telemetry tags per operation:

```groovy
configOptions = [
    mode: "java-client",
    tags: """
        {
          "*": {
            "httpClientTag": "some.tag.Common",
            "telemetryTag": "some.tag.Common"
          },
          "instrument": {
            "httpClientTag": "some.tag.Instrument",
            "telemetryTag": "some.tag.Instrument"
          },
          "shop": {
            "httpClientTag": "some.tag.Shop",
            "telemetryTag": "some.tag.Shop"
          }
        }
        """
]
```

### Tag Purpose

| Tag Type | Purpose |
|----------|---------|
| `httpClientTag` | HTTP client configuration (timeouts, retries) |
| `telemetryTag` | Metrics and tracing configuration |

## 7. Interceptor Order

Interceptors are executed in the following order:

1. Global interceptors (`*`)
2. Tag-specific interceptors (by tag name)
3. Type-specific interceptors

## 8. Troubleshooting

| Problem | Solution |
|---------|----------|
| Interceptor not applied | Check `type` class name matches exactly |
| Tag not resolved | Ensure `@Tag` annotation on interceptor |
| Wrong interceptor order | Reorder in JSON configuration |
| Interceptor not found | Verify interceptor is in classpath and has `@Component` |
| Client tags not working | Tags only work for clients, not servers |

---

## Related References

- [openapi-codegen-reference.md](openapi-codegen-reference.md) — OpenAPI Generator configuration
- [authorization-reference.md](authorization-reference.md) — Authorization mechanisms
- [validation-reference.md](validation-reference.md) — Server-side validation
