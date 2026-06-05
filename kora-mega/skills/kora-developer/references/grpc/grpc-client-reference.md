# gRPC Client Reference

**Source:** [.kora-agent/kora-docs/mkdocs/docs/en/documentation/grpc-client.md](.kora-agent/kora-docs/mkdocs/docs/en/documentation/grpc-client.md)  
**Examples:** `.kora-agent/kora-examples/kora-java-grpc-client/`

## 1. Overview

Module for gRPC client service support based on [grpc.io](https://grpc.io/docs/languages/java/basics/) functionality.

## 2. Dependency

===! ":fontawesome-brands-java: `Java`"

    ```groovy
    dependencies {
        implementation "ru.tinkoff.kora:grpc-client"
        implementation "io.grpc:grpc-protobuf:1.62.2"
        implementation "javax.annotation:javax.annotation-api:1.3.2"
    }
    ```

    Module:
    ```java
    @KoraApp
    public interface Application extends GrpcClientModule { }
    ```

=== ":simple-kotlin: `Kotlin`"

    ```kotlin
    dependencies {
        implementation("ru.tinkoff.kora:grpc-client")
        implementation("io.grpc:grpc-protobuf:1.62.2")
        implementation("javax.annotation:javax.annotation-api:1.3.2")
    }
    ```

    Module:
    ```kotlin
    @KoraApp
    interface Application : GrpcClientModule
    ```

## 3. Protobuf Plugin

The code for the gRPC client is created with [protobuf gradle plugin](https://github.com/google/protobuf-gradle-plugin).

===! ":fontawesome-brands-java: `Java`"

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

=== ":simple-kotlin: `Kotlin`"

    ```kotlin
    import com.google.protobuf.gradle.id

    plugins {
        id("com.google.protobuf") version ("0.9.4")
    }

    protobuf {
        protoc { artifact = "com.google.protobuf:protoc:3.25.3" }
        plugins {
            id("grpc") { artifact = "io.grpc:protoc-gen-grpc-java:1.62.2" }
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

gRPC service named `SimpleService`, will have configuration with path of `grpcClient.SimpleService`.

Example of the complete configuration:

===! ":material-code-json: `Hocon`"

    ```javascript
    grpcClient {
        SimpleService {
            url = "grpc://localhost:8090" //(1)!
            timeout = "10s"  //(2)!
            keepAliveTime = "0s" //(3)!
            keepAliveTimeout = "0s" //(4)!
            loadBalancingPolicy = "pick_first" //(5)!
            telemetry {
                logging {
                    enabled = false //(6)!
                }
                metrics {
                    enabled = true //(7)!
                    slo = [ 1, 10, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000, 30000, 60000, 90000 ] //(8)!
                }
                tracing {
                    enabled = true //(9)!
                }
            }
        }
    }
    ```

    1. URL of the server where to make requests (**required**)
    2. Maximum request time (optional)
    3. Sets the interval in milliseconds between PING frames
    4. Sets the timeout in milliseconds for a PING frame to be acknowledged
    5. Sets the load balancing policy
    6. Enables module logging (default `false`)
    7. Enables module metrics (default `true`)
    8. Configures SLO for DistributionSummary metrics
    9. Enables module tracing (default `true`)

=== ":simple-yaml: `YAML`"

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
          tracing:
            enabled: true
    ```

## 5. Service Injection

Created gRPC services can be injected as dependency:

===! ":fontawesome-brands-java: `Java`"

    ```java
    @KoraApp
    public interface Application extends HoconConfigModule, GrpcClientModule {

        default SomeService(SimpleServiceGrpc.SimpleServiceBlockingStub grpcService) {
            return new SomeService(grpcService);
        }
    }
    ```

=== ":simple-kotlin: `Kotlin`"

    ```kotlin
    @KoraApp
    interface Application : HoconConfigModule, GrpcClientModule {
        fun SomeService(grpcService: SimpleServiceGrpc.SimpleServiceBlockingStub?) {
            return SomeService(grpcService)
        }
    }
    ```

## 6. Interceptors

[Interceptors](https://grpc.github.io/grpc-java/javadoc/io/grpc/ClientInterceptor.html) allow you to intercept requests before they are passed to services.

### Default Interceptors

The following interceptors are used at client startup by default:
- `GrpcClientConfigInterceptor`

### Custom Interceptors

In order to add your custom interceptor, you need to register the interceptor as a component with the service tag:

===! ":fontawesome-brands-java: `Java`"

    ```java
    @Tag(SimpleServiceGrpc.class)
    @Component
    public final class MyClientInterceptor implements ClientInterceptor {
        @Override
        public <ReqT, RespT> ClientCall<ReqT, RespT> interceptCall(
            MethodDescriptor<ReqT, RespT> method, 
            CallOptions callOptions, 
            Channel next
        ) {
            LoggerFactory.getLogger(Application.class).info("INTERCEPTED");
            return next.newCall(method, callOptions);
        }
    }
    ```

=== ":simple-kotlin: `Kotlin`"

    ```kotlin
    @Tag(SimpleServiceGrpc::class)
    @Component
    class MyClientInterceptor : ClientInterceptor {
        fun <ReqT, RespT> interceptCall(
            method: MethodDescriptor<ReqT, RespT>,
            callOptions: CallOptions,
            next: Channel
        ): ClientCall<ReqT, RespT> {
            return next.newCall(method, callOptions)
        }
    }
    ```

Alternatively you can modify the gRPC service with [GraphInterceptor](container.md#component-inspection).

## 7. Troubleshooting

| Problem | Solution |
|---------|----------|
| Generated classes not found | Check protobuf plugin configuration and run `generateProto` task |
| Connection refused | Verify `grpcClient.<ServiceName>.url` configuration |
| Interceptor not applied | Ensure `@Tag` annotation matches the service class |
