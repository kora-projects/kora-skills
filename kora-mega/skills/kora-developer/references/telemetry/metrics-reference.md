# Kora Metrics Reference

**Source:** [.kora-agent/kora-docs/mkdocs/docs/en/documentation/metrics.md](.kora-agent/kora-docs/mkdocs/docs/en/documentation/metrics.md)  
**Examples:** `.kora-agent/kora-examples/kora-java-metrics-micrometer/`

Full reference for metrics in Kora applications.

## Modules

### MetricsModule

**Dependency:** `ru.tinkoff.kora:micrometer-module`

**Module:** `ru.tinkoff.kora.micrometer.module.MetricsModule`

**Configuration:**
```hocon
metrics {
    opentelemetrySpec = "V120"  # or "V123"
}
```

**Important:** Use the `ru.tinkoff.kora:micrometer-module` dependency — it includes all necessary integrations with Kora modules (HTTP, gRPC, Database, Kafka, Cache, etc.) and automatically configures metrics for them.

## HTTP Server Metrics

### http.server.request.duration

**Type:** DistributionSummary  
**Description:** Duration of HTTP request processing  
**Tags:**
- `method` — HTTP method (GET, POST, etc.)
- `status` — HTTP status code (200, 404, 500)
- `route` — HTTP route template (/api/users/{id})
- `scheme` — Scheme (http, https)

### http.server.active.requests

**Type:** Gauge  
**Description:** Number of active HTTP requests  
**Tags:**
- `method` — HTTP method
- `route` — HTTP route template

## HTTP Client Metrics

### http.client.request.duration

**Type:** DistributionSummary  
**Description:** Duration of HTTP client requests  
**Tags:**
- `method` — HTTP method
- `status` — HTTP status code
- `server` — Server name

### http.client.active.requests

**Type:** Gauge  
**Description:** Number of active HTTP client requests  
**Tags:**
- `method` — HTTP method
- `server` — Server name

## gRPC Metrics

### rpc.server.duration

**Type:** DistributionSummary  
**Description:** Duration of gRPC server calls  
**Tags:**
- `service` — gRPC service (e.g., helloworld.Greeter)
- `method` — gRPC method (e.g., SayHello)
- `status` — gRPC status (OK, CANCELLED, ERROR)

### rpc.server.requests.per.rpc

**Type:** DistributionSummary  
**Description:** Number of messages per RPC call (server)  
**Tags:**
- `service`, `method`, `status`

### rpc.server.responses.per.rpc

**Type:** DistributionSummary  
**Description:** Number of responses per RPC call (server)  
**Tags:**
- `service`, `method`, `status`

### rpc.client.duration

**Type:** DistributionSummary  
**Description:** Duration of gRPC client calls  
**Tags:**
- `service`, `method`, `status`

## Database Metrics

### db.client.request.duration

**Type:** DistributionSummary  
**Description:** Duration of database operations  
**Tags:**
- `pool` — Connection pool name
- `operation` — Operation type (select, insert, update, delete)

### db.client.active.connections

**Type:** Gauge  
**Description:** Number of active connections  
**Tags:**
- `pool` — Connection pool name

## Kafka Metrics

### kafka.consumer.records.consumed

**Type:** Counter  
**Description:** Number of consumed records  
**Tags:**
- `topic` — Topic
- `group.id` — Consumer group

### kafka.producer.records.sent

**Type:** Counter  
**Description:** Number of sent records  
**Tags:**
- `topic` — Topic

## JVM Metrics (automatic)

### jvm.gc.pause

**Type:** DistributionSummary  
**Description:** GC pause duration  
**Tags:**
- `cause` — GC cause (End of Minor GC, End of Major GC)
- `action` — Action (no gc, end of minor collection)

### jvm.memory.used

**Type:** Gauge  
**Description:** Memory usage  
**Tags:**
- `area` — Area (heap, nonheap)
- `id` — Area ID (eden, survivor, old gen, metaspace)

### jvm.memory.committed

**Type:** Gauge  
**Description:** Committed memory

### jvm.memory.max

**Type:** Gauge  
**Description:** Maximum memory

### jvm.threads.live

**Type:** Gauge  
**Description:** Number of live threads

### jvm.threads.daemon

**Type:** Gauge  
**Description:** Number of daemon threads

### jvm.threads.blocked

**Type:** Gauge  
**Description:** Number of blocked threads

### jvm.threads.waiting

**Type:** Gauge  
**Description:** Number of waiting threads

### process.cpu.usage

**Type:** Gauge  
**Description:** Process CPU usage (0–1)

### process.files.open

**Type:** Gauge  
**Description:** Number of open files

### process.files.max

**Type:** Gauge  
**Description:** Maximum number of files

### process.uptime

**Type:** Gauge  
**Description:** Process uptime (ms)

## Prometheus Integration

### Setup

**build.gradle:**
```groovy
implementation "io.micrometer:micrometer-registry-prometheus:1.12.+"
```

**application.conf:**
```hocon
httpServer {
    privateApiHttpMetricsPath = "/metrics"
}
```

### Prometheus Config

```yaml
scrape_configs:
  - job_name: 'my-service'
    scrape_interval: 15s
    metrics_path: '/metrics'
    static_configs:
      - targets: ['localhost:8080']
```

### Example Request

```bash
curl http://localhost:8080/metrics
```

**Response:**
```
# HELP http_server_request_duration_seconds Duration of HTTP requests
# TYPE http_server_request_duration_seconds summary
http_server_request_duration_seconds{method="GET",route="/api/users",status="200",quantile="0.5"} 0.012
http_server_request_duration_seconds{method="GET",route="/api/users",status="200",quantile="0.9"} 0.025
http_server_request_duration_seconds{method="GET",route="/api/users",status="200",quantile="0.99"} 0.045
```

## Metrics Customization

### Common Tags

```java
@Module
public interface MetricsConfigModule {
    default PrometheusMeterRegistryInitializer commonTagsInit() {
        return registry -> {
            registry.config()
                .commonTags("service", "my-service")
                .commonTags("environment", "production")
                .commonTags("version", "1.0.0");
            return registry;
        };
    }
}
```

### Custom Metrics

```java
@Component
public class CustomMetrics {
    private final MeterRegistry registry;

    public CustomMetrics(MeterRegistry registry) {
        this.registry = registry;
        
        // Counter
        registry.counter("custom.counter", "tag", "value");
        
        // Timer
        Timer timer = Timer.builder("custom.timer")
            .tag("tag", "value")
            .register(registry);
        
        // Gauge
        Gauge.builder("custom.gauge", this, CustomMetrics::getValue)
            .tag("tag", "value")
            .register(registry);
    }

    private double getValue() {
        return 42.0;
    }
}
```

### DistributionSummary

```java
@Component
public class RequestMetrics {
    private final DistributionSummary summary;

    public RequestMetrics(MeterRegistry registry) {
        this.summary = DistributionSummary.builder("request.size")
            .tag("endpoint", "api")
            .register(registry);
    }

    public void record(long size) {
        summary.record(size);
    }
}
```

### Metrics Caching via Map (Kora pattern)

**Why caching is needed:**

Micrometer's internal implementation uses a `ConcurrentHashMap` to store metrics. Each call to `builder.register()` involves:
1. Looking up an existing metric by the name + tags combination
2. Creating a new one if not found
3. Synchronization for thread safety

Under high load (thousands of calls/sec) repeated access to Micrometer's internal maps becomes a bottleneck. Caching metric instances in your own `ConcurrentHashMap` eliminates this overhead — you access your map (fast) rather than Micrometer's internal structure (slower due to locking).

**Pattern from `MicrometerCacheMetrics`:**

```java
public final class CustomMetricsWithCache {
    
    // Key for caching metrics
    record MetricKey(String cacheName, String operation, String status) {}
    
    // Cache Timers to avoid repeated registration
    private final ConcurrentHashMap<MetricKey, Timer> durations = new ConcurrentHashMap<>();
    private final ConcurrentHashMap<MetricKey, Counter> counters = new ConcurrentHashMap<>();
    
    private final MeterRegistry meterRegistry;
    
    public CustomMetricsWithCache(MeterRegistry meterRegistry) {
        this.meterRegistry = meterRegistry;
    }
    
    public void recordOperation(String cacheName, String operation, long durationNanos, boolean success) {
        // Build the key
        var status = success ? "success" : "failed";
        var key = new MetricKey(cacheName, operation, status);
        
        // Get or create the metric (computeIfAbsent is atomic)
        var timer = durations.computeIfAbsent(key, k -> {
            var builder = Timer.builder("custom.operation.duration")
                .tag("cache", k.cacheName())
                .tag("operation", k.operation())
                .tag("status", k.status());
            
            return builder.register(meterRegistry);
        });
        
        // Record the value
        timer.record(durationNanos, TimeUnit.NANOSECONDS);
    }
    
    public void incrementCounter(String cacheName, String operation, String type) {
        var key = new MetricKey(cacheName, operation, type);
        
        var counter = counters.computeIfAbsent(key, k -> {
            var builder = Counter.builder("custom.operation.count")
                .tag("cache", k.cacheName())
                .tag("operation", k.operation())
                .tag("type", k.type());
            
            return builder.register(meterRegistry);
        });
        
        counter.increment();
    }
}
```

**Key principles:**

1. **Key contains only dynamic tags** — `MetricKey` should include only values that change at runtime (cacheName, operation, status). Do not include static tags (environment, version, service) in the key — add them via `commonTags` at the registry level.

2. **Tag collisions** — if two metrics are created with the same name and tags but different values (e.g., `userId="user1"` and `userId="user2"`), Micrometer will discard the second one. Therefore the map key must contain only tags with a bounded set of values (low cardinality).

3. **`record` for keys** — immutable record classes are ideal as Map keys (correct hashCode/equals)

4. **`computeIfAbsent` is atomic** — safe for concurrent access, creates the metric only once

5. **Create each metric once** — reusing from the Map reduces overhead from accessing Micrometer's internal structures

6. **Separate Timer and Counter** — different metric types for different purposes, separate maps for each type

**When to use Map caching:**

- High-throughput operations (thousands of calls per second)
- Metrics with multiple tag combinations (low cardinality)
- Custom business-operation metrics

**When NOT to use:**

- Simple counters without tags
- Metrics with unique per-call tags (userId, requestId, sessionId) — leads to memory leaks and collisions
- Low-throughput operations (< 100 calls/sec)

- Simple counters without tags
- Metrics with unique per-call tags (leads to memory leaks)

## Best Practices

1. **Use common tags** to add service, environment, version
2. **Configure retention** for long-term storage (Prometheus, Thanos, Mimir)
3. **Use histograms** for latency metrics (p50, p90, p99)
4. **Avoid high-cardinality tags** (userId, requestId)
5. **Monitor JVM metrics** to understand resource usage
