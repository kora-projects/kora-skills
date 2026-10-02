---
name: kora-soap-client
description: "SOAP/WSDL clients in Kora 2.x — wsdl2java (Apache CXF, jakarta) generates jakarta.jws @WebService interfaces, then the Kora processor generates $Service_SoapClientImpl and a @Module $Service_SoapClientModule from artifact io.koraframework:soap-client. Covers SoapClientModule, SoapServiceConfig under soapClient.<PortType> (url, timeout, telemetry), synchronous generated methods, SoapFaultException / SoapInvalidHttpResponseException / SoapRequestMarshallingException, typed @WebFault exceptions, WS-Security via SoapEnvelopeProcessorsUtils.wssAuth and the tagged Function<SoapEnvelope, SoapEnvelope> envelope processor, MTOM/XOP multipart responses, RPC Holder out-params, and the Gradle wsdl2java wiring for Java (annotation-processors) and Kotlin (KSP symbol-processors). Use when consuming an external SOAP service from a Kora service, or when a generated SOAP client is missing from the graph."
license: Apache-2.0
metadata:
  kora-version: "2.x"
---

# Kora SOAP Client — compile-time clients from WSDL

> **Kora sub-skill — obey the [kora-v2 meta rules](../../SKILL.md) on every task:** **R0** ground the workspace on Kora 2.0 refs before starting (framework source at tag `2.0.0.RC2` + `kora-examples` at `migration/2.0` + Kora 2.0 docs at koraframework.io/v2, which trail the source; 1.x `kora-docs` pages are never an authority) · **R1** read this sub-skill before writing code · **R2** Kora 2.0 APIs only — no Spring/Micronaut/Quarkus, no Kora 1.x APIs, no invented annotations or config keys · **R3** journal any incorrect Kora usage. Add comments/Javadoc only if asked.

**Version:** Kora 2.0 (`io.koraframework`, `2.0.0.RC2` on Maven Central) | **Java:** 25 | **Kotlin:** 2.4 + KSP | **Gradle:** 9+ | **JAX-WS:** jakarta only

Kora consumes SOAP services through **compile-time generated clients**. There are two generators in
the chain and they are easy to confuse:

1. **`wsdl2java` (Apache CXF)** turns a `.wsdl` into `jakarta.jws.@WebService` interfaces plus JAXB
   model classes. This is a build-tool step, not a Kora one.
2. **The Kora processor** (`annotation-processors` for Java, `symbol-processors` for Kotlin) sees
   `@WebService` and generates, into the same package, an implementation `$<Iface>_SoapClientImpl`
   and a `@Module` interface `$<Iface>_SoapClientModule` that registers it in the graph.

You then inject the **WSDL interface** — never the generated `$…_SoapClientImpl` — and call its
methods. Calls are **synchronous**: the generated method overrides the interface method verbatim and
returns the WSDL payload type. Kora 2.0 has no reactive, `CompletionStage` or `suspend` SOAP contract.

## Migrating from Kora 1.x

The 2.0 side of every row is verified in the Kora 2.0 framework source; the 1.x side describes what
the Kora 1.x documentation specified for `ru.tinkoff.kora:soap-client`.

| Kora 1.x | Kora 2.x |
|---|---|
| BOM `ru.tinkoff.kora:kora-parent` | **`io.koraframework:kora-bom`** |
| `ru.tinkoff.kora:soap-client` | **`io.koraframework:soap-client`** |
| `ru.tinkoff.kora.soap.client.common.*` | **`io.koraframework.soap.client.common.*`** |
| `javax.jws.WebService` **or** `jakarta.jws.WebService` | **`jakarta.jws.WebService` only** — the 2.0 processors register no `javax` variant. `useJakarta = true` is mandatory |
| `<method>Async` returning `CompletionStage<T>` on `$…_SoapClientImpl` | **removed** — only the interface's own synchronous methods are generated |
| `InvalidHttpResponseSoapException` | **`SoapInvalidHttpResponseException`** |
| `SoapRequestMarshallingException` / `SoapResponseUnmarshallingException` extend `RuntimeException` | both now **extend `SoapException`** — one `catch (SoapException)` covers them |
| `SoapEnvelopeProcessors.wssAuth(...)` | **`SoapEnvelopeProcessorsUtils.wssAuth(...)`** in `…common.util` |
| Envelope processor wired by **replacing** the generated client factory with your own `@Module` method | the generated module **injects** it: declare a `@Tag(Iface.class) Function<SoapEnvelope, SoapEnvelope>` component and nothing else |
| `SoapClientLogger.SoapClientLoggerBodyMapper` `@DefaultComponent` for masking logged bodies | **removed** — subclass `DefaultSoapClientLoggerFactory` instead ([telemetry reference](references/telemetry-reference.md)) |
| `telemetry.metrics.enabled` defaults to `true` | **defaults to `false`** — nothing is reported until you switch it on |
| Metrics `kora.soap.client.*` (counter + `DistributionSummary`) | one Timer **`rpc.client.call.duration`** with OpenTelemetry semconv tags |
| `implementation("…:soap-client") { exclude group: "jakarta.xml" … }` | **drop every exclude** — 2.0 `soap-client` declares the jakarta/JAXB stack itself as `api` at pinned versions |
| `annotationProcessor "…:soap-client-annotation-processor"` listed separately | already inside `io.koraframework:annotation-processors` (KSP: `symbol-processors`) |
| `logging.level { … }` | **`logging.levels { … }`** |

`SoapRequestExecutor` and `SoapResult` are **not new and not renamed** — 1.x had both, with the same
`Success(Object body)` / `Failure(SoapFault fault, String faultMessage)` shape. Only the package moved.

## Key facts (do not get these wrong)

- **Inject the WSDL interface** (`SimpleService`), not `$SimpleService_SoapClientImpl`. The generated
  module registers the impl *as the interface type*, with `@DefaultComponent`.
- **`SoapResult` never reaches your code.** It is the return type of the internal
  `SoapRequestExecutor.call(SoapEnvelope)`. The generated method unwraps it: `Success` → cast to the
  declared return type; `Failure` → throw a typed `@WebFault` exception or `SoapFaultException`.
- **The config section is the `@WebService` name, which is the WSDL `portType` name** — not the
  `wsdl:service` name. `<wsdl:portType name="SimpleService">` → `soapClient.SimpleService`.
  Resolution order: `@WebService.name` → `serviceName` → `portName` → interface simple name.
- **`url` is required**; `timeout` defaults to `60s`. There are no other top-level keys.
- **`telemetry.logging.enabled` and `telemetry.metrics.enabled` default to `false`**;
  `telemetry.tracing.enabled` defaults to `true`.
- **`@KoraApp` needs `SoapClientModule` plus an HTTP transport module and a config module.** The
  generated `$…_SoapClientModule` is `@Module`-annotated and picked up automatically — do **not**
  extend it from `@KoraApp`.
- **No Jakarta-EE `javax.*`.** `javax.jws.*`, `javax.xml.ws.*` and `javax.xml.bind.*` play no part in
  Kora 2.0 SOAP generation. Two **JDK** `javax` packages are still correct and must not be
  "migrated": `javax.xml.namespace.QName` (the type of `SoapFault.getFaultcode()`) and
  `javax.xml.parsers.*`.
- **No Kora `Context`.** There is no `Context` type in Kora 2.0 at all; the SOAP client propagates
  telemetry through `ScopedValue`, which needs nothing from you.
- **After changing `packageName` (or any package rename), run `clean` + `--no-build-cache`** — see
  [Stale generated sources](#stale-generated-sources).

## Quick Start

### 1. `gradle.properties`

`2.0.0.RC2` is the Kora 2.0 release on Maven Central. `2.0.0-SNAPSHOT` is the `master` development
line and needs the snapshot repository — do not put it in a new project.

```properties
koraVersion=2.0.0.RC2
```

### 2. Build file

Full, ready-to-copy build files live in `assets/` —
[`build.gradle.template`](assets/build.gradle.template) (Java) and
[`build.gradle.kts.template`](assets/build.gradle.kts.template) (Kotlin/KSP). The Kora-specific parts:

```groovy
plugins {
    id "java"
    id "application"
    id "com.github.bjornvester.wsdl2java" version "2.0.2"
}

// the koraBom configuration and the extendsFrom wiring are in the template
dependencies {
    koraBom platform("io.koraframework:kora-bom:$koraVersion")
    annotationProcessor "io.koraframework:annotation-processors"

    implementation "io.koraframework:soap-client"
    implementation "io.koraframework:http-client-ok"   // any transport; supplies HttpClient
    implementation "io.koraframework:config-hocon"
    implementation "io.koraframework:logging-logback"
}

wsdl2java {
    cxfVersion = "4.0.2"
    wsdlDir = layout.projectDirectory.dir("src/main/resources/wsdl")
    useJakarta = true
    markGenerated = true
    verbose = false
    packageName = "com.example.generated.soap"
    generatedSourceDir.set(layout.buildDirectory.dir("generated/sources/wsdl2java/java"))
    includesWithOptions = [
            "**/simple-service.wsdl": ["-wsdlLocation", "https://example.com/simple/service?wsdl"],
    ]
}
```

- **`useJakarta = true` is mandatory.** With `false` the plugin emits `javax.jws` annotations and the
  Kora processor generates nothing at all — no error, just a missing component later.
- **Never add excludes** to `soap-client`. It declares `jakarta.xml.ws-api`, `jakarta.xml.bind-api`,
  `org.glassfish.jaxb:jaxb-runtime` and `commons-codec` as `api` dependencies on purpose.
- **Kotlin needs one extra line** so KSP can see the Java sources wsdl2java produced:
  `sourceSets.main { java.srcDir(layout.buildDirectory.dir("generated/sources/wsdl2java/java")) }`.
- Coordinates, transports and the `cxfVersion` question are covered in
  [architecture-reference.md → Gradle wiring](references/architecture-reference.md#7-gradle-wiring).

### 3. WSDL and generation

Put the contract under `src/main/resources/wsdl/`, then:

```shell
./gradlew wsdl2java     # CXF: WSDL -> @WebService interface + JAXB classes
./gradlew classes       # Kora processor: -> $Iface_SoapClientImpl + $Iface_SoapClientModule
```

### 4. Application graph

```java
import io.koraframework.application.graph.KoraApplication;
import io.koraframework.common.annotation.KoraApp;
import io.koraframework.config.hocon.HoconConfigModule;
import io.koraframework.http.client.ok.OkHttpClientModule;
import io.koraframework.logging.logback.LogbackModule;
import io.koraframework.soap.client.common.SoapClientModule;

@KoraApp
public interface Application extends
        HoconConfigModule,
        LogbackModule,
        OkHttpClientModule,
        SoapClientModule {

    static void main(String[] args) {
        KoraApplication.run(ApplicationGraph::graph);
    }
}
```

```kotlin
@KoraApp
interface Application : HoconConfigModule, LogbackModule, OkHttpClientModule, SoapClientModule

fun main() {
    KoraApplication.run { ApplicationGraph.graph() }
}
```

`SoapClientModule` contributes exactly one component — the `DefaultSoapClientTelemetryFactory`. The
client and its config come from the generated `$…_SoapClientModule`.

### 5. Configuration

```hocon
soapClient.SimpleService {
  url = ${SOAP_CLIENT_URL}
  timeout = 30s
  telemetry.logging.enabled = true
}

httpClient {
  connectTimeout = 5s
  readTimeout = 2m
}

logging.levels {
  "root": "WARN"
  "io.koraframework": "INFO"
  "com.example.generated.soap.SimpleService.request": "TRACE"
  "com.example.generated.soap.SimpleService.response": "TRACE"
}
```

`soapClient.<Service>.timeout` becomes the per-request timeout on the outgoing HTTP request; the
transport-level `httpClient.connectTimeout` / `readTimeout` are separate and belong to the HTTP
client module.

### 6. Inject and call

```java
import io.koraframework.common.annotation.Component;
import com.example.generated.soap.SimpleService;
import com.example.generated.soap.TestRequest;

@Component
public final class CustomerService {

    private final SimpleService service;

    public CustomerService(SimpleService service) {
        this.service = service;
    }

    public String lookup(String id) {
        var request = new TestRequest();
        request.setVal1(id);

        var response = service.test(request);
        return response.getVal1();
    }
}
```

```kotlin
@Component
class CustomerService(private val service: SimpleService) {

    fun lookup(id: String): String? {
        val request = TestRequest().apply { val1 = id }
        return service.test(request).val1
    }
}
```

The `@WebService` interface is Java generated by CXF, so from Kotlin its types are platform types —
assign the result to a nullable type (`String?`) rather than fighting the compiler with `!!`.

## Generated artefacts

For `com.example.generated.soap.SimpleService` the processor writes into the same package:

| Generated type | What it is |
|---|---|
| `$SimpleService_SoapClientImpl` | `implements SimpleService`. One `SoapRequestExecutor` field per `@WebMethod`. Public constructors `(HttpClient, SoapClientTelemetryFactory, SoapServiceConfig)` and `(…, Function<SoapEnvelope, SoapEnvelope>)`, both `throws JAXBException` |
| `$SimpleService_SoapClientModule` | `@Module` interface, auto-discovered. `simpleService_SoapConfig(...)` → `@DefaultComponent @Tag(SimpleService.class) SoapServiceConfig`, read from `config.get("soapClient.SimpleService")`. `simpleService_SoapClientImpl(...)` → `@DefaultComponent SimpleService` |

Full signatures, the request/response mapping, RPC `Holder` out-parameters and MTOM/XOP handling:
[architecture-reference.md](references/architecture-reference.md).

## Configuration reference

`io.koraframework.soap.client.common.SoapServiceConfig`, section `soapClient.<ServiceName>`:

| Key | Required | Default | Notes |
|---|---|---|---|
| `url` | **yes** | — | Endpoint the `POST` goes to. Missing → graph build fails on a null config value |
| `timeout` | no | `60s` | Applied as the HTTP request timeout |
| `telemetry.logging.enabled` | no | **`false`** | |
| `telemetry.metrics.enabled` | no | **`false`** | |
| `telemetry.metrics.slo` | no | `TelemetryConfig.MetricsConfig.DEFAULT_SLO` | Timer SLO buckets |
| `telemetry.metrics.tags` | no | `{}` | Extra tags on `rpc.client.call.duration` |
| `telemetry.tracing.enabled` | no | **`true`** | |
| `telemetry.tracing.attributes` | no | `{}` | Extra span attributes |

There is **no** `soapClient.<Service>.headers`, `retries`, or `keepAlive` key — anything beyond the
table above belongs to the HTTP transport module or does not exist.

## Errors

Everything is unchecked and, except for typed WSDL faults, rooted at `SoapException`:

```
RuntimeException
└── io.koraframework.soap.client.common.exception.SoapException
    ├── SoapFaultException                 // SOAP Fault with no matching typed fault; getFault()
    ├── SoapInvalidHttpResponseException   // HTTP status other than 200 or 500
    ├── SoapRequestMarshallingException    // JAXB marshalling of the request failed
    └── SoapResponseUnmarshallingException // JAXB unmarshalling of the response failed
```

A `<wsdl:fault>` produces a typed `@WebFault` exception that the operation `throws` directly; it does
**not** extend `SoapException`, so catch it first. Transport failures arrive as a `SoapException`
wrapping an `HttpClientConnectionException` / `HttpClientTimeoutException` — there is no bare
`ConnectException` to catch.

**→ [error-handling-reference.md](references/error-handling-reference.md)**

## Telemetry

| Signal | Shape |
|---|---|
| Metric | Timer **`rpc.client.call.duration`**, tags `rpc.system.name=soap`, `rpc.service`, `rpc.method`, `server.address`, `server.port`, `http.response.status_code`, `error.type`, `soap.fault.code`, `system.config`, `system.name.simple`, `system.name.canonical` |
| Span | `SOAP <service> <method>`, `SpanKind.CLIENT`, attributes `rpc.*`, `server.*`, `http.response.status_code`, plus `soap.fault.code` / `soap.fault.actor` on a fault |
| Logs | Loggers `<interface FQN>.request` and `<interface FQN>.response`. Envelope bodies are logged **only at `TRACE`** |

**→ [telemetry-reference.md](references/telemetry-reference.md)**

## Customising the request envelope (WS-Security)

The generated module injects an optional, tagged envelope processor. Declare it and it is applied to
every request envelope before marshalling — no need to replace the generated client.

```java
import io.koraframework.common.annotation.Module;
import io.koraframework.common.annotation.Tag;
import io.koraframework.soap.client.common.envelope.SoapEnvelope;
import io.koraframework.soap.client.common.util.SoapEnvelopeProcessorsUtils;
import java.util.function.Function;

@Module
public interface SoapEnvelopeModule {

    @Tag(SimpleService.class)
    default Function<SoapEnvelope, SoapEnvelope> simpleServiceEnvelopeProcessor(SoapCredentialsConfig config) {
        return SoapEnvelopeProcessorsUtils.wssAuth(config.username(), config.password());
    }
}
```

`wssAuth` adds a WS-Security `UsernameToken` with a **plaintext** `PasswordText`, so it is only safe
over TLS. For anything else, write your own `Function<SoapEnvelope, SoapEnvelope>` that appends to
`envelope.getHeader().getAny()`. `@Module` interfaces are discovered automatically — do not also
extend this one from `@KoraApp`.

## Stale generated sources

`wsdl2java` does not delete its previous output, and the Gradle build-cache key does not account for
a changed `packageName`. After a rename, the old and the new package sit in the same source set and
the compiler reports errors in files you never wrote, all under `build/generated/`:

```
error: package ru.tinkoff.kora.example.generated.soap does not exist
```

```shell
./gradlew clean --continue
./gradlew classes testClasses --continue --no-build-cache
```

Never edit anything under `build/generated/` and never add a dependency to "find" the missing 1.x
package — both hide the real problem.

## Troubleshooting

| Problem | Cause / fix |
|---|---|
| `No component found for dependency … SimpleService` | The Kora processor never ran on the generated interface. Check `annotationProcessor "io.koraframework:annotation-processors"` (Kotlin: `ksp "io.koraframework:symbol-processors"`), and that `wsdl2java` ran before `compileJava` |
| Interface generated, but no `$…_SoapClientImpl` | `useJakarta = false` (or omitted) → `javax.jws` annotations, which 2.0 ignores. Set `useJakarta = true` and rebuild after `clean` |
| Kotlin: interface exists but KSP does not see it | Missing `sourceSets.main { java.srcDir(…wsdl2java/java) }` |
| `No component found for dependency … SoapClientTelemetryFactory` | `SoapClientModule` is not in the `@KoraApp` interface list |
| `No component found for dependency … HttpClient` | No transport module: add `OkHttpClientModule` / `ApacheHttpClientModule` / `JdkHttpClientModule` |
| `ConfigValueException: … null at path: 'ROOT.soapClient.SimpleService.url'` | `url` missing, or the section name is not the `portType` name (a `wsdl:service` name such as `SimpleServiceService` will not match) |
| `Multiple components match dependency: … SimpleService` | Two non-default providers of the interface. The generated one is `@DefaultComponent` and yields to yours, so a collision means you declared it **twice** — or mark one fallback `@DefaultComponent` |
| Phantom `package ru.tinkoff.kora… does not exist` under `build/generated` | [Stale generated sources](#stale-generated-sources) |
| No metrics / no request logs | Both default to `false`; set `telemetry.metrics.enabled` / `telemetry.logging.enabled` per client |
| Logging enabled but no XML in the logs | Bodies are `TRACE`-only; raise `<interface FQN>.request` / `.response` to `TRACE` |
| `'test' overrides nothing` in Kotlin | The Kotlin type does not match the Java contract — keep the CXF-generated Java interface as the contract and do not re-declare it in Kotlin |

## Reference Files

| File | Description |
|---|---|
| [architecture-reference.md](references/architecture-reference.md) | Codegen chain, generated signatures, request/response mapping, RPC `Holder`, MTOM/XOP, Gradle wiring, testing |
| [error-handling-reference.md](references/error-handling-reference.md) | Exception hierarchy, typed `@WebFault` faults, `SoapFault` API, transport failures, resilience |
| [telemetry-reference.md](references/telemetry-reference.md) | `rpc.client.call.duration` tags, span shape, logger names and levels, body masking, custom factories |

| Asset | Description |
|---|---|
| [build.gradle.template](assets/build.gradle.template) | Java: BOM, `annotation-processors`, `wsdl2java` |
| [build.gradle.kts.template](assets/build.gradle.kts.template) | Kotlin: BOM, KSP `symbol-processors`, `wsdl2java`, `java.srcDir` |

## Common Pitfalls

- **`useJakarta = false`** — silently produces a `javax.jws` interface that Kora 2.0 does not process.
- **Injecting `$SimpleService_SoapClientImpl`** — inject the WSDL interface; the impl is an
  implementation detail and its name starts with `$`.
- **Expecting `SoapResult` from a generated method** — it is internal to `SoapRequestExecutor`.
- **Reactive / `suspend` / `CompletionStage` SOAP methods** — none exist in 2.0; do not enable
  wsdl2java's async method generation either, the generated mapping casts the SOAP body straight to
  the declared return type.
- **1.x jakarta/glassfish `exclude` blocks carried over** — they strip the JAXB runtime that 2.0
  `soap-client` deliberately ships.
- **Using the `wsdl:service` name as the config section** — it is the `portType` name.
- **`logging.level`** — the key is `logging.levels`.
- **Assuming metrics are on** — `metrics.enabled` was `true` in 1.x and is `false` in 2.0.
- **Editing `build/generated` to fix phantom `ru.tinkoff.kora` errors** — `clean` + `--no-build-cache`.
