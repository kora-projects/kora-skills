# gRPC Client Configuration Reference

**Source:** `.kora-agent/kora-docs/mkdocs/docs/en/documentation/grpc-client.md`

## Contents

- [1. Overview](#1-overview)
- [2. Basic configuration](#2-basic-configuration)
- [3. Full configuration](#3-full-configuration)
- [4. Environment variables](#4-environment-variables)
- [5. Enabling GrpcClientModule](#5-enabling-grpcclientmodule)
- [6. Protobuf Gradle plugin](#6-protobuf-gradle-plugin)
- [7. Troubleshooting](#7-troubleshooting)

## 1. Overview

A gRPC service named `SimpleService` is configured under `grpcClient.SimpleService`. Each generated client gets its own configuration section keyed by the protobuf service name.

## 2. Basic configuration

The `url` is required. Plaintext vs TLS is controlled by the URL scheme (`http://` for plaintext in local setups); there is no `usePlaintext` key.

===! "Hocon"

```hocon
grpcClient {
  SimpleService {
    url = "grpc://localhost:8090"   // (1) required
    timeout = "10s"                  // (2) max request time, optional
  }
}
```

=== "YAML"

```yaml
grpcClient:
  SimpleService:
    url: "grpc://localhost:8090"
    timeout: "10s"
```

## 3. Full configuration

These are the keys from `GrpcClientConfig` (defaults / example values shown).

===! "Hocon"

```hocon
grpcClient {
  SimpleService {
    url = "grpc://localhost:8090"
    timeout = "10s"
    keepAliveTime = "0s"            // (1) interval between PING frames
    keepAliveTimeout = "0s"         // (2) PING acknowledgement timeout
    loadBalancingPolicy = "pick_first" // (3) load balancing policy
    telemetry {
      logging {
        enabled = false             // (4) default false
      }
      metrics {
        enabled = true              // (5) default true
        slo = [ 1, 10, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000, 30000, 60000, 90000 ] // (6)
        tags = {                    // (7) optional metric tags
          "key1" = "value1"
        }
      }
      tracing {
        enabled = true              // (8) default true
        attributes = {              // (9) optional tracing attributes
          "key1" = "value1"
        }
      }
    }
  }
}
```

=== "YAML"

```yaml
grpcClient:
  SimpleService:
    url: "grpc://localhost:8090"
    timeout: "10s"
    keepAliveTime: "0s"
    keepAliveTimeout: "0s"
    loadBalancingPolicy: "pick_first"
    telemetry:
      logging:
        enabled: false
      metrics:
        enabled: true
        slo: [ 1, 10, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000, 30000, 60000, 90000 ]
        tags:
          key1: value1
      tracing:
        enabled: true
        attributes:
          key1: value1
```

1. Interval between PING frames.
2. Timeout for a PING frame to be acknowledged; the connection is closed if no acknowledgement arrives in time.
3. Load balancing policy.
4. Enables module logging (default `false`).
5. Enables module metrics (default `true`).
6. SLO buckets for the `DistributionSummary` metrics.
7. Optional metric tags.
8. Enables module tracing (default `true`).
9. Optional tracing attributes.

Netty transport options are documented in `.kora-agent/kora-docs/mkdocs/docs/en/documentation/netty.md`. Metrics are described in `.kora-agent/kora-docs/mkdocs/docs/en/documentation/metrics.md` (section `grpc-client`).

## 4. Environment variables

Externalize values with `${?VAR}` (optional override) or `${?VAR:default}`:

===! "Hocon"

```hocon
grpcClient {
  SimpleService {
    url = "http://localhost:8090"
    url = ${?GRPC_SERVER_URL}
    timeout = ${?GRPC_TIMEOUT:"10s"}
  }
}
```

=== "YAML"

```yaml
grpcClient:
  SimpleService:
    url: ${?GRPC_SERVER_URL:"http://localhost:8090"}
    timeout: ${?GRPC_TIMEOUT:"10s"}
```

## 5. Enabling GrpcClientModule

===! "Java"

```java
@KoraApp
public interface Application extends HoconConfigModule, GrpcClientModule { }
```

=== "Kotlin"

```kotlin
@KoraApp
interface Application : HoconConfigModule, GrpcClientModule
```

## 6. Protobuf Gradle plugin

Generated client code is produced by the `com.google.protobuf` Gradle plugin. Pin the Kora BOM via `kora-parent` and keep the mandatory annotation processor.

===! "Java (build.gradle)"

```groovy
plugins {
    id "com.google.protobuf" version "0.9.4"
}

dependencies {
    annotationProcessor "ru.tinkoff.kora:annotation-processors"
    implementation "ru.tinkoff.kora:grpc-client"
    implementation "io.grpc:grpc-protobuf:1.74.0"
    compileOnly "javax.annotation:javax.annotation-api:1.3.2"
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
    id("com.google.protobuf") version "0.9.4"
}

dependencies {
    ksp("ru.tinkoff.kora:symbol-processors")
    implementation("ru.tinkoff.kora:grpc-client")
    implementation("io.grpc:grpc-protobuf:1.74.0")
    compileOnly("javax.annotation:javax.annotation-api:1.3.2")
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

## 7. Troubleshooting

| Problem | Solution |
|---------|----------|
| Connection refused | Check `grpcClient.<ServiceName>.url` |
| `UNAVAILABLE` | Verify host/port and that the server is running |
| Generated classes missing | Run `./gradlew generateProto` and check the source dirs |
| Config not applied | Confirm the key path is `grpcClient.<ServiceName>` (matches the proto service name) |
