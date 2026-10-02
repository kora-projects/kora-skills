---
name: kora-grpc-server
description: "Kora 2.0 gRPC server — io.koraframework:grpc-server, GrpcServerModule, untagged @Component handlers extending the generated *Grpc.*ImplBase (io.grpc.BindableService), untagged io.grpc.ServerInterceptor components, the grpcServer config section (port, reflectionEnabled, maxMessageSize, telemetry), OkHttp transport on virtual threads, gRPC Server Reflection. Use when serving unary or streaming RPCs from a Kora service, pinning io.grpc/protobuf versions against grpc-java 1.84.0, or debugging AbstractMethodError buildClientTransportServers, an interceptor that never runs, or handlers that are not registered."
license: Apache-2.0
metadata:
  kora-version: "2.x"
---

# Kora gRPC Server

> **Kora sub-skill — obey the [kora-v2 meta rules](../../SKILL.md) on every task:** **R0** ground the workspace on Kora 2.0 refs before starting (framework source at tag `2.0.0.RC2` + `kora-examples` at `migration/2.0` + Kora 2.0 docs at koraframework.io/v2, which trail the source; 1.x `kora-docs` pages are never an authority) · **R1** read this sub-skill before writing code · **R2** Kora 2.0 APIs only — no Spring/Micronaut/Quarkus, no Kora 1.x APIs, no invented annotations or config keys · **R3** journal any incorrect Kora usage. Add comments/Javadoc only if asked.

| | |
|---|---|
| **Artifact** | `io.koraframework:grpc-server` (BOM `io.koraframework:kora-bom:2.0.0.RC2`, plain `mavenCentral()`) |
| **Module** | `io.koraframework.grpc.server.GrpcServerModule` — add it to the `@KoraApp` interface |
| **Config section** | `grpcServer` (telemetry component name `kora-grpc`) |
| **Transport** | **OkHttp** (`io.grpc.okhttp.OkHttpServerBuilder`), calls dispatched onto **virtual threads** |
| **Handler** | untagged `@Component` extending the generated `*Grpc.*ImplBase` (an `io.grpc.BindableService`) |
| **Interceptor** | untagged `@Component` implementing `io.grpc.ServerInterceptor` |
| **Pinned gRPC** | grpc-java **`1.84.0`**, protobuf-java **`3.25.9`** (transitive), protoc **`3.25.3`**, protobuf Gradle plugin **`0.10.0`** |

The `.proto` contract is the source of truth. The `com.google.protobuf` Gradle plugin generates the
message classes and a `*Grpc.*ImplBase` base type; you implement a Kora `@Component` that extends
it. `GrpcServerModule` collects every `BindableService` and `ServerInterceptor` in the graph at
**compile time** and starts one server — no classpath scanning, no reflection-based wiring.

## When to use vs NOT

Use this skill when:
- implementing gRPC handlers that extend a generated `*Grpc.*ImplBase`,
- wiring `GrpcServerModule` into a `@KoraApp` and pinning the `io.grpc:*` / protobuf versions,
- configuring `grpcServer` (port, message size, telemetry, keepalive, reflection),
- adding `io.grpc.ServerInterceptor` components for auth/logging,
- customising the server builder (TLS credentials, `Configurer`),
- enabling gRPC Server Reflection for `grpcurl`.

Do NOT use this skill for:
- consuming gRPC services (stub injection) — that is the `kora-grpc-client` skill,
- HTTP/JSON endpoints — use `kora-http-server`.

---

## Changed from Kora 1.x — check this first on ported code

| Kora 1.x | Kora 2.0 | Failure mode if left as-is |
|---|---|---|
| `ru.tinkoff.kora:kora-parent` | **`io.koraframework:kora-bom`** | artifact not found |
| `ru.tinkoff.kora:grpc-server` | **`io.koraframework:grpc-server`** | artifact not found |
| `ru.tinkoff.kora.grpc.server.GrpcServerModule` | **`io.koraframework.grpc.server.GrpcServerModule`** | compile error |
| `ru.tinkoff.kora.common.Component` | **`io.koraframework.common.annotation.Component`** | compile error |
| Netty transport, `netty { }` tuning | **OkHttp transport**; `netty-common` is only used by `redis-lettuce` in 2.0 | `netty { }` silently tunes nothing |
| `ContextServerInterceptor`, `CoroutineContextInjectInterceptor`, `MetricCollectorServerInterceptor`, `LoggingServerInterceptor` | **gone** — the module adds exactly one built-in, `io.koraframework.grpc.server.interceptor.TelemetryInterceptor` | naming them is wrong |
| override `serverBuilder` on `GrpcModule` to customise | **`GrpcServerFactoryModule`**: supply an untagged `Configurer<ForwardingServerBuilder<?>>`, `ServerCredentials`, or your own `ForwardingServerBuilder<?>` | `GrpcModule` does not exist |
| `telemetry.metrics.enabled` defaulted **true** | defaults **`false`** | metrics silently absent |
| Kora `Context` for per-call state | **`Context` no longer exists anywhere in Kora** (`io.grpc.Context` is gRPC's own, unrelated type) | compile error |
| Kotlin `suspend` / `Mono` / `Flux` handlers | **synchronous only**, on virtual threads | not a Kora contract |
| grpc-java `1.74.x` pins | **`1.84.0` everywhere** | `AbstractMethodError` at runtime |

---

## ⚑ Version alignment — the runtime failure class

`kora-bom` constrains **only `io.koraframework:*`**. It pins nothing under `io.grpc` or
`com.google.protobuf`, so every one of those coordinates is yours to keep consistent.

`io.koraframework:grpc-server:2.0.0.RC2` declares `io.grpc:grpc-okhttp:1.84.0` and
`io.grpc:grpc-stub:1.84.0`, and `grpc-okhttp:1.84.0` drags in `grpc-core`/`grpc-api`/`grpc-util` at
`1.84.0`.

**Rule 1 — pin every `io.grpc:*` you add to `1.84.0`**, in `implementation` and `testImplementation`
alike (`grpc-protobuf`, `grpc-services`, `grpc-netty`, `grpc-inprocess`, `grpc-testing`,
`protoc-gen-grpc-java`). An older pin resolves `grpc-core` to 1.84.0 while leaving your module
behind, and the server dies at **runtime** with an error that names nothing useful:

```
java.lang.AbstractMethodError: ... does not define or inherit an implementation of the
resolved method 'buildClientTransportServers(List, MetricRecorder)'
```

The migrated examples on `migration/2.0` still pin the previous `1.83.1`; raise every `io.grpc` pin
to `1.84.0` when copying from them.

**Rule 2 — generate with `com.google.protobuf:protoc:3.25.3`.** `io.grpc:grpc-protobuf:1.84.0`
brings `com.google.protobuf:protobuf-java:` **`3.25.9`**, not the 4.x line. protoc 4.x gencode
references `com.google.protobuf.Generated` and `com.google.protobuf.RuntimeVersion`, and **neither
class exists in protobuf-java 3.25.9**, so the build fails:

```
error: cannot find symbol
@com.google.protobuf.Generated
  symbol:   class Generated
  location: package com.google.protobuf
```

(If a 4.x `protobuf-java` is on the compile classpath but a 3.x one wins at runtime, the same
mismatch surfaces later as `NoClassDefFoundError: com/google/protobuf/RuntimeVersion`.)

All eight migrated gRPC projects — client and server, examples and guides — pin `protoc:3.25.3`.
To use protobuf 4.x instead, pin **both** `com.google.protobuf:protoc:4.36.2` and an explicit
`implementation "com.google.protobuf:protobuf-java:4.36.2"`; the catalog's `4.36.2` works inside
Kora's own build only because it pins `protobuf-java` alongside it.

Details and the full compatible matrix: [references/grpc-server-reference.md](references/grpc-server-reference.md).

---

## Quick Start

### 1. Dependencies

```groovy
dependencies {
    koraBom platform("io.koraframework:kora-bom:$koraVersion")   // 2.0.0.RC2
    annotationProcessor "io.koraframework:annotation-processors"

    implementation "io.koraframework:grpc-server"
    implementation "io.koraframework:config-hocon"
    implementation "io.koraframework:logging-logback"

    implementation "io.grpc:grpc-protobuf:1.84.0"
    compileOnly "javax.annotation:javax.annotation-api:1.3.2"    // generated stubs need @Generated

    // Optional: gRPC Server Reflection (grpcurl / Postman gRPC)
    implementation "io.grpc:grpc-services:1.84.0"

    testImplementation "io.koraframework:test-junit5"
}
```

Kotlin: replace the processor with `ksp("io.koraframework:symbol-processors:$koraVersion")`.
Never put a version on an `io.koraframework:*` artifact — the BOM controls those. Always put an
explicit `1.84.0` on every `io.grpc:*` artifact — the BOM controls none of those.

Full build files: [assets/build.gradle.server.template](assets/build.gradle.server.template),
[assets/build.gradle.server.kt.template](assets/build.gradle.server.kt.template).

### 2. Protobuf Gradle plugin

```groovy
plugins {
    id "com.google.protobuf" version "0.10.0"
}

protobuf {
    protoc { artifact = "com.google.protobuf:protoc:3.25.3" }
    plugins {
        grpc { artifact = "io.grpc:protoc-gen-grpc-java:1.84.0" }
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

The generated sources are **Java** in both languages — a Kotlin service extends the same
`*Grpc.*ImplBase`, so the `java` source set is where the generated directories go.

### 3. `.proto` contract (`src/main/proto/user_service.proto`)

```protobuf
syntax = "proto3";

package io.koraframework.example.grpc;
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
import io.koraframework.application.graph.KoraApplication;
import io.koraframework.common.annotation.KoraApp;
import io.koraframework.config.hocon.HoconConfigModule;
import io.koraframework.grpc.server.GrpcServerModule;
import io.koraframework.logging.logback.LogbackModule;

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

### 5. Handler — untagged `@Component` extending the generated `*ImplBase`

```java
import io.grpc.Status;
import io.grpc.stub.StreamObserver;
import io.koraframework.common.annotation.Component;

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

The handler is a plain Kora component: constructor injection, business logic delegated to a service.
The method body is **synchronous** — it already runs on a virtual thread, so blocking is correct.

### 6. Configuration (`application.conf`)

```hocon
grpcServer {
  port = ${GRPC_PORT}
  telemetry.logging.enabled = true    # default false
  telemetry.metrics.enabled = true    # default false
}
```

### 7. Run and probe

```bash
./gradlew clean classes   # generateProto + build the compile-time graph
./gradlew run
grpcurl -plaintext -d '{"user_id":"42"}' \
  localhost:8090 io.koraframework.example.grpc.UserService/GetUser
```

A method's full name is `<proto package>.<service>/<Method>`. Default port is **8090**.

---

## References

| File | Purpose |
|------|---------|
| [references/grpc-server-reference.md](references/grpc-server-reference.md) | Module wiring, version matrix, transport, builder/TLS customisation, lifecycle, native image, troubleshooting |
| [references/grpc-service-reference.md](references/grpc-service-reference.md) | Handler patterns: unary + all three streaming kinds, execution model, message conversion, Java/Kotlin |
| [references/grpc-config-reference.md](references/grpc-config-reference.md) | Every `grpcServer` key with its real default; the metric, span and log records actually emitted |
| [references/grpc-interceptors-reference.md](references/grpc-interceptors-reference.md) | Exact collection mechanism, ordering, auth/logging/exception interceptors |
| [references/grpc-error-handling-reference.md](references/grpc-error-handling-reference.md) | `io.grpc.Status` codes, error metadata, streaming errors |
| [references/grpc-reflection-reference.md](references/grpc-reflection-reference.md) | Reflection setup and `grpcurl` usage |

Templates: see [`assets/`](assets/). Regression cases: see [`evals/evals.json`](evals/evals.json).

---

## Core patterns

### Discovery — what "untagged" means

`GrpcServerFactoryModule` collects services and interceptors with
`@Tag(Tag.Factory.class) All<ValueOf<BindableService>>` and
`@Tag(Tag.Factory.class) All<ValueOf<ServerInterceptor>>`. `Tag.Factory` resolves to the tag of the
enclosing factory module, and `GrpcServerModule.grpcServer()` carries **no** `@Tag` — so the claim
is untagged, and an untagged claim matches **only untagged components**.

> Putting `@Tag(...)` on a handler or an interceptor removes it from the collection. It still
> compiles and the app still starts — the RPC just answers `UNIMPLEMENTED`, or the interceptor
> simply never runs. Cover both with a test.

### RPC method signatures

| RPC type | Handler signature |
|----------|-------------------|
| Unary | `void method(Req, StreamObserver<Resp>)` |
| Server streaming | `void method(Req, StreamObserver<Resp>)` — many `onNext`, one `onCompleted` |
| Client streaming | `StreamObserver<Req> method(StreamObserver<Resp>)` |
| Bidirectional streaming | `StreamObserver<Req> method(StreamObserver<Resp>)` |

All four are supported, in Java and Kotlin, with the same `io.grpc.stub.StreamObserver` shapes as
plain grpc-java. Full examples: [references/grpc-service-reference.md](references/grpc-service-reference.md).

### Execution model

Kora 2.0 contracts are synchronous. `OkHttpServerBuilder` is configured `.directExecutor()` with
`VirtualThreadExecutorTransportFilter` as both transport filter and call executor, so every call
body runs on a virtual thread named `grpc-<remote-address>`. Blocking JDBC, blocking HTTP clients
and `Thread.sleep` inside a handler are all fine.

- **No `suspend`, no `Mono`/`Flux`, no `CompletionStage`** — none of these is a Kora contract in 2.0.
- **The Kora `Context` type is gone from the whole framework.** `io.grpc.Context` is gRPC's own,
  unrelated type and still exists; do not treat one as a rename of the other.
- Per-call MDC and the OpenTelemetry context are carried in `ScopedValue`s bound around the call
  (`MDC.VALUE`, `OpentelemetryContext.VALUE`). Handing work to your own thread pool leaves both
  behind.
- **Kotlin uses the Java generated stubs.** Kora ships no server-side `protoc-gen-grpc-kotlin`
  wiring, and every migrated Kotlin example and guide extends `*Grpc.*ImplBase`.

### Errors via `io.grpc.Status`

```java
throw Status.NOT_FOUND.withDescription("User not found: " + id).asRuntimeException();
```

Common codes: `NOT_FOUND`, `INVALID_ARGUMENT`, `ALREADY_EXISTS`, `PERMISSION_DENIED`,
`UNAUTHENTICATED`, `INTERNAL`, `UNAVAILABLE`. Inside a handler either throw
`...asRuntimeException()` or call `responseObserver.onError(...)`. Send exactly one terminal signal
per call — never `onNext` after `onError`/`onCompleted`.
Details: [references/grpc-error-handling-reference.md](references/grpc-error-handling-reference.md).

### Interceptors

```java
import io.grpc.*;
import io.koraframework.common.annotation.Component;

@Component
public final class LoggingInterceptor implements ServerInterceptor {

    private static final Logger logger = LoggerFactory.getLogger(LoggingInterceptor.class);

    @Override
    public <ReqT, RespT> ServerCall.Listener<ReqT> interceptCall(
            ServerCall<ReqT, RespT> call, Metadata headers, ServerCallHandler<ReqT, RespT> next) {
        logger.info("gRPC call: {}", call.getMethodDescriptor().getFullMethodName());
        return next.startCall(call, headers);
    }
}
```

Every interceptor is global — the module has no per-service registration. Scope one to a single
service by comparing `call.getMethodDescriptor().getServiceName()` against the generated
`XxxGrpc.SERVICE_NAME`. The only interceptor Kora adds itself is `TelemetryInterceptor`, and it is
added **last**, which under gRPC's reverse-order contract makes it the outermost one — your
interceptors run inside the telemetry span.
Details: [references/grpc-interceptors-reference.md](references/grpc-interceptors-reference.md).

### Reflection

Add `io.grpc:grpc-services:1.84.0` **and** set `reflectionEnabled = true` (default `false`).
The module probes for `io.grpc.protobuf.services.ProtoReflectionServiceV1` and, if the class is
missing, ignores the flag **without a warning**.

```hocon
grpcServer { reflectionEnabled = ${?GRPC_REFLECTION_ENABLED} }
```

```bash
grpcurl -plaintext localhost:8090 list
```

Keep it off in production unless the endpoint is internal-only.
See [references/grpc-reflection-reference.md](references/grpc-reflection-reference.md).

### Telemetry

One metric — `rpc.server.call.duration` (a Micrometer `Timer`, tags `rpc.system.name`, `rpc.service`, `rpc.method`, `rpc.response.status_code` = the status code name, `error.type`; RC1 called it `rpc.server.duration`). Spans are named `<service>/<method>`,
kind `SERVER`, with the W3C traceparent read from the call metadata. Request/response logs go to
`io.koraframework.grpc.server.GrpcServer.request` / `.response`: metadata at `DEBUG` with the
`telemetry.logging.maskHeaders` keys (default `authorization`, `cookie`, `set-cookie`) masked by the
`@Tag(GrpcServerTelemetry.class) MaskingStrategy` (default `***`), protobuf bodies at `TRACE`
**unmasked** unless you supply your own `DefaultGrpcServerBodyConverter`. Details:
[grpc-config-reference → Log masking](references/grpc-config-reference.md#log-masking); shared
model: [kora-aop-logging](../kora-aop-logging/references/logging-masking.md).

**Logging and metrics default to `false`; tracing defaults to `true`.** Any config that claims to
demonstrate metrics or request logging must enable them explicitly.
Keys and tag lists: [references/grpc-config-reference.md](references/grpc-config-reference.md).

---

## Common pitfalls

| Symptom | Cause / fix |
|---------|-------------|
| `AbstractMethodError ... buildClientTransportServers(List, MetricRecorder)` | An `io.grpc:*` artifact pinned below `1.84.0` (often `grpc-inprocess`/`grpc-netty` in tests). Pin every one to `1.84.0` |
| `cannot find symbol: class Generated` / `class RuntimeVersion` in generated sources | protoc 4.x gencode against the protobuf-java `3.25.9` that `grpc-protobuf:1.84.0` brings. Use `protoc:3.25.3`, or pin `protobuf-java:4.36.2` explicitly |
| Handler compiles, RPC answers `UNIMPLEMENTED` | Missing `@Component`, not extending `*Grpc.*ImplBase`, or a `@Tag(...)` on the component — the collection is untagged |
| Interceptor never runs | Same cause: a `@Tag(...)` on the `ServerInterceptor` component takes it out of `All<ValueOf<ServerInterceptor>>` |
| `Component` import won't resolve | It is `io.koraframework.common.annotation.Component` |
| No `rpc_server_call_duration` metric | `grpcServer.telemetry.metrics.enabled` defaults to **`false`** in 2.0 — set it, and add `micrometer-module` |
| No request logs | `grpcServer.telemetry.logging.enabled` defaults to **`false`** |
| `authorization` shows up in clear after adding a key to `maskHeaders` | The list **replaces** the default `authorization`, `cookie`, `set-cookie` — restate them |
| Personal data in `TRACE` logs | Bodies are logged via `DefaultGrpcServerBodyConverter` without masking — provide a subclass as a component, or keep `TRACE` off |
| `grpcurl list` → `UNIMPLEMENTED` | `io.grpc:grpc-services` missing (flag ignored silently) or `reflectionEnabled` not set |
| `netty { }` tuning changes nothing | 2.0 serves gRPC over OkHttp; that section belongs to `redis-lettuce` |
| `Kotlin suspend fun overrides nothing` | The generated stubs are Java; handler methods are plain synchronous overrides |
| Generated classes not found | `./gradlew clean classes`; check the `com.google.protobuf` plugin and the proto `srcDirs` |
| Phantom `ru.tinkoff.kora` errors after renaming | Stale `build/generated` — `./gradlew clean` then build with `--no-build-cache` |
