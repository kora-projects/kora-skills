# gRPC Client Interceptors Reference (Kora 2.0)

How Kora collects `io.grpc.ClientInterceptor` components, what tag binds them, and the other
per-service extension points on the channel.

## Contents

- [1. How interceptors are collected](#1-how-interceptors-are-collected)
- [2. Registration — the tag is the generated `<Service>Grpc` class](#2-registration--the-tag-is-the-generated-servicegrpc-class)
- [3. Metadata patterns](#3-metadata-patterns)
- [4. ChannelCredentials — TLS](#4-channelcredentials--tls)
- [5. Configurer — everything else on the builder](#5-configurer--everything-else-on-the-builder)
- [6. Replacing telemetry](#6-replacing-telemetry)
- [7. Kora Context does not exist; io.grpc.Context does](#7-kora-context-does-not-exist-iogrpccontext-does)
- [8. Troubleshooting](#8-troubleshooting)

---

## 1. How interceptors are collected

`ManagedChannelLifecycle` takes `All<ClientInterceptor> interceptors` as its **third** constructor
parameter, and the compile-time extension tags the first four parameters with the service tag. So
the graph request is, verbatim:

```java
@Tag(UserServiceGrpc.class) All<ClientInterceptor> interceptors
```

At `init()` the lifecycle builds the list and hands it to the channel builder:

```java
var interceptors = new ArrayList<ClientInterceptor>(2);
this.interceptors.forEach(interceptors::add);          // your tagged components
interceptors.add(new GrpcClientTelemetryInterceptor(telemetry));
interceptors.add(new GrpcClientConfigInterceptor(this.config));
builder.intercept(interceptors);
```

Consequences:

- **An untagged `ClientInterceptor` component is never picked up.** `All<T>` under a tag collects
  only components carrying that tag.
- Two interceptors for the same service are both collected — `All<T>` is a collection, not a
  single-component lookup, so there is no "multiple components match" ambiguity here.
- Kora's own two interceptors are always appended, whether or not you contribute any. They are not
  components and cannot be removed or reordered from the graph.
- `GrpcClientConfigInterceptor` is what applies `grpcClient.<Service>.timeout` as a call deadline;
  `GrpcClientTelemetryInterceptor` is what produces the `rpc.client.call.duration` metric, the spans and
  the request/response logs.

---

## 2. Registration — the tag is the generated `<Service>Grpc` class

===! "Java"

```java
import io.grpc.CallOptions;
import io.grpc.Channel;
import io.grpc.ClientCall;
import io.grpc.ClientInterceptor;
import io.grpc.MethodDescriptor;
import io.koraframework.common.annotation.Component;
import io.koraframework.common.annotation.Tag;
import io.koraframework.example.grpc.UserServiceGrpc;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

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
import io.grpc.*
import io.koraframework.common.annotation.Component
import io.koraframework.common.annotation.Tag
import io.koraframework.example.grpc.UserServiceGrpc
import org.slf4j.LoggerFactory

@Tag(UserServiceGrpc::class)
@Component
class LoggingInterceptor : ClientInterceptor {

    private val logger = LoggerFactory.getLogger(LoggingInterceptor::class.java)

    override fun <ReqT : Any?, RespT : Any?> interceptCall(
        method: MethodDescriptor<ReqT, RespT>,
        callOptions: CallOptions,
        next: Channel
    ): ClientCall<ReqT, RespT> {
        logger.info("Calling gRPC method {}", method.fullMethodName)
        return next.newCall(method, callOptions)
    }
}
```

**What the tag must be — and what it must not be:**

| | |
|---|---|
| ✅ `@Tag(UserServiceGrpc.class)` | the protoc-generated outer class |
| ❌ `@Tag(UserServiceGrpc.UserServiceBlockingStub.class)` | the stub, not the service |
| ❌ `@Tag(GrpcClientModule.class)` | a Kora module class — nothing looks interceptors up by it |
| ❌ no tag at all | not collected |

Every wrong form **compiles cleanly and starts cleanly**; the interceptor simply never runs. If the
interceptor carries auth, calls start failing with `UNAUTHENTICATED` and nothing in the logs points
at the tag. Cover it with a test that asserts the header arrives, the way the guide app's
`rejectsStreamingCallsWithoutApiKey…` test does.

Kotlin note: the interceptor's type parameters must be declared as `<ReqT : Any?, RespT : Any?>` to
match the Java signature; with `<ReqT : Any, RespT : Any>` Kotlin reports
`'interceptCall' overrides nothing`.

---

## 3. Metadata patterns

gRPC metadata is the **only** authentication mechanism for a Kora gRPC client. There is no
`@HttpClient`-style auth annotation, no security module, no `Principal` plumbing on the client side.

Headers must be written inside `start()`, before `super.start()` — the call has not been sent yet
at `interceptCall` time.

### Static or config-backed credential

```java
import io.koraframework.config.common.annotation.ConfigSource;

@ConfigSource("auth.apiKey")
public interface UserServiceAuthConfig {
    String value();
}
```

```java
@Tag(UserServiceGrpc.class)
@Component
public final class AuthInterceptor implements ClientInterceptor {

    private static final Metadata.Key<String> AUTHORIZATION =
        Metadata.Key.of("authorization", Metadata.ASCII_STRING_MARSHALLER);

    private final UserServiceAuthConfig authConfig;

    public AuthInterceptor(UserServiceAuthConfig authConfig) {
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

```hocon
auth.apiKey.value = "test-api-key"
auth.apiKey.value = ${?GRPC_API_KEY}
```

### Rotating / fetched token

Inject the token source as an ordinary component and read it per call — the interceptor instance is
shared for the channel's whole lifetime, so never cache a token in a field.

```java
@Override
public void start(Listener<RespT> responseListener, Metadata headers) {
    headers.put(AUTHORIZATION, "Bearer " + tokenProvider.currentToken());
    super.start(responseListener, headers);
}
```

### Binary metadata

`Metadata.Key.of(name, Metadata.BINARY_BYTE_MARSHALLER)` requires the key name to end in `-bin`;
`ASCII_STRING_MARSHALLER` keys must not. gRPC enforces this at `Key.of` time.

### Reading response headers or trailers

```java
return new ForwardingClientCall.SimpleForwardingClientCall<>(next.newCall(method, callOptions)) {
    @Override
    public void start(Listener<RespT> responseListener, Metadata headers) {
        super.start(new ForwardingClientCallListener.SimpleForwardingClientCallListener<>(responseListener) {
            @Override
            public void onHeaders(Metadata headers) {
                logger.debug("response headers: {}", headers);
                super.onHeaders(headers);
            }
        }, headers);
    }
};
```

Templates: [`assets/client-interceptor.client.java.template`](../assets/client-interceptor.client.java.template),
[`assets/client-interceptor.client.kt.template`](../assets/client-interceptor.client.kt.template).

---

## 4. ChannelCredentials — TLS

`ManagedChannelLifecycle`'s second parameter is `@Nullable ChannelCredentials`, tagged with the same
service tag. When absent, the channel is built with `forAddress(host, port)`; when present, with
`forAddress(host, port, credentials)`.

```java
@KoraApp
public interface Application extends HoconConfigModule, LogbackModule, GrpcClientModule {

    @Tag(UserServiceGrpc.class)
    default ChannelCredentials userServiceCredentials(UserServiceTlsConfig config) throws IOException {
        return TlsChannelCredentials.newBuilder()
            .trustManager(new File(config.trustStorePath()))
            .keyManager(new File(config.certPath()), new File(config.keyPath()))
            .build();
    }

    static void main(String[] args) {
        KoraApplication.run(ApplicationGraph::graph);
    }
}
```

Remember that credentials alone do not switch the transport to TLS-by-URL logic: the `url` scheme
still decides whether `usePlaintext()` is called. Use `https://` with credentials.

---

## 5. Configurer — everything else on the builder

`io.koraframework.common.Configurer<T>` is a single-method `T configure(T)`. Two slots exist:

| Component | Tag | When it runs |
|---|---|---|
| `Configurer<ManagedChannelBuilder<?>>` | `@Tag(<Service>Grpc.class)` | in `ManagedChannelLifecycle.init()`, **after** interceptors, keep-alive, load balancing and `defaultServiceConfig` |
| `Configurer<ManagedChannelBuilder<?>>` | untagged | inside `GrpcOkHttpClientChannelFactory`, for every channel it creates |

```java
@Tag(UserServiceGrpc.class)
@Component
public final class UserServiceChannelConfigurer implements Configurer<ManagedChannelBuilder<?>> {

    @Override
    public ManagedChannelBuilder<?> configure(ManagedChannelBuilder<?> builder) {
        return builder
            .maxInboundMessageSize(16 * 1024 * 1024)
            .userAgent("user-service-client/1.0");
    }
}
```

Because it runs last, a configurer can override anything the config set. That is the intended escape
hatch: `grpcClient.*` deliberately exposes a small key set, and everything else on
`ManagedChannelBuilder` is reached this way rather than through invented config keys.

To replace the transport wholesale, supply your own `GrpcClientChannelFactory` component — it
overrides the module's `@DefaultComponent` OkHttp factory.

---

## 6. Replacing telemetry

`GrpcClientModule.defaultGrpcClientTelemetryFactory(...)` is a `@DefaultComponent`, so declaring a
plain `@Component GrpcClientTelemetryFactory` replaces it globally (it is requested **untagged**, so
one implementation covers every gRPC client). Subclassing `DefaultGrpcClientTelemetryFactory` and
overriding `build(...)` keeps the config-driven enable/disable behaviour while swapping in custom
metrics or logging.

The finer-grained hooks are the `@Nullable DefaultGrpcClientLoggerFactory` and
`@Nullable DefaultGrpcClientMetricsFactory` parameters: contribute a subclass of either as a
`@Component` and the default telemetry factory uses it instead of its `INSTANCE` singleton.

---

## 7. Kora Context does not exist; io.grpc.Context does

`Context` was removed from the whole Kora framework in 2.0 — there is no
`io.koraframework.common.Context`. Any ported code with a Kora `Context` parameter, a
`Context.current()` call against Kora's class, or a context-propagating interceptor built on it must
be rewritten.

`io.grpc.Context` is a **different, unrelated** class that gRPC still ships, and it remains the
correct tool for gRPC-scoped propagation inside interceptors:

```java
private static final Context.Key<String> TENANT = Context.key("tenant");
```

Be explicit about which one you mean in any code comment or explanation — the names are identical
and the confusion is the point of failure. For cross-cutting values that used to ride Kora's
`Context`, prefer passing them as method parameters: contracts are synchronous on virtual threads,
so there is no async boundary forcing an ambient carrier.

---

## 8. Troubleshooting

| Problem | Cause / fix |
|---|---|
| Interceptor never runs | wrong tag or no tag — must be `@Tag(<Service>Grpc.class)` on a `@Component` |
| Interceptor runs for the wrong service | the tag names a different `*Grpc` class than the stub being injected |
| `UNAUTHENTICATED` although the interceptor exists | it is not tagged, or the header is written outside `start()` |
| Headers never arrive | `super.start(responseListener, headers)` called before `headers.put(...)` |
| Kotlin `'interceptCall' overrides nothing` | declare `<ReqT : Any?, RespT : Any?>` |
| `IllegalArgumentException` from `Metadata.Key.of` | binary keys must end in `-bin`, ASCII keys must not |
| TLS still not used with credentials present | `url` scheme is `http` — `usePlaintext()` wins |
| Cannot set `maxInboundMessageSize` | no such config key — use a tagged `Configurer<ManagedChannelBuilder<?>>` |
| Kora `Context` will not compile | it was removed in 2.0; `io.grpc.Context` is a different class |
