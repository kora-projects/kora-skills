# gRPC Server Reflection Reference — Kora 2.0

**Framework source (authority):** [`GrpcServerFactoryModule`](https://github.com/kora-projects/kora/blob/2.0.0.RC2/grpc/grpc-server/src/main/java/io/koraframework/grpc/server/GrpcServerFactoryModule.java) · [`GrpcServerConfig`](https://github.com/kora-projects/kora/blob/2.0.0.RC2/grpc/grpc-server/src/main/java/io/koraframework/grpc/server/GrpcServerConfig.java)
**Migrated example:** [`kora-java-guide-grpc-server-advanced-app`](https://github.com/kora-projects/kora-examples/tree/migration/2.0/guides/java/kora-java-guide-grpc-server-advanced-app) (`reflectionEnabled = true`)

## Contents

1. What Kora registers
2. Both halves are required
3. Dependency
4. Configuration
5. Using grpcurl
6. Using Postman
7. Production considerations
8. Troubleshooting

---

## 1. What Kora registers

```java
if (grpcServerConfig.reflectionEnabled()
        && isClassPresent("io.grpc.protobuf.services.ProtoReflectionServiceV1")) {
    builder.addService(ProtoReflectionServiceV1.newInstance());
}
```

Kora 2.0 registers the **v1** reflection service, `io.grpc.protobuf.services.ProtoReflectionServiceV1`
— the `grpc.reflection.v1.ServerReflection` protocol. Modern `grpcurl` and Postman negotiate v1 and
fall back to `v1alpha`; a very old client that only speaks `v1alpha` will not discover this server.

## 2. Both halves are required

Reflection turns on only when **both** conditions hold:

1. `grpcServer.reflectionEnabled = true`, and
2. `io.grpc.protobuf.services.ProtoReflectionServiceV1` is on the classpath.

The classpath probe is a `try { loadClass } catch (ClassNotFoundException)`. When the class is
missing the flag is **ignored with no log line and no error** — the server starts perfectly and
`grpcurl list` answers `UNIMPLEMENTED`. Setting the flag without adding `io.grpc:grpc-services` is
therefore a silent no-op, and it is the usual explanation for "reflection is enabled but does not
work".

## 3. Dependency

===! `Java`

```groovy
implementation "io.grpc:grpc-services:1.84.0"
```

=== `Kotlin`

```kotlin
implementation("io.grpc:grpc-services:1.84.0")
```

The version must be **`1.84.0`**, matching the `grpc-core` that arrives with
`io.koraframework:grpc-server`. `kora-bom` does not manage `io.grpc:*`, so nothing pins this for you
— see [grpc-server-reference.md](grpc-server-reference.md) §2.

## 4. Configuration

===! `HOCON`

```hocon
grpcServer {
  port = 8090
  reflectionEnabled = true      # default false
}
```

=== `YAML`

```yaml
grpcServer:
  port: 8090
  reflectionEnabled: true
```

Gate it per environment rather than hard-coding `true`:

```hocon
grpcServer {
  reflectionEnabled = false
  reflectionEnabled = ${?GRPC_REFLECTION_ENABLED}
}
```

The literal is the default; the `${?VAR}` line overrides it only when the variable is set.

## 5. Using grpcurl

```bash
# list services
grpcurl -plaintext localhost:8090 list

# list a service's methods
grpcurl -plaintext localhost:8090 list io.koraframework.example.grpc.UserService

# describe a service or a message
grpcurl -plaintext localhost:8090 describe io.koraframework.example.grpc.UserService
grpcurl -plaintext localhost:8090 describe .io.koraframework.example.grpc.CreateUserRequest

# invoke — the full method name is <proto package>.<Service>/<Method>
grpcurl -plaintext -d '{"user_id":"42"}' \
  localhost:8090 io.koraframework.example.grpc.UserService/GetUser

# with metadata, e.g. for an auth interceptor
grpcurl -plaintext -H 'authorization: my-api-key' -d '{}' \
  localhost:8090 io.koraframework.example.grpc.UserStreamingService/GetAllUsers
```

`list` includes `grpc.reflection.v1.ServerReflection` itself — seeing it is the quickest confirmation
that reflection is actually live.

Names are fully qualified with the `.proto` `package`, **not** the `java_package`. A service that
`grpcurl` cannot find under the name you expect is usually being addressed with the Java package.

Over TLS, drop `-plaintext`; the server uses TLS only when an untagged `ServerCredentials` component
is supplied ([grpc-server-reference.md](grpc-server-reference.md) §7.1).

## 6. Using Postman

1. New → gRPC Request.
2. Server URL `localhost:8090`.
3. Choose **Using server reflection** for the method definition.
4. Pick the service and method, fill the message, Invoke.

Add request metadata under the Metadata tab for interceptor-based auth.

## 7. Production considerations

Reflection publishes your full service and message schema to anyone who can open a connection. It
does not expose data, and the runtime cost is limited to the extra service registration — but the
schema itself is information.

- Keep `reflectionEnabled = false` on anything internet-facing.
- Enable it in dev/test, or in production only when the port is reachable solely from inside the
  cluster.
- Reflection is **not** authentication-aware by itself. A `ServerInterceptor` is global, so an
  auth interceptor that guards only `UserServiceGrpc.SERVICE_NAME` leaves the reflection service
  open. To protect it, match on `grpc.reflection.v1.ServerReflection` explicitly, or leave the flag
  off.

## 8. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `grpcurl list` → `UNIMPLEMENTED` | `grpc-services` absent (flag silently ignored) or `reflectionEnabled` not set | add `io.grpc:grpc-services:1.84.0` **and** set the flag |
| Reflection works, one service missing | that handler is not collected | untagged `@Component` extending `*Grpc.*ImplBase` |
| `Failed to dial target host` | wrong port, or TLS expected | default port is `8090`; drop/add `-plaintext` |
| Service name not found | addressed with the `java_package` | use the `.proto` `package` |
| Only some clients discover the service | an old client that speaks only `v1alpha` | Kora registers `ProtoReflectionServiceV1`; upgrade the client |
| `AbstractMethodError` after adding `grpc-services` | it was pinned below `1.84.0` | pin `1.84.0` |
