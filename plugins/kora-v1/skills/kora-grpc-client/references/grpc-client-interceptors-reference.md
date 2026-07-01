# gRPC Client Interceptors Reference

**Source:** `.kora-agent/kora-docs/mkdocs/docs/en/documentation/grpc-client.md`, guide `.kora-agent/kora-docs/mkdocs/docs/en/guides/grpc-client-advanced.md`

## Contents

- [1. Overview](#1-overview)
- [2. Interface](#2-interface)
- [3. Registration with @Tag](#3-registration-with-tag)
- [4. Patterns](#4-patterns)
- [5. Default interceptors](#5-default-interceptors)
- [6. GraphInterceptor alternative](#6-graphinterceptor-alternative)
- [7. Troubleshooting](#7-troubleshooting)

## 1. Overview

A `io.grpc.ClientInterceptor` intercepts outbound calls before they reach the server. Use them for logging, metadata-based authentication, request IDs, deadlines, and tracing — concerns that belong near the transport boundary rather than at every call site.

## 2. Interface

```java
public interface ClientInterceptor {
    <ReqT, RespT> ClientCall<ReqT, RespT> interceptCall(
        MethodDescriptor<ReqT, RespT> method,
        CallOptions callOptions,
        Channel next
    );
}
```

## 3. Registration with @Tag

Register the interceptor as a `@Component` and scope it to one service's client with `@Tag(ServiceGrpc.class)`. The `@Tag` is what binds the interceptor to that generated client; it does not affect stub injection.

===! "Java"

```java
import io.grpc.CallOptions;
import io.grpc.Channel;
import io.grpc.ClientCall;
import io.grpc.ClientInterceptor;
import io.grpc.MethodDescriptor;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import ru.tinkoff.kora.common.Component;
import ru.tinkoff.kora.common.Tag;
import ru.tinkoff.kora.example.grpc.UserServiceGrpc;

@Tag(UserServiceGrpc.class)
@Component
public final class LoggingInterceptor implements ClientInterceptor {

    private static final Logger logger = LoggerFactory.getLogger(LoggingInterceptor.class);

    @Override
    public <ReqT, RespT> ClientCall<ReqT, RespT> interceptCall(
            MethodDescriptor<ReqT, RespT> method, CallOptions callOptions, Channel next) {
        logger.info("Calling gRPC method {}", method.getFullMethodName());
        return next.newCall(method, callOptions);
    }
}
```

=== "Kotlin"

```kotlin
import io.grpc.CallOptions
import io.grpc.Channel
import io.grpc.ClientCall
import io.grpc.ClientInterceptor
import io.grpc.MethodDescriptor
import org.slf4j.LoggerFactory
import ru.tinkoff.kora.common.Component
import ru.tinkoff.kora.common.Tag
import ru.tinkoff.kora.example.grpc.UserServiceGrpc

@Tag(UserServiceGrpc::class)
@Component
class LoggingInterceptor : ClientInterceptor {

    private val logger = LoggerFactory.getLogger(LoggingInterceptor::class.java)

    override fun <ReqT, RespT> interceptCall(
        method: MethodDescriptor<ReqT, RespT>,
        callOptions: CallOptions,
        next: Channel
    ): ClientCall<ReqT, RespT> {
        logger.info("Calling gRPC method {}", method.fullMethodName)
        return next.newCall(method, callOptions)
    }
}
```

## 4. Patterns

### Metadata headers

Headers must be added before delegating to `super.start()`. Wrap the call with `ForwardingClientCall.SimpleForwardingClientCall`.

```java
private static final Metadata.Key<String> REQUEST_ID_KEY =
    Metadata.Key.of("x-request-id", Metadata.ASCII_STRING_MARSHALLER);

@Override
public <ReqT, RespT> ClientCall<ReqT, RespT> interceptCall(
        MethodDescriptor<ReqT, RespT> method, CallOptions callOptions, Channel next) {
    return new ForwardingClientCall.SimpleForwardingClientCall<>(next.newCall(method, callOptions)) {
        @Override
        public void start(Listener<RespT> responseListener, Metadata headers) {
            headers.put(REQUEST_ID_KEY, UUID.randomUUID().toString());
            super.start(responseListener, headers);
        }
    };
}
```

### Auth interceptor with config

Inject a `@ConfigSource` config and attach the credential as an `authorization` metadata header.

```java
import io.grpc.CallOptions;
import io.grpc.Channel;
import io.grpc.ClientCall;
import io.grpc.ClientInterceptor;
import io.grpc.ForwardingClientCall;
import io.grpc.Metadata;
import io.grpc.MethodDescriptor;
import ru.tinkoff.kora.common.Component;
import ru.tinkoff.kora.common.Tag;
import ru.tinkoff.kora.example.grpc.UserServiceGrpc;

@Tag(UserServiceGrpc.class)
@Component
public final class AuthInterceptor implements ClientInterceptor {

    private static final Metadata.Key<String> AUTHORIZATION =
        Metadata.Key.of("authorization", Metadata.ASCII_STRING_MARSHALLER);

    private final AuthConfig authConfig;

    public AuthInterceptor(AuthConfig authConfig) {
        this.authConfig = authConfig;
    }

    @Override
    public <ReqT, RespT> ClientCall<ReqT, RespT> interceptCall(
            MethodDescriptor<ReqT, RespT> method, CallOptions callOptions, Channel next) {
        return new ForwardingClientCall.SimpleForwardingClientCall<>(next.newCall(method, callOptions)) {
            @Override
            public void start(Listener<RespT> responseListener, Metadata headers) {
                headers.put(AUTHORIZATION, authConfig.value());
                super.start(responseListener, headers);
            }
        };
    }
}
```

## 5. Default interceptors

Kora always applies at client startup:

- `GrpcClientConfigInterceptor` — applies the configuration from `grpcClient.<ServiceName>.*`.

## 6. GraphInterceptor alternative

Instead of a tagged `ClientInterceptor`, you can post-process the gRPC `Channel` (or any component) with a `GraphInterceptor`. See `.kora-agent/kora-docs/mkdocs/docs/en/documentation/container.md` (component inspection).

```java
import io.grpc.Channel;
import io.grpc.ClientInterceptors;
import ru.tinkoff.kora.application.graph.GraphInterceptor;
import ru.tinkoff.kora.common.Component;

@Component
public final class GrpcGraphInterceptor implements GraphInterceptor<Channel> {
    @Override
    public Channel init(Channel value) {
        return ClientInterceptors.intercept(value, new MyInterceptor());
    }

    @Override
    public Channel release(Channel value) {
        return value;
    }
}
```

## 7. Troubleshooting

| Problem | Solution |
|---------|----------|
| Interceptor never runs | Ensure `@Tag(ServiceGrpc.class)` matches the generated class exactly |
| `start` not called | Wrap the call in `ForwardingClientCall.SimpleForwardingClientCall` |
| Headers not sent | Add headers before calling `super.start()` |
