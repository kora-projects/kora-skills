---
name: kora-grpc-server
description: "Builds gRPC server handlers in Kora using GrpcServerModule, @Component handlers that extend the generated *GrpcImplBase, io.grpc ServerInterceptor beans, grpcServer HOCON/YAML config (port, maxMessageSize, telemetry), the com.google.protobuf Gradle plugin, and gRPC Server Reflection. Use when serving gRPC RPCs (unary/server/client/bidirectional streaming) from a Kora service, mapping protobuf messages to a service layer, returning io.grpc.Status errors, or enabling reflection for grpcurl. Triggers on grpc-server, GrpcServerModule, *GrpcImplBase, StreamObserver, ServerInterceptor, reflectionEnabled."
---

# Kora gRPC Server

Serve gRPC RPCs from a Kora application. The `.proto` contract is the source of truth: the `protobuf` Gradle plugin generates message classes and a `*Grpc.*ImplBase` base type, and you implement a Kora `@Component` that extends that base. `GrpcServerModule` discovers every `@Component` handler and `ServerInterceptor` and starts the server — no reflection-based wiring, everything is resolved through the compile-time graph.

## When to use vs NOT

Use this skill when:
- implementing gRPC handlers that extend the generated `*GrpcImplBase`,
- wiring `GrpcServerModule` into a `@KoraApp`,
- configuring `grpcServer` (port, message size, telemetry, keepalive, reflection),
- adding `io.grpc.ServerInterceptor` beans for auth/logging/metrics,
- enabling gRPC Server Reflection for `grpcurl`.

Do NOT use this skill for:
- consuming gRPC services (declarative stubs) — that is the `kora-grpc-client` skill,
- HTTP/JSON endpoints — use `kora-http-server`.

## Quick Start

### 1. Dependencies (BOM pins all `ru.tinkoff.kora:*` versions)

```groovy
dependencies {
    koraBom platform("ru.tinkoff.kora:kora-parent:1.2.17")
    annotationProcessor "ru.tinkoff.kora:annotation-processors"

    implementation "ru.tinkoff.kora:grpc-server"
    implementation "ru.tinkoff.kora:config-hocon"
    implementation "ru.tinkoff.kora:logging-logback"
    implementation "io.grpc:grpc-protobuf:1.74.0"
    implementation "javax.annotation:javax.annotation-api:1.3.2"

    // Optional: gRPC Server Reflection (grpcurl / Postman gRPC)
    implementation "io.grpc:grpc-services:1.74.0"
}
```

Kotlin: replace the processor with `ksp "ru.tinkoff.kora:symbol-processors"`. Never put a version on a `ru.tinkoff.kora:*` artifact — the BOM controls them.

### 2. Protobuf Gradle plugin

```groovy
plugins {
    id "com.google.protobuf" version "0.10.0"
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
    main.java {
        srcDirs "build/generated/source/proto/main/grpc"
        srcDirs "build/generated/source/proto/main/java"
    }
}
```

### 3. `.proto` contract (`src/main/proto/user_service.proto`)

```protobuf
syntax = "proto3";

package ru.tinkoff.kora.example.grpc;
option java_multiple_files = true;

import "google/protobuf/timestamp.proto";

service UserService {
  rpc CreateUser(CreateUserRequest) returns (UserResponse) {}
  rpc GetUser(GetUserRequest) returns (UserResponse) {}
}

message CreateUserRequest { string name = 1; string email = 2; }
message GetUserRequest { string user_id = 1; }
message UserResponse {
  string id = 1;
  string name = 2;
  string email = 3;
  google.protobuf.Timestamp created_at = 4;
}
```

### 4. Application module

```java
@KoraApp
public interface Application extends
        HoconConfigModule,
        LogbackModule,
        GrpcServerModule {

    static void main(String[] args) {
        KoraApplication.run(ApplicationGraph::graph);
    }
}
```

### 5. Handler — `@Component` extending the generated `*ImplBase`

```java
import io.grpc.Status;
import io.grpc.stub.StreamObserver;
import ru.tinkoff.kora.common.Component;

@Component
public final class UserServiceGrpcHandler extends UserServiceGrpc.UserServiceImplBase {

    private final UserService userService;

    public UserServiceGrpcHandler(UserService userService) {
        this.userService = userService;
    }

    @Override
    public void getUser(GetUserRequest request, StreamObserver<UserResponse> responseObserver) {
        var user = userService.getUser(request.getUserId())
            .orElseThrow(() -> Status.NOT_FOUND
                .withDescription("User not found: " + request.getUserId())
                .asRuntimeException());
        responseObserver.onNext(toGrpcUser(user));
        responseObserver.onCompleted();
    }
}
```

The handler is a plain Kora component: constructor injection, business logic delegated to `UserService`. The generated protobuf types are transport DTOs — keep domain logic out of the handler.

### 6. Configuration (`application.conf`)

```hocon
grpcServer {
  port = ${GRPC_PORT}
  telemetry.logging.enabled = true
}
```

### 7. Run and probe

```bash
./gradlew clean classes   # generate proto + build the compile-time graph
./gradlew run
grpcurl -plaintext -d '{"user_id":"42"}' \
  localhost:8090 ru.tinkoff.kora.example.grpc.UserService/GetUser
```

The gRPC method's full name is `<proto package>.<service>/<Method>`.

---

## References

| File | Purpose |
|------|---------|
| [references/grpc-server-reference.md](references/grpc-server-reference.md) | Module, dependency, protobuf plugin, default interceptors, troubleshooting |
| [references/grpc-service-reference.md](references/grpc-service-reference.md) | Handler patterns: unary + all three streaming kinds, message conversion |
| [references/grpc-config-reference.md](references/grpc-config-reference.md) | Full `grpcServer` config, telemetry tags/attributes, Netty transport, metrics |
| [references/grpc-interceptors-reference.md](references/grpc-interceptors-reference.md) | `ServerInterceptor` beans: auth, logging, metrics, exception mapping, ordering |
| [references/grpc-error-handling-reference.md](references/grpc-error-handling-reference.md) | `io.grpc.Status` codes, error metadata, streaming errors |
| [references/grpc-reflection-reference.md](references/grpc-reflection-reference.md) | Reflection setup and `grpcurl`/Postman usage |

Assets (templates): see [assets/README.md](assets/README.md).

---

## Core patterns

### RPC method signatures

| RPC type | Handler signature |
|----------|-------------------|
| Unary | `void method(Req, StreamObserver<Resp>)` |
| Server streaming | `void method(Req, StreamObserver<Resp>)` — many `onNext`, one `onCompleted` |
| Client streaming | `StreamObserver<Req> method(StreamObserver<Resp>)` |
| Bidirectional streaming | `StreamObserver<Req> method(StreamObserver<Resp>)` |

Server streaming: emit each item with `onNext`, then a single `onCompleted`.

```java
@Override
public void getAllUsers(Empty request, StreamObserver<UserResponse> responseObserver) {
    for (var user : userService.getAllUsers()) {
        responseObserver.onNext(toGrpcUser(user));
    }
    responseObserver.onCompleted();
}
```

Client/bidirectional streaming: return a `StreamObserver<Req>` that accumulates `onNext` values and replies on `onCompleted`.

```java
@Override
public StreamObserver<CreateUserRequest> createUsers(StreamObserver<CreateUsersResponse> responseObserver) {
    return new StreamObserver<>() {
        private final List<UserRequest> requests = new ArrayList<>();
        public void onNext(CreateUserRequest v) { requests.add(new UserRequest(v.getName(), v.getEmail())); }
        public void onError(Throwable t) { responseObserver.onError(t); }
        public void onCompleted() {
            var created = userService.createUsers(requests);
            responseObserver.onNext(CreateUsersResponse.newBuilder()
                .setCreatedCount(created.size()).build());
            responseObserver.onCompleted();
        }
    };
}
```

See [references/grpc-service-reference.md](references/grpc-service-reference.md) for full examples including timestamp/`ByteString` conversion.

### Errors via `io.grpc.Status`

Map domain failures to gRPC status codes. Common: `NOT_FOUND`, `INVALID_ARGUMENT`, `ALREADY_EXISTS`, `PERMISSION_DENIED`, `UNAUTHENTICATED`, `INTERNAL`, `UNAVAILABLE`.

```java
throw Status.NOT_FOUND.withDescription("User not found: " + id).asRuntimeException();
```

Inside a handler use either `throw ...asRuntimeException()` (when the call propagates) or `responseObserver.onError(...)`. Send exactly one terminal signal per call — never `onNext` after `onError`/`onCompleted`. Details: [references/grpc-error-handling-reference.md](references/grpc-error-handling-reference.md).

### Interceptors

Register a cross-cutting interceptor by implementing `io.grpc.ServerInterceptor` and annotating it `@Component`; `GrpcServerModule` adds it automatically.

```java
import io.grpc.*;
import ru.tinkoff.kora.common.Component;

@Component
public final class MyServerInterceptor implements ServerInterceptor {
    private final Logger logger = LoggerFactory.getLogger(MyServerInterceptor.class);

    @Override
    public <ReqT, RespT> ServerCall.Listener<ReqT> interceptCall(
            ServerCall<ReqT, RespT> call, Metadata headers, ServerCallHandler<ReqT, RespT> next) {
        logger.info("gRPC call: {}", call.getMethodDescriptor().getFullMethodName());
        return next.startCall(call, headers);
    }
}
```

Default interceptors registered by the module: `ContextServerInterceptor`, `CoroutineContextInjectInterceptor`, `MetricCollectorServerInterceptor`, `LoggingServerInterceptor`. To replace the default list, override the `serverBuilder` method from `GrpcModule`. Auth and exception-mapping examples: [references/grpc-interceptors-reference.md](references/grpc-interceptors-reference.md).

### Reflection

Add `io.grpc:grpc-services` and set `reflectionEnabled = true` (default is `false`) for `grpcurl`/Postman discovery.

```hocon
grpcServer { reflectionEnabled = ${?GRPC_REFLECTION_ENABLED} }
```

```bash
grpcurl -plaintext localhost:8090 list
```

Keep it disabled in production unless the endpoint is internal-only. See [references/grpc-reflection-reference.md](references/grpc-reflection-reference.md).

### Telemetry

The module emits metrics (`rpc.server.duration`, `rpc.server.requests_per_rpc`, `rpc.server.responses_per_rpc`), tracing, and logging — all toggled under `grpcServer.telemetry`. Metrics default on, tracing default on, logging default off. Add custom metric tags / trace attributes under `telemetry.metrics.tags` / `telemetry.tracing.attributes` ([references/grpc-config-reference.md](references/grpc-config-reference.md)).

---

## Common pitfalls

| Symptom | Fix |
|---------|-----|
| Generated classes not found | Run `./gradlew clean classes`; verify the `com.google.protobuf` plugin and the proto `srcDirs` source sets |
| Handler not registered | Annotate it `@Component` and ensure it extends the generated `*GrpcImplBase` |
| `Component` import won't resolve | Import `ru.tinkoff.kora.common.Component` (not any `annotation.processor` package) |
| Client hangs on a stream | Always finish with `onCompleted()` (or `onError`) after the `onNext` calls |
| `INVALID_ARGUMENT` returned for everything | Use specific `Status` codes instead of a blanket `INTERNAL` |
| `UNIMPLEMENTED: unknown service` via grpcurl | Add `io.grpc:grpc-services` and set `reflectionEnabled = true` |
| RPC returns `UNIMPLEMENTED` from a real client | Generated service/method names must match the `.proto` used by the client |
| Build hangs after clean | `./gradlew --stop`, then rebuild |
