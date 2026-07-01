# gRPC Client Streaming Reference

**Source:** guide `.kora-agent/kora-docs/mkdocs/docs/en/guides/grpc-client-advanced.md`

## Contents

- [1. Streaming shapes](#1-streaming-shapes)
- [2. Server streaming](#2-server-streaming)
- [3. Client streaming](#3-client-streaming)
- [4. Bidirectional streaming](#4-bidirectional-streaming)
- [5. StreamObserver handling](#5-streamobserver-handling)
- [6. Troubleshooting](#6-troubleshooting)

## 1. Streaming shapes

| Type | Stub | Pattern |
|------|------|---------|
| Unary | `*BlockingStub` | `response = stub.method(request)` |
| Server streaming | `*BlockingStub` / `*Stub` | `Iterator<Response>` (blocking) or `StreamObserver` (async) |
| Client streaming | `*Stub` | `StreamObserver<Request>` returned by the call |
| Bidirectional | `*Stub` | `StreamObserver<Request>` + `StreamObserver<Response>` |

Keep stream lifecycle handling in a wrapper service so callbacks do not leak across the codebase. Wrap streaming results in a `CompletableFuture` to expose a synchronous-looking API to controllers/jobs.

## 2. Server streaming

### Blocking (Iterator)

```java
var iterator = blockingStub.getAllUsers(Empty.getDefaultInstance());
var users = new ArrayList<UserDto>();
iterator.forEachRemaining(user -> users.add(toDto(user)));
```

### Async (StreamObserver)

```java
asyncStub.getAllUsers(Empty.getDefaultInstance(), new StreamObserver<UserResponse>() {
    @Override
    public void onNext(UserResponse value) {
        // handle each streamed element
    }

    @Override
    public void onError(Throwable t) {
        logger.error("Stream error", t);
    }

    @Override
    public void onCompleted() {
        // stream finished
    }
});
```

## 3. Client streaming

The async stub returns a request `StreamObserver`. Push all requests, then call `onCompleted()`. The single summary response arrives through the response observer.

```java
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
    public void onCompleted() { }
};

var requestObserver = asyncStub.createUsers(responseObserver);
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
    throw new RuntimeException("Failed to create users over gRPC streaming", e);
}
```

## 4. Bidirectional streaming

Requests and responses flow independently on the same call. Collect responses in a thread-safe structure (e.g. `CopyOnWriteArrayList`) and complete the future in `onCompleted()`.

```java
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

var requestObserver = asyncStub.updateUsers(responseObserver);
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
    throw new RuntimeException("Failed to update users over gRPC streaming", e);
}
```

## 5. StreamObserver handling

### onError — map gRPC status

```java
@Override
public void onError(Throwable t) {
    if (t instanceof StatusRuntimeException sre) {
        logger.error("gRPC error: {} - {}", sre.getStatus().getCode(), sre.getStatus().getDescription());
    } else {
        logger.error("Unknown error", t);
    }
}
```

### Awaiting completion

A `CompletableFuture` completed inside `onCompleted()` (as above) gives a clean blocking boundary. A `CountDownLatch` is an alternative when no value is returned:

```java
private final CountDownLatch latch = new CountDownLatch(1);

@Override
public void onCompleted() {
    latch.countDown();
}

// caller
latch.await(30, TimeUnit.SECONDS);
```

## 6. Troubleshooting

| Problem | Solution |
|---------|----------|
| Stream never completes | Call `requestObserver.onCompleted()` after sending all requests |
| `UNAVAILABLE` | Check the server is running and reachable |
| `UNAUTHENTICATED` on streaming calls | Tag the auth interceptor to the streaming service's generated class |
| Resource leak | Always complete or error the request observer |
| Messages not received | Verify the `onNext` implementation and response observer wiring |
