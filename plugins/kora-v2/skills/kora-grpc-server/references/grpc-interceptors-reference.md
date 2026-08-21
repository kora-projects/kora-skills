# gRPC Interceptors Reference

**Source:** `.kora-agent/kora-docs/mkdocs/docs/en/documentation/grpc-server.md`
**Examples:** `kora-examples/examples/java/kora-java-grpc-server/.../MyServerInterceptor.java`, `kora-examples/guides/java/kora-java-guide-grpc-server-advanced-app/.../grpc/UserStreamingAuthInterceptor.java`

## Contents

1. Overview
2. Default Interceptors
3. Custom Interceptor Pattern
4. Authentication Interceptors
5. Exception Handling Interceptor
6. Metrics Interceptor
7. Request/Response Logging Interceptor
8. MDC / Context Propagation Interceptor
9. Interceptor Ordering
10. Common Pitfalls

## 1. Overview

`io.grpc.ServerInterceptor` allows intercepting and processing gRPC calls before they reach the handler.

Use cases:
- Authentication/Authorization
- Logging and auditing
- Metrics collection
- Request/response validation
- Error handling

## 2. Default Interceptors

Kora automatically registers these interceptors:

| Interceptor | Purpose |
|-------------|---------|
| `ContextServerInterceptor` | Context propagation |
| `CoroutineContextInjectInterceptor` | Kotlin coroutine context |
| `MetricCollectorServerInterceptor` | Micrometer metrics |
| `LoggingServerInterceptor` | Request logging |

To override defaults, override `serverBuilder` method in `GrpcModule`.

## 3. Custom Interceptor Pattern

### Basic Interceptor

=== ":fontawesome-brands-java: `Java`"
```java
package ru.tinkoff.kora.example.grpc.server;

import io.grpc.*;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import ru.tinkoff.kora.common.Component;

@Component
public final class GrpcLoggingInterceptor implements ServerInterceptor {
    
    private final Logger logger = LoggerFactory.getLogger(getClass());

    @Override
    public <ReqT, RespT> ServerCall.Listener<ReqT> interceptCall(
        ServerCall<ReqT, RespT> call,
        Metadata headers,
        ServerCallHandler<ReqT, RespT> next) {
        
        logger.info("gRPC call: {}", call.getMethodDescriptor().getFullMethodName());
        
        return next.startCall(call, headers);
    }
}
```

=== ":simple-kotlin: `Kotlin`"
```kotlin
package ru.tinkoff.kora.example.grpc.server

import io.grpc.*
import org.slf4j.LoggerFactory
import ru.tinkoff.kora.common.Component

@Component
class GrpcLoggingInterceptor : ServerInterceptor {
    
    private val logger = LoggerFactory.getLogger(javaClass)

    override fun <ReqT, RespT> interceptCall(
        call: ServerCall<ReqT, RespT>,
        headers: Metadata,
        next: ServerCallHandler<ReqT, RespT>
    ): ServerCall.Listener<ReqT> {
        
        logger.info("gRPC call: {}", call.methodDescriptor.fullMethodName)
        
        return next.startCall(call, headers)
    }
}
```

## 4. Authentication Interceptors

### API Key Authentication

Adapted from `kora-java-guide-grpc-server-advanced-app`. The API key comes from a typed `@ConfigSource` interface injected as a normal component. In Kora `@ConfigSource` annotates an interface (not a constructor parameter), and the config is read by the generated config extractor.

```java
package ru.tinkoff.kora.example.grpc.server;

import ru.tinkoff.kora.config.common.annotation.ConfigSource;

@ConfigSource("auth.apiKey")
public interface ApiKeyConfig {
    String value();   // bound to auth.apiKey.value, externalize via ${API_KEY}
}
```

```java
package ru.tinkoff.kora.example.grpc.server;

import io.grpc.*;
import ru.tinkoff.kora.common.Component;

@Component
public final class ApiKeyAuthInterceptor implements ServerInterceptor {

    private static final Metadata.Key<String> AUTHORIZATION_KEY =
        Metadata.Key.of("authorization", Metadata.ASCII_STRING_MARSHALLER);

    private final ApiKeyConfig config;

    public ApiKeyAuthInterceptor(ApiKeyConfig config) {
        this.config = config;
    }

    @Override
    public <ReqT, RespT> ServerCall.Listener<ReqT> interceptCall(
        ServerCall<ReqT, RespT> call,
        Metadata headers,
        ServerCallHandler<ReqT, RespT> next) {

        var authKey = headers.get(AUTHORIZATION_KEY);

        if (!config.value().equals(authKey)) {
            call.close(
                Status.UNAUTHENTICATED.withDescription("Invalid API key"),
                new Metadata()
            );
            return new ServerCall.Listener<ReqT>() {};
        }

        return next.startCall(call, headers);
    }
}
```

To guard only one service, compare against the generated `SERVICE_NAME`:

```java
if (!UserStreamingServiceGrpc.SERVICE_NAME.equals(call.getMethodDescriptor().getServiceName())) {
    return next.startCall(call, headers); // not the protected service, pass through
}
```

### Bearer Token Authentication

```java
@Component
public final class BearerAuthInterceptor implements ServerInterceptor {
    
    private static final Metadata.Key<String> AUTHORIZATION_KEY =
        Metadata.Key.of("authorization", Metadata.ASCII_STRING_MARSHALLER);
    
    private final JwtValidator jwtValidator;

    public BearerAuthInterceptor(JwtValidator jwtValidator) {
        this.jwtValidator = jwtValidator;
    }

    @Override
    public <ReqT, RespT> ServerCall.Listener<ReqT> interceptCall(
        ServerCall<ReqT, RespT> call,
        Metadata headers,
        ServerCallHandler<ReqT, RespT> next) {
        
        var authHeader = headers.get(AUTHORIZATION_KEY);
        
        if (authHeader == null || !authHeader.startsWith("Bearer ")) {
            call.close(
                Status.UNAUTHENTICATED.withDescription("Missing or invalid Bearer token"),
                new Metadata()
            );
            return new ServerCall.Listener<ReqT>() {};
        }
        
        var token = authHeader.substring(7);
        
        try {
            var claims = jwtValidator.validate(token);
            // Store claims in context for handler access
            var newCall = call.withAttributes(
                Attributes.newBuilder()
                    .set(AttributeKey.valueOf("claims"), claims)
                    .build()
            );
            return next.startCall(newCall, headers);
        } catch (JwtValidationException e) {
            call.close(
                Status.UNAUTHENTICATED.withDescription(e.getMessage()),
                new Metadata()
            );
            return new ServerCall.Listener<ReqT>() {};
        }
    }
}
```

## 5. Exception Handling Interceptor

Centralized error handling for all gRPC calls:

```java
package ru.tinkoff.kora.example.grpc.server;

import io.grpc.*;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import ru.tinkoff.kora.common.Component;

@Component
public final class GrpcExceptionHandlerServerInterceptor implements ServerInterceptor {
    
    private final Logger logger = LoggerFactory.getLogger(getClass());

    @Override
    public <ReqT, RespT> ServerCall.Listener<ReqT> interceptCall(
        ServerCall<ReqT, RespT> call,
        Metadata metadata,
        ServerCallHandler<ReqT, RespT> next) {
        
        try {
            return next.startCall(call, metadata);
        } catch (StatusRuntimeException e) {
            // Already a gRPC status exception - pass through
            logger.error("gRPC call failed: {} - {}", 
                call.getMethodDescriptor().getFullMethodName(), 
                e.getStatus().getCode(), e);
            call.close(e.getStatus(), new Metadata());
            return new ServerCall.Listener<ReqT>() {};
        } catch (IllegalArgumentException e) {
            // Client error
            call.close(
                Status.INVALID_ARGUMENT.withDescription(e.getMessage()),
                new Metadata()
            );
            logger.warn("Invalid argument: {}", e.getMessage());
            return new ServerCall.Listener<ReqT>() {};
        } catch (Exception e) {
            // Internal server error
            call.close(
                Status.INTERNAL.withDescription("Internal server error").withCause(e),
                new Metadata()
            );
            logger.error("Internal error", e);
            return new ServerCall.Listener<ReqT>() {};
        }
    }
}
```

## 6. Metrics/Tracing Interceptor

```java
@Component
public final class GrpcMetricsInterceptor implements ServerInterceptor {
    
    private final MeterRegistry meterRegistry;
    private final Timer timer;

    public GrpcMetricsInterceptor(MeterRegistry meterRegistry) {
        this.meterRegistry = meterRegistry;
        this.timer = meterRegistry.timer("grpc.server.call");
    }

    @Override
    public <ReqT, RespT> ServerCall.Listener<ReqT> interceptCall(
        ServerCall<ReqT, RespT> call,
        Metadata headers,
        ServerCallHandler<ReqT, RespT> next) {
        
        var method = call.getMethodDescriptor().getFullMethodName();
        
        return timer.record(() -> {
            try {
                var listener = next.startCall(call, headers);
                return new MeteringListener<>(listener, method, meterRegistry);
            } catch (Exception e) {
                meterRegistry.counter("grpc.server.errors", "method", method).increment();
                throw e;
            }
        });
    }
    
    private static class MeteringListener<ReqT, RespT> 
            extends ForwardingServerCallListener.SimpleForwardingServerCallListener<ReqT> {
        
        private final String method;
        private final MeterRegistry meterRegistry;

        MeteringListener(ServerCall.Listener<ReqT> delegate, 
                        String method, 
                        MeterRegistry meterRegistry) {
            super(delegate);
            this.method = method;
            this.meterRegistry = meterRegistry;
        }

        @Override
        public void onHalfClose() {
            meterRegistry.counter("grpc.server.requests", "method", method).increment();
            super.onHalfClose();
        }

        @Override
        public void onError(Throwable t) {
            meterRegistry.counter("grpc.server.errors", "method", method).increment();
            super.onError(t);
        }
    }
}
```

## 7. Request/Response Logging Interceptor

```java
@Component
public final class GrpcRequestLoggingInterceptor implements ServerInterceptor {
    
    private final Logger logger = LoggerFactory.getLogger(getClass());
    private final boolean logPayloads;

    // LoggingConfig is a @ConfigSource interface (e.g. @ConfigSource("grpc.requestLogging"))
    // exposing boolean payloads(); inject it as a component, do not annotate the parameter.
    public GrpcRequestLoggingInterceptor(LoggingConfig config) {
        this.logPayloads = config.payloads();
    }

    @Override
    public <ReqT, RespT> ServerCall.Listener<ReqT> interceptCall(
        ServerCall<ReqT, RespT> call,
        Metadata headers,
        ServerCallHandler<ReqT, RespT> next) {
        
        var method = call.getMethodDescriptor().getFullMethodName();
        var startTime = System.nanoTime();
        
        logger.info("gRPC request started: {} (headers: {})", method, headers);
        
        return new SimpleForwardingServerCallListener<>(next.startCall(call, headers)) {
            @Override
            public void onMessage(ReqT message) {
                if (logPayloads) {
                    logger.debug("gRPC request payload: {}", message);
                }
                super.onMessage(message);
            }

            @Override
            public void onHalfClose() {
                var duration = TimeUnit.NANOSECONDS.toMillis(System.nanoTime() - startTime);
                logger.info("gRPC request completed: {} ({} ms)", method, duration);
                super.onHalfClose();
            }

            @Override
            public void onError(Throwable t) {
                var duration = TimeUnit.NANOSECONDS.toMillis(System.nanoTime() - startTime);
                logger.error("gRPC request failed: {} ({} ms) - {}", method, duration, t.getMessage());
                super.onError(t);
            }
        };
    }
}
```

## 8. MDC/Context Propagation Interceptor

```java
@Component
public final class GrpcMdcInterceptor implements ServerInterceptor {
    
    private static final Metadata.Key<String> TRACE_ID_KEY =
        Metadata.Key.of("x-trace-id", Metadata.ASCII_STRING_MARSHALLER);
    
    private static final Metadata.Key<String> SPAN_ID_KEY =
        Metadata.Key.of("x-span-id", Metadata.ASCII_STRING_MARSHALLER);

    @Override
    public <ReqT, RespT> ServerCall.Listener<ReqT> interceptCall(
        ServerCall<ReqT, RespT> call,
        Metadata headers,
        ServerCallHandler<ReqT, RespT> next) {
        
        var traceId = headers.get(TRACE_ID_KEY);
        var spanId = headers.get(SPAN_ID_KEY);
        
        // Set MDC context for logging
        if (traceId != null) {
            MDC.put("traceId", traceId);
        }
        if (spanId != null) {
            MDC.put("spanId", spanId);
        }
        
        try {
            return next.startCall(call, headers);
        } finally {
            MDC.clear();
        }
    }
}
```

## 9. Interceptor Ordering

When multiple interceptors are present, they are applied in order. The first interceptor wraps the second, etc.:

```
Interceptor1 -> Interceptor2 -> Interceptor3 -> Handler
```

Order is determined by the order of interceptors in the module or by priority if supported:

```java
@Component
public class GrpcMdcInterceptor implements ServerInterceptor { ... }

@Component
public class GrpcAuthInterceptor implements ServerInterceptor { ... }

@Component
public class GrpcLoggingInterceptor implements ServerInterceptor { ... }
```

## 10. Common Pitfalls

| Problem | Solution |
|---------|----------|
| **Interceptor not called** | Ensure `@Component` annotation is present |
| **Context not propagated** | Use MDC.clear() in finally block |
| **Auth not working** | Check header name matches client sending |
| **Exception swallowed** | Always re-throw or properly handle in onError() |
