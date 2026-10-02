# gRPC Error Handling Reference — Kora 2.0

**Framework source (authority):** [`TelemetryInterceptor`](https://github.com/kora-projects/kora/blob/2.0.0.RC2/grpc/grpc-server/src/main/java/io/koraframework/grpc/server/interceptor/TelemetryInterceptor.java) · [`DefaultGrpcServerLoggerFactory`](https://github.com/kora-projects/kora/blob/2.0.0.RC2/grpc/grpc-server/src/main/java/io/koraframework/grpc/server/telemetry/impl/DefaultGrpcServerLoggerFactory.java)
**Migrated example:** [`UserServiceGrpcHandler.java`](https://github.com/kora-projects/kora-examples/blob/migration/2.0/guides/java/kora-java-guide-grpc-server-advanced-app/src/main/java/io/koraframework/guide/grpcserver/advanced/grpc/UserServiceGrpcHandler.java)

Error handling on a Kora gRPC server is plain grpc-java: `io.grpc.Status`, `StatusRuntimeException`,
`StreamObserver.onError`. Kora adds no exception-mapping layer of its own — there is no gRPC
equivalent of `HttpServerResponseException`, and nothing analogous to an HTTP error mapper.

## Contents

1. Status codes
2. Signalling an error from a handler
3. How Kora observes an error
4. Error metadata
5. Errors in streaming
6. Mapping domain exceptions
7. Common pitfalls

---

## 1. Status codes

| Code | Name | Typical HTTP analogue | Use for |
|---|---|---|---|
| 1 | `CANCELLED` | 499 | client cancelled |
| 2 | `UNKNOWN` | 500 | unclassified |
| 3 | `INVALID_ARGUMENT` | 400 | request is malformed regardless of state |
| 4 | `DEADLINE_EXCEEDED` | 504 | the call's deadline elapsed |
| 5 | `NOT_FOUND` | 404 | entity does not exist |
| 6 | `ALREADY_EXISTS` | 409 | entity already exists |
| 7 | `PERMISSION_DENIED` | 403 | authenticated but not allowed |
| 8 | `RESOURCE_EXHAUSTED` | 429 | quota / rate limit |
| 9 | `FAILED_PRECONDITION` | 400 | request invalid *for the current state* |
| 10 | `ABORTED` | 409 | concurrency conflict; retryable at a higher level |
| 11 | `OUT_OF_RANGE` | 400 | past the end of a range |
| 12 | `UNIMPLEMENTED` | 501 | method not implemented — **also what an uncollected handler returns** |
| 13 | `INTERNAL` | 500 | invariant broken on the server |
| 14 | `UNAVAILABLE` | 503 | transient; safe to retry with backoff |
| 16 | `UNAUTHENTICATED` | 401 | missing or invalid credentials |

`INVALID_ARGUMENT` vs `FAILED_PRECONDITION`: the first means the request would be wrong in any
state; the second means it is wrong right now.

> `UNIMPLEMENTED` from a method you *did* implement almost always means the handler was not
> collected — see [grpc-server-reference.md](grpc-server-reference.md) §4.

## 2. Signalling an error from a handler

Two equivalent forms.

```java
// throw — the generated stub catches it and closes the call
throw Status.NOT_FOUND
    .withDescription("User not found: " + id)
    .asRuntimeException();
```

```java
// explicit — required inside a StreamObserver callback, where throwing has nowhere to go
responseObserver.onError(Status.NOT_FOUND
    .withDescription("User not found: " + id)
    .asRuntimeException());
```

Rules that hold for both:

- **Exactly one terminal signal per call** — `onCompleted()` **or** `onError(...)`, never both,
  never twice, and never an `onNext` after either.
- `withCause(e)` attaches the cause **server-side only**. It is not serialised to the client; it
  reaches Kora's response log and your own logging. Put anything the client needs into
  `withDescription(...)` or trailers (§4).
- `withDescription(...)` crosses the wire. Do not put stack traces, SQL, or internal identifiers
  into it.
- A `StatusRuntimeException` raised by a *downstream* gRPC client carries that server's status.
  Re-throwing it verbatim leaks the downstream's `NOT_FOUND` as if it were yours — translate it.

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

An exception that escapes a handler entirely still terminates the call, but as `UNKNOWN` with no
description — always map deliberately.

## 3. How Kora observes an error

`TelemetryInterceptor` wraps every call, so errors are recorded whether you throw or call `onError`:

- the span gets `StatusCode.ERROR`, the `rpc.response.status_code` attribute (the code name, e.g.
  `NOT_FOUND`) and, when an exception ended the call, `error.type`;
- `rpc.server.call.duration` is timed with `rpc.response.status_code` set to the code name and
  `error.type` set to the exception class (`""` otherwise);
- the response logger emits at **`WARN`** with `status`, `exceptionType` and the throwable attached,
  instead of the `INFO` used for a successful call.

Those three require `grpcServer.telemetry.{tracing,metrics,logging}` to be enabled — and metrics and
logging default to **`false`** ([grpc-config-reference.md](grpc-config-reference.md) §3). A service
whose gRPC errors are "invisible" is usually just a service with telemetry left at its defaults.

## 4. Error metadata

Machine-readable detail goes into trailers, not the description:

```java
var trailers = new Metadata();
trailers.put(Metadata.Key.of("error-code", Metadata.ASCII_STRING_MARSHALLER), "USER_NOT_FOUND");
trailers.put(Metadata.Key.of("user-id", Metadata.ASCII_STRING_MARSHALLER), request.getUserId());

responseObserver.onError(Status.NOT_FOUND
    .withDescription("User not found")
    .asRuntimeException(trailers));
```

The client reads them from `StatusRuntimeException.getTrailers()`. Keys must be lower-case ASCII;
a key ending in `-bin` uses `Metadata.BINARY_BYTE_MARSHALLER` and carries raw bytes — that is how
`google.rpc.Status` details are conventionally attached.

## 5. Errors in streaming

### Server streaming

Once you have sent `onNext` messages, an error mid-stream is still a single terminal `onError`. The
client keeps whatever it already received.

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

### Client and bidirectional streaming

`StreamObserver.onError(Throwable)` on the **request** observer is an inbound notification — the
client failed or the call was cancelled. It is not a place to send an error; the call is already
over. Log it and release resources.

```java
return new StreamObserver<CreateUserRequest>() {
    private final List<UserRequest> requests = new ArrayList<>();

    @Override
    public void onNext(CreateUserRequest value) {
        requests.add(new UserRequest(value.getName(), value.getEmail()));
    }

    @Override
    public void onError(Throwable t) {
        logger.error("Client streaming failed", t);   // inbound: call already terminated
    }

    @Override
    public void onCompleted() {
        try {
            var created = userStreamingService.createUsers(requests);
            responseObserver.onNext(CreateUsersResponse.newBuilder()
                .setCreatedCount(created.size()).build());
            responseObserver.onCompleted();
        } catch (Exception e) {
            responseObserver.onError(Status.INTERNAL
                .withDescription("Failed to create users").withCause(e).asRuntimeException());
        }
    }
};
```

Validating a single message inside `onNext` and calling `responseObserver.onError(...)` ends the
whole call. If later messages should still be processed, collect the failure and report it in the
response instead.

## 6. Mapping domain exceptions

Keep the mapping in one place so every handler agrees:

```java
public final class GrpcStatusMapper {

    private GrpcStatusMapper() {}

    public static StatusRuntimeException toStatus(Exception e) {
        return switch (e) {
            case StatusRuntimeException sre -> sre;
            case UserNotFoundException ex -> Status.NOT_FOUND.withDescription(ex.getMessage()).asRuntimeException();
            case UserAlreadyExistsException ex -> Status.ALREADY_EXISTS.withDescription(ex.getMessage()).asRuntimeException();
            case IllegalArgumentException ex -> Status.INVALID_ARGUMENT.withDescription(ex.getMessage()).asRuntimeException();
            case SecurityException ex -> Status.PERMISSION_DENIED.withDescription(ex.getMessage()).asRuntimeException();
            default -> Status.INTERNAL.withDescription("Internal server error").withCause(e).asRuntimeException();
        };
    }
}
```

```java
@Override
public void deleteUser(DeleteUserRequest request, StreamObserver<Empty> responseObserver) {
    try {
        userService.deleteUser(request.getUserId());
        responseObserver.onNext(Empty.getDefaultInstance());
        responseObserver.onCompleted();
    } catch (Exception e) {
        responseObserver.onError(GrpcStatusMapper.toStatus(e));
    }
}
```

To apply the mapping without a `try/catch` in every method, wrap the call listener in an interceptor
— see [grpc-interceptors-reference.md](grpc-interceptors-reference.md) §8. Wrapping only
`startCall` does not catch handler exceptions.

## 7. Common pitfalls

| Symptom | Cause | Fix |
|---|---|---|
| `UNIMPLEMENTED` from an implemented method | handler not collected (missing `@Component`, wrong base class, or a `@Tag`) | [grpc-server-reference.md](grpc-server-reference.md) §4 |
| `UNKNOWN` with no description | an exception escaped the handler unmapped | map every path to a `Status` |
| Client hangs to its deadline | some path returns without a terminal signal | exactly one `onCompleted`/`onError` per call |
| `IllegalStateException: call already closed` | a second terminal signal, or `onNext` after one | send one terminal signal |
| Cause not visible to the client | `withCause` is server-side only | put client-facing detail in the description or trailers |
| Stack trace leaked to callers | it was put into `withDescription` | log it; send a short description |
| A downstream `NOT_FOUND` surfaces as yours | a `StatusRuntimeException` re-thrown verbatim | translate downstream statuses |
| Errors invisible in metrics/logs | telemetry off | `telemetry.metrics.enabled` / `telemetry.logging.enabled` default to `false` |
| `onError` on the request observer never fires a response | inbound notification, call already over | reply from `onCompleted` |
