# HTTP Interceptors Reference

**Source:** [.kora-agent/kora-docs/mkdocs/docs/en/documentation/http-server.md](.kora-agent/kora-docs/mkdocs/docs/en/documentation/http-server.md)  
**Examples:** `.kora-agent/kora-examples/kora-java-http-server/`

## HttpServerInterceptor

Interceptors allow you to intercept and modify requests/responses.

```java
public interface HttpServerInterceptor {
    CompletionStage<HttpServerResponse> intercept(
        Context context,
        HttpServerRequest request,
        InterceptChain chain
    ) throws Exception;
}
```

## Interceptor Scopes

### Method-Level Interceptor

Applied to a specific controller method.

```java
@Component
@HttpController
public final class LoggedController {
    
    public static final class LogInterceptor implements HttpServerInterceptor {
        @Override
        public CompletionStage<HttpServerResponse> intercept(
            Context ctx,
            HttpServerRequest request,
            InterceptChain chain
        ) {
            System.out.println("Request: " + request.method() + " " + request.uri());
            return chain.process(ctx, request);
        }
    }
    
    @InterceptWith(LogInterceptor.class)
    @HttpRoute(method = HttpMethod.GET, path = "/logged")
    public String logged() {
        return "Logged response";
    }
}
```

### Controller-Level Interceptor

Applied to all methods of the controller.

```java
@InterceptWith(AuthInterceptor.class)
@Component
@HttpController
public final class SecureController {
    
    @HttpRoute(method = HttpMethod.GET, path = "/secure")
    public String secure() {
        return "Secure response";
    }
    
    @HttpRoute(method = HttpMethod.GET, path = "/also-secure")
    public String alsoSecure() {
        return "Also secure response";
    }
}
```

### Global Interceptor

Applied to all controllers in the application.

```java
@Tag(HttpServerModule.class)  // Key marker for a global interceptor
@Component
public final class GlobalLoggingInterceptor implements HttpServerInterceptor {
    
    @Override
    public CompletionStage<HttpServerResponse> intercept(
        Context ctx,
        HttpServerRequest request,
        InterceptChain chain
    ) {
        long startTime = System.currentTimeMillis();
        
        return chain.process(ctx, request)
            .thenApply(response -> {
                long duration = System.currentTimeMillis() - startTime;
                System.out.println(
                    "Response: " + response.status() + 
                    " in " + duration + "ms"
                );
                return response;
            });
    }
}
```

**Important:** Only one global interceptor with `@Tag(HttpServerModule.class)` is allowed.

## Error Handling Interceptor

Global error handling via an interceptor.

```java
@Tag(HttpServerModule.class)
@Component
public final class GlobalErrorInterceptor implements HttpServerInterceptor {
    
    @Override
    public CompletionStage<HttpServerResponse> intercept(
        Context ctx,
        HttpServerRequest request,
        InterceptChain chain
    ) {
        return chain.process(ctx, request).exceptionally(e -> {
            // Unwrap CompletionException
            if (e instanceof CompletionException) {
                e = e.getCause();
            }
            
            // Handle known exceptions
            if (e instanceof HttpServerResponseException ex) {
                return ex.getResponse();
            }
            
            if (e instanceof IllegalArgumentException) {
                return HttpServerResponse.of(
                    400,
                    HttpBody.plaintext("Bad request: " + e.getMessage())
                );
            }
            
            if (e instanceof TimeoutException) {
                return HttpServerResponse.of(
                    408,
                    HttpBody.plaintext("Request timeout")
                );
            }
            
            if (e instanceof NotFoundException) {
                return HttpServerResponse.of(
                    404,
                    HttpBody.plaintext("Not found")
                );
            }
            
            // Unknown exceptions → 500
            System.err.println("Unhandled exception: " + e);
            e.printStackTrace();
            return HttpServerResponse.of(
                500,
                HttpBody.plaintext("Internal server error")
            );
        });
    }
}
```

## Authentication Interceptor

```java
@Component
@HttpController
@InterceptWith(AuthInterceptor.class)
public final class AuthenticatedController {
    
    public static final class AuthInterceptor implements HttpServerInterceptor {
        @Override
        public CompletionStage<HttpServerResponse> intercept(
            Context ctx,
            HttpServerRequest request,
            InterceptChain chain
        ) throws Exception {
            String authHeader = request.headers().getFirst("Authorization");
            
            if (authHeader == null || !authHeader.startsWith("Bearer ")) {
                return CompletableFuture.completedFuture(
                    HttpServerResponse.of(401, HttpBody.plaintext("Unauthorized"))
                );
            }
            
            String token = authHeader.substring(7);
            
            try {
                // Validate token
                JwtClaims claims = validateToken(token);
                
                // Add user context
                Context newContext = ctx.withValue("userId", claims.getSubject());
                
                return chain.process(newContext, request);
            } catch (JwtException e) {
                return CompletableFuture.completedFuture(
                    HttpServerResponse.of(401, HttpBody.plaintext("Invalid token"))
                );
            }
        }
    }
    
    @HttpRoute(method = HttpMethod.GET, path = "/profile")
    @Json
    public UserProfile getProfile() {
        // userId is available from Context
        // ...
    }
}
```

## Rate Limiting Interceptor

```java
@Tag(HttpServerModule.class)
@Component
public final class RateLimitingInterceptor implements HttpServerInterceptor {
    
    private final LoadingCache<String, RateLimiter> limiters = 
        CacheBuilder.newBuilder()
            .expireAfterAccess(1, TimeUnit.MINUTES)
            .build(new CacheLoader<String, RateLimiter>() {
                @Override
                public RateLimiter load(String ip) {
                    return RateLimiter.create(100.0); // 100 requests/sec
                }
            });
    
    @Override
    public CompletionStage<HttpServerResponse> intercept(
        Context ctx,
        HttpServerRequest request,
        InterceptChain chain
    ) {
        String ip = request.headers().getFirst("X-Forwarded-For");
        RateLimiter limiter = limiters.getUnchecked(ip);
        
        if (!limiter.tryAcquire()) {
            return CompletableFuture.completedFuture(
                HttpServerResponse.of(
                    429,
                    HttpHeaders.of("Retry-After", "1"),
                    HttpBody.plaintext("Rate limit exceeded")
                )
            );
        }
        
        return chain.process(ctx, request);
    }
}
```

## CORS Interceptor

```java
@Tag(HttpServerModule.class)
@Component
public final class CorsInterceptor implements HttpServerInterceptor {
    
    @Override
    public CompletionStage<HttpServerResponse> intercept(
        Context ctx,
        HttpServerRequest request,
        InterceptChain chain
    ) {
        // Handle preflight OPTIONS request
        if (request.method() == HttpMethod.OPTIONS) {
            return CompletableFuture.completedFuture(
                HttpServerResponse.of(
                    204,
                    HttpHeaders.of(
                        "Access-Control-Allow-Origin", "*",
                        "Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS",
                        "Access-Control-Allow-Headers", "Content-Type, Authorization",
                        "Access-Control-Max-Age", "3600"
                    ),
                    HttpBody.empty()
                )
            );
        }
        
        // Add CORS headers to response
        return chain.process(ctx, request)
            .thenApply(response -> {
                HttpHeaders corsHeaders = HttpHeaders.of(
                    "Access-Control-Allow-Origin", "*",
                    "Access-Control-Allow-Credentials", "true"
                );
                return response.withHeaders(corsHeaders);
            });
    }
}
```

## InterceptChain

`InterceptChain` allows you to continue processing the request.

```java
public interface InterceptChain {
    CompletionStage<HttpServerResponse> process(
        Context context,
        HttpServerRequest request
    ) throws Exception;
}
```

**Usage:**
```java
@Override
public CompletionStage<HttpServerResponse> intercept(
    Context ctx,
    HttpServerRequest request,
    InterceptChain chain
) {
    // Before processing
    logRequest(request);
    
    // Continue chain
    return chain.process(ctx, request)
        .thenApply(response -> {
            // After processing
            logResponse(response);
            return response;
        })
        .exceptionally(e -> {
            // Error handling
            logError(e);
            throw new CompletionException(e);
        });
}
```

## Multiple Interceptors

```java
@Component
@HttpController
@InterceptWith(LoggingInterceptor.class)
@InterceptWith(AuthInterceptor.class)
@InterceptWith(RateLimitInterceptor.class)
public final class MultiInterceptedController {
    
    @HttpRoute(method = HttpMethod.GET, path = "/endpoint")
    public String endpoint() {
        return "Response";
    }
}
```

**Execution order:**
1. LoggingInterceptor (before)
2. AuthInterceptor (before)
3. RateLimitInterceptor (before)
4. Handler method
5. RateLimitInterceptor (after)
6. AuthInterceptor (after)
7. LoggingInterceptor (after)
