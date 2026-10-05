# gRPC Client Streaming Reference (Kora 2.0)

Consuming unary and streaming RPCs from synchronous Kora components.

## Contents

- [1. Shapes and stub choice](#1-shapes-and-stub-choice)
- [2. Unary](#2-unary)
- [3. Server streaming](#3-server-streaming)
- [4. Client streaming](#4-client-streaming)
- [5. Bidirectional streaming](#5-bidirectional-streaming)
- [6. Bridging back to a synchronous contract](#6-bridging-back-to-a-synchronous-contract)
- [7. Deadlines, cancellation and errors](#7-deadlines-cancellation-and-errors)
- [8. Testing a streaming client](#8-testing-a-streaming-client)
- [9. Troubleshooting](#9-troubleshooting)

---

## 1. Shapes and stub choice

| Shape | Stub | Call style |
|---|---|---|
| Unary | `*BlockingStub` | `response = stub.method(request)` |
| Unary, async | `*FutureStub` | `ListenableFuture<Response>` |
| Server streaming | `*BlockingStub` | returns `Iterator<Response>` |
| Server streaming, async | `*Stub` | `stub.method(request, responseObserver)` |
| Client streaming | `*Stub` | returns a request `StreamObserver` |
| Bidirectional | `*Stub` | returns a request `StreamObserver`, responses arrive independently |

Kora 2.0 contracts are **synchronous on virtual threads**. There are no `Mono`/`Flux`,
`CompletionStage` or `suspend` gRPC contracts to return from a controller or a component method —
the callback style is gRPC's, and it stops at the wrapper component's boundary.

Blocking a virtual thread on `future.get(...)` inside a wrapper is the intended pattern here: the
carrier thread is released while the virtual thread parks.

---

## 2. Unary

```java
@Component
public final class UserClientService {

    private final UserServiceGrpc.UserServiceBlockingStub stub;

    public UserClientService(UserServiceGrpc.UserServiceBlockingStub stub) {
        this.stub = stub;
    }

    public UserDto getUser(String userId) {
        var response = stub.getUser(GetUserRequest.newBuilder().setUserId(userId).build());
        return toDto(response);
    }
}
```

A per-call deadline overrides the `grpcClient.<Service>.timeout` default:

```java
stub.withDeadlineAfter(2, TimeUnit.SECONDS).getUser(request);
```

---

## 3. Server streaming

### Blocking — `Iterator`

```java
public List<UserDto> getAllUsers() {
    var users = new ArrayList<UserDto>();
    var iterator = blockingStub.getAllUsers(Empty.getDefaultInstance());
    iterator.forEachRemaining(user -> users.add(toDto(user)));
    return users;
}
```

The iterator is lazy: each `next()` pulls the next message off the wire and can throw
`StatusRuntimeException` mid-iteration. Draining it fully (or abandoning the call) is required —
an abandoned half-read iterator holds the stream open until the deadline.

### Async — `StreamObserver`

Use this when responses must be processed as they arrive rather than collected.

```java
asyncStub.getAllUsers(Empty.getDefaultInstance(), new StreamObserver<UserResponse>() {
    @Override
    public void onNext(UserResponse value) {
        sink.accept(toDto(value));
    }

    @Override
    public void onError(Throwable t) {
        logger.error("Stream failed", t);
    }

    @Override
    public void onCompleted() {
        logger.debug("Stream finished");
    }
});
```

Exactly one of `onError` / `onCompleted` is ever called, and never both.

---

## 4. Client streaming

The async stub returns the **request** observer; push every request, then `onCompleted()`. The
single summary response arrives through the response observer you supplied.

```java
public CreateUsersResult createUsers(List<UserRequest> requests) {
    var future = new CompletableFuture<CreateUsersResult>();
    var responseObserver = new StreamObserver<CreateUsersResponse>() {
        @Override
        public void onNext(CreateUsersResponse value) {
            future.complete(new CreateUsersResult(value.getCreatedCount(), List.copyOf(value.getUserIdsList())));
        }

        @Override
        public void onError(Throwable t) {
            future.completeExceptionally(t);
        }

        @Override
        public void onCompleted() {
        }
    };

    var requestObserver = this.asyncStub.createUsers(responseObserver);
    try {
        for (var request : requests) {
            requestObserver.onNext(CreateUserRequest.newBuilder()
                .setName(request.name())
                .setEmail(request.email())
                .build());
        }
        requestObserver.onCompleted();
        return future.get(5, TimeUnit.SECONDS);
    } catch (Exception e) {
        requestObserver.onError(e);
        throw new IllegalStateException("Failed to create users over gRPC streaming", e);
    }
}
```

The `catch` calling `requestObserver.onError(e)` is not decoration — without it a failure between
`onNext` calls leaves the stream open until the deadline.

---

## 5. Bidirectional streaming

Requests and responses flow independently on one call, so responses can (and do) arrive while you
are still sending. Collect them in a thread-safe structure and complete in `onCompleted()`.

```java
public List<UserDto> updateUsers(List<UserUpdateRequest> updates) {
    var future = new CompletableFuture<List<UserDto>>();
    var responses = new CopyOnWriteArrayList<UserDto>();
    var responseObserver = new StreamObserver<UserResponse>() {
        @Override
        public void onNext(UserResponse value) {
            responses.add(toDto(value));
        }

        @Override
        public void onError(Throwable t) {
            future.completeExceptionally(t);
        }

        @Override
        public void onCompleted() {
            future.complete(List.copyOf(responses));
        }
    };

    var requestObserver = this.asyncStub.updateUsers(responseObserver);
    try {
        for (var update : updates) {
            requestObserver.onNext(UpdateUserRequest.newBuilder()
                .setUserId(update.userId())
                .setName(update.name())
                .setEmail(update.email())
                .build());
        }
        requestObserver.onCompleted();
        return future.get(5, TimeUnit.SECONDS);
    } catch (Exception e) {
        requestObserver.onError(e);
        throw new IllegalStateException("Failed to update users over gRPC streaming", e);
    }
}
```

A `StreamObserver` returned by a call is **not thread-safe** — `onNext` must not be invoked
concurrently from several threads. Send from one thread, or guard it.

---

## 6. Bridging back to a synchronous contract

`CompletableFuture` completed inside the observer is the pattern used by the migrated guide apps.
`CountDownLatch` is the leaner alternative when nothing is returned:

```java
private final CountDownLatch latch = new CountDownLatch(1);

@Override
public void onCompleted() {
    latch.countDown();
}

// caller
if (!latch.await(30, TimeUnit.SECONDS)) {
    throw new IllegalStateException("gRPC stream did not complete in time");
}
```

Always use the timed `get` / `await` overloads. The channel deadline covers the wire, not a bug that
leaves the observer un-completed.

Kotlin: the same code, unchanged — do **not** reach for `suspendCancellableCoroutine`,
`runBlocking`, `Dispatchers.IO` or `Flow` to wrap it. Those exist to bridge blocking code into
coroutines, and Kora 2.0 has no coroutine contract to bridge into.

---

## 7. Deadlines, cancellation and errors

- The `timeout` key becomes a **default** deadline: `GrpcClientConfigInterceptor` sets it only when
  `callOptions.getDeadline() == null`. It applies to the **whole call**, so a long-lived stream
  needs either no `timeout` on that client or a per-call `withDeadlineAfter`.
- Cancel from the client with `((ClientCallStreamObserver<Req>) requestObserver).cancel(reason,
  cause)`, or by letting the deadline expire.
- Map statuses at the wrapper boundary:

```java
@Override
public void onError(Throwable t) {
    if (t instanceof StatusRuntimeException sre) {
        logger.warn("gRPC error: {} — {}", sre.getStatus().getCode(), sre.getStatus().getDescription());
    }
    future.completeExceptionally(t);
}
```

- `future.get(...)` wraps the cause in `ExecutionException`; unwrap with `e.getCause()` before
  testing for `StatusRuntimeException`.

---

## 8. Testing a streaming client

The migrated guide apps test the wrapper against an **in-process** gRPC server rather than the Kora
graph: build a fake `*ImplBase`, serve it on `InProcessServerBuilder`, and construct the wrapper
with `ServiceGrpc.newStub(channel)` directly.

```java
var serverName = InProcessServerBuilder.generateName();
this.server = InProcessServerBuilder.forName(serverName)
        .directExecutor()
        .addService(new FakeUserStreamingService())
        .build()
        .start();
this.channel = InProcessChannelBuilder.forName(serverName).directExecutor().build();
this.service = new UserStreamingClientService(
        UserStreamingServiceGrpc.newBlockingStub(channel),
        UserStreamingServiceGrpc.newStub(channel));
```

To exercise a tagged interceptor in that setup, apply it by hand — the in-process channel is not
built by `ManagedChannelLifecycle`, so nothing collects tagged components:

```java
var interceptedChannel = ClientInterceptors.intercept(channel,
        new UserStreamingAuthInterceptor(() -> "test-api-key"),
        new LoggingInterceptor());
```

`io.grpc:grpc-inprocess` **must be the same version as the rest of gRPC** (`1.84.0`); a stale pin
produces `AbstractMethodError: … buildClientTransportServers(List, MetricRecorder)` at server build
time, an error that names nothing related to versions.

Add `testImplementation "io.grpc:grpc-inprocess:1.84.0"`.

---

## 9. Troubleshooting

| Problem | Cause / fix |
|---|---|
| Stream never completes | `requestObserver.onCompleted()` not called after the last request |
| Call stays open after a failure | no `requestObserver.onError(e)` in the `catch` |
| `DEADLINE_EXCEEDED` on a long stream | `grpcClient.<Service>.timeout` applies to the whole call — drop it or override per call |
| Responses missing on a bidi stream | completing the future in `onNext` instead of `onCompleted` |
| `ConcurrentModificationException` / lost messages | `onNext` invoked from several threads; the observer is not thread-safe |
| `ExecutionException` instead of `StatusRuntimeException` | unwrap `e.getCause()` |
| `UNAUTHENTICATED` only in tests | the tagged interceptor is not applied to a hand-built in-process channel — use `ClientInterceptors.intercept` |
| `AbstractMethodError … buildClientTransportServers` | `grpc-inprocess` / `grpc-netty` version differs from the rest of gRPC |
| Half-read `Iterator` leaks a call | drain it, or cancel the call |
