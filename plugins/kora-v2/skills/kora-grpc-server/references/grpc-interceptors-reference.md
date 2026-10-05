# gRPC Interceptors Reference — Kora 2.0

**Framework source (authority):** [`GrpcServerFactoryModule`](https://github.com/kora-projects/kora/blob/2.0.0.RC2/grpc/grpc-server/src/main/java/io/koraframework/grpc/server/GrpcServerFactoryModule.java) · [`DynamicServerInterceptor`](https://github.com/kora-projects/kora/blob/2.0.0.RC2/grpc/grpc-server/src/main/java/io/koraframework/grpc/server/interceptor/DynamicServerInterceptor.java) · [`TelemetryInterceptor`](https://github.com/kora-projects/kora/blob/2.0.0.RC2/grpc/grpc-server/src/main/java/io/koraframework/grpc/server/interceptor/TelemetryInterceptor.java)
**Migrated examples:** [`MyServerInterceptor.java`](https://github.com/kora-projects/kora-examples/blob/migration/2.0/examples/java/kora-java-grpc-server/src/main/java/io/koraframework/example/grpc/server/MyServerInterceptor.java) · [`UserStreamingAuthInterceptor.java`](https://github.com/kora-projects/kora-examples/blob/migration/2.0/guides/java/kora-java-guide-grpc-server-advanced-app/src/main/java/io/koraframework/guide/grpcserver/advanced/grpc/UserStreamingAuthInterceptor.java)

## Contents

1. How Kora 2.0 collects interceptors
2. The one built-in interceptor
3. Ordering
4. Basic interceptor
5. Scoping an interceptor to one service
6. API-key authentication
7. Bearer-token authentication
8. Centralised exception mapping
9. What NOT to write yourself
10. Common pitfalls

---

## 1. How Kora 2.0 collects interceptors

There is **no tag** and no registration API. `GrpcServerFactoryModule` declares:

```java
@Tag(Tag.Factory.class)
public WrappedRefreshListener<List<DynamicServerInterceptor>> dynamicInterceptorsListener(
        @Tag(Tag.Factory.class) All<ValueOf<ServerInterceptor>> interceptors) {
    // each is wrapped in a DynamicServerInterceptor that re-reads its ValueOf on graph refresh
}
```

and the builder consumes them with:

```java
interceptors.forEach(builder::intercept);
builder.intercept(new TelemetryInterceptor(...));
```

`@Tag(Tag.Factory.class)` means "the tag of the enclosing factory module". `GrpcServerModule`
declares `@FactoryModule default GrpcServerFactoryModule grpcServer()` with **no** `@Tag`, so the
resolved tag is **null**. Kora's `TagUtils.tagsMatch(required, provided)` returns `true` for
`(null, null)` and `false` for `(null, anything)` — therefore:

> **An untagged `@Component` implementing `io.grpc.ServerInterceptor` is registered globally.
> Putting `@Tag(...)` on it silently removes it from the collection.** The build succeeds, the app
> starts, and the interceptor simply never runs.

This is the single most likely silent regression when porting from Kora 1.x, and the only reliable
guard is a test that asserts the interceptor's observable effect.

```java
import io.grpc.*;
import io.koraframework.common.annotation.Component;

@Component                      // ← untagged. No @Tag(...) here, ever.
public final class LoggingInterceptor implements ServerInterceptor { … }
```

Interceptors are ordinary components: constructor injection works, and they may depend on config
interfaces, repositories, clients — anything in the graph.

## 2. The one built-in interceptor

Kora 2.0 registers exactly one interceptor of its own:

| Class | Purpose |
|---|---|
| `io.koraframework.grpc.server.interceptor.TelemetryInterceptor` | opens the `GrpcServerObservation` (span, metric timer, request/response logs) and binds the per-call `ScopedValue`s |

The Kora 1.x names — `ContextServerInterceptor`, `CoroutineContextInjectInterceptor`,
`MetricCollectorServerInterceptor`, `LoggingServerInterceptor` — **do not exist in 2.0**, and neither
does the `GrpcModule` class whose `serverBuilder` method 1.x told you to override. To change how the
builder is assembled, see [grpc-server-reference.md](grpc-server-reference.md) §7.

## 3. Ordering

Kora adds your interceptors first and its own `TelemetryInterceptor` **last**. gRPC's
[`ServerBuilder#intercept`](https://grpc.github.io/grpc-java/javadoc/io/grpc/ServerBuilder.html)
contract is that "interceptors run in the reverse order in which they are added" — so the
`TelemetryInterceptor` is the **outermost** one and your interceptors run inside it:

```
TelemetryInterceptor  →  your interceptors  →  handler
```

Two consequences:

- Inside your interceptor the span is already open and `MDC.VALUE` / `OpentelemetryContext.VALUE`
  are already bound, so anything you log is correlated.
- A call you reject with `call.close(...)` in your own interceptor is still observed and timed.

**The relative order among your own interceptors is the graph's `All<...>` collection order.** Kora
offers no priority annotation for it and nothing in the declaration makes it explicit. Do not build
behaviour that depends on interceptor A running before interceptor B — make each one independent,
and scope it explicitly (§5).

## 4. Basic interceptor

===! `Java`

```java
package io.koraframework.example.grpc.server;

import io.grpc.Metadata;
import io.grpc.ServerCall;
import io.grpc.ServerCallHandler;
import io.grpc.ServerInterceptor;
import io.koraframework.common.annotation.Component;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

@Component
public final class LoggingInterceptor implements ServerInterceptor {

    private static final Logger logger = LoggerFactory.getLogger(LoggingInterceptor.class);

    @Override
    public <ReqT, RespT> ServerCall.Listener<ReqT> interceptCall(
            ServerCall<ReqT, RespT> call,
            Metadata headers,
            ServerCallHandler<ReqT, RespT> next) {
        logger.info("Incoming gRPC request: method={}", call.getMethodDescriptor().getFullMethodName());
        return next.startCall(call, headers);
    }
}
```

=== `Kotlin`

```kotlin
package io.koraframework.kotlin.example.grpc.server

import io.grpc.Metadata
import io.grpc.ServerCall
import io.grpc.ServerCallHandler
import io.grpc.ServerInterceptor
import io.koraframework.common.annotation.Component
import org.slf4j.LoggerFactory

@Component
class LoggingInterceptor : ServerInterceptor {

    private val logger = LoggerFactory.getLogger(LoggingInterceptor::class.java)

    override fun <ReqT : Any, RespT : Any> interceptCall(
        call: ServerCall<ReqT, RespT>,
        headers: Metadata,
        next: ServerCallHandler<ReqT, RespT>
    ): ServerCall.Listener<ReqT> {
        logger.info("Incoming gRPC request: method={}", call.methodDescriptor.fullMethodName)
        return next.startCall(call, headers)
    }
}
```

The Kotlin `<ReqT : Any, RespT : Any>` bounds are what the migrated example uses; dropping them
gives `overrides nothing`.

## 5. Scoping an interceptor to one service

Every interceptor is global. To limit one to a single proto service, compare against the generated
`SERVICE_NAME` constant and pass everything else straight through:

```java
if (!UserStreamingServiceGrpc.SERVICE_NAME.equals(call.getMethodDescriptor().getServiceName())) {
    return next.startCall(call, headers);
}
```

For a single method, match `call.getMethodDescriptor().getFullMethodName()` against
`<proto package>.<Service>/<Method>`.

## 6. API-key authentication

Straight from the advanced guide. The expected key comes from a typed `@ConfigSource` **interface**
injected as an ordinary component — in Kora `@ConfigSource` annotates a type, never a constructor
parameter.

```java
package io.koraframework.example.grpc.server;

import io.koraframework.config.common.annotation.ConfigSource;

@ConfigSource("auth.apiKey")
public interface ApiKeyConfig {

    String value();      // bound to auth.apiKey.value
}
```

```hocon
auth.apiKey.value = ${?GRPC_API_KEY}
```

```java
package io.koraframework.example.grpc.server;

import io.grpc.Metadata;
import io.grpc.ServerCall;
import io.grpc.ServerCallHandler;
import io.grpc.ServerInterceptor;
import io.grpc.Status;
import io.koraframework.common.annotation.Component;

@Component
public final class ApiKeyAuthInterceptor implements ServerInterceptor {

    private static final Metadata.Key<String> AUTHORIZATION =
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

        if (!UserStreamingServiceGrpc.SERVICE_NAME.equals(call.getMethodDescriptor().getServiceName())) {
            return next.startCall(call, headers);
        }

        var authorization = headers.get(AUTHORIZATION);
        if (!this.config.value().equals(authorization)) {
            call.close(Status.UNAUTHENTICATED.withDescription("Invalid API key"), new Metadata());
            return new ServerCall.Listener<>() {};
        }

        return next.startCall(call, headers);
    }
}
```

Rejecting a call is two steps: `call.close(status, trailers)` **and** returning an empty
`ServerCall.Listener`. Returning `next.startCall(...)` after closing is a double-terminal error.

Metadata header names must be lower-case ASCII. `Metadata.Key.of` normalises them, but a client
sending `Authorization` and a server reading `authorization` do match — the wire format is
lower-cased by HTTP/2 itself.

## 7. Bearer-token authentication

Same skeleton; the difference is where the verified identity goes. There is no Kora `Context` in
2.0, so attach it to the gRPC call context and read it in the handler with the same key:

```java
package io.koraframework.example.grpc.server;

import io.grpc.*;
import io.koraframework.common.annotation.Component;

@Component
public final class BearerAuthInterceptor implements ServerInterceptor {

    public static final Context.Key<String> USER_ID = Context.key("userId");

    private static final Metadata.Key<String> AUTHORIZATION =
            Metadata.Key.of("authorization", Metadata.ASCII_STRING_MARSHALLER);

    private final JwtVerifier jwtVerifier;

    public BearerAuthInterceptor(JwtVerifier jwtVerifier) {
        this.jwtVerifier = jwtVerifier;
    }

    @Override
    public <ReqT, RespT> ServerCall.Listener<ReqT> interceptCall(
            ServerCall<ReqT, RespT> call,
            Metadata headers,
            ServerCallHandler<ReqT, RespT> next) {

        var header = headers.get(AUTHORIZATION);
        if (header == null || !header.startsWith("Bearer ")) {
            call.close(Status.UNAUTHENTICATED.withDescription("Missing Bearer token"), new Metadata());
            return new ServerCall.Listener<>() {};
        }

        final String userId;
        try {
            userId = jwtVerifier.verify(header.substring("Bearer ".length()));
        } catch (JwtVerificationException e) {
            call.close(Status.UNAUTHENTICATED.withDescription(e.getMessage()), new Metadata());
            return new ServerCall.Listener<>() {};
        }

        var context = Context.current().withValue(USER_ID, userId);
        return Contexts.interceptCall(context, call, headers, next);
    }
}
```

`io.grpc.Context` / `io.grpc.Contexts` are gRPC's own types and are unaffected by the removal of the
Kora `Context`. In the handler: `var userId = BearerAuthInterceptor.USER_ID.get();`.

`Contexts.interceptCall` is what propagates the context to the handler — a bare
`next.startCall(call, headers)` after `Context.current().withValue(...)` does not.

## 8. Centralised exception mapping

An interceptor only wraps `startCall`; an exception thrown from inside a handler method surfaces on
the returned `Listener`, not from `startCall`. To catch handler failures centrally, wrap the
listener:

```java
package io.koraframework.example.grpc.server;

import io.grpc.*;
import io.koraframework.common.annotation.Component;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

@Component
public final class ExceptionMappingInterceptor implements ServerInterceptor {

    private static final Logger logger = LoggerFactory.getLogger(ExceptionMappingInterceptor.class);

    @Override
    public <ReqT, RespT> ServerCall.Listener<ReqT> interceptCall(
            ServerCall<ReqT, RespT> call,
            Metadata headers,
            ServerCallHandler<ReqT, RespT> next) {

        var delegate = next.startCall(call, headers);
        return new ForwardingServerCallListener.SimpleForwardingServerCallListener<>(delegate) {

            @Override
            public void onHalfClose() {
                try {
                    super.onHalfClose();
                } catch (RuntimeException e) {
                    close(e);
                }
            }

            @Override
            public void onMessage(ReqT message) {
                try {
                    super.onMessage(message);
                } catch (RuntimeException e) {
                    close(e);
                }
            }

            private void close(RuntimeException e) {
                if (e instanceof StatusRuntimeException sre) {
                    call.close(sre.getStatus(), sre.getTrailers() == null ? new Metadata() : sre.getTrailers());
                } else if (e instanceof IllegalArgumentException) {
                    call.close(Status.INVALID_ARGUMENT.withDescription(e.getMessage()), new Metadata());
                } else {
                    logger.error("Unhandled error in gRPC handler", e);
                    call.close(Status.INTERNAL.withDescription("Internal server error"), new Metadata());
                }
            }
        };
    }
}
```

A `try/catch` around `next.startCall(call, headers)` alone only catches failures raised while the
call is being *set up*, which is rarely where handler bugs live.

## 9. What NOT to write yourself

| Do not write | Because |
|---|---|
| A metrics interceptor | `TelemetryInterceptor` already records `rpc.server.call.duration` with `rpc.service` / `rpc.method` / `rpc.response.status_code` / `error.type` tags — set `grpcServer.telemetry.metrics.enabled = true` |
| A request/response logging interceptor | the module already logs to `…GrpcServer.request` / `.response` — set `grpcServer.telemetry.logging.enabled = true`, and `TRACE` on those loggers adds bodies |
| A tracing/trace-id interceptor | the module extracts and injects W3C trace context and opens a `SERVER` span per call |
| An MDC-population interceptor | `VirtualThreadExecutorTransportFilter` binds `MDC.VALUE` as a `ScopedValue` around each call |

See [grpc-config-reference.md](grpc-config-reference.md) for what each of those emits.

## 10. Common pitfalls

| Symptom | Cause | Fix |
|---|---|---|
| Interceptor never runs | a `@Tag(...)` on the component | remove it — the collection is untagged |
| Interceptor never runs, no `@Tag` | missing `@Component`, or not implementing `io.grpc.ServerInterceptor` | add both |
| `ContextServerInterceptor` / `GrpcModule` won't resolve | 1.x names, removed in 2.0 | see §2 |
| Handler exceptions bypass the interceptor | only `startCall` was wrapped | wrap the returned `Listener` (§8) |
| Rejected call hangs the client | `call.close(...)` without returning an empty listener | do both |
| `CANCELLED: call already closed` | `next.startCall(...)` after `call.close(...)` | return `new ServerCall.Listener<>() {}` instead |
| Auth context missing in the handler | `Context.current().withValue(...)` without `Contexts.interceptCall` | use `Contexts.interceptCall` (§7) |
| `overrides nothing` (Kotlin) | missing `: Any` bounds on `ReqT`/`RespT` | match the example signature (§4) |
| Order-dependent interceptors misbehave | `All<...>` order is not a declared contract | make each interceptor independent and scope it (§5) |
