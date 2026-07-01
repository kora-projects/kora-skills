# Liveness and Readiness Probes

**Kora Version:** 1.2.x

This reference covers liveness and readiness probes in Kora, including configuration and custom probe implementations.

---

## Overview

Kora does **NOT** have a separate `probes` module. The `ru.tinkoff.kora:probes` artifact does not exist.

Liveness and readiness probes are **built into the HTTP server module** (`UndertowHttpServerModule`, `VertxHttpServerModule`, etc.) and exposed on the private HTTP port.

---

## Configuration

```hocon
httpServer {
  publicApiHttpPort = 8080   # Business traffic
  privateApiHttpPort = 8085  # Metrics, probes, admin
  
  # Probe endpoints (defaults shown)
  privateApiHttpLivenessPath = "/system/liveness"
  privateApiHttpReadinessPath = "/system/readiness"
}
```

---

## Default Probes

### Liveness Probe

**Endpoint:** `/system/liveness` (configurable via `privateApiHttpLivenessPath`)

**Behavior:** Returns `200 OK` if the application is running.

**Use case:** Kubernetes liveness probe — restart the pod if this fails.

```bash
curl -i http://localhost:8085/system/liveness
# HTTP/1.1 200 OK
```

### Readiness Probe

**Endpoint:** `/system/readiness` (configurable via `privateApiHttpReadinessPath`)

**Behavior:** Returns `200 OK` if all registered `ReadinessProbe` components report ready. Returns `503 Service Unavailable` if any probe fails.

**Use case:** Kubernetes readiness probe — remove from load balancer if this fails.

```bash
curl -i http://localhost:8085/system/readiness
# HTTP/1.1 200 OK  (all probes ready)
# HTTP/1.1 503 Service Unavailable  (one or more probes failed)
```

---

## Custom Probes

### ReadinessProbe

Implement `ru.tinkoff.kora.http.server.common.ReadinessProbe` for custom readiness checks:

```java
import ru.tinkoff.kora.common.Component;
import ru.tinkoff.kora.http.server.common.ReadinessProbe;

@Component
public final class DatabaseReadinessProbe implements ReadinessProbe {
    private final JdbcDataSource dataSource;
    
    public DatabaseReadinessProbe(JdbcDataSource dataSource) {
        this.dataSource = dataSource;
    }
    
    @Override
    public Result check() {
        try (Connection conn = dataSource.getConnection()) {
            if (conn.isValid(1)) {
                return Result.success();
            } else {
                return Result.failure("Database connection invalid");
            }
        } catch (SQLException e) {
            return Result.failure("Database connection failed: " + e.getMessage());
        }
    }
}
```

**Result types:**
- `Result.success()` — Probe is ready
- `Result.failure(String reason)` — Probe is not ready (reason logged)

### LivenessProbe

Implement `ru.tinkoff.kora.http.server.common.LivenessProbe` for custom liveness checks (rarely needed):

```java
import ru.tinkoff.kora.common.Component;
import ru.tinkoff.kora.http.server.common.LivenessProbe;

@Component
public final class HealthCheckProbe implements LivenessProbe {
    @Override
    public Result check() {
        // Custom health check logic
        if (isHealthy()) {
            return Result.success();
        } else {
            return Result.failure("Unhealthy state");
        }
    }
    
    private boolean isHealthy() {
        // Check memory, threads, external dependencies
        return true;
    }
}
```

---

## Probe Aggregation

The readiness endpoint aggregates **all** registered `ReadinessProbe` components:

- If **all** probes return `Result.success()` → readiness returns `200 OK`
- If **any** probe returns `Result.failure()` → readiness returns `503 Service Unavailable`

Failed probe reasons are logged but not exposed in the HTTP response (security).

---

## Kubernetes Configuration

Example Kubernetes probe configuration:

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: my-service
spec:
  containers:
  - name: app
    image: my-service:latest
    ports:
    - containerPort: 8080  # Public traffic
    - containerPort: 8085  # Metrics/probes
    livenessProbe:
      httpGet:
        path: /system/liveness
        port: 8085
      initialDelaySeconds: 30
      periodSeconds: 10
      timeoutSeconds: 5
      failureThreshold: 3
    readinessProbe:
      httpGet:
        path: /system/readiness
        port: 8085
      initialDelaySeconds: 5
      periodSeconds: 5
      timeoutSeconds: 3
      failureThreshold: 1
```

**Key settings:**
- `port: 8085` — probes on private port, not public
- `initialDelaySeconds` — give app time to start
- `failureThreshold: 1` for readiness — fail fast on dependency issues

---

## Common Probe Patterns

### Database Connectivity

```java
@Component
public final class DatabaseReadinessProbe implements ReadinessProbe {
    private final JdbcDataSource dataSource;
    
    @Override
    public Result check() {
        try (Connection conn = dataSource.getConnection()) {
            conn.isValid(1);
            return Result.success();
        } catch (SQLException e) {
            return Result.failure("Database unavailable: " + e.getMessage());
        }
    }
}
```

### Kafka Consumer Lag

```java
@Component
public final class KafkaLagProbe implements ReadinessProbe {
    private final KafkaConsumer<String, String> consumer;
    
    @Override
    public Result check() {
        Map<TopicPartition, Long> lag = getConsumerLag();
        long maxLag = lag.values().stream().max(Long::compareTo).orElse(0L);
        
        if (maxLag > 10000) {
            return Result.failure("Consumer lag too high: " + maxLag);
        }
        return Result.success();
    }
}
```

### External Dependency Check

```java
@Component
public final class ExternalApiProbe implements ReadinessProbe {
    private final HttpClient httpClient;
    
    @Override
    public Result check() {
        try {
            HttpResponse response = httpClient.get("/health").execute();
            if (response.statusCode() == 200) {
                return Result.success();
            } else {
                return Result.failure("External API returned " + response.statusCode());
            }
        } catch (Exception e) {
            return Result.failure("External API unavailable: " + e.getMessage());
        }
    }
}
```

---

## Debugging

### Probe Returns 503

Check application logs for probe failure messages:

```
Readiness probe failed: Database connection failed: Connection refused
Readiness probe failed: Consumer lag too high: 15000
```

### Probe Not Called

Verify:
1. `@Component` annotation on probe class
2. Probe class is in component scan path
3. HTTP server module is in `@KoraApp extends ...`
4. Private port is configured and accessible

---

## See Also

- [Metrics Module](../SKILL.md) — Micrometer metrics on private port
- [HTTP Server Configuration](../../kora-http-server/references/configuration-reference.md) — `privateApiHttpPort`, paths
