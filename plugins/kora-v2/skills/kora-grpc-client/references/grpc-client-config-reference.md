# gRPC Client Configuration Reference (Kora 2.0)

Everything under `grpcClient.*`, plus the Gradle wiring that produces the stubs the config
belongs to.

## Contents

- [1. Section naming](#1-section-naming)
- [2. Complete key set](#2-complete-key-set)
- [3. URL scheme — plaintext vs TLS](#3-url-scheme--plaintext-vs-tls)
- [4. Timeout, keep-alive, load balancing](#4-timeout-keep-alive-load-balancing)
- [5. defaultServiceConfig](#5-defaultserviceconfig)
- [6. Telemetry](#6-telemetry)
- [7. Environment substitution](#7-environment-substitution)
- [8. Anything the config does not expose](#8-anything-the-config-does-not-expose)
- [9. Gradle and protobuf wiring](#9-gradle-and-protobuf-wiring)
- [10. Version alignment](#10-version-alignment)
- [11. Troubleshooting](#11-troubleshooting)

---

## 1. Section naming

`GrpcClientConfig.defaultConfig(config, mapper, serviceName)` is called with
`<Service>Grpc.SERVICE_NAME`, takes the substring after the last `.`, and reads
`grpcClient.<that>`.

`SERVICE_NAME` is the **protobuf** fully-qualified service name, so:

| `.proto` | `SERVICE_NAME` | Config section |
|---|---|---|
| `package io.koraframework.example.grpc;`<br>`service UserService { … }` | `io.koraframework.example.grpc.UserService` | `grpcClient.UserService` |
| no `package`, `service Events { … }` | `Events` | `grpcClient.Events` |

Not the Java class (`UserServiceGrpc`), not `option java_outer_classname`, not the stub name.
Every client of the same proto service shares one section and one channel.

Two proto services with the same simple name in different proto packages collide on one section.
Rename one in the `.proto`, or give each its own `Configurer` — there is no per-client override key.

---

## 2. Complete key set

Verified against `io.koraframework.grpc.client.GrpcClientConfig` and
`io.koraframework.telemetry.common.TelemetryConfig`. Nothing else is read.

| Key | Type | Required | Default |
|---|---|---|---|
| `url` | `String` | **yes** | — |
| `timeout` | `Duration` | no | unset (no deadline added) |
| `keepAliveTime` | `Duration` | no | unset (gRPC default) |
| `keepAliveTimeout` | `Duration` | no | unset (gRPC default) |
| `loadBalancingPolicy` | `String` | no | unset (gRPC default, `pick_first`) |
| `defaultServiceConfig` | object | no | unset |
| `telemetry.logging.enabled` | `boolean` | no | `false` |
| `telemetry.logging.maskHeaders` | `Set<String>` | no | `["authorization", "cookie", "set-cookie"]` |
| `telemetry.metrics.enabled` | `boolean` | no | `false` |
| `telemetry.metrics.slo` | `Duration[]` | no | `1, 10, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000, 30000, 60000, 90000` ms |
| `telemetry.metrics.tags` | `Map<String,String>` | no | `{}` |
| `telemetry.tracing.enabled` | `boolean` | no | `true` |
| `telemetry.tracing.attributes` | `Map<String,String>` | no | `{}` |

Keys that existed in Kora 1.x guidance and **do not exist in 2.0**: `maxInboundMessageSize`,
`usePlaintext`. `config-common` performs no unknown-key validation, so a stale key is read by
nobody and reported by nobody.

### HOCON

```hocon
grpcClient {
  UserService {
    url = "http://localhost:8090"
    timeout = "10s"
    keepAliveTime = "30s"
    keepAliveTimeout = "5s"
    loadBalancingPolicy = "round_robin"
    telemetry {
      logging.enabled = true
      metrics {
        enabled = true
        slo = [1, 10, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000, 30000, 60000, 90000]
        tags { environment = "prod" }
      }
      tracing {
        enabled = true
        attributes { peer = "user-service" }
      }
    }
  }
}
```

### YAML

```yaml
grpcClient:
  UserService:
    url: "http://localhost:8090"
    timeout: "10s"
    keepAliveTime: "30s"
    keepAliveTimeout: "5s"
    loadBalancingPolicy: "round_robin"
    telemetry:
      logging:
        enabled: true
      metrics:
        enabled: true
        slo: [1, 10, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000, 30000, 60000, 90000]
        tags:
          environment: "prod"
      tracing:
        enabled: true
        attributes:
          peer: "user-service"
```

Durations accept either an ISO-8601 string (`"PT10S"`), a HOCON-style string (`"10s"`, `"250ms"`,
`"5m"`), or a bare number, which is **milliseconds**. That is why the `slo` list above is a list of
plain numbers: each is a millisecond bucket.

---

## 3. URL scheme — plaintext vs TLS

`ManagedChannelLifecycle.init()` parses `url` as a `java.net.URI` and then:

1. If the URI has **no port**, the scheme must be `http` (→ 80) or `https` (→ 443); anything else
   throws `IllegalArgumentException: Unsupported gRPC client URL scheme '<x>' in '<url>'; use
   http://host[:port] or https://host[:port]`.
2. `usePlaintext()` is called **only** when the scheme is exactly `http`.

| `url` | Result |
|---|---|
| `http://localhost:8090` | plaintext |
| `http://user-service` | plaintext, port 80 |
| `https://user-service` | TLS, port 443 |
| `https://user-service:8443` | TLS |
| `grpc://localhost:8090` | **TLS** — port present, scheme is not `http`, no exception, handshake fails against a plaintext server |
| `grpc://localhost` | `IllegalArgumentException` at startup |

A Kora 1.x config that used `grpc://` therefore does not fail loudly — it produces a TLS
handshake error at first call. Rewrite every `grpc://` to `http://` (or `https://`).

For mutual TLS or a custom trust store, supply a tagged `io.grpc.ChannelCredentials` component —
see [grpc-client-interceptors-reference.md](grpc-client-interceptors-reference.md#4-channelcredentials--tls).

---

## 4. Timeout, keep-alive, load balancing

`timeout` is applied by `GrpcClientConfigInterceptor`:

```java
if (callOptions.getDeadline() == null && this.config.timeout() != null) {
    callOptions = callOptions.withDeadlineAfter(this.config.timeout().toMillis(), MILLISECONDS);
}
```

So it is a **default deadline**, not a ceiling: a call that already carries a deadline
(`stub.withDeadlineAfter(...)`) keeps its own, longer or shorter. Deadline expiry surfaces as
`StatusRuntimeException` with `DEADLINE_EXCEEDED`.

`keepAliveTime` / `keepAliveTimeout` map onto `ManagedChannelBuilder.keepAliveTime` /
`keepAliveTimeout`; both are skipped entirely when unset. `loadBalancingPolicy` maps onto
`defaultLoadBalancingPolicy` and only matters when the target resolves to several addresses
(`round_robin` needs a DNS name with multiple A records or a headless Service).

---

## 5. defaultServiceConfig

The `defaultServiceConfig` object is passed verbatim to
`ManagedChannelBuilder.defaultServiceConfig(Map)` — it is the standard gRPC service config, so its
schema is gRPC's, not Kora's. Kora only converts the HOCON/YAML tree into a `Map`, mapping every
number to a **double** (the gRPC service config accepts no other numeric type) and dropping nulls.

```hocon
grpcClient {
  UserService {
    url = "http://localhost:8090"
    defaultServiceConfig {
      methodConfig = [
        {
          name = [ { service = "io.koraframework.example.grpc.UserService" } ]
          retryPolicy {
            maxAttempts = 4
            initialBackoff = "0.1s"
            maxBackoff = "1s"
            backoffMultiplier = 2
            retryableStatusCodes = [ "UNAVAILABLE" ]
          }
        }
      ]
    }
  }
}
```

This is how you get gRPC-level retries — there is **no** Kora `retry` key under `grpcClient`.
(Kora's own `@Retryable` aspect from `resilient-kora` is a separate, method-level mechanism and can
be applied to the wrapper component instead.)

---

## 6. Telemetry

`GrpcClientTelemetryConfig extends TelemetryConfig`, adding one key of its own:
`logging.maskHeaders`.

**Defaults are off for logging and metrics.** If a task asks to "show gRPC client metrics" or "log
gRPC calls", the config must turn them on explicitly:

```hocon
grpcClient.UserService.telemetry {
  logging.enabled = true
  metrics.enabled = true
}
```

Beyond the flags, each signal also needs its provider component in the graph — `metrics` needs a
`MeterRegistry` (`micrometer-module`), `tracing` needs a `Tracer` (`opentelemetry-tracing`).
`DefaultGrpcClientTelemetryFactory` checks both: `tracer != null && tracing().enabled()`,
`meterRegistry != null && metrics().enabled()`. With neither and logging off it returns a no-op
telemetry, so there is no cost when everything is disabled.

**Metric.** One Micrometer `Timer` named `rpc.client.call.duration`, tagged `rpc.system.name=grpc`,
`rpc.service`, `rpc.method`, `rpc.response.status_code` (the `Status.Code` **name**, e.g. `OK`,
`UNAVAILABLE`), `server.address`, `server.port`, `error.type`, plus your `telemetry.metrics.tags`.
2.0.0.RC1 called it `rpc.client.duration` with `rpc.system` and a numeric `rpc.grpc.status_code`
(renamed in RC2, #972). The span (named after the full method name) carries the same `rpc.*` /
`server.*` attributes; `server.port` falls back to `80` when the URL has no port. `slo` becomes the timer's service-level objectives.

**Loggers.** Two, named after the **full** proto service name:

```
io.koraframework.example.grpc.UserService.request
io.koraframework.example.grpc.UserService.response
```

At `INFO` they log `GrpcClient request started` / `GrpcClient response received` with a structured
`grpcRequest` / `grpcResponse` payload; at `DEBUG` the request logger adds the outgoing `Metadata`.
Failures log at `WARN` with the cause. Level them like any other logger:

```hocon
logging.levels {
  "io.koraframework.example.grpc.UserService.request" = "DEBUG"
  "io.koraframework.example.grpc.UserService.response" = "INFO"
}
```

Turning `telemetry.logging.enabled` on but leaving the logger at `WARN` produces nothing — both
switches must agree.

**Masking.** The `DEBUG` metadata dump masks the values of every key in
`telemetry.logging.maskHeaders` (default `authorization`, `cookie`, `set-cookie`; one `key: value`
line per value, `-bin` values Base64-encoded unless masked). The client logs no message bodies.

- A configured list **replaces** the default — when adding `x-api-key`, restate the three defaults.
  Keys are lower-cased before matching.
- There is no `mask` key. The replacement (default `***`) is a
  `@Tag(GrpcClientTelemetry.class) MaskingStrategy` (`io.koraframework.grpc.client.telemetry.GrpcClientTelemetry`,
  `io.koraframework.logging.common.masking.MaskingStrategy`), shared by every gRPC client; a tagged
  component of your own replaces the module's `@DefaultComponent`:

```java
@Tag(GrpcClientTelemetry.class)
default MaskingStrategy grpcClientMaskingStrategy() {
    return new MaskingKeepLast("***", 4);
}
```

```kotlin
@Tag(GrpcClientTelemetry::class)
fun grpcClientMaskingStrategy(): MaskingStrategy = MaskingKeepLast("***", 4)
```

```hocon
grpcClient.UserService.telemetry.logging {
  enabled = true
  maskHeaders = ["authorization", "cookie", "set-cookie", "x-api-key"]
}
```

Shared masking model: [kora-aop-logging → masking](../../kora-aop-logging/references/logging-masking.md).

---

## 7. Environment substitution

```hocon
grpcClient {
  UserService {
    url = "http://localhost:8090"
    url = ${?GRPC_SERVER_URL}          # override only if the variable is set
    timeout = ${?GRPC_TIMEOUT}
    telemetry.logging.enabled = ${?GRPC_LOG_ENABLED}
  }
}
```

```yaml
grpcClient:
  UserService:
    url: ${?GRPC_SERVER_URL:"http://localhost:8090"}
    timeout: ${?GRPC_TIMEOUT:"10s"}
```

`${VAR}` (no `?`) makes the variable mandatory and fails startup when absent — appropriate for a
URL that must never default to localhost in production.

---

## 8. Anything the config does not expose

Two extension points, both optional and both `@Nullable` in the graph:

| Component | Tag | Applies to |
|---|---|---|
| `Configurer<ManagedChannelBuilder<?>>` | `@Tag(<Service>Grpc.class)` | that one service, applied **last**, after every config-driven setting |
| `Configurer<ManagedChannelBuilder<?>>` | untagged | every channel built by the default `GrpcOkHttpClientChannelFactory` |

```java
@Tag(UserServiceGrpc.class)
@Component
public final class UserServiceChannelConfigurer implements Configurer<ManagedChannelBuilder<?>> {

    @Override
    public ManagedChannelBuilder<?> configure(ManagedChannelBuilder<?> builder) {
        return builder.maxInboundMessageSize(16 * 1024 * 1024);
    }
}
```

That is the 2.0 replacement for the `maxInboundMessageSize` config key, and the way to reach
`executor`, `userAgent`, `idleTimeout`, `maxRetryAttempts` and anything else on
`ManagedChannelBuilder`.

---

## 9. Gradle and protobuf wiring

`kora-bom` constrains `io.koraframework:*` only. gRPC and protobuf versions are yours.

===! "Java (build.gradle)"

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
    koraBom platform("io.koraframework:kora-bom:$koraVersion")   // 2.0.0.RC2
    annotationProcessor "io.koraframework:annotation-processors"

    implementation "io.koraframework:grpc-client"
    implementation "io.koraframework:config-hocon"
    implementation "io.koraframework:logging-logback"

    implementation "io.grpc:grpc-protobuf:1.84.0"   // brings protobuf-java 3.25.9 transitively
    compileOnly "javax.annotation:javax.annotation-api:1.3.2"

    testImplementation "io.koraframework:test-junit5"
    testImplementation "io.grpc:grpc-inprocess:1.84.0"
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

=== "Kotlin (build.gradle.kts)"

```kotlin
import com.google.protobuf.gradle.id

plugins {
    id("org.jetbrains.kotlin.jvm") version "2.4.20"
    id("com.google.devtools.ksp") version "2.3.12"
    id("application")
    id("com.google.protobuf") version "0.10.0"
}

kotlin { jvmToolchain { languageVersion.set(JavaLanguageVersion.of(25)) } }
java { toolchain { languageVersion.set(JavaLanguageVersion.of(25)) } }

dependencies {
    implementation(platform("io.koraframework:kora-bom:${property("koraVersion")}"))
    ksp("io.koraframework:symbol-processors:${property("koraVersion")}")

    implementation("io.koraframework:grpc-client")
    implementation("io.koraframework:config-hocon")
    implementation("io.koraframework:logging-logback")

    implementation("io.grpc:grpc-protobuf:1.84.0")   // brings protobuf-java 3.25.9 transitively
    compileOnly("javax.annotation:javax.annotation-api:1.3.2")

    testImplementation("io.koraframework:test-junit5")
    testImplementation("io.grpc:grpc-inprocess:1.84.0")
}

protobuf {
    protoc { artifact = "com.google.protobuf:protoc:3.25.3" }
    plugins { id("grpc") { artifact = "io.grpc:protoc-gen-grpc-java:1.84.0" } }
    generateProtoTasks { all().forEach { it.plugins { id("grpc") } } }
}

// protoc-gen-grpc-java emits JAVA — register it on the java source set, not the kotlin one
sourceSets.main {
    java.srcDir(layout.buildDirectory.dir("generated/source/proto/main/grpc"))
    java.srcDir(layout.buildDirectory.dir("generated/source/proto/main/java"))
}
```

Two details that are easy to get wrong in Kotlin projects:

- the generated gRPC code is **Java**, so the source dirs go on `sourceSets.main.java`, not on
  `kotlin.srcDir`;
- KSP must see the generated stub classes, which it does because they are compiled Java sources of
  the same module — no extra wiring, but `generateProto` must run before `kspKotlin`, which the
  Gradle plugin arranges as long as the source dirs are declared.

---

## 10. Version alignment

A mismatch between the gRPC artifacts you declare and the `grpc-core` that arrives through
`io.koraframework:grpc-client` fails at runtime, not at compile time. Both migration guides record
the symptom:

```
AbstractMethodError: ... does not define or inherit an implementation of the resolved method
'buildClientTransportServers(List, MetricRecorder)'
```

It typically shows up in tests, where `io.grpc:grpc-inprocess` or `io.grpc:grpc-netty` is pinned to
an older version than the rest. Pin one set across main and test:

| Coordinate | Version |
|---|---|
| `io.grpc:grpc-protobuf`, `io.grpc:protoc-gen-grpc-java`, `io.grpc:grpc-inprocess`, `io.grpc:grpc-netty`, `io.grpc:grpc-services` | `1.84.0` |
| `io.grpc:grpc-kotlin-stub`, `io.grpc:protoc-gen-grpc-kotlin` | `1.5.0` |
| `com.google.protobuf:protoc` | `3.25.3` |
| `com.google.protobuf:protobuf-java` | leave transitive — `grpc-protobuf:1.84.0` declares `3.25.9` |
| Gradle plugin `com.google.protobuf` | `0.10.0` |

### protobuf: leave it transitive

The two halves of the alignment are handled differently, and this is the part that most often gets
copied wrong.

`io.grpc:grpc-protobuf:1.84.0` declares `com.google.protobuf:protobuf-java:3.25.9` (compile scope,
verified in the published POM). Pinning `protoc` to `3.25.3` therefore produces generated code that
the transitively-resolved runtime already satisfies — **no protobuf override is needed, and adding
one only risks clamping the runtime below whatever a future gRPC bump brings.** All eight migrated
Kora gRPC projects — both examples and all four guide apps, client and server — pin `protoc:3.25.3`.

**Upgrading protoc is a paired change.** Kora's own version catalog uses protobuf `4.36.2`, and an
application may use it too — but protoc 4.x generated code references `com.google.protobuf.Generated`,
a class that does not exist in `protobuf-java` `3.25.9`. Bumping `protoc` alone fails to compile:

```
error: cannot find symbol
  symbol:   class Generated
  location: package com.google.protobuf
```

The fix is to move the runtime with it, so the explicit pin outranks the transitive `3.25.9`:

```groovy
protobuf { protoc { artifact = "com.google.protobuf:protoc:4.36.2" } }
dependencies { implementation "com.google.protobuf:protobuf-java:4.36.2" }
```

Both recipes are correct. `3.25.3` is the default here because it is the one that stays correct when
only half of it is copied.

### Making the gRPC half enforceable

gRPC is the half that does need forcing — nothing in the dependency graph stops a transitive pull
onto a different `grpc-core`:

```groovy
configurations.configureEach {
    resolutionStrategy.eachDependency {
        // grpc-kotlin has its own version line (1.5.0); "contains" also spares protoc-gen-grpc-kotlin,
        // which "startsWith" would not.
        if (it.requested.group == "io.grpc" && !it.requested.name.contains("kotlin")) {
            it.useVersion "1.84.0"
        }
    }
}
```

---

## 11. Troubleshooting

| Problem | Cause / fix |
|---|---|
| `ConfigValueException: Config expected value, but got null at path: 'ROOT.grpcClient.<X>.url'` | section name wrong (must be the **proto** service simple name), or `url` genuinely missing |
| Config edits have no effect | the key is not in the table above — unknown keys are ignored silently |
| TLS handshake failure against a plaintext server | `url` uses `grpc://` — use `http://` |
| `IllegalArgumentException: Unsupported gRPC client URL scheme` | non-`http`/`https` scheme **and** no explicit port |
| `DEADLINE_EXCEEDED` on every call | `timeout` too small; it becomes the call's default deadline |
| No `rpc.client.call.duration` metric | `telemetry.metrics.enabled` defaults to `false`; a `MeterRegistry` must also be in the graph |
| Nothing logged although `telemetry.logging.enabled = true` | the `<protoService>.request` / `.response` loggers are below `INFO` |
| `round_robin` behaves like `pick_first` | the target resolves to a single address |
| `AbstractMethodError … buildClientTransportServers` | gRPC version mismatch — see [version alignment](#10-version-alignment) |
| `package ru.tinkoff.kora … does not exist` under `build/generated` | stale protobuf output — `clean` + `--no-build-cache` |
