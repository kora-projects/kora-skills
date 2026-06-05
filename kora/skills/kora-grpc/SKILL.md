---
name: kora-grpc
description: Build gRPC clients and servers in Kora: grpc-client/grpc-server modules, protobuf-gradle-plugin (0.9.4+), @Component handlers, GrpcClientModule/GrpcServerModule, ClientInterceptor/ServerInterceptor, and gRPC Server Reflection. Use for high-performance RPC APIs, microservice communication, and streaming data. Triggers: gRPC, protobuf, @GrpcClient, @GrpcServer, ClientInterceptor, ServerInterceptor, gRPC reflection.
---

# Kora gRPC — gRPC Services in Kora Applications

Skill for creating gRPC clients and servers in Kora based on the [protobuf gradle plugin](https://github.com/google/protobuf-gradle-plugin).

Read this first when:
- adding gRPC service handlers with `@Component` extending generated `*GrpcImplBase`,
- configuring gRPC clients with `GrpcClientModule` and `@GrpcClient` interfaces,
- enabling gRPC Server Reflection for CLI tools (grpcurl, bloomrpc),
- implementing ClientInterceptor/ServerInterceptor for auth, logging, or metrics,
- setting up protobuf compilation with `protobuf-gradle-plugin` 0.9.4+.

## Quick Start

### 1. gRPC Server

**build.gradle:**
```groovy
plugins {
    id "com.google.protobuf" version "0.9.4"
}
dependencies {
    implementation "ru.tinkoff.kora:grpc-server"
    implementation "io.grpc:grpc-protobuf:1.62.2"
}
```

**Application.java:**
```java
@KoraApp
public interface Application extends GrpcServerModule, HoconConfigModule {
    static void main(String[] args) { KoraApplication.run(ApplicationGraph::graph); }
}
```

**application.conf:**
```hocon
grpcServer {
    port = 8090
    reflectionEnabled = false  # true to enable gRPC CLI tools
}
```

**Handler:**
```java
@Component
public class GreeterService extends GreeterGrpc.GreeterImplBase {
    @Override
    public void sayHello(HelloRequest req, StreamObserver<HelloResponse> responseObserver) {
        HelloResponse response = HelloResponse.newBuilder()
            .setMessage("Hello, " + req.getName())
            .build();
        responseObserver.onNext(response);
        responseObserver.onCompleted();
    }
}
```

### 2. gRPC Client

**build.gradle:**
```groovy
plugins {
    id "com.google.protobuf" version "0.9.4"
}
dependencies {
    implementation "ru.tinkoff.kora:grpc-client"
    implementation "io.grpc:grpc-protobuf:1.62.2"
}
```

**Application.java:**
```java
@KoraApp
public interface Application extends GrpcClientModule, HoconConfigModule {
    static void main(String[] args) { KoraApplication.run(ApplicationGraph::graph); }
}
```

**application.conf:**
```hocon
grpcClient {
    GreeterService {
        url = "grpc://localhost:8090"
        timeout = "10s"
    }
}
```

**Client Wrapper:**
```java
@Component
public class GreeterClient {
    private final GreeterGrpc.GreeterBlockingStub stub;
    
    public GreeterClient(@Tag(GreeterGrpc.class) GreeterGrpc.GreeterBlockingStub stub) {
        this.stub = stub;
    }
    
    public HelloResponse sayHello(String name) {
        HelloRequest request = HelloRequest.newBuilder().setName(name).build();
        return stub.sayHello(request);
    }
}
```

---

## Assets (Templates)

Ready-to-use templates in `assets/`:

**Java Client:** `build.gradle.client.template`, `Application.client.java.template`, `client-wrapper.client.java.template`, `client-interceptor.client.java.template`, `application.client.conf.template`

**Java Server:** `build.gradle.server.template`, `Application.server.java.template`, `service-impl.server.java.template`, `server-interceptor.server.java.template`, `application.server.conf.template`, `service.proto.template`

**Kotlin Client:** `build.gradle.client.kt.template`, `Application.client.kt.template`, `client-wrapper.client.kt.template`, `client-interceptor.client.kt.template`

**Kotlin Server:** `build.gradle.server.kt.template`, `Application.server.kt.template`, `service-impl.server.kt.template`, `server-interceptor.server.kt.template`

**Usage:** Copy the template into your project and replace the placeholders (`${package}`, `${service_name}`, etc.).

---

## 📝 Core Concepts

### Protobuf Plugin

```groovy
plugins {
    id "com.google.protobuf" version "0.9.4"
}

protobuf {
    protoc { artifact = "com.google.protobuf:protoc:3.25.3" }
    plugins {
        grpc { artifact = "io.grpc:protoc-gen-grpc-java:1.62.2" }
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

### Server Handler

```java
@Component
public class MyService extends MyServiceGrpc.MyServiceImplBase {
    @Override
    public void myMethod(MyRequest request, StreamObserver<MyResponse> responseObserver) {
        // Business logic
        MyResponse response = MyResponse.newBuilder().build();
        responseObserver.onNext(response);
        responseObserver.onCompleted();
    }
}
```

### Client Stub Injection

```java
@Component
public class MyClient {
    private final MyServiceGrpc.MyServiceBlockingStub stub;
    
    public MyClient(@Tag(MyServiceGrpc.class) MyServiceGrpc.MyServiceBlockingStub stub) {
        this.stub = stub;
    }
    
    public MyResponse call(MyRequest request) {
        return stub.myMethod(request);
    }
}
```

### Configuration

**Server (application.conf):**
```hocon
grpcServer {
    port = 8090
    maxMessageSize = "4MiB"
    reflectionEnabled = false
    shutdownWait = "30s"
    telemetry {
        logging { enabled = true }
        metrics { enabled = true }
        tracing { enabled = true }
    }
}
```

**Client (application.conf):**
```hocon
grpcClient {
    ServiceName {
        url = "grpc://localhost:8090"
        timeout = "10s"
        telemetry {
            logging { enabled = true }
            metrics { enabled = true }
            tracing { enabled = true }
        }
    }
}
```

---

## Advanced Patterns

### Server Interceptors

```java
@Component
public class GrpcLoggingInterceptor implements ServerInterceptor {
    @Override
    public <ReqT, RespT> ServerCall.Listener<ReqT> interceptCall(
        ServerCall<ReqT, RespT> call,
        Metadata headers,
        ServerCallHandler<ReqT, RespT> next
    ) {
        // Logging, auth validation, metrics
        return next.startCall(call, headers);
    }
}
```

### Client Interceptors

```java
@Tag(ServiceGrpc.class)
@Component
public class AuthClientInterceptor implements ClientInterceptor {
    @Override
    public <ReqT, RespT> ClientCall<ReqT, RespT> interceptCall(
        MethodDescriptor<ReqT, RespT> method,
        CallOptions callOptions,
        Channel next
    ) {
        // Add auth headers, logging
        return next.newCall(method, callOptions);
    }
}
```

### gRPC Server Reflection

For debugging via gRPC CLI tools:

**build.gradle:**
```groovy
implementation "io.grpc:grpc-services:1.62.2"
```

**application.conf:**
```hocon
grpcServer {
    reflectionEnabled = true
}
```

---

## Quick Reference

```java
// Modules: GrpcServerModule / GrpcClientModule
// Annotations: @Component (handlers), @Tag(ServiceGrpc.class) (client stubs/interceptors)
// Plugin: com.google.protobuf 0.9.4, protoc 3.25.3, protoc-gen-grpc-java 1.62.2
// Dependencies: grpc-server / grpc-client, grpc-protobuf:1.62.2, javax.annotation-api:1.3.2
// Config: grpcServer { port, reflectionEnabled, telemetry } / grpcClient.ServiceName { url, timeout, telemetry }
// Interceptors: ServerInterceptor (global @Component), ClientInterceptor (@Tag + @Component)
// Reflection: grpc-services:1.62.2 + reflectionEnabled = true
```

**Templates:** `assets/` — ready-to-use templates for servers, clients, interceptors, proto files, and configuration.

**References:**
- [references/grpc-client-reference.md](references/grpc-client-reference.md) — full client reference
- [references/grpc-server-reference.md](references/grpc-server-reference.md) — full server reference

---

## Evals (Test scenarios)

See `evals/evals.json` — tests covering: server setup, client setup, interceptors, reflection, configuration.

---

## Common Pitfalls

- **Missing `@Component` on handler** → gRPC handler not discovered without `@Component`.
- **Wrong stub type** → match stub type to usage: `BlockingStub` for sync, `FutureStub` for async.
- **Missing `@Tag` for client stub** → tag stubs when multiple gRPC clients used.
- **protobuf classes not generated** → run `./gradlew generateProto`; check protobuf plugin config.
- **Server reflection not working** → add `grpc-services` dependency + `reflectionEnabled = true`.
