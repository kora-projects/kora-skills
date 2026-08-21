# gRPC Server Reference

**Source:** `.kora-agent/kora-docs/mkdocs/docs/en/documentation/grpc-server.md`
**Examples:** `.kora-agent/kora-examples/examples/java/kora-java-grpc-server/`

## Contents

1. Overview
2. Dependency
3. Protobuf Plugin
4. Configuration
5. Handlers
6. Interceptors
7. Reflection
8. Troubleshooting

## 1. Overview

Module for gRPC server handlers support based on [grpc.io](https://grpc.io/docs/languages/java/basics/) functionality.

## 2. Dependency

===! ":fontawesome-brands-java: `Java`"

    ```groovy
    dependencies {
        implementation "ru.tinkoff.kora:grpc-server"
        implementation "io.grpc:grpc-protobuf:1.74.0"
        implementation "javax.annotation:javax.annotation-api:1.3.2"
    }
    ```

    Module:
    ```java
    @KoraApp
    public interface Application extends GrpcServerModule { }
    ```

=== ":simple-kotlin: `Kotlin`"

    ```kotlin
    dependencies {
        implementation("ru.tinkoff.kora:grpc-server")
        implementation("io.grpc:grpc-protobuf:1.74.0")
        implementation("javax.annotation:javax.annotation-api:1.3.2")
    }
    ```

    Module:
    ```kotlin
    @KoraApp
    interface Application : GrpcServerModule
    ```

## 3. Protobuf Plugin

The code for the gRPC server is created with the `com.google.protobuf` Gradle plugin.

===! ":fontawesome-brands-java: `Java`"

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

## 4. Configuration

Example of a complete configuration:

===! ":material-code-json: `Hocon`"

    ```javascript
    grpcServer {
        port = 8090 //(1)!
        maxMessageSize = "4MiB" //(2)!
        reflectionEnabled = false //(3)!
        shutdownWait = "30s" //(4)!
        maxConnectionAge = "0s" //(5)!
        maxConnectionAgeGrace = "0s" //(6)!
        keepAliveTime = "0s" //(7)!
        keepAliveTimeout = "0s" //(8)!
        telemetry {
            logging {
                enabled = false //(9)!
            }
            metrics {
                enabled = true //(10)!
                slo = [ 1, 10, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000, 30000, 60000, 90000 ] //(11)!
            }
            tracing {
                enabled = true //(12)!
            }
        }
    }
    ```

    1. gRPC server port
    2. Maximum size of the incoming message (specified as number of bytes / or as `4MiB` / `4MB` / `1000Kb` etc.)
    3. Enables [gRPC Server Reflection](#reflection) service
    4. Time to wait for processing before shutting down the server in case of [graceful shutdown](container.md#graceful-shutdown)
    5. Sets a custom max connection age
    6. Sets a custom grace time for the graceful connection termination
    7. Sets the interval in milliseconds between PING frames
    8. Sets the timeout in milliseconds for a PING frame to be acknowledged
    9. Enables module logging (default `false`)
    10. Enables module metrics (default `true`)
    11. Configures SLO for DistributionSummary metrics
    12. Enables module tracing (default `true`)

=== ":simple-yaml: `YAML`"

    ```yaml
    grpcServer:
      port: 8090
      maxMessageSize: "4MiB"
      reflectionEnabled: false
      shutdownWait: "30s"
      maxConnectionAge: "0s"
      maxConnectionAgeGrace: "0s"
      keepAliveTime: "0s"
      keepAliveTimeout: "0s"
      telemetry:
        logging:
          enabled: false
        metrics:
          enabled: true
          slo: [ 1, 10, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000, 30000, 60000, 90000 ]
        tracing:
          enabled: true
    ```

## 5. Handlers

Created gRPC service handlers are required to be tagged with the `@Component` annotation:

===! ":fontawesome-brands-java: `Java`"

    ```java
    @Component
    public class ExampleService extends ExampleGrpc.ExampleImplBase {}
    ```

=== ":simple-kotlin: `Kotlin`"

    ```kotlin
    @Component
    class ExampleService : ExampleGrpc.ExampleImplBase {}
    ```

## 6. Interceptors

Interceptors (`io.grpc.ServerInterceptor`) allow you to intercept requests before they are passed to handlers.

### Default Interceptors

The following interceptors are used at server startup by default:
- `ContextServerInterceptor`
- `CoroutineContextInjectInterceptor`
- `MetricCollectorServerInterceptor`
- `LoggingServerInterceptor`

To override the default interceptor list, you can override the `serverBuilder` method from the `GrpcModule` class.

### Custom Interceptors

Adding your custom interceptor requires creating an inheritor of `ServerInterceptor` with the `@Component` annotation:

===! ":fontawesome-brands-java: `Java`"

    ```java
    @Component
    public class GrpcExceptionHandlerServerInterceptor implements ServerInterceptor {

        @Override
        public <ReqT, RespT> ServerCall.Listener<ReqT> interceptCall(
            ServerCall<ReqT, RespT> serverCall, 
            Metadata metadata,
            ServerCallHandler<ReqT, RespT> serverCallHandler
        ) {
            // do something
            
            return serverCallHandler.startCall(serverCall, metadata);
        }
    }
    ```

=== ":simple-kotlin: `Kotlin`"

    ```kotlin
    @Component
    class GrpcExceptionHandlerServerInterceptor : ServerInterceptor {

        override fun <ReqT, RespT> interceptCall(
            serverCall: ServerCall<ReqT, RespT>,
            metadata: Metadata,
            serverCallHandler: ServerCallHandler<ReqT, RespT>
        ): ServerCall.Listener<ReqT> {
            // do something
            
            return serverCallHandler.startCall(serverCall, metadata)
        }
    }
    ```

## 7. Reflection

Supported by gRPC Server Reflection, which provides information about publicly available gRPC services on the server and helps clients at runtime build RPC requests and responses without pre-compiled service information.

### Dependency

An optional gRPC Server Reflection dependency is required:

===! ":fontawesome-brands-java: `Java`"

    ```groovy
    implementation "io.grpc:grpc-services:1.74.0"
    ```

=== ":simple-kotlin: `Kotlin`"

    ```kotlin
    implementation("io.grpc:grpc-services:1.74.0")
    ```

### Configuration

You must also enable the gRPC Server Reflection service in the configuration:

===! ":material-code-json: `Hocon`"

    ```javascript
    grpcServer {
        reflectionEnabled = false //(1)!
    }
    ```

    1. Enables gRPC Server Reflection service

=== ":simple-yaml: `YAML`"

    ```yaml
    grpcServer:
      reflectionEnabled: false
    ```

## 8. Troubleshooting

| Problem | Solution |
|---------|----------|
| Generated classes not found | Check protobuf plugin configuration and run `generateProto` task |
| Port already in use | Change `grpcServer.port` or stop conflicting process |
| Handler not registered | Ensure `@Component` annotation is present |
| Reflection not working | Add `grpc-services` dependency and set `reflectionEnabled = true` |
