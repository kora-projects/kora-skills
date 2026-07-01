---
name: kora-soap-client
description: "SOAP client integration in Kora Framework. Compile-time generated SOAP clients from JAX-WS annotations (@WebService), WSDL-to-Java (wsdl2java), SoapClientModule, telemetry. Use when integrating with external SOAP services or consuming WSDL-based web services."
---

# Kora SOAP Client

**Compile-time generated SOAP clients** for external SOAP web services. Zero runtime reflection — all code generated at compile time from JAX-WS annotations (`@WebService`).

**Key features:**
- WSDL-first workflow via `wsdl2java` Gradle plugin
- Full telemetry (logging, metrics, tracing)
- Reactive methods (`*Reactive` → `Mono<T>`)
- `javax.jws` and `jakarta.jws` support

---

## Quick Start

### 1. Dependencies

```groovy
plugins {
    id "com.github.bjornvester.wsdl2java" version "2.0.2"
}

dependencies {
    koraBom platform("ru.tinkoff.kora:kora-parent:1.2.16")
    annotationProcessor "ru.tinkoff.kora:annotation-processors"
    annotationProcessor "ru.tinkoff.kora:soap-client-annotation-processor"
    implementation "ru.tinkoff.kora:soap-client"
    implementation "ru.tinkoff.kora:http-client-jdk"  // Required
}
```

### 2. WSDL Setup

Place WSDL in `src/main/resources/wsdl/`:

```groovy
wsdl2java {
    cxfVersion = "4.0.2"
    wsdlDir = layout.projectDirectory.dir("src/main/resources/wsdl")
    useJakarta = true
    markGenerated = true
    packageName = "com.example.generated.soap"
    generatedSourceDir.set(layout.buildDirectory.dir("generated/sources/wsdl2java/java"))
    includesWithOptions = [
        "**/simple-service.wsdl": ["-wsdlLocation", "https://api.example.com/service?wsdl"]
    ]
}
```

### 3. Application Graph

```java
@KoraApp
public interface Application extends
        HoconConfigModule,
        LogbackModule,
        JdkHttpClientModule,
        SoapClientModule {

    static void main(String[] args) {
        KoraApplication.run(ApplicationGraph::graph);
    }
}
```

### 4. Configuration

```hocon
soapClient {
  SimpleService {
    url = ${CUSTOMER_SERVICE_URL}
    timeout = 30s
  }
}
```

### 5. Usage

```java
@Component
public final class MyService {

    private final SimpleService soapClient;

    public MyService(SimpleService soapClient) {
        this.soapClient = soapClient;
    }

    public void call() {
        TestRequest req = new TestRequest();
        req.setVal1("value");
        TestResponse resp = soapClient.test(req);  // Blocking
    }
}
```

**Reactive:**
```java
@Component
public final class MyAsyncService {
    private final SimpleServiceImpl client;  // Impl for reactive

    public Mono<TestResponse> callAsync() {
        return client.testReactive(new TestRequest());
    }
}
```

---

## Architecture

```
WSDL → wsdl2java → @WebService interfaces → Kora AP → *Impl.java → DI
```

**Generated:**
- `SimpleService.java` — interface with `@WebService`
- `SimpleServiceImpl.java` — Kora SOAP client implementation
- DTOs: `TestRequest.java`, `TestResponse.java`

**→ [Architecture & Code Generation](references/architecture-reference.md)**

---

## Configuration

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| `url` | **Yes** | — | Service endpoint URL |
| `timeout` | No | `60s` | Request timeout |
| `telemetry.logging.enabled` | No | `false` | Request/response logging |
| `telemetry.metrics.enabled` | No | `true` | Micrometer metrics |
| `telemetry.tracing.enabled` | No | `true` | OpenTelemetry tracing |

**Service name:** From `@WebService.name` or WSDL `<wsdl:portType name="...">`

**→ [Full Configuration Reference](references/configuration-reference.md)**

---

## Telemetry

### Logging
```hocon
soapClient.SimpleService.telemetry.logging.enabled = true
logging.level."com.example.generated.SimpleService" = "DEBUG"
```

### Metrics
- **Name:** `kora.soap.client`
- **Tags:** `soap_service`, `soap_method`, `status`
- **Types:** Counter (requests), DistributionSummary (duration)

### Tracing
- **Span:** `SOAP <ServiceName>.<MethodName>`
- **Attributes:** `soap.service`, `soap.method`, `soap.url`

**→ [Full Telemetry Details](references/telemetry-reference.md)**

---

## Error Handling

```java
try {
    soapClient.test(request);
} catch (SoapException e) {
    // SOAP fault from server
    SoapFault fault = e.getSoapFault();
} catch (SoapRequestMarshallingException e) {
    // Request serialization error
} catch (InvalidHttpResponseSoapException e) {
    // Non-SOAP response
}
```

| Error | Cause | Solution |
|-------|-------|----------|
| `SoapException` | Server fault | Handle business error |
| `SoapRequestMarshallingException` | Invalid DTO | Validate fields |
| `InvalidHttpResponseSoapException` | Non-SOAP response | Check URL/network |
| `ConnectException` | Service unreachable | Check URL/firewall |

**→ [Full Error Handling Guide](references/error-handling-reference.md)**

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| No factory found for SoapService | Add `SoapClientModule` to `@KoraApp` |
| Client not generated | Check `wsdl2java` config, run `./gradlew clean build` |
| Connection refused | Verify URL, check service is running |
| Invalid SOAP response | Enable logging, check response in logs |

---

## References

| Resource | Link |
|----------|------|
| Official Docs | `.kora-agent/kora-docs/mkdocs/docs/en/documentation/soap-client.md` |
| Java Example | `.kora-agent/kora-examples/examples/java/kora-java-soap-client/` |
| Kotlin Example | `.kora-agent/kora-examples/examples/kotlin/kora-kotlin-soap-client/` |
| WSDL Plugin | https://github.com/bjornvester/wsdl2java-gradle-plugin |

---

## When to Use

**Use this skill when:**
- Integrating with legacy SOAP services
- Consuming WSDL-based external APIs
- Migrating from Spring WS to Kora
- Need compile-time validated SOAP client

**Not covered:**
- SOAP server (Kora is client-only)
- Custom SOAP handlers/interceptors
- MTOM/attachments (limited support)
