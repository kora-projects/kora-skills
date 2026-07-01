---
name: kora-grpc-client
description: "Builds gRPC clients in Kora via GrpcClientModule, the protobuf Gradle plugin, and generated stubs injected directly into components. Covers grpcClient.<ServiceName> HOCON/YAML config, plaintext vs TLS through the URL scheme, custom ClientInterceptor scoped with @Tag(ServiceGrpc.class) for metadata auth and logging, and unary plus server/client/bidirectional streaming with blocking and async stubs. Use when wiring an outbound gRPC call, injecting a *BlockingStub / *FutureStub / *Stub, adding authorization headers via gRPC metadata, configuring keepAliveTime/timeout/loadBalancingPolicy, or debugging UNAVAILABLE/UNAUTHENTICATED and missing-stub graph errors."
---

# Kora gRPC Client

Generate gRPC client stubs from a `.proto` contract and inject them as components through `GrpcClientModule`. Kora wires the configured channel and the generated stubs into the application graph; your code just builds protobuf requests and calls stub methods.

Read this first when:
- enabling `GrpcClientModule` and injecting a generated `*BlockingStub`/`*FutureStub`/`*Stub`,
- configuring a client under `grpcClient.<ServiceName>.*`,
- adding a `ClientInterceptor` for metadata headers, auth, or logging,
- making unary or streaming calls.

## Key facts (do not get these wrong)

- **Stubs are injected directly by type — no `@Tag` on the constructor parameter.** Kora produces one stub per generated `*Grpc` class. Injecting `UserServiceGrpc.UserServiceBlockingStub` is enough.
- **`@Tag(ServiceGrpc.class)` belongs on a `ClientInterceptor`**, to scope that interceptor to one service's client. It is not used for stub injection.
- Annotations come from `ru.tinkoff.kora.common.*` (`@Component`, `@Tag`, `@KoraApp`), not from any `annotation.processor.*` package.
- Plaintext vs TLS is chosen by the **URL scheme** (`http://` = plaintext, `https://`/`grpc://` per transport). There is no `usePlaintext` config key.
- The mandatory annotation processor must be present: Java `annotationProcessor "ru.tinkoff.kora:annotation-processors"`, Kotlin `ksp "ru.tinkoff.kora:symbol-processors"`.

## Quick Start

### 1. Dependencies

Pin the BOM (`kora-parent`); never version individual `ru.tinkoff.kora:*` artifacts.

```groovy
plugins {
    id "application"
    id "com.google.protobuf" version "0.9.4"
}

configurations {
    koraBom
    annotationProcessor.extendsFrom(koraBom)
    implementation.extendsFrom(koraBom)
}

dependencies {
    koraBom platform("ru.tinkoff.kora:kora-parent:1.2.17")
    annotationProcessor "ru.tinkoff.kora:annotation-processors"

    implementation "ru.tinkoff.kora:grpc-client"
    implementation "ru.tinkoff.kora:config-hocon"
    implementation "ru.tinkoff.kora:logging-logback"
    implementation "io.grpc:grpc-protobuf:1.74.0"
    compileOnly "javax.annotation:javax.annotation-api:1.3.2"
}

protobuf {
    protoc { artifact = "com.google.protobuf:protoc:3.25.3" }
    plugins {
        grpc { artifact = "io.grpc:protoc-gen-grpc-java:1.74.0" }
    }
    generateProtoTasks {
        all()*.plugins { grpc {} }
    }
}

sourceSets {
    main {
        java {
            srcDirs "build/generated/source/proto/main/grpc"
            srcDirs "build/generated/source/proto/main/java"
        }
    }
}
```

### 2. Define the protobuf service

`src/main/proto/user_service.proto`:

```protobuf
syntax = "proto3";
package ru.tinkoff.kora.example.grpc;
option java_multiple_files = true;

service UserService {
  rpc GetUser (GetUserRequest) returns (UserResponse) {}
}

message GetUserRequest { string user_id = 1; }
message UserResponse {
  string id = 1;
  string name = 2;
  string email = 3;
}
```

### 3. Enable the module

```java
import ru.tinkoff.grpc.client.GrpcClientModule;
import ru.tinkoff.kora.application.graph.KoraApplication;
import ru.tinkoff.kora.common.KoraApp;
import ru.tinkoff.kora.config.hocon.HoconConfigModule;
import ru.tinkoff.kora.logging.logback.LogbackModule;

@KoraApp
public interface Application extends HoconConfigModule, LogbackModule, GrpcClientModule {
    static void main(String[] args) {
        KoraApplication.run(ApplicationGraph::graph);
    }
}
```

### 4. Inject the stub and wrap it in a service

Inject the generated stub **directly** by type. Wrap it so protobuf builders and gRPC status handling stay at the transport boundary.

```java
import ru.tinkoff.kora.common.Component;
import ru.tinkoff.kora.example.grpc.UserServiceGrpc;
import ru.tinkoff.kora.example.grpc.GetUserRequest;

@Component
public final class UserClientService {

    private final UserServiceGrpc.UserServiceBlockingStub userService;

    public UserClientService(UserServiceGrpc.UserServiceBlockingStub userService) {
        this.userService = userService;
    }

    public UserDto getUser(String userId) {
        var response = userService.getUser(GetUserRequest.newBuilder()
            .setUserId(userId)
            .build());
        return new UserDto(response.getId(), response.getName(), response.getEmail());
    }
}
```

### 5. Configure the client

A service named `UserService` is configured under `grpcClient.UserService`. Use the URL scheme to control plaintext vs TLS; externalize the URL with `${?VAR}`.

```hocon
grpcClient {
  UserService {
    url = "http://localhost:8090"   // http:// => plaintext for local
    url = ${?GRPC_SERVER_URL}
    timeout = "10s"
    telemetry.logging.enabled = true
  }
}
```

## Stub types

| Stub | Use for |
|------|---------|
| `*BlockingStub` | Unary calls and server-streaming reads (returns `Iterator<Response>`) |
| `*FutureStub` | Unary calls returning `ListenableFuture<Response>` |
| `*Stub` (async) | Client-streaming and bidirectional streaming via `StreamObserver` |

A service may inject several stub types at once (e.g. a `*BlockingStub` for reads and a `*Stub` for client streaming). See [grpc-client-stubs-reference.md](references/grpc-client-stubs-reference.md).

## Client interceptors

Register a `ClientInterceptor` as a `@Component` and scope it to one service with `@Tag(ServiceGrpc.class)`. Kora applies it to that service's channel automatically; it does not change stub injection.

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

The default `GrpcClientConfigInterceptor` (applies `grpcClient.*` config) is always present. See [grpc-client-interceptors-reference.md](references/grpc-client-interceptors-reference.md) for logging, metadata, and `GraphInterceptor` patterns.

## Streaming

Server streaming can be consumed with a `*BlockingStub` (returns an `Iterator`) or asynchronously with a `*Stub`. Client and bidirectional streaming require the async `*Stub` and a `StreamObserver`. See [grpc-client-streaming-reference.md](references/grpc-client-streaming-reference.md).

## Configuration

`grpcClient.<ServiceName>.*` keys: `url` (required), `timeout`, `keepAliveTime`, `keepAliveTimeout`, `loadBalancingPolicy`, `maxInboundMessageSize`, and `telemetry.{logging,metrics,tracing}`. Full reference (HOCON + YAML, defaults, env substitution): [grpc-client-config-reference.md](references/grpc-client-config-reference.md).

## Common pitfalls

| Symptom | Fix |
|---------|-----|
| `Required dependency not found: ...BlockingStub` | Enable `GrpcClientModule` on `@KoraApp`; run `./gradlew classes` so protobuf + processors run |
| Stub class does not exist | Run protobuf generation and add the `build/generated/source/proto/...` source dirs to `sourceSets` |
| Tried to add `@Tag(...)` on a stub parameter | Remove it — stubs inject by type; `@Tag` is only for interceptors |
| `UNAVAILABLE` | Check `grpcClient.<ServiceName>.url` host/port and that the server is up |
| `UNAUTHENTICATED` | Add an `AuthInterceptor` (above) putting credentials into `Metadata` |
| Interceptor never runs | Ensure `@Component` + `@Tag(ServiceGrpc.class)` matches the generated class exactly |
| Wanted plaintext but got TLS | Use an `http://` URL; there is no `usePlaintext` key |

## References & assets

| File | Purpose |
|------|---------|
| [references/grpc-client-stubs-reference.md](references/grpc-client-stubs-reference.md) | Stub types, direct injection, service wrappers |
| [references/grpc-client-config-reference.md](references/grpc-client-config-reference.md) | Full config + protobuf plugin setup |
| [references/grpc-client-interceptors-reference.md](references/grpc-client-interceptors-reference.md) | Interceptor patterns, metadata, GraphInterceptor |
| [references/grpc-client-streaming-reference.md](references/grpc-client-streaming-reference.md) | Server/client/bidirectional streaming |
| [assets/README.md](assets/README.md) | Template catalog and usage |
</invoke>
