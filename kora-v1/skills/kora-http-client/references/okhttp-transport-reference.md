# OkHttp Transport Reference

Reference for [kora-http-client](../SKILL.md).

## Contents

- [Overview](#overview)
- [Setup](#setup)
- [Configuration](#configuration)
- [HTTP version](#http-version)
- [Per-client configuration](#per-client-configuration)
- [OkHttpConfigurer](#okhttpconfigurer)
- [Telemetry](#telemetry)
- [Proxy](#proxy)
- [Troubleshooting](#troubleshooting)

---

## Overview

OkHttp is the recommended transport for Kora HTTP clients. It supports HTTP/1.1, HTTP/2, and HTTP/3 and GZip. The implementation is written in Kotlin and pulls in the corresponding dependencies. Alternatives are `http-client-async` (AsyncHttpClient) and `http-client-jdk` (JDK native client).

---

## Setup

```groovy
dependencies {
    koraBom platform("ru.tinkoff.kora:kora-parent:1.2.17")

    annotationProcessor "ru.tinkoff.kora:annotation-processors"

    implementation "ru.tinkoff.kora:http-client-ok"
    implementation "ru.tinkoff.kora:json-module"
}
```

```java
@KoraApp
public interface Application extends OkHttpClientModule, JsonModule { }
```

```kotlin
@KoraApp
interface Application : OkHttpClientModule, JsonModule
```

---

## Configuration

Common transport settings live under `httpClient`, OkHttp-specific ones under `httpClient.ok`. These are the keys described by `OkHttpClientConfig` and `HttpClientConfig` (default/example values shown).

```hocon
httpClient {
  ok {
    followRedirects = true       # follow HTTP redirects
    httpVersion = "HTTP_1_1"     # HTTP_1_1, HTTP_2, HTTP_3
  }
  connectTimeout = "5s"          # time to establish a connection
  readTimeout = "2m"             # time to read the response
  useEnvProxy = false            # use HTTP_PROXY/HTTPS_PROXY/NO_PROXY env vars
  proxy {
    host = "localhost"
    port = 8090
    user = "user"
    password = "password"
    nonProxyHosts = [ "host1", "host2" ]
  }
  telemetry {
    logging {
      enabled = false
      mask = "***"
      maskQueries = [ ]
      maskHeaders = [ "authorization", "cookie", "set-cookie" ]
      pathTemplate = true
    }
    metrics {
      enabled = true
      slo = [ 1, 10, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000, 30000, 60000, 90000 ]
    }
    tracing { enabled = true }
  }
}
```

YAML form:

```yaml
httpClient:
  ok:
    followRedirects: true
    httpVersion: "HTTP_1_1"
  connectTimeout: "5s"
  readTimeout: "2m"
  telemetry:
    logging:
      enabled: false
      maskHeaders: [ "authorization", "cookie", "set-cookie" ]
    metrics:
      enabled: true
    tracing:
      enabled: true
```

Metrics default to `true` and tracing to `true`; logging defaults to `false`.

---

## HTTP version

| Value | Description |
|-------|-------------|
| `HTTP_1_1` | HTTP/1.1, maximum compatibility |
| `HTTP_2` | HTTP/2, multiplexing and header compression |
| `HTTP_3` | HTTP/3 over QUIC (requires server support) |

The JDK transport supports only `HTTP_1_1` and `HTTP_2`; AsyncHttpClient does not expose this key.

---

## Per-client configuration

Each `@HttpClient` resolves its own config block (by `configPath` or lower-case class name). The `url` key is required there; common keys can be overridden per client.

```hocon
httpClient {
  usersApi {
    url = "http://users-service:8080"
    requestTimeout = "10s"
    telemetry { logging { enabled = true } }
  }
  ordersApi {
    url = "http://orders-service:8080"
    requestTimeout = "30s"
  }
}
```

```java
@HttpClient(configPath = "httpClient.usersApi")
public interface UsersApiClient { }

@HttpClient(configPath = "httpClient.ordersApi")
public interface OrdersApiClient { }
```

`requestTimeout` spans the entire call (DNS, connect, write, server processing, read), including redirects/retries.

---

## OkHttpConfigurer

For advanced OkHttp tuning, register an `OkHttpConfigurer` component. It receives the `OkHttpClient.Builder` and must return a builder.

```java
@Component
public final class ConnectionPoolConfigurer implements OkHttpConfigurer {

    @Override
    public OkHttpClient.Builder configure(OkHttpClient.Builder builder) {
        return builder.connectionPool(new ConnectionPool(50, 5, TimeUnit.MINUTES));
    }
}
```

```kotlin
@Component
class ConnectionPoolConfigurer : OkHttpConfigurer {
    override fun configure(builder: OkHttpClient.Builder): OkHttpClient.Builder {
        return builder.connectionPool(ConnectionPool(50, 5, TimeUnit.MINUTES))
    }
}
```

---

## Telemetry

### Logging

```hocon
httpClient {
  telemetry {
    logging {
      enabled = true
      mask = "***"
      maskQueries = [ "password", "token" ]
      maskHeaders = [ "authorization", "cookie", "set-cookie" ]
      pathTemplate = true   # log the path template, except for TRACE level which logs the full path
    }
  }
}
```

### Metrics

```hocon
httpClient {
  telemetry {
    metrics {
      enabled = true
      slo = [ 1, 10, 50, 100, 200, 500, 1000, 2000, 5000 ]   # ms buckets for the DistributionSummary
    }
  }
}
```

Metrics are described in the Metrics module documentation.

### Tracing

```hocon
httpClient {
  telemetry {
    tracing {
      enabled = true
      attributes = { "peer.service" = "users-service" }
    }
  }
}
```

---

## Proxy

Environment-driven:

```hocon
httpClient { useEnvProxy = true }   # HTTP_PROXY, HTTPS_PROXY, NO_PROXY
```

Explicit:

```hocon
httpClient {
  proxy {
    host = "proxy.example.com"
    port = 8080
    user = "proxyuser"
    password = "proxypass"
    nonProxyHosts = [ "localhost", "127.0.0.1" ]
  }
}
```

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Connection timeout | Raise `connectTimeout`; verify the target is reachable |
| HTTP/2 not used | Set `httpClient.ok.httpVersion = "HTTP_2"` and confirm server support |
| Too many open connections | Tune the connection pool via an `OkHttpConfigurer` |
| Credentials leaking into logs | Add header/query names to `maskHeaders` / `maskQueries` |

---

## See also

- [declarative-client-reference](declarative-client-reference.md)
- [async-client-reference](async-client-reference.md)
- [interceptors-reference](interceptors-reference.md)
