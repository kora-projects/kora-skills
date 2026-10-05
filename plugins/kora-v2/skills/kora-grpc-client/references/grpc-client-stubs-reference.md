# gRPC Client Stubs Reference (Kora 2.0)

How protoc-generated stubs become injectable components, which stub flavours exist, and how to
wrap them.

## Contents

- [1. How a stub reaches the graph](#1-how-a-stub-reaches-the-graph)
- [2. Stub flavours](#2-stub-flavours)
- [3. Injection by type — never by tag](#3-injection-by-type--never-by-tag)
- [4. Kotlin coroutine stubs](#4-kotlin-coroutine-stubs)
- [5. Wrapping a stub](#5-wrapping-a-stub)
- [6. Injecting the Channel or the config directly](#6-injecting-the-channel-or-the-config-directly)
- [7. Troubleshooting](#7-troubleshooting)

---

## 1. How a stub reaches the graph

`io.koraframework:grpc-client` ships **no annotation**. Instead, `annotation-processors`
(Java) and `symbol-processors` (Kotlin) contain a `kora-app` *extension* that is asked to
produce any dependency the graph cannot otherwise satisfy.

When a component asks for a type that is a subclass of `io.grpc.stub.AbstractStub` and whose
**enclosing** class carries `io.grpc.stub.annotations.GrpcGenerated`, the extension emits the
factory call and, in turn, requests the channel it needs:

| Step | What is generated / requested | Tag |
|---|---|---|
| 1 | `UserServiceGrpc.newBlockingStub(channel)` | the stub itself is **untagged** |
| 2 | `io.grpc.Channel` | `@Tag(UserServiceGrpc.class)` |
| 3 | `ManagedChannelLifecycle(config, credentials, interceptors, configurer, telemetryFactory, channelFactory, UserServiceGrpc.getServiceDescriptor())` | first four parameters carry `@Tag(UserServiceGrpc.class)`, the last two are untagged |
| 4 | `GrpcClientConfig` | `@Tag(UserServiceGrpc.class)` → `GrpcClientConfig.defaultConfig(config, mapper, UserServiceGrpc.SERVICE_NAME)` |

Step 4 is where the config section name comes from: `defaultConfig` takes the **proto**
`SERVICE_NAME` (e.g. `io.koraframework.example.grpc.UserService`), strips everything up to the
last dot, and reads `grpcClient.UserService`.

The single consequence worth memorising: **the generated `<Service>Grpc` class is the tag for
everything per-service** — interceptors, credentials, channel-builder configurer.

The method chosen depends on the requested type's name suffix:

| Requested type ends with | Factory used |
|---|---|
| `BlockingStub` | `newBlockingStub` |
| `FutureStub` | `newFutureStub` |
| anything else | `newStub` |

`GrpcClientModule` itself only contributes three `@DefaultComponent`s: the
`ConfigValueMapper<DefaultServiceConfig>`, the `GrpcClientTelemetryFactory`, and the
`GrpcClientChannelFactory` (OkHttp). It contains no stub factories — those are generated per
service at compile time.

---

## 2. Stub flavours

### `*BlockingStub`

Synchronous. The natural fit for Kora 2.0, whose contracts are synchronous on virtual threads.
Handles unary calls and consumes server streaming as an `Iterator`.

```java
UserServiceGrpc.UserServiceBlockingStub blockingStub;

UserResponse response = blockingStub.getUser(request);              // unary
Iterator<UserResponse> stream = blockingStub.getAllUsers(request);  // server streaming
```

### `*FutureStub`

Unary calls returning a Guava `ListenableFuture`.

```java
UserServiceGrpc.UserServiceFutureStub futureStub;
ListenableFuture<UserResponse> future = futureStub.getUser(request);
```

### `*Stub` (async)

Callback-driven via `io.grpc.stub.StreamObserver`. **Required** for client streaming and
bidirectional streaming.

```java
UserServiceGrpc.UserServiceStub asyncStub;
StreamObserver<CreateUserRequest> requestObserver = asyncStub.createUsers(responseObserver);
```

All three are the ordinary protoc-generated types — Kora does not subclass or proxy them, so
gRPC's own semantics (deadlines, `withDeadlineAfter`, `withCallCredentials`, `withInterceptors`)
apply unchanged.

---

## 3. Injection by type — never by tag

```java
import io.koraframework.common.annotation.Component;
import io.koraframework.example.grpc.UserServiceGrpc;

@Component
public final class UserClientService {

    private final UserServiceGrpc.UserServiceBlockingStub userService;

    public UserClientService(UserServiceGrpc.UserServiceBlockingStub userService) {
        this.userService = userService;
    }
}
```

The extension returns `null` for a **tagged** stub request, so `@Tag(...)` on a stub parameter
means the graph has no way to build it and the build fails. `@Tag` belongs on interceptors,
credentials and configurers, never on the stub.

One component may take several flavours of the same service; they share one channel:

```java
@Component
public final class UserStreamingClientService {

    private final UserStreamingServiceGrpc.UserStreamingServiceBlockingStub blockingStub;
    private final UserStreamingServiceGrpc.UserStreamingServiceStub asyncStub;

    public UserStreamingClientService(
            UserStreamingServiceGrpc.UserStreamingServiceBlockingStub blockingStub,
            UserStreamingServiceGrpc.UserStreamingServiceStub asyncStub) {
        this.blockingStub = blockingStub;
        this.asyncStub = asyncStub;
    }
}
```

A default factory method on the `@KoraApp` interface works too — the stub is an ordinary
parameter:

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

---

## 4. Kotlin coroutine stubs

The KSP extension recognises a second family: subclasses of `io.grpc.kotlin.AbstractCoroutineStub`
whose enclosing object is annotated `@io.grpc.kotlin.StubFor(<Service>Grpc::class)` — the shape
`protoc-gen-grpc-kotlin` emits. It resolves the channel under the tag named by `@StubFor`, and a
companion symbol processor generates a module exposing the stub as a `@DefaultComponent`. The
framework's own KSP test builds a graph with `EventsGrpcKt.EventsCoroutineStub` injected, so
**injection is genuinely supported**.

What that does *not* mean:

- A generated `suspend fun` on a coroutine stub is **grpc-kotlin's** code, not a Kora contract.
  Kora does not generate it, intercept it, or provide a coroutine scope to call it from.
- Kora 2.0 contracts — `@Component` methods, `@HttpController` routes, repositories — are
  **synchronous**, executed on virtual threads. Calling a coroutine stub means you own the
  coroutine boundary yourself.
- **No migrated Kora example uses coroutine stubs.** Both Kotlin examples and both Kotlin guide
  apps inject the Java `*BlockingStub` / `*Stub` and use `StreamObserver`.

`grpc-kotlin` `1.5.0` is the version in Kora's catalog; it appears there for the symbol
processor's own tests, and is not a dependency of `grpc-client`. If you do use coroutine stubs,
add `io.grpc:grpc-kotlin-stub:1.5.0` and the `protoc-gen-grpc-kotlin:1.5.0` protoc plugin
yourself, and keep them aligned with grpc-java `1.84.0`.

**Recommendation:** use the Java stubs. They match Kora 2.0's execution model with no extra
machinery.

---

## 5. Wrapping a stub

Generated stubs speak protobuf messages and gRPC statuses. Keep both at the boundary: expose a
component that takes and returns application types.

```java
import io.koraframework.common.annotation.Component;
import io.koraframework.example.grpc.GetUserRequest;
import io.koraframework.example.grpc.UserServiceGrpc;

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

Mapping `io.grpc.StatusRuntimeException` to a domain error belongs here as well:

```java
try {
    return toDto(stub.getUser(request));
} catch (StatusRuntimeException e) {
    if (e.getStatus().getCode() == Status.Code.NOT_FOUND) {
        throw new UserNotFoundException(userId);
    }
    throw e;
}
```

Templates: [`assets/client-wrapper.client.java.template`](../assets/client-wrapper.client.java.template),
[`assets/client-wrapper.client.kt.template`](../assets/client-wrapper.client.kt.template).

---

## 6. Injecting the Channel or the config directly

Both are reachable, but only **with the service tag** — the extension refuses an untagged
`Channel` or `GrpcClientConfig` request:

```java
@Component
public final class ChannelProbe {

    private final Channel channel;

    public ChannelProbe(@Tag(UserServiceGrpc.class) Channel channel) {
        this.channel = channel;
    }
}
```

This is rarely what you want — it is the escape hatch for building a stub by hand (for instance
a stub flavour generated into a different package). For everything routine, inject the stub.

---

## 7. Troubleshooting

| Problem | Cause / fix |
|---|---|
| `Required dependency not found: …BlockingStub` | `@KoraApp` does not extend `GrpcClientModule`; the processor is not on the classpath; or `generateProto` has not run so the type does not exist yet |
| Stub type exists in the IDE but not at build time | generated dirs missing from `sourceSets` — add `build/generated/source/proto/main/grpc` and `.../main/java` |
| Graph fails on a stub parameter that carries `@Tag` | remove the `@Tag`; the extension only serves **untagged** stub requests |
| `Required dependency not found: io.grpc.Channel` | you asked for a `Channel` **without** a tag — tag it with the generated `<Service>Grpc` class |
| Extension never fires at all | the enclosing `*Grpc` class has no `@GrpcGenerated` — regenerate with `protoc-gen-grpc-java:1.84.0` and keep `io.grpc:grpc-stub` on the compile classpath (it arrives with `grpc-client`) |
| `cannot find symbol: javax.annotation.Generated` | add `compileOnly "javax.annotation:javax.annotation-api:1.3.2"` |
| Phantom `ru.tinkoff.kora` errors in `build/generated` | stale protobuf output — `./gradlew clean --continue` then `./gradlew classes testClasses --no-build-cache` |
