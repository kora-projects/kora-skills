# gRPC Server Reference — Kora 2.0

**Framework source (authority):** [`grpc/grpc-server` @ `2.0.0.RC2`](https://github.com/kora-projects/kora/tree/2.0.0.RC2/grpc/grpc-server)
**Migrated examples:** [`kora-java-grpc-server`](https://github.com/kora-projects/kora-examples/tree/migration/2.0/examples/java/kora-java-grpc-server) · [`kora-kotlin-grpc-server`](https://github.com/kora-projects/kora-examples/tree/migration/2.0/examples/kotlin/kora-kotlin-grpc-server) · [`kora-java-guide-grpc-server-advanced-app`](https://github.com/kora-projects/kora-examples/tree/migration/2.0/guides/java/kora-java-guide-grpc-server-advanced-app)

## Contents

1. What the module contributes
2. Dependencies and the version matrix
3. Protobuf Gradle plugin
4. Service discovery
5. Interceptor collection
6. Transport and threading
7. Customising the server builder (TLS, `Configurer`, full replacement)
8. Lifecycle, readiness and graceful shutdown
9. Reflection
10. Native image
11. Troubleshooting

---

## 1. What the module contributes

`io.koraframework.grpc.server.GrpcServerModule` is an interface you add to the `@KoraApp`. It has
exactly two methods:

```java
public interface GrpcServerModule {

    @FactoryModule
    default GrpcServerFactoryModule grpcServer() {
        return new GrpcServerFactoryModule("kora-grpc", "grpcServer");
    }

    @DefaultComponent
    default GrpcServerTelemetryFactory defaultGrpcServerTelemetryFactory(@Nullable Tracer tracer,
                                                                         @Nullable MeterRegistry meterRegistry,
                                                                         @Nullable DefaultGrpcServerLoggerFactory loggerFactory,
                                                                         @Nullable DefaultGrpcServerMetricsFactory metricsFactory,
                                                                         @Nullable DefaultGrpcServerBodyConverter bodyConverter) { … }
}
```

The two constructor arguments are load-bearing:

| Argument | Value | Meaning |
|---|---|---|
| `name` | `"kora-grpc"` | the `server.name` tag on metrics and the `serverName` field in logs |
| `configPath` | `"grpcServer"` | the config section the server reads |

`GrpcServerFactoryModule` (a `@FactoryModule`) then provides, all under `@Tag(Tag.Factory.class)`:

| Provider | Kind | Notes |
|---|---|---|
| `GrpcServerConfig` | mapped from `config.get("grpcServer")` | via `ConfigValueMapper.mapOrThrow` |
| `ForwardingServerBuilder<?>` | `@DefaultComponent` | the OkHttp builder; replaceable |
| `GrpcServer` | `@Root` | `Lifecycle` + `ReadinessProbe`; starts without being a dependency |
| `WrappedRefreshListener<List<DynamicBindableService>>` | from `All<ValueOf<BindableService>>` | your handlers |
| `WrappedRefreshListener<List<DynamicServerInterceptor>>` | from `All<ValueOf<ServerInterceptor>>` | your interceptors |

Because `GrpcServer` is `@Root`, nothing has to depend on it for the server to start.

## 2. Dependencies and the version matrix

`io.koraframework:grpc-server:2.0.0.RC2` declares exactly these dependencies (its
`build.gradle` at that tag):

| Coordinate | Version |
|---|---|
| `org.jspecify:jspecify` | `1.0.1` |
| `io.koraframework:logging-common` | `2.0.0.RC2` |
| `io.koraframework:telemetry-common` | `2.0.0.RC2` |
| `io.grpc:grpc-okhttp` | `1.84.0` |
| `io.grpc:grpc-stub` | `1.84.0` |

`grpc-okhttp:1.84.0` in turn brings `grpc-api`, `grpc-util` and `grpc-core` at `1.84.0`.

**`kora-bom` constrains only `io.koraframework:*` artifacts.** It contains no third-party
constraints at all, so nothing under `io.grpc` or `com.google.protobuf` is managed for you.

### The matrix that works

| Coordinate | Version | Who provides it |
|---|---|---|
| `io.grpc:grpc-okhttp`, `grpc-stub`, `grpc-core`, `grpc-api`, `grpc-util` | `1.84.0` | transitive via `io.koraframework:grpc-server` |
| `io.grpc:grpc-protobuf` | `1.84.0` | **you**, `implementation` |
| `io.grpc:grpc-services` (reflection) | `1.84.0` | **you**, `implementation`, optional |
| `io.grpc:protoc-gen-grpc-java` | `1.84.0` | **you**, protobuf plugin |
| `io.grpc:grpc-netty` / `grpc-inprocess` / `grpc-testing` | `1.84.0` | **you**, `testImplementation`, when a test needs a client transport |
| `com.google.protobuf:protobuf-java` | `3.25.9` | transitive via `grpc-protobuf:1.84.0` |
| `com.google.protobuf:protoc` | `3.25.3` | **you**, protobuf plugin |
| `com.google.protobuf` Gradle plugin | `0.10.0` | **you**, `plugins { }` |
| `javax.annotation:javax.annotation-api` | `1.3.2` | **you**, `compileOnly` — the generated stubs reference `@javax.annotation.Generated` |

The framework's own [`gradle/libs.versions.toml`](https://github.com/kora-projects/kora/blob/2.0.0.RC2/gradle/libs.versions.toml)
lists `grpc-java = "1.84.0"`, `grpc-kotlin = "1.5.0"`, `protobuf-java`/`protobuf-protoc` `4.36.2`
and the protobuf plugin at `0.10.0`. `grpc-kotlin = 1.5.0` is consumed by
`grpc-client-symbol-processor` to inject `*CoroutineStub` client stubs — it plays no part in the
server.

### ⚑ A catalog entry is what the framework pins for itself, not what a consumer can copy

The `4.36.2` protobuf entries are the clearest example, and the distinction generalises to every
third-party version in that file.

Kora's `grpc/grpc-server/build.gradle` declares `compileOnly libs.protobuf.java` and
`testImplementation libs.protobuf.java` — an **explicit** `protobuf-java:4.36.2` that outranks the
`3.25.9` arriving transitively through `grpc-protobuf`. Inside Kora's build the two halves travel
together, so `protoc:4.36.2` is correct there.

A consumer who copies only the protoc line inherits `protobuf-java:3.25.9` and a build that does not
compile. The 4.x recipe is correct **only while both halves stay together**; the 3.25.3 recipe needs
no override at all, which is why the migrated corpus uses it eight times out of eight.

So: read the catalog for what version the framework *builds against*, then check what your own
dependency graph actually resolves before copying the number. `./gradlew dependencies` is the
authority for your project — `libs.versions.toml` is not.

### Failure 1 — a stale `io.grpc:*` pin

An `io.grpc` artifact left at an older version (`1.74.0` is the common Kora 1.x carry-over) still
resolves `grpc-core` up to `1.84.0` through Gradle's highest-wins rule, while the stale module keeps
its own older classes. The server then fails at **runtime**, not at compile time:

```
java.lang.AbstractMethodError: ... does not define or inherit an implementation of the
resolved method 'buildClientTransportServers(List, MetricRecorder)'
```

The message names neither the offending artifact nor the version, so audit the whole build:

```bash
./gradlew dependencies --configuration runtimeClasspath | grep 'io.grpc'
./gradlew dependencies --configuration testRuntimeClasspath | grep 'io.grpc'
```

Every line must read `1.84.0`.

### Failure 2 — protoc newer than the protobuf runtime

`grpc-protobuf:1.84.0` brings `protobuf-java:3.25.9`. protoc 4.x gencode annotates every generated
type with `@com.google.protobuf.Generated` and opens each one with

```java
com.google.protobuf.RuntimeVersion.validateProtobufGencodeVersion(
    com.google.protobuf.RuntimeVersion.RuntimeDomain.PUBLIC, …);
```

**Neither `Generated` nor `RuntimeVersion` exists in protobuf-java `3.25.9`**, so the usual symptom
is a compile failure in the generated sources:

```
error: cannot find symbol
@com.google.protobuf.Generated
  symbol:   class Generated
  location: package com.google.protobuf
```

Verified by generating the same `.proto` twice and compiling both against `protobuf-java:3.25.9`:
protoc `3.25.3` gencode compiles clean, protoc `4.36.2` gencode does not. If a 4.x `protobuf-java`
is on the compile classpath but a 3.x one wins at runtime, the mismatch instead surfaces on the
first `newBuilder()` as `NoClassDefFoundError: com/google/protobuf/RuntimeVersion`.

Two consistent choices:

```groovy
// A — what every migrated example uses
protobuf { protoc { artifact = "com.google.protobuf:protoc:3.25.3" } }
// protobuf-java 3.25.9 arrives transitively; nothing else to do

// B — protobuf 4.x, both halves pinned
implementation "com.google.protobuf:protobuf-java:4.36.2"
protobuf { protoc { artifact = "com.google.protobuf:protoc:4.36.2" } }
```

Never mix: protoc 4.x with the transitive 3.25.9 runtime is failure 2; protoc 3.x with an explicit
4.x runtime works but buys nothing.

## 3. Protobuf Gradle plugin

===! `Java` — `build.gradle`

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

test.dependsOn tasks.generateProto
```

=== `Kotlin` — `build.gradle.kts`

```kotlin
import com.google.protobuf.gradle.id

plugins {
    id("com.google.protobuf") version "0.10.0"
}

protobuf {
    protoc { artifact = "com.google.protobuf:protoc:3.25.3" }
    plugins {
        id("grpc") { artifact = "io.grpc:protoc-gen-grpc-java:1.84.0" }
    }
    generateProtoTasks {
        all().forEach { task -> task.plugins { id("grpc") } }
    }
}

sourceSets.main {
    java.srcDir("build/generated/source/proto/main/grpc")
    java.srcDir("build/generated/source/proto/main/java")
}
```

The generated stubs are **Java in both languages**, so the directories belong to the `java` source
set even in a Kotlin module. Wiring them into `kotlin.srcDir(...)` does not compile them.

## 4. Service discovery

```java
@Tag(Tag.Factory.class)
public WrappedRefreshListener<List<DynamicBindableService>> dynamicBindableServicesListener(
        @Tag(Tag.Factory.class) All<ValueOf<BindableService>> services) { … }
```

- The generated `*Grpc.*ImplBase` implements `io.grpc.BindableService`, so any component that
  extends it satisfies the claim.
- `Tag.Factory` means "the tag of the enclosing factory module". `GrpcServerModule.grpcServer()`
  has no `@Tag`, so the resolved tag is **null**, and Kora's `TagUtils.tagsMatch(null, provided)`
  returns `true` only when `provided` is also null. **A tagged handler is not collected.**
- Each service is wrapped in `DynamicBindableService`, which re-reads `ValueOf<BindableService>` on
  graph refresh — that is what lets a handler be swapped on config reload without rebinding routes.

```java
@Component
public final class UserServiceGrpcHandler extends UserServiceGrpc.UserServiceImplBase { … }
```

```kotlin
@Component
class UserServiceGrpcHandler(private val userService: UserService)
    : UserServiceGrpc.UserServiceImplBase()
```

Multiple handler components are fine — every one is added to the same server. There is no
per-service port and no per-service registration API.

### Kotlin coroutine stubs

`io.grpc.kotlin.AbstractCoroutineServerImpl` does implement `BindableService`, so a
`protoc-gen-grpc-kotlin` service would mechanically be collected. Kora ships **no** server-side
support for it: nothing in `grpc-server` references `io.grpc.kotlin`, and every migrated Kotlin
example and guide extends the Java `*Grpc.*ImplBase`. A coroutine impl would also run its bodies on
its own dispatcher, outside the virtual-thread executor and outside the `ScopedValue` bindings that
carry MDC and the OpenTelemetry context (§6). Use the Java stubs.

## 5. Interceptor collection

Identical mechanism, identical tagging rule:

```java
@Tag(Tag.Factory.class)
public WrappedRefreshListener<List<DynamicServerInterceptor>> dynamicInterceptorsListener(
        @Tag(Tag.Factory.class) All<ValueOf<ServerInterceptor>> interceptors) { … }
```

An untagged `@Component` implementing `io.grpc.ServerInterceptor` is registered globally.
Full patterns: [grpc-interceptors-reference.md](grpc-interceptors-reference.md).

## 6. Transport and threading

`GrpcServerFactoryModule.grpcServerBuilder` builds the server like this:

```java
var builder = OkHttpServerBuilder.forPort(config.port(), serverCredentials)
    .directExecutor()
    .addTransportFilter(VirtualThreadExecutorTransportFilter.INSTANCE)
    .callExecutor(VirtualThreadExecutorTransportFilter.INSTANCE)
    .maxInboundMessageSize((int) config.maxMessageSize().toBytes());
```

- The transport is **OkHttp**, not Netty. `netty-common` still exists in 2.0 but is a dependency of
  `redis-lettuce` only; the top-level `netty { }` config section does not reach the gRPC server.
- `VirtualThreadExecutorTransportFilter` gives every transport a single-threaded executor backed by
  virtual threads named `grpc-<remote-address>`, and supplies it as the per-call executor. Handler
  bodies therefore run on a virtual thread: **blocking is the correct style**.
- The same filter binds two `ScopedValue`s around each call — `io.koraframework.logging.common.MDC.VALUE`
  and `io.koraframework.common.telemetry.OpentelemetryContext.VALUE`. Work handed to a thread pool
  you created yourself leaves both behind.
- `maxConnectionAge`, `maxConnectionAgeGrace`, `keepAliveTime` and `keepAliveTimeout` are applied
  only when non-null; there is no "0 = unlimited" sentinel (§ [grpc-config-reference.md](grpc-config-reference.md)).

## 7. Customising the server builder

Three hooks, in increasing order of bluntness. All three are declared inside the factory module with
`@Tag(Tag.Factory.class)`, which for the default `GrpcServerModule` resolves to **no tag** — so you
supply them as ordinary untagged components.

### 7.1 TLS — an untagged `ServerCredentials`

Without one, the module falls back to `InsecureServerCredentials.create()`.

```java
@KoraApp
public interface Application extends GrpcServerModule, … {

    default ServerCredentials grpcServerCredentials() {
        try {
            return TlsServerCredentials.newBuilder()
                .keyManager(new File("/etc/tls/server.crt"), new File("/etc/tls/server.key"))
                .build();
        } catch (IOException e) {
            throw new UncheckedIOException("Failed to load gRPC server TLS material", e);
        }
    }
}
```

The `try/catch` is not optional: every file- and stream-based `keyManager` / `trustManager`
overload, and `TlsServerCredentials.create`, declares a checked `IOException`. A module method
cannot propagate it — the generated graph code calls it without a `throws` clause — so wrap it.

### 7.2 Fine-tuning — an untagged `Configurer<ForwardingServerBuilder<?>>`

`io.koraframework.common.Configurer<T>` is a `@FunctionalInterface` with `T configure(T t)`, applied
as the **last** step before `build()`, after services, interceptors and telemetry have been added.

```java
default Configurer<ForwardingServerBuilder<?>> grpcServerConfigurer() {
    return builder -> {
        builder.maxInboundMetadataSize(16 * 1024);
        return builder;
    };
}
```

Use the **statement** form and return the same reference. `ForwardingServerBuilder<T extends
ServerBuilder<T>>` declares its setters as returning `T`, so through the wildcard
`ForwardingServerBuilder<?>` they return a capture that javac will not widen back:

```java
// does NOT compile
return builder -> builder.maxInboundMetadataSize(16 * 1024);
// error: incompatible types: bad return type in lambda expression
//        CAP#1 cannot be converted to ForwardingServerBuilder<?>
```

### 7.3 Full replacement — your own `ForwardingServerBuilder<?>`

`grpcServerBuilder` is a `@DefaultComponent`, so an untagged component of the same type wins. This
opts you out of everything the module does — service registration, interceptor registration,
telemetry, the virtual-thread executor. Prefer 7.1/7.2.

## 8. Lifecycle, readiness and graceful shutdown

`GrpcServer implements Lifecycle, ReadinessProbe`.

| Phase | Behaviour |
|---|---|
| `init()` | builds and starts the server; logs `gRPC Server started on port <port> in …` (the bound port, also as a `port` structured marker) |
| bind failure | `IllegalStateException: gRPC server failed to start on port 'N': port is already in use; stop the other process or configure a different port` |
| readiness | `INIT` → `"GRPC Server init"`, `RUN` → ready, `SHUTDOWN` → `"GRPC Server shutdown"` |
| `release()` | `shutdown()`, then waits `shutdownWait` (default `30s`); on timeout logs a warning and calls `shutdownNow()` |

The readiness probe is surfaced through whatever readiness endpoint the app exposes — for an app
that also runs the HTTP system server, that is `GET /system/readiness`.

## 9. Reflection

```java
if (config.reflectionEnabled() && isClassPresent("io.grpc.protobuf.services.ProtoReflectionServiceV1")) {
    builder.addService(ProtoReflectionServiceV1.newInstance());
}
```

Both halves are required: the flag **and** `io.grpc:grpc-services:1.84.0` on the classpath. When the
class is missing the flag is ignored with no warning. Kora registers the **v1** reflection service
(`ProtoReflectionServiceV1`), not `v1alpha`.
See [grpc-reflection-reference.md](grpc-reflection-reference.md).

## 10. Native image

`grpc-server` ships its own reachability metadata at
`META-INF/native-image/io.koraframework/grpc-server/reflect-config.json`. The file name is
load-bearing: GraalVM reads `reflect-config.json` and silently ignores `reflection-config.json`.
The file shipped at `2.0.0.RC2` carries the correct name, so this module needs nothing from you —
but the trap is real, so check your **own** `META-INF/native-image/` directories for the misspelling:

```bash
find . -name "reflection-config.json"   # every hit is a dead file
```

A green `nativeCompile` proves nothing on its own. Validate by starting the image and issuing a real
RPC.

## 11. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `AbstractMethodError … buildClientTransportServers(List, MetricRecorder)` | mixed `io.grpc` versions | pin every `io.grpc:*` to `1.84.0`, main and test |
| `cannot find symbol: class Generated` / `class RuntimeVersion` | protoc 4.x gencode, protobuf-java 3.25.9 on the classpath | `protoc:3.25.3`, or pin `protobuf-java:4.36.2` too |
| RPC answers `UNIMPLEMENTED` | handler not collected | untagged `@Component`, extends `*Grpc.*ImplBase` |
| Interceptor never runs | tagged component | remove the `@Tag(...)` |
| `port is already in use` | port taken | change `grpcServer.port` |
| Server starts on 8090 unexpectedly | `grpcServer.port` unset | `port` defaults to `8090` |
| `cannot find symbol: class Generated` in generated stubs | missing `javax.annotation-api` | add `compileOnly "javax.annotation:javax.annotation-api:1.3.2"` |
| Generated classes not found | proto sources not on the source set | add both `build/generated/source/proto/main/{grpc,java}` to the **java** source set |
| Phantom `ru.tinkoff.kora` compile errors | stale `build/generated` from a 1.x build | `./gradlew clean` then build with `--no-build-cache` |
| `netty { }` tuning has no effect | 2.0 serves gRPC over OkHttp | remove it; use a `Configurer` (§7.2) |
