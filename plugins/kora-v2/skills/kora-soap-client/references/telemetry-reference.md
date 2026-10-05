# SOAP Client Telemetry — Kora 2.0

The metric name, the span name and the log format all changed in Kora 2.0. Nothing on this page
matches the 1.x `kora.soap.client.*` model.

---

## 1. Defaults — the silent-failure trap

`SoapClientTelemetryConfig` extends the framework-wide `TelemetryConfig`, so the SOAP client inherits
its defaults:

| Key | Default | Was in 1.x |
|---|---|---|
| `telemetry.logging.enabled` | **`false`** | `false` |
| `telemetry.metrics.enabled` | **`false`** | `true` |
| `telemetry.tracing.enabled` | `true` | `true` |

**Metrics are off by default in 2.0.** A dashboard that worked on 1.x goes blank after the migration
with no error anywhere. Enable them per client:

```hocon
soapClient.SimpleService {
  url = ${SOAP_CLIENT_URL}
  telemetry {
    logging.enabled = true
    metrics {
      enabled = true
      slo = [1, 10, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000, 30000, 60000, 90000]
      tags { environment = "production", team = "payments" }
    }
    tracing {
      enabled = true
      attributes { criticality = "high" }
    }
  }
}
```

`slo` defaults to `TelemetryConfig.MetricsConfig.DEFAULT_SLO` (the fourteen buckets shown above, in
milliseconds). `tags` and `attributes` default to `{}`.

`DefaultSoapClientTelemetryFactory` short-circuits to `NoopSoapClientTelemetry` when tracing, metrics
**and** logging are all effectively off — no observation object is even allocated. Tracing counts as
off when no `Tracer` is on the graph, metrics when no `MeterRegistry` is, regardless of the flags.

So enabling a flag is necessary but not sufficient: metrics also need `MetricsModule`
(`io.koraframework:micrometer-module`) and tracing needs `OpentelemetryTracingModule`
(`io.koraframework:opentelemetry-tracing`) plus an exporter in the `@KoraApp`.

---

## 2. Metrics

One meter, a Micrometer `Timer`:

| | |
|---|---|
| Name | **`rpc.client.call.duration`** (2.0.0.RC1: `rpc.client.duration`, renamed in RC2 by #972) |
| Type | `Timer`, recorded in nanoseconds, with `serviceLevelObjectives(slo)` |
| Recorded | Once per call, in `SoapClientObservation.end()` — success, fault and exception alike |

Tags, in the order the implementation adds them:

| Tag | Source | Value when absent |
|---|---|---|
| `rpc.system.name` | constant | `soap` |
| `rpc.service` | `@WebService` name | — |
| `rpc.method` | `@WebMethod.operationName` or the Java method name | — |
| `server.address` | host of `soapClient.<Service>.url` | — |
| `server.port` | explicit port, else `80`/`443` by scheme | — |
| `http.response.status_code` | HTTP status | `-1` when the call never got a response |
| `error.type` | thrown exception's canonical name; if the call ended in a SOAP fault with a detail, the **detail class's** canonical name | `""` |
| `soap.fault.code` | `SoapFault.getFaultcode().toString()` | `""` |
| `system.config` | the config path, e.g. `soapClient.SimpleService` | — |
| `system.name.simple` | interface simple name, e.g. `SimpleService` | — |
| `system.name.canonical` | interface FQN | — |
| *(your `telemetry.metrics.tags`)* | config | — |

There is **no** request counter and **no** separate fault counter — a Timer carries the count. There
is no `soap_service` / `soap_method` / `status` tag; those were the 1.x names.

Useful queries (Prometheus naming applies `_` for `.` and appends the unit):

```promql
sum(rate(rpc_client_call_duration_seconds_count{rpc_system_name="soap"}[5m])) by (rpc_service, rpc_method)
sum(rate(rpc_client_call_duration_seconds_count{rpc_system_name="soap", error_type!=""}[5m])) by (rpc_service, error_type)
histogram_quantile(0.99, sum(rate(rpc_client_call_duration_seconds_bucket{rpc_system_name="soap"}[5m])) by (le, rpc_method))
```

---

## 3. Tracing

| | |
|---|---|
| Span name | **`SOAP <service> <method>`** — space-separated, e.g. `SOAP SimpleService test` |
| Kind | `SpanKind.CLIENT` |
| Parent | `io.opentelemetry.context.Context.current()` |

Attributes set at span start: `rpc.service`, `rpc.method`, `rpc.system.name=soap`, `system.config`,
`system.name.simple`, `system.name.canonical`, `server.address`, and `server.port` when it resolves
(a URL with no port and an unknown scheme leaves it unset). Then, as the call proceeds:

| Event | Effect on the span |
|---|---|
| HTTP response received | `http.response.status_code` |
| SOAP fault | status `ERROR`, `soap.fault.code`, `soap.fault.actor` |
| Exception | `recordException(e)`, `error.type` = canonical class name, status `ERROR` |
| Clean finish | status `OK` |

Context propagation runs through `ScopedValue` (`Observation.VALUE`, `OpentelemetryContext.VALUE`)
inside `SoapRequestExecutor.call`. Kora 2.0 has no `Context` type to create, pass or clear — code
migrated from 1.x should delete every `Context.current()` / `Context.Reactive` reference.

---

## 4. Logging

`telemetry.logging.enabled = true` activates `DefaultSoapClientLoggerFactory`, which creates **two**
SLF4J loggers per client, named after the `@WebService` interface's fully-qualified name:

```
com.example.generated.soap.SimpleService.request
com.example.generated.soap.SimpleService.response
```

Level behaviour, per logger:

| Effective level | What is logged |
|---|---|
| below `INFO` | nothing — the logger returns immediately |
| `INFO` | the event with its key-values, no payload |
| `DEBUG` | same, emitted at `DEBUG` |
| `TRACE` | same, **plus the full XML envelope** |

So the SOAP payload appears only at `TRACE`. Configure it through the Kora logging config — the key
is `logging.levels` (it was `logging.level` in 1.x):

```hocon
logging.levels {
  "root": "WARN"
  "io.koraframework": "INFO"
  "com.example.generated.soap.SimpleService.request": "TRACE"
  "com.example.generated.soap.SimpleService.response": "TRACE"
}
```

Structured fields on each event:

| Event | Message | Key-values |
|---|---|---|
| Request | `SoapService requesting` | `clientConfigPath`, `soapMethod`, `soapService`; `soapRequestBody` at `TRACE` |
| Success | `SoapService received response` | the same three, `soapStatus=success`; `soapResponseBody` at `TRACE` |
| Fault | `SoapService received 'failure'` | `soapStatus=failure`, `soapFaultCode`, `soapFaultActor` — always at `INFO` |
| Exception | `SoapService received 'failure'` | `soapStatus=failure`, `exceptionType` — always at `INFO` |

Fault and error events are emitted at `INFO` regardless of how high the logger is turned up; only the
request/response events follow the ladder.

---

## 5. Masking logged payloads

Kora 1.x had a `SoapClientLogger.SoapClientLoggerBodyMapper` `@DefaultComponent`. **It does not exist
in 2.0.** The seam is now `DefaultSoapClientLoggerFactory`, which `SoapClientModule` injects as
`@Nullable` — supply your own and it is used instead of the built-in `INSTANCE`:

```java
import io.koraframework.common.annotation.Component;
import io.koraframework.soap.client.common.telemetry.impl.DefaultSoapClientLoggerFactory;
import io.koraframework.soap.client.common.telemetry.impl.DefaultSoapClientTelemetry;

@Component
public class MaskingSoapClientLoggerFactory extends DefaultSoapClientLoggerFactory {

    @Override
    public DefaultSoapClientLogger create(DefaultSoapClientTelemetry.TelemetryContext context) {
        var requestLog = LoggerFactory.getLogger(context.clientCanonicalName() + ".request");
        var responseLog = LoggerFactory.getLogger(context.clientCanonicalName() + ".response");
        return new MaskingLogger(requestLog, responseLog, context);
    }

    static final class MaskingLogger extends DefaultSoapClientLogger {

        MaskingLogger(Logger requestLog, Logger responseLog,
                      DefaultSoapClientTelemetry.TelemetryContext context) {
            super(requestLog, responseLog, context);
        }

        @Override
        protected String prepareRequestBodyForLog(byte[] requestXml) {
            return "<masked/>";
        }

        @Override
        protected String prepareResponseBodyForLog(byte[] xml) {
            return "<masked/>";
        }
    }
}
```

`prepareRequestBodyForLog` / `prepareResponseBodyForLog` are `protected` on
`DefaultSoapClientLoggerFactory.DefaultSoapClientLogger` precisely for this. The equivalent hook for
metrics is `DefaultSoapClientMetricsFactory`, injected the same way.

Both factories are used by **every** SOAP client in the application — there is no per-service
override at this level.

---

## 6. Replacing telemetry wholesale

The contracts, all in `io.koraframework.soap.client.common.telemetry`:

```java
public interface SoapClientTelemetryFactory {
    SoapClientTelemetry get(String clientConfigPath,
                            String clientCanonicalName,
                            SoapClientTelemetryConfig config,
                            SoapMethodDescriptor descriptor,
                            String url);
}

public interface SoapClientTelemetry {
    SoapClientObservation observe(SoapEnvelope requestEnvelope);
}

public interface SoapClientObservation extends Observation {
    void observeRequest(SoapEnvelope requestEnvelope);
    void observeRequestXml(byte[] requestXml);
    void observeHttpResponse(HttpClientResponse httpClientResponse);
    void observeResponseBody(byte[] body);
    void observeFailure(SoapResult.Failure result);
    void observeResult(Object body);
}
```

`SoapClientModule` provides `DefaultSoapClientTelemetryFactory` as a `@DefaultComponent`, so a
`@Component` of type `SoapClientTelemetryFactory` replaces it outright. Prefer subclassing
`DefaultSoapClientTelemetryFactory` (override `build(...)`) over a from-scratch implementation —
`SoapMethodDescriptor(serviceClass, service, method, soapAction)` and the `Observation` lifecycle
(`end()` must always run) are easy to get wrong.

---

## 7. Checklist

- [ ] `telemetry.metrics.enabled = true` per client — the 2.0 default is `false`
- [ ] `MetricsModule` in the `@KoraApp` when metrics are wanted; `OpentelemetryTracingModule` plus an exporter for spans
- [ ] Dashboards query `rpc_client_call_duration_*` with `rpc_system_name="soap"`, not `kora_soap_client_*` (nor the RC1 `rpc_client_duration_*`)
- [ ] Alerts filter on `error_type != ""` / `soap_fault_code != ""`, not on a `status` tag
- [ ] `logging.levels`, not `logging.level`
- [ ] Envelope bodies need `TRACE` on `<interface FQN>.request` / `.response`
- [ ] Payload masking implemented before turning `TRACE` on in an environment with real data
