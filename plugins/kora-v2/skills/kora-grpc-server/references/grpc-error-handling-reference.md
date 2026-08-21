# gRPC Error Handling Reference

**Source:** `.kora-agent/kora-docs/mkdocs/docs/en/documentation/grpc-server.md`
**Examples:** `kora-examples/guides/java/kora-java-guide-grpc-server-advanced-app/.../grpc/UserServiceGrpcHandler.java`

## Contents

1. Status Codes
2. Throwing Errors in Handlers
3. Complete Error Handling Example
4. Centralized Exception Interceptor
5. Error Metadata
6. Error Handling in Streaming
7. Mapping Domain Exceptions to Status Codes
8. Common Pitfalls

## 1. Status Codes

gRPC uses standard status codes for error handling:

| Code | Name | HTTP Equivalent | Description |
|------|------|-----------------|-------------|
| 0 | `OK` | 200 | Success |
| 1 | `CANCELLED` | 499 | Client cancelled request |
| 2 | `UNKNOWN` | 500 | Unknown error |
| 3 | `INVALID_ARGUMENT` | 400 | Invalid input |
| 4 | `DEADLINE_EXCEEDED` | 504 | Timeout |
| 5 | `NOT_FOUND` | 404 | Resource not found |
| 6 | `ALREADY_EXISTS` | 409 | Resource exists |
| 7 | `PERMISSION_DENIED` | 403 | AuthZ failure |
| 8 | `RESOURCE_EXHAUSTED` | 429 | Rate limited |
| 9 | `FAILED_PRECONDITION` | 400 | Precondition failed |
| 10 | `ABORTED` | 409 | Transaction aborted |
| 11 | `OUT_OF_RANGE` | 400 | Range error |
| 12 | `UNIMPLEMENTED` | 501 | Not implemented |
| 13 | `INTERNAL` | 500 | Internal error |
| 14 | `UNAVAILABLE` | 503 | Service unavailable |
| 15 | `DATA_LOSS` | 500 | Data loss |
| 16 | `UNAUTHENTICATED` | 401 | AuthN failure |

## 2. Throwing Errors in Handlers

### StatusException Pattern

```java
import io.grpc.Status;
import io.grpc.StatusRuntimeException;

@Override
public void getUser(GetUserRequest request, 
                   StreamObserver<UserResponse> responseObserver) {
    try {
        var user = userService.findById(request.getId());
        
        if (user == null) {
            throw Status.NOT_FOUND
                .withDescription("User not found: " + request.getId())
                .asRuntimeException();
        }
        
        responseObserver.onNext(toGrpcUser(user));
        responseObserver.onCompleted();
        
    } catch (StatusRuntimeException e) {
        // Already a gRPC status - pass through
        responseObserver.onError(e);
    } catch (Exception e) {
        // Unexpected error
        responseObserver.onError(
            Status.INTERNAL
                .withDescription("Failed to get user")
                .withCause(e)
                .asRuntimeException()
        );
    }
}
```

### Direct onError Call

```java
@Override
public void createUser(CreateUserRequest request, 
                      StreamObserver<UserResponse> responseObserver) {
    try {
        var user = userService.create(request.getName());
        responseObserver.onNext(toGrpcUser(user));
        responseObserver.onCompleted();
    } catch (UserAlreadyExistsException e) {
        responseObserver.onError(
            Status.ALREADY_EXISTS
                .withDescription(e.getMessage())
                .asRuntimeException()
        );
    } catch (InvalidUserException e) {
        responseObserver.onError(
            Status.INVALID_ARGUMENT
                .withDescription(e.getMessage())
                .asRuntimeException()
        );
    } catch (Exception e) {
        responseObserver.onError(
            Status.INTERNAL
                .withDescription("Internal server error")
                .withCause(e)
                .asRuntimeException()
        );
    }
}
```

## 3. Complete Error Handling Example

```java
package ru.tinkoff.kora.guide.grpcserver.advanced.grpc;

import com.google.protobuf.Empty;
import io.grpc.Status;
import io.grpc.StatusRuntimeException;
import io.grpc.stub.StreamObserver;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import ru.tinkoff.kora.common.Component;
import ru.tinkoff.kora.guide.grpcserver.advanced.*;
import ru.tinkoff.kora.guide.grpcserver.advanced.service.UserNotFoundException;
import ru.tinkoff.kora.guide.grpcserver.advanced.service.UserService;

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
            var user = userService.createUser(request.getName(), request.getEmail());
            responseObserver.onNext(toGrpcUser(user));
            responseObserver.onCompleted();
        } catch (UserAlreadyExistsException e) {
            logger.warn("User already exists: {}", request.getEmail());
            responseObserver.onError(
                Status.ALREADY_EXISTS
                    .withDescription(e.getMessage())
                    .asRuntimeException()
            );
        } catch (IllegalArgumentException e) {
            logger.warn("Invalid argument: {}", e.getMessage());
            responseObserver.onError(
                Status.INVALID_ARGUMENT
                    .withDescription(e.getMessage())
                    .asRuntimeException()
            );
        } catch (Exception e) {
            logger.error("Failed to create user", e);
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
        } catch (StatusRuntimeException e) {
            responseObserver.onError(e);
        } catch (Exception e) {
            logger.error("Failed to get user", e);
            responseObserver.onError(
                Status.INTERNAL
                    .withDescription("Failed to get user")
                    .withCause(e)
                    .asRuntimeException()
            );
        }
    }

    @Override
    public void updateUser(UpdateUserRequestUnary request, 
                          StreamObserver<UserResponse> responseObserver) {
        try {
            var user = userService.updateUser(
                request.getUserId(), 
                request.getName(), 
                request.getEmail()
            );
            responseObserver.onNext(toGrpcUser(user));
            responseObserver.onCompleted();
        } catch (UserNotFoundException e) {
            responseObserver.onError(
                Status.NOT_FOUND
                    .withDescription(e.getMessage())
                    .asRuntimeException()
            );
        } catch (Exception e) {
            logger.error("Failed to update user", e);
            responseObserver.onError(
                Status.INTERNAL
                    .withDescription("Failed to update user")
                    .withCause(e)
                    .asRuntimeException()
            );
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
        } catch (Exception e) {
            logger.error("Failed to delete user", e);
            responseObserver.onError(
                Status.INTERNAL
                    .withDescription("Failed to delete user")
                    .withCause(e)
                    .asRuntimeException()
            );
        }
    }

    private UserResponse toGrpcUser(ru.tinkoff.kora.guide.grpcserver.advanced.dto.UserResponse user) {
        return UserResponse.newBuilder()
            .setId(user.id())
            .setName(user.name())
            .setEmail(user.email())
            .build();
    }
}
```

## 4. Centralized Exception Interceptor

For cross-cutting error handling:

```java
package ru.tinkoff.kora.example.grpc.server;

import io.grpc.*;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import ru.tinkoff.kora.common.Component;

@Component
public final class GrpcExceptionHandlerServerInterceptor implements ServerInterceptor {
    
    private final Logger logger = LoggerFactory.getLogger(getClass());

    @Override
    public <ReqT, RespT> ServerCall.Listener<ReqT> interceptCall(
        ServerCall<ReqT, RespT> call,
        Metadata metadata,
        ServerCallHandler<ReqT, RespT> next) {
        
        try {
            return next.startCall(call, metadata);
        } catch (StatusRuntimeException e) {
            // Already a gRPC status exception
            logger.error("gRPC call failed: {} - {}", 
                call.getMethodDescriptor().getFullMethodName(),
                e.getStatus().getCode(), e);
            
            call.close(e.getStatus(), new Metadata());
            return new ServerCall.Listener<ReqT>() {};
            
        } catch (IllegalArgumentException e) {
            // Client error
            var status = Status.INVALID_ARGUMENT.withDescription(e.getMessage());
            logger.warn("Invalid argument: {}", e.getMessage());
            
            call.close(status, new Metadata());
            return new ServerCall.Listener<ReqT>() {};
            
        } catch (SecurityException e) {
            // AuthZ error
            var status = Status.PERMISSION_DENIED.withDescription(e.getMessage());
            logger.warn("Permission denied: {}", e.getMessage());
            
            call.close(status, new Metadata());
            return new ServerCall.Listener<ReqT>() {};
            
        } catch (Exception e) {
            // Unexpected server error
            var status = Status.INTERNAL
                .withDescription("Internal server error")
                .withCause(e);
            logger.error("Internal error", e);
            
            call.close(status, new Metadata());
            return new ServerCall.Listener<ReqT>() {};
        }
    }
}
```

## 5. Error Metadata

Add additional error details using Metadata:

```java
@Override
public void getUser(GetUserRequest request, 
                   StreamObserver<UserResponse> responseObserver) {
    try {
        var user = userService.findById(request.getId())
            .orElseThrow(() -> new UserNotFoundException(request.getId()));
        
        responseObserver.onNext(toGrpcUser(user));
        responseObserver.onCompleted();
        
    } catch (UserNotFoundException e) {
        var metadata = new Metadata();
        metadata.put(Metadata.Key.of("user-id", Metadata.ASCII_STRING_MARSHALLER), 
                    request.getId());
        metadata.put(Metadata.Key.of("error-code", Metadata.ASCII_STRING_MARSHALLER), 
                    "USER_NOT_FOUND");
        
        responseObserver.onError(
            Status.NOT_FOUND
                .withDescription(e.getMessage())
                .asRuntimeException(metadata)
        );
    }
}
```

## 6. Error Handling in Streaming

### Server Streaming

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
        // Send error and terminate stream
        responseObserver.onError(
            Status.INTERNAL
                .withDescription("Failed to list users")
                .withCause(e)
                .asRuntimeException()
        );
    }
}
```

### Client Streaming

```java
@Override
public StreamObserver<CreateUserRequest> createUsers(
    StreamObserver<CreateUsersResponse> responseObserver) {
    
    return new StreamObserver<CreateUserRequest>() {
        private final List<UserRequest> batch = new ArrayList<>();

        @Override
        public void onNext(CreateUserRequest request) {
            try {
                // Validate each request
                if (request.getName().isEmpty()) {
                    throw Status.INVALID_ARGUMENT
                        .withDescription("Name is required")
                        .asRuntimeException();
                }
                batch.add(toDomainRequest(request));
            } catch (StatusRuntimeException e) {
                responseObserver.onError(e);
            }
        }

        @Override
        public void onError(Throwable t) {
            logger.error("Client streaming failed", t);
            // Error already sent to client
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

## 7. Mapping Domain Exceptions to Status Codes

```java
public class GrpcExceptionMapper {
    
    public static StatusRuntimeException mapToGrpcException(Exception e) {
        if (e instanceof UserNotFoundException ex) {
            return Status.NOT_FOUND.withDescription(ex.getMessage()).asRuntimeException();
        }
        if (e instanceof UserAlreadyExistsException ex) {
            return Status.ALREADY_EXISTS.withDescription(ex.getMessage()).asRuntimeException();
        }
        if (e instanceof IllegalArgumentException ex) {
            return Status.INVALID_ARGUMENT.withDescription(ex.getMessage()).asRuntimeException();
        }
        if (e instanceof SecurityException ex) {
            return Status.PERMISSION_DENIED.withDescription(ex.getMessage()).asRuntimeException();
        }
        // Default to internal error
        return Status.INTERNAL
            .withDescription("Internal server error")
            .withCause(e)
            .asRuntimeException();
    }
}

// Usage in handler:
@Override
public void deleteUser(DeleteUserRequest request, 
                      StreamObserver<Empty> responseObserver) {
    try {
        userService.deleteUser(request.getUserId());
        responseObserver.onNext(Empty.getDefaultInstance());
        responseObserver.onCompleted();
    } catch (Exception e) {
        responseObserver.onError(GrpcExceptionMapper.mapToGrpcException(e));
    }
}
```

## 8. Common Pitfalls

| Problem | Solution |
|---------|----------|
| **Calling onNext after onError** | Always ensure only one terminal call (onError/onCompleted) |
| **Swallowing exceptions** | Log errors before converting to StatusException |
| **Generic INTERNAL for all errors** | Use specific status codes (NOT_FOUND, INVALID_ARGUMENT) |
| **Not handling streaming errors** | Implement onError() in StreamObserver |
