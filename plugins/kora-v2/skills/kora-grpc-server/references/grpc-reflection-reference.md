# gRPC Server Reflection Reference

**Source:** `.kora-agent/kora-docs/mkdocs/docs/en/documentation/grpc-server.md`

## Contents

1. Overview
2. Dependency
3. Configuration
4. Using grpcurl
5. Using BloomRPC
6. Using Postman
7. Production Considerations
8. Troubleshooting
9. Complete Example

## 1. Overview

gRPC Server Reflection provides information about publicly available gRPC services on the server and helps clients at runtime build RPC requests and responses without pre-compiled service information.

**Use cases:**
- `grpcurl` CLI tool for testing
- BloomRPC, Postman gRPC debugging
- Dynamic client generation
- Service discovery

## 2. Dependency

=== ":fontawesome-brands-java: `Java`"
```groovy
dependencies {
    implementation "io.grpc:grpc-services:1.74.0"
}
```

=== ":simple-kotlin: `Kotlin`"
```kotlin
dependencies {
    implementation("io.grpc:grpc-services:1.74.0")
}
```

## 3. Configuration

Enable reflection in server configuration:

=== ":material-code-json: `HOCON`"
```hocon
grpcServer {
  reflectionEnabled = true
}
```

=== ":simple-yaml: `YAML`"
```yaml
grpcServer:
  reflectionEnabled: true
```

## 4. Using grpcurl

### List Services

```bash
grpcurl -plaintext localhost:9090 list
```

Output:
```
UserService
UserStreamingService
grpc.reflection.v1alpha.ServerReflection
```

### List Methods

```bash
grpcurl -plaintext localhost:9090 list UserService
```

Output:
```
UserService.CreateUser
UserService.GetUser
UserService.UpdateUser
UserService.DeleteUser
```

### Describe Service

```bash
grpcurl -plaintext localhost:9090 describe UserService
```

Output:
```json
{
  "name": "UserService",
  "method": [
    {
      "name": "CreateUser",
      "inputType": ".CreateUserRequest",
      "outputType": ".UserResponse"
    },
    {
      "name": "GetUser",
      "inputType": ".GetUserRequest",
      "outputType": ".UserResponse"
    }
  ]
}
```

### Describe Message

```bash
grpcurl -plaintext localhost:9090 describe CreateUserRequest
```

Output:
```json
{
  "name": "CreateUserRequest",
  "field": [
    {"name": "name", "number": 1, "label": "TYPE_STRING"},
    {"name": "email", "number": 2, "label": "TYPE_STRING"}
  ]
}
```

### Invoke RPC

```bash
grpcurl -plaintext -d '{"name": "John", "email": "john@example.com"}' \
    localhost:9090 UserService/CreateUser
```

Output:
```json
{
  "id": "123e4567-e89b-12d3-a456-426614174000",
  "name": "John",
  "email": "john@example.com",
  "createdAt": "2026-06-15T10:30:00Z"
}
```

### List with Filtering

```bash
# List only services matching pattern
grpcurl -plaintext localhost:9090 list UserService*
```

## 5. Using BloomRPC

1. Install BloomRPC: `npm install -g bloomrpc`
2. Open BloomRPC
3. Enter server address: `localhost:9090`
4. Enable reflection (auto-detected)
5. Services appear in left panel
6. Fill request JSON and click "Invoke"

## 6. Using Postman

1. Create new gRPC request
2. Enter server address: `localhost:9090`
3. Click "Use reflection" to auto-discover services
4. Select service and method
5. Fill message and send

## 7. Production Considerations

### Security

Reflection exposes your service schema. Consider disabling in production:

```hocon
grpcServer {
  // Enable only in dev/test environments
  reflectionEnabled = ${REFLECTION_ENABLED:false}
}
```

The reflection service is registered automatically once the flag is enabled and the `io.grpc:grpc-services` dependency is on the classpath.

### Performance

Reflection has minimal runtime overhead; it only adds the `io.grpc:grpc-services` dependency to the build.

## 8. Troubleshooting

| Problem | Solution |
|---------|----------|
| **UNIMPLEMENTED: unknown service** | Ensure `grpc-services` dependency is present |
| **Reflection not working** | Check `reflectionEnabled = true` in config |
| **Services not listed** | Verify handlers are `@Component` and extend `*ImplBase` |
| **grpcurl connection refused** | Check server is running on correct port |

## 9. Complete Example

```hocon
# application.conf
grpcServer {
  port = 8090
  reflectionEnabled = true

  telemetry {
    logging {
      enabled = true
    }
  }
}
```

```bash
# List services
grpcurl -plaintext localhost:8090 list

# Invoke a method (full name is <proto package>.<service>/<Method>)
grpcurl -plaintext \
  -d '{"user_id": "123"}' \
  localhost:8090 ru.tinkoff.kora.example.grpc.UserService/GetUser
```
