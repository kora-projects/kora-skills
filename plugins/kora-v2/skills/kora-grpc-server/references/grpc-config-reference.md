# gRPC Server Configuration Reference

**Source:** `.kora-agent/kora-docs/mkdocs/docs/en/documentation/grpc-server.md`, `netty.md`, `metrics.md`
**Config class:** `GrpcServerConfig`

## Contents

1. Module Setup
2. Dependencies
3. Protobuf Plugin Configuration
4. Server Configuration (HOCON / YAML)
5. Configuration Properties Reference
6. Netty Transport Configuration
7. Metrics
8. Common Issues

## 1. Module Setup

=== ":fontawesome-brands-java: `Java`"
```java
@KoraApp
public interface Application extends GrpcServerModule { }
```

=== ":simple-kotlin: `Kotlin`"
```kotlin
@KoraApp
interface Application : GrpcServerModule
```

## 2. Dependencies

=== ":fontawesome-brands-java: `Java`"
```groovy
dependencies {
    koraBom platform("ru.tinkoff.kora:kora-parent:$koraVersion")
    annotationProcessor "ru.tinkoff.kora:annotation-processors"
    
    implementation "ru.tinkoff.kora:grpc-server"
    implementation "io.grpc:grpc-protobuf:1.74.0"
    implementation "javax.annotation:javax.annotation-api:1.3.2"
}
```

=== ":simple-kotlin: `Kotlin`"
```kotlin
dependencies {
    koraBom platform("ru.tinkoff.kora:kora-parent:$koraVersion")
    ksp "ru.tinkoff.kora:symbol-processors"
    
    implementation("ru.tinkoff.kora:grpc-server")
    implementation("io.grpc:grpc-protobuf:1.74.0")
    implementation("javax.annotation:javax.annotation-api:1.3.2")
}
```

## 3. Protobuf Plugin Configuration

=== ":fontawesome-brands-java: `Java`"
```groovy
plugins {
    id "com.google.protobuf" version "0.10.0"
}

protobuf {
    protoc { artifact = "com.google.protobuf:protoc:3.25.3" }
    plugins {
        grpc { artifact = "io.grpc:protoc-gen-grpc-java:1.74.0" }
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

=== ":simple-kotlin: `Kotlin`"
```kotlin
import com.google.protobuf.gradle.id

plugins {
    id("com.google.protobuf") version ("0.10.0")
}

protobuf {
    protoc { artifact = "com.google.protobuf:protoc:3.25.3" }
    plugins {
        id("grpc") { artifact = "io.grpc:protoc-gen-grpc-java:1.74.0" }
    }
    generateProtoTasks {
        ofSourceSet("main").forEach { it.plugins { id("grpc") { } } }
    }
}

kotlin {
    sourceSets.main {
        kotlin.srcDir("build/generated/source/proto/main/grpc")
        kotlin.srcDir("build/generated/source/proto/main/java")
    }
}
```

## 4. Server Configuration

### HOCON Format

```hocon
grpcServer {
  port = 9090                           # gRPC server port (required)
  maxMessageSize = "4MiB"               # Max incoming message size
  reflectionEnabled = true              # Enable reflection for grpcurl
  shutdownWait = "30s"                  # Graceful shutdown timeout
  maxConnectionAge = "0s"               # Max connection age (0 = unlimited)
  maxConnectionAgeGrace = "0s"          # Grace period after max age
  keepAliveTime = "0s"                  # Keepalive ping interval
  keepAliveTimeout = "0s"               # Keepalive timeout
  
  # Telemetry configuration
  telemetry {
    logging {
      enabled = true                    # Enable request logging
    }
    metrics {
      enabled = true                    # Enable Micrometer metrics
      slo = [1, 10, 50, 100, 500, 1000] # SLO buckets in ms
      tags = {                          # Additional metric tags
        "service" = "user-service"
      }
    }
    tracing {
      enabled = true                    # Enable OpenTelemetry tracing
      attributes = {                    # Additional span attributes
        "service.name" = "user-service"
      }
    }
  }
}
```

### YAML Format

```yaml
grpcServer:
  port: 9090
  maxMessageSize: "4MiB"
  reflectionEnabled: true
  shutdownWait: "30s"
  maxConnectionAge: "0s"
  maxConnectionAgeGrace: "0s"
  keepAliveTime: "0s"
  keepAliveTimeout: "0s"
  telemetry:
    logging:
      enabled: true
    metrics:
      enabled: true
      slo: [1, 10, 50, 100, 500, 1000]
      tags:
        service: user-service
    tracing:
      enabled: true
      attributes:
        service.name: user-service
```

## 5. Configuration Properties Reference

| Property | Type | Default | Description |
|----------|------|---------|-------------|
| `port` | int | - | gRPC server port (required) |
| `maxMessageSize` | string | - | Maximum incoming message size (e.g., `4MiB`, `1000Kb`) |
| `reflectionEnabled` | boolean | `false` | Enable gRPC Server Reflection |
| `shutdownWait` | duration | `30s` | Graceful shutdown timeout |
| `maxConnectionAge` | duration | `0s` | Max connection age (0 = unlimited) |
| `maxConnectionAgeGrace` | duration | `0s` | Grace period after max connection age |
| `keepAliveTime` | duration | `0s` | Interval between PING frames |
| `keepAliveTimeout` | duration | `0s` | Timeout for PING acknowledgment |
| `telemetry.logging.enabled` | boolean | `false` | Enable request logging |
| `telemetry.metrics.enabled` | boolean | `true` | Enable Micrometer metrics |
| `telemetry.metrics.slo` | array | - | SLO buckets for DistributionSummary (ms) |
| `telemetry.metrics.tags` | map | - | Additional metric tags |
| `telemetry.tracing.enabled` | boolean | `true` | Enable OpenTelemetry tracing |
| `telemetry.tracing.attributes` | map | - | Additional span attributes |

## 6. Netty Transport Configuration

The gRPC server runs on Netty. Transport and event-loop tuning live under the separate top-level `netty` section (described by `NettyTransportConfig`), not under `grpcServer`:

```hocon
netty {
  transport = "NIO"   # preferred transport if its native dependency is present:
                      # Epoll (io.netty:netty-transport-native-epoll),
                      # KQueue (io.netty:netty-transport-native-kqueue), then Nio
  threads = 2         # Netty event-loop threads; default = CPU cores * 2
}
```

```yaml
netty:
  transport: "NIO"
  threads: 2
```

Source: `.kora-agent/kora-docs/mkdocs/docs/en/documentation/netty.md`.

## 7. Metrics

Module metrics (always under `grpcServer.telemetry.metrics`):

| Metric | Prometheus | Type |
|--------|-----------|------|
| `rpc.server.duration` | `rpc_server_duration_milliseconds` | DistributionSummary |
| `rpc.server.requests_per_rpc` | `rpc_server_requests_per_rpc_total` | Counter |
| `rpc.server.responses_per_rpc` | `rpc_server_responses_per_rpc_total` | Counter |

Tags: `rpc.service`, `rpc.method`, `rpc.status`, `error.type`. Source: `metrics.md#grpc-server`.

## 8. Common Issues

| Problem | Solution |
|---------|----------|
| **Port already in use** | Change `grpcServer.port` or stop conflicting process |
| **Protobuf classes not found** | Run `./gradlew generateProto`, check plugin version |
| **Generated sources not recognized** | Add `build/generated/source/proto` to source sets |
| **Build hangs after clean** | Run `./gradlew --stop` to kill daemons |
