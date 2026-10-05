# gRPC Service Implementation Reference — Kora 2.0

**Framework source (authority):** [`GrpcServerFactoryModule`](https://github.com/kora-projects/kora/blob/2.0.0.RC2/grpc/grpc-server/src/main/java/io/koraframework/grpc/server/GrpcServerFactoryModule.java) · [`VirtualThreadExecutorTransportFilter`](https://github.com/kora-projects/kora/blob/2.0.0.RC2/grpc/grpc-server/src/main/java/io/koraframework/grpc/server/handler/VirtualThreadExecutorTransportFilter.java)
**Migrated examples:** [`UserService.java`](https://github.com/kora-projects/kora-examples/blob/migration/2.0/examples/java/kora-java-grpc-server/src/main/java/io/koraframework/example/grpc/server/UserService.java) · [`UserService.kt`](https://github.com/kora-projects/kora-examples/blob/migration/2.0/examples/kotlin/kora-kotlin-grpc-server/src/main/kotlin/io/koraframework/kotlin/example/grpc/server/UserService.kt) · [`UserStreamingServiceGrpcHandler.java`](https://github.com/kora-projects/kora-examples/blob/migration/2.0/guides/java/kora-java-guide-grpc-server-advanced-app/src/main/java/io/koraframework/guide/grpcserver/advanced/grpc/UserStreamingServiceGrpcHandler.java)

## Contents

1. Handler pattern
2. Execution model — what Kora 2.0 does and does not accept
3. Unary RPC
4. Server streaming
5. Client streaming
6. Bidirectional streaming
7. Protobuf message conversion
8. Complete service — Java
9. Complete service — Kotlin
10. Common pitfalls

---

## 1. Handler pattern

A handler is an **untagged** `@Component` extending the generated `*Grpc.*ImplBase`.

===! `Java`

```java
import io.koraframework.common.annotation.Component;

@Component
public final class UserServiceGrpcHandler extends UserServiceGrpc.UserServiceImplBase {

    private final UserService userService;

    public UserServiceGrpcHandler(UserService userService) {
        this.userService = userService;
    }
}
```

=== `Kotlin`

```kotlin
import io.koraframework.common.annotation.Component

@Component
class UserServiceGrpcHandler(
    private val userService: UserService
) : UserServiceGrpc.UserServiceImplBase()
```

Three things are required and each fails differently:

| Requirement | If missing |
|---|---|
| `@Component` (Java: `io.koraframework.common.annotation.Component`) | the class is never in the graph; RPC → `UNIMPLEMENTED` |
| extends the generated `*ImplBase` | it is not a `BindableService`; never collected |
| **no** `@Tag(...)` on the class | the tagged component drops out of `All<ValueOf<BindableService>>`; RPC → `UNIMPLEMENTED` |

Constructor injection only — there is no field injection in Kora. The generated protobuf types are
transport DTOs; keep domain logic in an injected service component.

## 2. Execution model — what Kora 2.0 does and does not accept

The server is built `.directExecutor()` with `VirtualThreadExecutorTransportFilter` supplied both as
a `ServerTransportFilter` and as the `ServerCallExecutorSupplier`. Each transport gets a
single-threaded executor whose factory produces **virtual threads** named `grpc-<remote-address>`,
and the filter binds two `ScopedValue`s around every call body:

```java
executor.execute(() -> ScopedValue.where(MDC.VALUE, mdc)
    .where(OpentelemetryContext.VALUE, context)
    .run(command));
```

Consequences you must design around:

- **Handler bodies are synchronous and may block.** Blocking JDBC, a blocking `@HttpClient`, or
  `Thread.sleep` inside a handler is correct style, not a bug.
- **`suspend fun` is not a Kora contract.** The generated stubs are Java and their methods are
  `void`/`StreamObserver`-returning; a `suspend` override does not override anything. Kotlin reports
  `'createUser' overrides nothing`, which never mentions coroutines.
- **`Mono`, `Flux` and `CompletionStage` are not Kora contracts** in 2.0 and there is no
  reactive-to-`StreamObserver` bridge in the module.
- **The Kora `Context` type does not exist in 2.0.** A ported handler taking a Kora `Context`
  parameter, or calling `Context.current()` on it, does not compile. `io.grpc.Context` is gRPC's
  own, unrelated type and is still there — do not treat one as a rename of the other. Per-call state
  belongs in `io.grpc.Context`, in call `Attributes`, or in the MDC.
- **Do not hand work to your own executor.** A `ScopedValue` binding does not follow a task
  submitted to an unrelated pool, so MDC and the trace context are lost. If you need fan-out, use
  `StructuredTaskScope`, whose forks inherit scoped values.

## 3. Unary RPC

```java
@Override
public void getUser(GetUserRequest request, StreamObserver<UserResponse> responseObserver) {
    try {
        var user = userService.getUser(request.getUserId())
            .orElseThrow(() -> Status.NOT_FOUND
                .withDescription("User not found: " + request.getUserId())
                .asRuntimeException());
        responseObserver.onNext(toGrpcUser(user));
        responseObserver.onCompleted();
    } catch (StatusRuntimeException e) {
        responseObserver.onError(e);
    } catch (Exception e) {
        logger.error("Failed to get user", e);
        responseObserver.onError(Status.INTERNAL
            .withDescription("Failed to get user")
            .withCause(e)
            .asRuntimeException());
    }
}
```

## 4. Server streaming — one request, many responses

`.proto`:

```protobuf
rpc GetAllUsers(google.protobuf.Empty) returns (stream UserResponse) {}
```

Same handler signature as unary; emit many `onNext`, then exactly one `onCompleted`.

```java
@Override
public void getAllUsers(Empty request, StreamObserver<UserResponse> responseObserver) {
    try {
        for (var user : userStreamingService.getAllUsers()) {
            responseObserver.onNext(toGrpcUser(user));
        }
        responseObserver.onCompleted();
    } catch (Exception e) {
        responseObserver.onError(Status.INTERNAL
            .withDescription("Failed to stream users").withCause(e).asRuntimeException());
    }
}
```

## 5. Client streaming — many requests, one response

`.proto`:

```protobuf
rpc CreateUsers(stream CreateUserRequest) returns (CreateUsersResponse) {}
```

The handler returns the observer that receives the client's messages; it replies from `onCompleted`.

```java
@Override
public StreamObserver<CreateUserRequest> createUsers(StreamObserver<CreateUsersResponse> responseObserver) {
    return new StreamObserver<>() {
        private final List<UserRequest> requests = new ArrayList<>();

        @Override
        public void onNext(CreateUserRequest value) {
            requests.add(new UserRequest(value.getName(), value.getEmail()));
        }

        @Override
        public void onError(Throwable t) {
            logger.error("Client streaming failed", t);
            responseObserver.onError(t);
        }

        @Override
        public void onCompleted() {
            try {
                var created = userStreamingService.createUsers(requests);
                responseObserver.onNext(CreateUsersResponse.newBuilder()
                    .setCreatedCount(created.size())
                    .addAllUserIds(created.stream().map(UserResponse::id).toList())
                    .build());
                responseObserver.onCompleted();
            } catch (Exception e) {
                responseObserver.onError(Status.INTERNAL
                    .withDescription("Failed to create users").withCause(e).asRuntimeException());
            }
        }
    };
}
```

## 6. Bidirectional streaming — many requests, many responses

`.proto`:

```protobuf
rpc UpdateUsers(stream UpdateUserRequest) returns (stream UserResponse) {}
```

Same shape as client streaming; the difference is that you answer inside `onNext`.

```java
@Override
public StreamObserver<UpdateUserRequest> updateUsers(StreamObserver<UserResponse> responseObserver) {
    return new StreamObserver<>() {
        @Override
        public void onNext(UpdateUserRequest value) {
            try {
                var user = userStreamingService
                    .tryUpdateUser(value.getUserId(), new UserRequest(value.getName(), value.getEmail()))
                    .orElseThrow(() -> Status.NOT_FOUND
                        .withDescription("User not found: " + value.getUserId())
                        .asRuntimeException());
                responseObserver.onNext(toGrpcUser(user));
            } catch (StatusRuntimeException e) {
                responseObserver.onError(e);
            }
        }

        @Override
        public void onError(Throwable t) {
            logger.error("Bidirectional streaming failed", t);
            responseObserver.onError(t);
        }

        @Override
        public void onCompleted() {
            responseObserver.onCompleted();
        }
    };
}
```

`StreamObserver` is not thread-safe. When several sources may emit onto one response observer,
synchronise on it yourself.

## 7. Protobuf message conversion

### Timestamp

```java
import com.google.protobuf.Timestamp;
import java.time.ZoneOffset;

private UserResponse toGrpcUser(io.koraframework.example.dto.UserResponse user) {
    return UserResponse.newBuilder()
        .setId(user.id())
        .setName(user.name())
        .setEmail(user.email())
        .setCreatedAt(Timestamp.newBuilder()
            .setSeconds(user.createdAt().toEpochSecond(ZoneOffset.UTC))
            .setNanos(user.createdAt().getNano())
            .build())
        .build();
}
```

`google/protobuf/timestamp.proto` must be `import`ed in the `.proto`; `grpc-protobuf` supplies the
well-known types.

### ByteString

```java
import com.google.protobuf.ByteString;

builder.setId(ByteString.copyFromUtf8(UUID.randomUUID().toString()));
builder.setData(ByteString.copyFrom(bytes));
```

### proto3 has no null

Every scalar has a zero value (`""`, `0`, `false`) and `getX()` never returns `null`. To express
"absent", use `optional` in the `.proto` (which generates `hasX()`) or a wrapper type. Do not
`@Nullable`-annotate generated accessors.

## 8. Complete service — Java

```java
package io.koraframework.example.grpc.server;

import com.google.protobuf.Empty;
import com.google.protobuf.Timestamp;
import io.grpc.Status;
import io.grpc.stub.StreamObserver;
import io.koraframework.common.annotation.Component;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.time.ZoneOffset;

@Component
public final class UserServiceGrpcHandler extends UserServiceGrpc.UserServiceImplBase {

    private static final Logger logger = LoggerFactory.getLogger(UserServiceGrpcHandler.class);

    private final UserService userService;

    public UserServiceGrpcHandler(UserService userService) {
        this.userService = userService;
    }

    @Override
    public void createUser(CreateUserRequest request, StreamObserver<UserResponse> responseObserver) {
        try {
            var user = userService.createUser(new UserRequest(request.getName(), request.getEmail()));
            responseObserver.onNext(toGrpcUser(user));
            responseObserver.onCompleted();
        } catch (Exception e) {
            logger.error("Failed to create user", e);
            responseObserver.onError(Status.INTERNAL
                .withDescription("Failed to create user").withCause(e).asRuntimeException());
        }
    }

    @Override
    public void getUser(GetUserRequest request, StreamObserver<UserResponse> responseObserver) {
        try {
            var user = userService.getUser(request.getUserId())
                .orElseThrow(() -> Status.NOT_FOUND
                    .withDescription("User not found: " + request.getUserId())
                    .asRuntimeException());
            responseObserver.onNext(toGrpcUser(user));
            responseObserver.onCompleted();
        } catch (RuntimeException e) {
            responseObserver.onError(e);
        }
    }

    @Override
    public void deleteUser(DeleteUserRequest request, StreamObserver<Empty> responseObserver) {
        try {
            userService.deleteUser(request.getUserId());
            responseObserver.onNext(Empty.getDefaultInstance());
            responseObserver.onCompleted();
        } catch (UserNotFoundException e) {
            responseObserver.onError(Status.NOT_FOUND
                .withDescription(e.getMessage()).asRuntimeException());
        }
    }

    private UserResponse toGrpcUser(io.koraframework.example.grpc.server.dto.UserResponse user) {
        return UserResponse.newBuilder()
            .setId(user.id())
            .setName(user.name())
            .setEmail(user.email())
            .setCreatedAt(Timestamp.newBuilder()
                .setSeconds(user.createdAt().toEpochSecond(ZoneOffset.UTC))
                .setNanos(user.createdAt().getNano())
                .build())
            .build();
    }
}
```

## 9. Complete service — Kotlin

Kotlin extends the **same Java-generated** `*ImplBase`. There is no `suspend`, no `Flow` and no
`runBlocking` anywhere in this file.

```kotlin
package io.koraframework.kotlin.example.grpc.server

import com.google.protobuf.Empty
import com.google.protobuf.Timestamp
import io.grpc.Status
import io.grpc.stub.StreamObserver
import io.koraframework.common.annotation.Component
import org.slf4j.LoggerFactory
import java.time.ZoneOffset

@Component
class UserServiceGrpcHandler(
    private val userService: UserService
) : UserServiceGrpc.UserServiceImplBase() {

    private val logger = LoggerFactory.getLogger(UserServiceGrpcHandler::class.java)

    override fun createUser(request: CreateUserRequest, responseObserver: StreamObserver<UserResponse>) {
        try {
            val user = userService.createUser(UserRequest(request.name, request.email))
            responseObserver.onNext(user.toGrpcUser())
            responseObserver.onCompleted()
        } catch (e: Exception) {
            logger.error("Failed to create user", e)
            responseObserver.onError(
                Status.INTERNAL.withDescription("Failed to create user").withCause(e).asRuntimeException()
            )
        }
    }

    override fun getUser(request: GetUserRequest, responseObserver: StreamObserver<UserResponse>) {
        val user = userService.getUser(request.userId)
            ?: return responseObserver.onError(
                Status.NOT_FOUND.withDescription("User not found: ${request.userId}").asRuntimeException()
            )
        responseObserver.onNext(user.toGrpcUser())
        responseObserver.onCompleted()
    }

    override fun deleteUser(request: DeleteUserRequest, responseObserver: StreamObserver<Empty>) {
        try {
            userService.deleteUser(request.userId)
            responseObserver.onNext(Empty.getDefaultInstance())
            responseObserver.onCompleted()
        } catch (e: UserNotFoundException) {
            responseObserver.onError(Status.NOT_FOUND.withDescription(e.message).asRuntimeException())
        }
    }

    private fun io.koraframework.kotlin.example.grpc.server.dto.UserResponse.toGrpcUser(): UserResponse =
        UserResponse.newBuilder()
            .setId(id)
            .setName(name)
            .setEmail(email)
            .setCreatedAt(
                Timestamp.newBuilder()
                    .setSeconds(createdAt.toEpochSecond(ZoneOffset.UTC))
                    .setNanos(createdAt.nano)
                    .build()
            )
            .build()
}
```

The `<ReqT, RespT>` type parameters of a generated Java method are platform types in Kotlin; keep
the override signature exactly as the stub declares it. Adding `?` or removing it from a parameter
produces `overrides nothing`, an error that never mentions nullability.

## 10. Common pitfalls

| Symptom | Cause | Fix |
|---|---|---|
| RPC answers `UNIMPLEMENTED` | no `@Component`, wrong base class, or a `@Tag(...)` on the handler | untagged `@Component` extending `*Grpc.*ImplBase` |
| `'createUser' overrides nothing` (Kotlin) | `suspend fun`, or a changed parameter nullability | plain `override fun` with the stub's exact signature |
| Kora `Context` does not resolve | the type was removed in 2.0 | use `io.grpc.Context`, call `Attributes`, or the MDC |
| Client hangs forever | a path through the handler with no terminal signal | exactly one `onCompleted` **or** `onError` on every path |
| `onNext` after a terminal call | double completion | send exactly one terminal signal per call |
| MDC / trace id missing in a log line | work submitted to a foreign executor | keep it on the calling virtual thread, or use `StructuredTaskScope` |
| Interleaved/corrupt stream responses | concurrent `onNext` on one `StreamObserver` | synchronise on the observer |
| `getX()` returns `""` instead of null | proto3 zero values | use `optional` + `hasX()` |
| Generated classes not found | proto sources not on the `java` source set | add `build/generated/source/proto/main/{grpc,java}` |
