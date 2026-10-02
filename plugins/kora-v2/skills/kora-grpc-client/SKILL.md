---
name: kora-grpc-client
description: "Outbound gRPC clients in Kora 2.0 — io.koraframework:grpc-client and GrpcClientModule (io.koraframework.grpc.client). The kora-app processor/KSP extension makes protoc-generated *BlockingStub / *FutureStub / *Stub (and Kotlin *CoroutineStub) injectable by type, backed by a ManagedChannelLifecycle configured under grpcClient.<protoServiceName>. Covers url/timeout/keepAliveTime/keepAliveTimeout/loadBalancingPolicy/defaultServiceConfig, telemetry defaults (logging=false, metrics=false, tracing=true), io.grpc.ClientInterceptor collected with @Tag(<Service>Grpc.class), ChannelCredentials and Configurer<ManagedChannelBuilder> extension points, metadata auth, unary and streaming calls, and pinning grpc-java 1.84.0 / protoc 3.25.3 / protobuf plugin 0.10.0 against AbstractMethodError buildClientTransportServers. Use when wiring an outbound gRPC call, injecting a generated stub, adding an authorization metadata header, or debugging a missing-stub graph error."
license: Apache-2.0
metadata:
  kora-version: "2.x"
---

# Kora gRPC Client

> **Kora sub-skill — obey the [kora-v2 meta rules](../../SKILL.md) on every task:** **R0** ground the workspace on Kora 2.0 refs before starting (framework source at tag `2.0.0.RC2` + `kora-examples` at `migration/2.0` + Kora 2.0 docs at koraframework.io/v2, which trail the source; 1.x `kora-docs` pages are never an authority) · **R1** read this sub-skill before writing code · **R2** Kora 2.0 APIs only — no Spring/Micronaut/Quarkus, no Kora 1.x APIs, no invented annotations or config keys · **R3** journal any incorrect Kora usage. Add comments/Javadoc only if asked.

| | |
|---|---|
| **Artifact** | `io.koraframework:grpc-client` (BOM `io.koraframework:kora-bom`, `2.0.0.RC2`) |
| **Module** | `io.koraframework.grpc.client.GrpcClientModule` |
| **Config** | `io.koraframework.grpc.client.GrpcClientConfig`, section `grpcClient.<protoServiceName>` |
| **Transport** | OkHttp (`io.grpc:grpc-okhttp`) — `GrpcOkHttpClientChannelFactory` |
| **Processor** | `io.koraframework:annotation-processors` (Java) / `io.koraframework:symbol-processors` (Kotlin KSP) |
| **Third-party** | grpc-java `1.84.0`, protoc `3.25.3`, protobuf Gradle plugin `0.10.0` — **the BOM does not manage these** |

`grpc-client` has no annotation of its own. You declare a `.proto`, let the protobuf Gradle plugin
generate the ordinary gRPC Java stubs, and then **ask for a stub in a constructor**. A Kora
compile-time extension (`GrpcClientExtension`, shipped inside `annotation-processors` /
`symbol-processors`) recognises the stub type and generates the whole chain behind it:

```
YourComponent(UserServiceGrpc.UserServiceBlockingStub stub)
  └─ UserServiceGrpc.newBlockingStub(channel)          // stub, untagged
       └─ @Tag(UserServiceGrpc.class) Channel          // ManagedChannelLifecycle
            ├─ @Tag(UserServiceGrpc.class) GrpcClientConfig   -> grpcClient.UserService
            ├─ @Tag(UserServiceGrpc.class) ChannelCredentials (optional)
            ├─ @Tag(UserServiceGrpc.class) All<ClientInterceptor>
            ├─ @Tag(UserServiceGrpc.class) Configurer<ManagedChannelBuilder<?>> (optional)
            ├─ GrpcClientTelemetryFactory                     (untagged)
            └─ GrpcClientChannelFactory                       (untagged)
```

Everything you can customise per service hangs off **one tag: the generated `<Service>Grpc`
class**. Read that diagram before writing any interceptor or credentials component.

---

## Renamed / changed in 2.0 — check this before touching ported 1.x code

| Kora 1.x | Kora 2.0 |
|---|---|
| BOM `ru.tinkoff.kora:kora-parent` | **`io.koraframework:kora-bom`** (`2.0.0.RC2`) |
| `ru.tinkoff.kora:grpc-client` | **`io.koraframework:grpc-client`** |
| `ru.tinkoff.grpc.client.GrpcClientModule` | **`io.koraframework.grpc.client.GrpcClientModule`** |
| `ru.tinkoff.kora.common.{Component,Tag,KoraApp}` | **`io.koraframework.common.annotation.{Component,Tag,KoraApp}`** |
| `url = "grpc://host:port"` | **`url = "http://host:port"`** for plaintext — only `http` turns plaintext on |
| config key `maxInboundMessageSize` | **does not exist** — use a `Configurer<ManagedChannelBuilder<?>>` |
| `telemetry.metrics.enabled` defaulted on | **defaults to `false`** (so does `logging`; `tracing` stays `true`) |
| grpc-java 1.7x | **grpc-java `1.84.0`** (protoc stays `3.25.3`) |

Unchanged and verified in 2.0 source: stubs inject **by type with no `@Tag`**; a
`ClientInterceptor` is scoped with **`@Tag(<Service>Grpc.class)`**; the config section is
`grpcClient.<protoServiceName>`. Do not "fix" working 1.x code in those three places.

**There is no Kora `Context` in 2.0** — the class is gone from the whole framework. `io.grpc.Context`
is gRPC's own, unrelated propagation type and still exists; a `ClientInterceptor` may use it. Never
put a Kora `Context` parameter on anything.

---

## Quick start

### 1. Build file

Pin the Kora BOM, and pin gRPC/protobuf yourself — `kora-bom` constrains Kora modules only.

```groovy
plugins {
    id "application"
    id "com.google.protobuf" version "0.10.0"
}

java { toolchain { languageVersion = JavaLanguageVersion.of(25) } }

configurations {
    koraBom
    annotationProcessor.extendsFrom(koraBom)
    implementation.extendsFrom(koraBom)
    testImplementation.extendsFrom(koraBom)
    testAnnotationProcessor.extendsFrom(koraBom)
}

dependencies {
    koraBom platform("io.koraframework:kora-bom:$koraVersion")   // koraVersion=2.0.0.RC2
    annotationProcessor "io.koraframework:annotation-processors"

    implementation "io.koraframework:grpc-client"
    implementation "io.koraframework:config-hocon"
    implementation "io.koraframework:logging-logback"

    implementation "io.grpc:grpc-protobuf:1.84.0"   // brings protobuf-java 3.25.9 transitively
    compileOnly "javax.annotation:javax.annotation-api:1.3.2"   // javax.annotation.Generated in generated stubs
}

protobuf {
    protoc { artifact = "com.google.protobuf:protoc:3.25.3" }
    plugins { grpc { artifact = "io.grpc:protoc-gen-grpc-java:1.84.0" } }
    generateProtoTasks { all()*.plugins { grpc {} } }
}

sourceSets {
    main {
        java {
            srcDirs "build/generated/source/proto/main/grpc"
            srcDirs "build/generated/source/proto/main/java"
        }
    }
}
```

Full Java/Kotlin build files: [`assets/build.gradle.client.template`](assets/build.gradle.client.template),
[`assets/build.gradle.client.kt.template`](assets/build.gradle.client.kt.template).

### 2. `src/main/proto/user_service.proto`

```protobuf
syntax = "proto3";
package io.koraframework.example.grpc;
option java_multiple_files = true;

service UserService {
  rpc GetUser (GetUserRequest) returns (UserResponse) {}
}

message GetUserRequest { string user_id = 1; }
message UserResponse { string id = 1; string name = 2; string email = 3; }
```

The **proto** service name — `UserService`, not the Java class `UserServiceGrpc` — is what names the
config section.

### 3. Enable the module

```java
import io.koraframework.application.graph.KoraApplication;
import io.koraframework.common.annotation.KoraApp;
import io.koraframework.config.hocon.HoconConfigModule;
import io.koraframework.grpc.client.GrpcClientModule;
import io.koraframework.logging.logback.LogbackModule;

@KoraApp
public interface Application extends HoconConfigModule, LogbackModule, GrpcClientModule {
    static void main(String[] args) {
        KoraApplication.run(ApplicationGraph::graph);
    }
}
```

### 4. Inject the stub

Inject the generated stub **directly by type, with no `@Tag`**, and wrap it so protobuf builders and
gRPC statuses stay at the transport boundary.

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
        var response = stub.getUser(GetUserRequest.newBuilder().setUserId(userId).build());
        return new UserDto(response.getId(), response.getName(), response.getEmail());
    }
}
```

### 5. Configure

```hocon
grpcClient {
  UserService {                       # proto service simple name
    url = "http://localhost:8090"     # http:// => plaintext
    url = ${?GRPC_SERVER_URL}
    timeout = "10s"
    telemetry.logging.enabled = true  # off by default
  }
}
```

---

## The five facts that break ported code

1. **`url` scheme decides plaintext, and only `http` does.** `ManagedChannelLifecycle.init()` calls
   `usePlaintext()` **only** when the scheme is exactly `http`. `https` gets TLS. Any other scheme
   (`grpc://`, `dns://`, …) **with an explicit port silently gets TLS**; without a port it throws
   `IllegalArgumentException: Unsupported gRPC client URL scheme`. A ported 1.x `grpc://host:8090`
   therefore fails as a TLS handshake error against a plaintext server, not as a config error.
2. **Telemetry is off by default.** `logging.enabled = false`, `metrics.enabled = false`,
   `tracing.enabled = true`. If a task asks for gRPC client metrics or request logs, enable them
   explicitly under `grpcClient.<Service>.telemetry`.
3. **Unknown config keys are ignored silently.** `config-common` has no unknown-key rejection, so a
   stale key (`maxInboundMessageSize`, a mistyped service name, `grpcClient.UserServiceGrpc`) is not
   an error — the client just runs on defaults, or fails later with a `null` for the required `url`.
4. **The interceptor tag is the generated `<Service>Grpc` Java class.** Not the stub class, not the
   proto name, not a Kora module class. A wrong tag compiles and the interceptor never runs.
5. **gRPC and protobuf versions are yours to align.** `kora-bom` constrains only `io.koraframework:*`.
   See [version alignment](#version-alignment) below.

---

## Stub types

| Stub | Generated by | Use for |
|---|---|---|
| `*BlockingStub` | protoc-gen-grpc-java | unary calls; server streaming as `Iterator<Response>` |
| `*FutureStub` | protoc-gen-grpc-java | unary calls returning `ListenableFuture<Response>` |
| `*Stub` (async) | protoc-gen-grpc-java | client streaming and bidirectional streaming via `StreamObserver` |
| `*CoroutineStub` | protoc-gen-grpc-kotlin | Kotlin only, injectable, but **not used by any Kora example** — see below |

The Java extension resolves any subtype of `io.grpc.stub.AbstractStub` whose enclosing class carries
`io.grpc.stub.annotations.GrpcGenerated`, dispatching on the suffix (`BlockingStub` →
`newBlockingStub`, `FutureStub` → `newFutureStub`, otherwise `newStub`). One component may inject
several stub flavours of the same service at once — they share the channel.

**Kotlin coroutine stubs.** The KSP extension additionally resolves
`io.grpc.kotlin.AbstractCoroutineStub` subclasses annotated `@StubFor(<Service>Grpc::class)`, and
the framework's own KSP test builds a graph with `EventsGrpcKt.EventsCoroutineStub` injected. So
injection works. But Kora 2.0 contracts are **synchronous on virtual threads** — a generated
`suspend fun` on a coroutine stub is grpc-kotlin's code, not a Kora contract, and Kora provides no
coroutine scope to call it from. No migrated Kora example uses coroutine stubs; both Kotlin examples
use the Java stubs with `StreamObserver`. Prefer the Java stubs unless the caller already owns a
coroutine boundary.

Details: [references/grpc-client-stubs-reference.md](references/grpc-client-stubs-reference.md).

---

## Client interceptors

Register `io.grpc.ClientInterceptor` as a `@Component` tagged with the generated `<Service>Grpc`
class. `ManagedChannelLifecycle` receives them as `All<ClientInterceptor>` under that tag and passes
them to `ManagedChannelBuilder.intercept(...)`, followed by Kora's own
`GrpcClientTelemetryInterceptor` and `GrpcClientConfigInterceptor`.

```java
@Tag(UserServiceGrpc.class)
@Component
public final class AuthInterceptor implements ClientInterceptor {

    private static final Metadata.Key<String> AUTHORIZATION =
        Metadata.Key.of("authorization", Metadata.ASCII_STRING_MARSHALLER);

    private final AuthConfig authConfig;

    public AuthInterceptor(AuthConfig authConfig) {
        this.authConfig = authConfig;
    }

    @Override
    public <ReqT, RespT> ClientCall<ReqT, RespT> interceptCall(
            MethodDescriptor<ReqT, RespT> method, CallOptions callOptions, Channel next) {
        return new ForwardingClientCall.SimpleForwardingClientCall<>(next.newCall(method, callOptions)) {
            @Override
            public void start(Listener<RespT> responseListener, Metadata headers) {
                headers.put(AUTHORIZATION, authConfig.value());
                super.start(responseListener, headers);
            }
        };
    }
}
```

**gRPC metadata is the only auth mechanism** — there is no Kora gRPC-client auth module, no
`@HttpClient`-style annotation. Credentials go into `Metadata` inside `start()` before
`super.start()`. Details and the other extension points (`ChannelCredentials`, `Configurer`,
custom `GrpcClientTelemetryFactory`):
[references/grpc-client-interceptors-reference.md](references/grpc-client-interceptors-reference.md).

---

## Streaming

Unary and server streaming work with the blocking stub; client and bidirectional streaming need the
async `*Stub` and a `StreamObserver`. Because Kora contracts are synchronous, bridge the observer
back to the caller with a `CompletableFuture` (or a `CountDownLatch`) inside the wrapper component —
do not leak observers into controllers.
[references/grpc-client-streaming-reference.md](references/grpc-client-streaming-reference.md).

---

## Configuration

`grpcClient.<protoServiceName>` — the whole key set from `GrpcClientConfig`:

| Key | Type | Default | Notes |
|---|---|---|---|
| `url` | `String` | **required** | `http://` = plaintext, `https://` = TLS |
| `timeout` | `Duration` | none | applied as a call deadline only if the call has none |
| `keepAliveTime` | `Duration` | none | PING interval |
| `keepAliveTimeout` | `Duration` | none | PING acknowledgement timeout |
| `loadBalancingPolicy` | `String` | none | e.g. `round_robin` |
| `defaultServiceConfig` | object | none | raw gRPC service config passed to `defaultServiceConfig(Map)` |
| `telemetry.logging.enabled` | `boolean` | `false` | |
| `telemetry.logging.maskHeaders` | `Set<String>` | `authorization`, `cookie`, `set-cookie` | metadata keys masked in the `DEBUG` log by the `@Tag(GrpcClientTelemetry.class) MaskingStrategy`; a list replaces the default — see [config reference](references/grpc-client-config-reference.md#6-telemetry) |
| `telemetry.metrics.enabled` | `boolean` | `false` | |
| `telemetry.metrics.slo` | `Duration[]` | 1…90000 ms | |
| `telemetry.metrics.tags` | map | `{}` | |
| `telemetry.tracing.enabled` | `boolean` | `true` | |
| `telemetry.tracing.attributes` | map | `{}` | |

There is **no** `maxInboundMessageSize`, `usePlaintext`, `retry` or `executor` key. Anything the
config does not expose is set with a `Configurer<ManagedChannelBuilder<?>>` component.
Full HOCON/YAML reference: [references/grpc-client-config-reference.md](references/grpc-client-config-reference.md).

---

## Version alignment

`kora-bom` constrains only `io.koraframework:*`. gRPC and protobuf come from your own declarations,
and a mismatch fails **at runtime with an error that names nothing useful**:

```
AbstractMethodError: ... does not define or inherit an implementation of the resolved method
'buildClientTransportServers(List, MetricRecorder)'
```

Both migration guides record this for gRPC; it appears when a test transport
(`io.grpc:grpc-inprocess`, `io.grpc:grpc-netty`) is pinned to a different version from the
`grpc-core` that arrives through `io.koraframework:grpc-client`. Pin one set everywhere — main and
test source sets alike:

| Coordinate | Version |
|---|---|
| `io.grpc:grpc-protobuf`, `io.grpc:protoc-gen-grpc-java`, `io.grpc:grpc-inprocess`, `io.grpc:grpc-services` | `1.84.0` |
| `io.grpc:grpc-kotlin-stub`, `io.grpc:protoc-gen-grpc-kotlin` | `1.5.0` |
| `com.google.protobuf:protoc` | `3.25.3` |
| `com.google.protobuf:protobuf-java` | leave transitive — `grpc-protobuf:1.84.0` declares `3.25.9` |
| Gradle plugin `com.google.protobuf` | `0.10.0` |

gRPC is the half that must be forced; protobuf is the half that must be *left alone*.
`io.grpc:grpc-protobuf:1.84.0` declares `com.google.protobuf:protobuf-java:3.25.9`, and `protoc`
`3.25.3` generates code that runtime satisfies — so the default recipe needs no protobuf override
and cannot drift out of step. All eight migrated Kora gRPC projects pin `protoc:3.25.3`. The migrated examples on `migration/2.0` still pin the previous `1.83.1`; raise every `io.grpc` pin to `1.84.0` when copying from them.

**Upgrading protoc is a paired change, not a one-line one.** Kora's own catalog uses protobuf
`4.36.2`, and that works for an application too — but only if the runtime moves with it. protoc 4.x
generated code references `com.google.protobuf.Generated`, a class absent from `protobuf-java`
`3.25.9`, so bumping `protoc` alone fails to compile with `cannot find symbol: class Generated /
location: package com.google.protobuf`. Take both lines or neither:

```groovy
protoc { artifact = "com.google.protobuf:protoc:4.36.2" }
implementation "com.google.protobuf:protobuf-java:4.36.2"   // must outrank the transitive 3.25.9
```

**Stale generated sources.** After the `ru.tinkoff.kora` → `io.koraframework` rename, `generateProto`
does not delete its previous output, so `build/generated/source/proto` can hold both packages and
produce hundreds of errors in files you never wrote. Fix with
`./gradlew clean --continue` then `./gradlew classes testClasses --no-build-cache` — never by editing
generated code.

---

## Common pitfalls

| Symptom | Cause / fix |
|---|---|
| `Required dependency not found: …BlockingStub` | `@KoraApp` does not extend `GrpcClientModule`; or the processor is missing; or `generateProto` has not run and the generated dirs are not in `sourceSets` |
| Graph error mentioning `@Tag` on a stub | Remove the `@Tag` — stubs inject by type; the tag belongs on the interceptor |
| Interceptor never runs | Tag must be `@Tag(<Service>Grpc.class)` — the generated Java class, not the stub or the proto name |
| `ConfigValueException … 'ROOT.grpcClient.<X>.url'` | Section name must be the **proto** service simple name; `option java_outer_classname` and the `*Grpc` suffix are irrelevant |
| TLS handshake failure against a plaintext server | `url` uses `grpc://` (ported from 1.x). Use `http://` |
| `IllegalArgumentException: Unsupported gRPC client URL scheme` | Non-`http`/`https` scheme **and** no explicit port |
| No `rpc.client.call.duration` metric, no request logs | `telemetry.metrics.enabled` / `telemetry.logging.enabled` default to `false` |
| `AbstractMethodError … buildClientTransportServers` | gRPC version mismatch — see [version alignment](#version-alignment) |
| `UNAVAILABLE` | wrong host/port in `url`, or the server is down |
| `UNAUTHENTICATED` | add a tagged `ClientInterceptor` that puts credentials into `Metadata` |
| A metadata credential (`x-api-key`) appears in `DEBUG` logs | Only `authorization`, `cookie`, `set-cookie` are masked by default — add the key to `telemetry.logging.maskHeaders` and restate the defaults |
| `package ru.tinkoff.kora … does not exist` in `build/generated` | stale protobuf output — `clean` + `--no-build-cache` |

---

## References & assets

| File | Purpose |
|---|---|
| [references/grpc-client-stubs-reference.md](references/grpc-client-stubs-reference.md) | Stub flavours, how the extension resolves them, Kotlin coroutine stubs, wrappers |
| [references/grpc-client-config-reference.md](references/grpc-client-config-reference.md) | Full `GrpcClientConfig` key set, HOCON + YAML, telemetry, Gradle/protobuf wiring |
| [references/grpc-client-interceptors-reference.md](references/grpc-client-interceptors-reference.md) | Interceptor collection and tagging, metadata auth, `ChannelCredentials`, `Configurer` |
| [references/grpc-client-streaming-reference.md](references/grpc-client-streaming-reference.md) | Unary / server / client / bidirectional streaming on synchronous contracts |
| `assets/*.client.*` | Client templates: app, config, build files, interceptor, wrapper |
| `assets/*.server.*` | Minimal counterpart server for local testing — the authoritative server guidance is [`kora-grpc-server`](../kora-grpc-server/SKILL.md) |
| [assets/service.proto.template](assets/service.proto.template) | Proto skeleton shared by both sides |
