# gRPC Service Implementation Reference

**Source:** `.kora-agent/kora-docs/mkdocs/docs/en/documentation/grpc-server.md`, `.kora-agent/kora-docs/mkdocs/docs/en/guides/grpc-server.md`
**Examples:** `kora-examples/examples/java/kora-java-grpc-server`, `kora-examples/guides/java/kora-java-guide-grpc-server-advanced-app`

## Contents

1. Handler Pattern
2. Unary RPC
3. Server Streaming
4. Client Streaming
5. Bidirectional Streaming
6. Protobuf Message Conversion
7. Complete Service Example
8. Common Pitfalls

## 1. Handler Pattern

gRPC service handlers must extend `*GrpcImplBase` and be annotated with `@Component`:

=== ":fontawesome-brands-java: `Java`"
```java
@Component
public class UserService extends UserServiceGrpc.UserServiceImplBase {
    // Implement RPC methods
}
```

=== ":simple-kotlin: `Kotlin`"
```kotlin
@Component
class UserService : UserServiceGrpc.UserServiceImplBase() {
    // Implement RPC methods
}
```

**Important:** Handler must be `@Component` for auto-discovery by `GrpcServerModule`.

## 2. Unary RPC (One Request, One Response)

```java
@Override
public void getUser(GetUserRequest request, 
                   StreamObserver<GetUserResponse> responseObserver) {
    try {
        var user = userService.findById(request.getId());
        
        var response = GetUserResponse.newBuilder()
            .setId(user.getId())
            .setName(user.getName())
            .build();
        
        responseObserver.onNext(response);
        responseObserver.onCompleted();
    } catch (UserNotFoundException e) {
        responseObserver.onError(
            Status.NOT_FOUND
                .withDescription(e.getMessage())
                .asRuntimeException()
        );
    }
}
```

## 3. Server Streaming (One Request, Many Responses)

```java
@Override
public void listUsers(ListUsersRequest request, 
                     StreamObserver<User> responseObserver) {
    try {
        var users = userService.findAll(request.getPage(), request.getSize());
        
        for (var user : users) {
            responseObserver.onNext(toGrpcUser(user));
        }
        
        responseObserver.onCompleted();
    } catch (Exception e) {
        responseObserver.onError(
            Status.INTERNAL
                .withDescription("Failed to list users")
                .withCause(e)
                .asRuntimeException()
        );
    }
}
```

## 4. Client Streaming (Many Requests, One Response)

```java
@Override
public StreamObserver<CreateUserRequest> createUsers(
    StreamObserver<CreateUsersResponse> responseObserver) {
    
    return new StreamObserver<CreateUserRequest>() {
        private final List<UserRequest> batch = new ArrayList<>();

        @Override
        public void onNext(CreateUserRequest request) {
            batch.add(new UserRequest(request.getName(), request.getEmail()));
        }

        @Override
        public void onError(Throwable t) {
            logger.error("Client streaming failed", t);
            responseObserver.onError(t);
        }

        @Override
        public void onCompleted() {
            try {
                var createdIds = userService.createAll(batch);
                
                var response = CreateUsersResponse.newBuilder()
                    .addAllUserIds(createdIds)
                    .setCreatedCount(createdIds.size())
                    .build();
                
                responseObserver.onNext(response);
                responseObserver.onCompleted();
            } catch (Exception e) {
                responseObserver.onError(
                    Status.INTERNAL
                        .withDescription("Failed to create users")
                        .withCause(e)
                        .asRuntimeException()
                );
            }
        }
    };
}
```

## 5. Bidirectional Streaming (Many Requests, Many Responses)

```java
@Override
public StreamObserver<UpdateUserRequest> updateUsers(
    StreamObserver<User> responseObserver) {
    
    return new StreamObserver<UpdateUserRequest>() {
        @Override
        public void onNext(UpdateUserRequest request) {
            try {
                var updated = userService.update(
                    request.getUserId(),
                    new UserRequest(request.getName(), request.getEmail())
                );
                responseObserver.onNext(toGrpcUser(updated));
            } catch (UserNotFoundException e) {
                responseObserver.onError(
                    Status.NOT_FOUND
                        .withDescription(e.getMessage())
                        .asRuntimeException()
                );
            }
        }

        @Override
        public void onError(Throwable t) {
            logger.error("Bidi streaming failed", t);
            responseObserver.onError(t);
        }

        @Override
        public void onCompleted() {
            responseObserver.onCompleted();
        }
    };
}
```

## 6. Protobuf Message Conversion

### Timestamp Conversion

```java
import com.google.protobuf.Timestamp;
import java.time.ZoneOffset;

// Domain -> gRPC
private UserResponse toGrpcUser(ru.tinkoff.kora.dto.UserResponse user) {
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

// gRPC -> Domain
private UserRequest toDomainRequest(CreateUserRequest request) {
    return new UserRequest(request.getName(), request.getEmail());
}
```

### ByteString for Binary Data

```java
import com.google.protobuf.ByteString;

responseBuilder.setData(ByteString.copyFromUtf8(stringValue));
responseBuilder.setData(ByteString.copyFrom(byteArray));
```

## 7. Complete Service Example

```java
package ru.tinkoff.kora.example.grpc.server;

import com.google.protobuf.Empty;
import com.google.protobuf.Timestamp;
import io.grpc.Status;
import io.grpc.stub.StreamObserver;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import ru.tinkoff.kora.common.Component;

import java.time.ZoneOffset;
import java.util.List;

@Component
public final class UserServiceGrpcHandler extends UserServiceGrpc.UserServiceImplBase {

    private final Logger logger = LoggerFactory.getLogger(getClass());
    private final UserService userService;

    public UserServiceGrpcHandler(UserService userService) {
        this.userService = userService;
    }

    @Override
    public void createUser(CreateUserRequest request, 
                          StreamObserver<UserResponse> responseObserver) {
        try {
            var user = userService.createUser(toDomainRequest(request));
            responseObserver.onNext(toGrpcUser(user));
            responseObserver.onCompleted();
        } catch (Exception e) {
            responseObserver.onError(
                Status.INTERNAL
                    .withDescription("Failed to create user")
                    .withCause(e)
                    .asRuntimeException()
            );
        }
    }

    @Override
    public void getUser(GetUserRequest request, 
                       StreamObserver<UserResponse> responseObserver) {
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
    public void deleteUser(DeleteUserRequest request, 
                          StreamObserver<Empty> responseObserver) {
        try {
            userService.deleteUser(request.getUserId());
            responseObserver.onNext(Empty.getDefaultInstance());
            responseObserver.onCompleted();
        } catch (UserNotFoundException e) {
            responseObserver.onError(
                Status.NOT_FOUND
                    .withDescription(e.getMessage())
                    .asRuntimeException()
            );
        }
    }

    private UserResponse toGrpcUser(ru.tinkoff.kora.dto.UserResponse user) {
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

    private ru.tinkoff.kora.dto.UserRequest toDomainRequest(CreateUserRequest request) {
        return new ru.tinkoff.kora.dto.UserRequest(request.getName(), request.getEmail());
    }
}
```

## 8. Common Pitfalls

| Problem | Solution |
|---------|----------|
| **Handler not discovered** | Ensure `@Component` annotation and handler extends `*GrpcImplBase` |
| **Protobuf classes not generated** | Run `./gradlew generateProto`, check protobuf plugin config |
| **Streaming errors** | Always call `onCompleted()` after `onNext()`, handle `onError()` |
| **Missing method descriptor** | Ensure `.proto` file is in `src/main/proto` |
| **Timestamp conversion errors** | Use `ZoneOffset.UTC` for consistent timezone handling |
