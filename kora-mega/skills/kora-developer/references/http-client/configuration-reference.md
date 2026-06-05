# OkHttp Configuration Reference

**Source:** [.kora-agent/kora-docs/mkdocs/docs/en/documentation/http-client.md](.kora-agent/kora-docs/mkdocs/docs/en/documentation/http-client.md)  
**Examples:** `.kora-agent/kora-examples/kora-java-http-client-apache/`

**Important:** This is a reference for all available options. **You do not need to configure every parameter** — most values have sensible defaults. Only specify the ones you need to change.

## Global Configuration (`httpClient.ok`)

```hocon
httpClient {
    ok {
        followRedirects = true  # true — automatically follow redirects
        httpVersion = "HTTP_1_1"  # HTTP version: HTTP_1_1, HTTP_2, HTTP_3
    }
    connectTimeout = "5s"  # Connection establishment timeout
    readTimeout = "2m"  # Response read timeout
    useEnvProxy = false  # false — use environment variables (HTTP_PROXY, HTTPS_PROXY)
    
    proxy {
        host = "localhost"  # Proxy server host
        port = 8090  # Proxy server port
        user = "user"  # Username (optional)
        password = "password"  # Password (optional)
        nonProxyHosts = ["host1", "host2", "*.internal"]  # Hosts that bypass the proxy
    }
    
    telemetry {
        logging {
            enabled = false  # false — request/response logging
            mask = "***"  # Mask for sensitive data
            maskQueries = []  # Query parameters to mask
            maskHeaders = ["authorization", "cookie", "set-cookie"]  # Headers to mask
            pathTemplate = true  # true — path template in logs (/users/{id})
        }
        metrics {
            enabled = true  # true — metrics collection
            slo = [1, 10, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000, 30000, 60000, 90000]  # SLO buckets (ms)
        }
        tracing { enabled = true }  # true — distributed tracing
    }
}
```

## Client Configuration (`httpClient.{clientName}`)

Each client can override the global settings:

```hocon
httpClient {
    someClient {
        url = "https://localhost:8090"  # Base URL for the client
        requestTimeout = "10s"  # Request timeout (overrides readTimeout)
        followRedirects = false  # Do not follow redirects
        
        telemetry {
            logging { enabled = false }  # Disable logging for this client
            metrics { enabled = true }
            tracing { enabled = true }
        }
    }
    
    externalApi {
        url = "https://api.external.com"
        requestTimeout = "30s"
    }
}
```

## Method Configuration (`httpClient.{clientName}.{methodName}`)

Fine-grained configuration for individual client methods:

```hocon
httpClient {
    someClient {
        hello {
            requestTimeout = "10s"
            telemetry { logging { enabled = true }; metrics { enabled = true }; tracing { enabled = true } }
        }
        slowOperation {
            requestTimeout = "5m"  # Extended timeout for slow operations
        }
    }
}
```

## Configuration Priority

| Level | Path | Priority |
|---------|------|-----------|
| 1 | `httpClient.{clientName}.{methodName}` | Highest (method-level) |
| 2 | `httpClient.{clientName}` | Medium (client-level) |
| 3 | `httpClient.ok` / `httpClient.connectTimeout` | Base (global) |

## Option Descriptions

| Option | Default | Description |
|-------|---------|----------|
| `httpClient.ok.followRedirects` | true | Automatically follow redirects |
| `httpClient.ok.httpVersion` | "HTTP_1_1" | HTTP version: HTTP_1_1, HTTP_2, HTTP_3 |
| `httpClient.connectTimeout` | "5s" | Connection establishment timeout |
| `httpClient.readTimeout` | "2m" | Response read timeout |
| `httpClient.useEnvProxy` | false | Use environment variables for proxy |
| `httpClient.proxy.host/port` | - | Proxy server host/port |
| `httpClient.proxy.user/password` | - | Proxy credentials (optional) |
| `httpClient.proxy.nonProxyHosts` | [] | Hosts that bypass the proxy |
| `httpClient.telemetry.logging.enabled` | false | Request/response logging |
| `httpClient.telemetry.logging.mask` | "***" | Mask for sensitive data |
| `httpClient.telemetry.logging.maskQueries` | [] | Query parameters to mask |
| `httpClient.telemetry.logging.maskHeaders` | [auth, cookie] | Headers to mask |
| `httpClient.telemetry.logging.pathTemplate` | true | Path template in logs (/users/{id}) |
| `httpClient.telemetry.metrics.enabled` | true | Metrics collection |
| `httpClient.telemetry.metrics.slo` | [1..90000] | SLO buckets (ms) |
| `httpClient.telemetry.tracing.enabled` | true | Distributed tracing |

## OkHttpConfigurer

To customize the `OkHttpClient.Builder`, use the `OkHttpConfigurer` interface:

```java
@Component
public class SomeConfigurer implements OkHttpConfigurer {
    @Override
    public OkHttpClient.Builder configure(OkHttpClient.Builder builder) {
        // Customization: interceptors, connection pool, SSL settings, retry logic
        return builder;
    }
}
```

### Example: CustomLoggingInterceptor

```java
@Component
public class CustomOkHttpConfigurer implements OkHttpConfigurer {
    private final CustomLoggingInterceptor loggingInterceptor;
    
    public CustomOkHttpConfigurer(CustomLoggingInterceptor loggingInterceptor) {
        this.loggingInterceptor = loggingInterceptor;
    }
    
    @Override
    public OkHttpClient.Builder configure(OkHttpClient.Builder builder) {
        return builder
            .addInterceptor(loggingInterceptor)
            .connectionPool(new ConnectionPool(10, 5, TimeUnit.MINUTES))
            .retryOnConnectionFailure(true);
    }
}
```

### When to Use OkHttpConfigurer

| Use Case | Example |
|----------|--------|
| Custom interceptors | Logging, retry, circuit breaker |
| Connection pool | Pool size and keep-alive tuning |
| SSL settings | Custom SSLContext, TrustManager |
| Retry logic | Custom retry logic |
