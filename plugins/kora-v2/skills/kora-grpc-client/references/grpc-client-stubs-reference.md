# gRPC Client Stubs Reference

**Source:** `.kora-agent/kora-docs/mkdocs/docs/en/documentation/grpc-client.md`, guide `.kora-agent/kora-docs/mkdocs/docs/en/guides/grpc-client.md`, example `.kora-agent/kora-examples/examples/java/kora-java-grpc-client`

## Contents

- [1. Overview](#1-overview)
- [2. Stub types](#2-stub-types)
- [3. Direct injection (no @Tag)](#3-direct-injection-no-tag)
- [4. Wrapping a stub in a service](#4-wrapping-a-stub-in-a-service)
- [5. Factory-style provisioning](#5-factory-style-provisioning)
- [6. Troubleshooting](#6-troubleshooting)

## 1. Overview

Kora creates one gRPC client stub bean per generated `*Grpc` class through `GrpcClientModule`. The stub is bound to a channel configured under `grpcClient.<ServiceName>.*`. Stubs are injected **directly by type** into any `@Component`.

## 2. Stub types

### `*BlockingStub`

Synchronous calls. Used for unary RPC and for consuming server-streaming responses as an `Iterator`.

```java
UserServiceGrpc.UserServiceBlockingStub blockingStub;
UserResponse response = blockingStub.getUser(request);                 // unary
Iterator<UserResponse> stream = blockingStub.getAllUsers(request);     // server streaming
```

### `*FutureStub`

Asynchronous unary calls returning a `ListenableFuture`.

```java
UserServiceGrpc.UserServiceFutureStub futureStub;
ListenableFuture<UserResponse> future = futureStub.getUser(request);
```

### `*Stub` (async)

Asynchronous calls driven by `StreamObserver`. Required for client streaming and bidirectional streaming.

```java
UserServiceGrpc.UserServiceStub asyncStub;
StreamObserver<CreateUserRequest> requestObserver = asyncStub.createUsers(responseObserver);
```

## 3. Direct injection (no @Tag)

Inject the generated stub by its exact type. **Do not** add `@Tag` to the constructor parameter — stubs are unique per generated class.

```java
import ru.tinkoff.kora.common.Component;
import ru.tinkoff.kora.example.grpc.UserServiceGrpc;

@Component
public final class UserClientService {

    private final UserServiceGrpc.UserServiceBlockingStub userService;

    public UserClientService(UserServiceGrpc.UserServiceBlockingStub userService) {
        this.userService = userService;
    }
}
```

A single component may inject several stub types for the same service (e.g. a blocking stub for reads and an async stub for client streaming):

```java
@Component
public final class UserStreamingClientService {

    private final UserServiceGrpc.UserServiceBlockingStub blockingStub;
    private final UserServiceGrpc.UserServiceStub asyncStub;

    public UserStreamingClientService(
            UserServiceGrpc.UserServiceBlockingStub blockingStub,
            UserServiceGrpc.UserServiceStub asyncStub) {
        this.blockingStub = blockingStub;
        this.asyncStub = asyncStub;
    }
}
```

## 4. Wrapping a stub in a service

Generated stubs are transport objects: they speak protobuf request/response types and gRPC statuses. Wrap them in an application service so protobuf construction and error mapping stay at the boundary.

```java
import ru.tinkoff.kora.common.Component;
import ru.tinkoff.kora.example.grpc.UserServiceGrpc;
import ru.tinkoff.kora.example.grpc.GetUserRequest;

@Component
public final class UserClientService {

    private final UserServiceGrpc.UserServiceBlockingStub stub;

    public UserClientService(UserServiceGrpc.UserServiceBlockingStub stub) {
        this.stub = stub;
    }

    public UserDto getUser(String userId) {
        var response = stub.getUser(GetUserRequest.newBuilder()
            .setUserId(userId)
            .build());
        return new UserDto(response.getId(), response.getName(), response.getEmail());
    }
}
```

Benefits:
- hides protobuf builder construction,
- isolates transport types from the rest of the app,
- centralizes gRPC status handling.

## 5. Factory-style provisioning

You can also bind a wrapper through a default factory method on the `@KoraApp` interface instead of `@Component`. The stub is passed in as a normal parameter:

===! "Java"

```java
@KoraApp
public interface Application extends HoconConfigModule, GrpcClientModule {

    default UserClientService userClientService(UserServiceGrpc.UserServiceBlockingStub stub) {
        return new UserClientService(stub);
    }
}
```

=== "Kotlin"

```kotlin
@KoraApp
interface Application : HoconConfigModule, GrpcClientModule {

    fun userClientService(stub: UserServiceGrpc.UserServiceBlockingStub): UserClientService =
        UserClientService(stub)
}
```

## 6. Troubleshooting

| Problem | Solution |
|---------|----------|
| `Required dependency not found: ...BlockingStub` | Enable `GrpcClientModule` on `@KoraApp`; run `./gradlew classes` |
| Stub injected with `@Tag` fails to resolve | Remove `@Tag` from the stub parameter — it injects by type |
| Wrong stub behaviour | Pick `*BlockingStub` / `*FutureStub` / `*Stub` per call style |
| Protobuf/stub classes missing | Run `./gradlew generateProto` and verify the `sourceSets` source dirs |
