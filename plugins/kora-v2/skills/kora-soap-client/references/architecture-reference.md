# SOAP Client Architecture — Kora 2.0

How a WSDL becomes an injectable client, what exactly is generated, and how the generated code
behaves at runtime. Everything here is taken from the Kora 2.0 `soap-client`,
`soap-client-annotation-processor` and `soap-client-symbol-processor` modules.

---

## 1. The two-stage generation chain

```
src/main/resources/wsdl/simple-service.wsdl
        │
        │  ① wsdl2java  (Apache CXF 4.x, jakarta namespaces) — a build-tool step
        ▼
build/generated/sources/wsdl2java/java/
        com/example/generated/soap/SimpleService.java      @WebService interface
        com/example/generated/soap/TestRequest.java        JAXB model
        com/example/generated/soap/ObjectFactory.java      JAXB factory
        │
        │  ② Kora processor  (annotation-processors / symbol-processors)
        │     triggered by jakarta.jws.WebService
        ▼
build/generated/sources/annotationProcessor/…/com/example/generated/soap/
        $SimpleService_SoapClientImpl.java     implements SimpleService
        $SimpleService_SoapClientModule.java   @Module
        │
        │  ③ @KoraApp processor picks up every @Module interface in the compilation
        ▼
ApplicationGraph — SimpleService is injectable
```

Stage ③ is why `@KoraApp` never mentions `$SimpleService_SoapClientModule`: the `@KoraApp` processor
collects **all** `@Module`-annotated interfaces it sees in the round, and merges their components into
the graph. Extending the generated module from `@KoraApp` as well would declare the same components
twice.

The only Kora module you list yourself is `SoapClientModule`, and it contributes one component:

```java
public interface SoapClientModule {

    @DefaultComponent
    default DefaultSoapClientTelemetryFactory defaultSoapClientTelemetryFactory(
            @Nullable Tracer tracer,
            @Nullable MeterRegistry meterRegistry,
            @Nullable DefaultSoapClientLoggerFactory loggerFactory,
            @Nullable DefaultSoapClientMetricsFactory metricsFactory) { … }
}
```

Every parameter is `@Nullable`, so a service with neither Micrometer nor OpenTelemetry on the graph
still builds — telemetry simply degrades to no-op.

---

## 2. What `wsdl2java` produces

For `<wsdl:portType name="SimpleService">` in namespace `http://example.com/simple/service`:

```java
@WebService(targetNamespace = "http://example.com/simple/service", name = "SimpleService")
@XmlSeeAlso({ObjectFactory.class})
public interface SimpleService {

    @WebMethod(action = "http://example.com/simple/service/test")
    @WebResult(name = "TestResponse", targetNamespace = "…", partName = "response")
    TestResponse test(
        @WebParam(partName = "request", name = "TestRequest", targetNamespace = "…")
        TestRequest request
    ) throws TestError1Msg, TestError2Msg;
}
```

Three things on this interface drive Kora's generation:

| Element | Effect |
|---|---|
| `@WebService(name = …)` | Config section: `soapClient.SimpleService`. Falls back to `serviceName`, then `portName`, then the interface simple name |
| `@WebMethod(action = …)` | When non-empty, a `SOAPAction` HTTP header is sent. Empty → no header |
| `@WebMethod(operationName = …)` | The `method` recorded in telemetry and in the executor field name. Empty → the Java method name |
| `throws XMsg` where `XMsg` is `@WebFault` | The fault `detail` is matched against `XMsg.getFaultInfo()`'s type and that exception is thrown |
| `@XmlSeeAlso({ObjectFactory.class, …})` | Every listed class joins `JAXBContext.newInstance(...)`; `ObjectFactory` classes are also used to resolve `@RequestWrapper` / `@ResponseWrapper` accessors |

> The config section comes from the **`portType`** name, not from `<wsdl:service name="…">`. A WSDL
> commonly names them differently — `portType SimpleService` next to `service SimpleServiceService`.

---

## 3. What Kora generates

### 3.1 `$SimpleService_SoapClientModule`

Shape (annotations and body are exact; formatting is not byte-for-byte):

```java
@Module
public interface $SimpleService_SoapClientModule {

    @Tag(SimpleService.class)
    @DefaultComponent
    default SoapServiceConfig simpleService_SoapConfig(Config config,
                                                       ConfigValueMapper<SoapServiceConfig> mapper) {
        return mapper.mapOrThrow(config.get("soapClient.SimpleService"));
    }

    @DefaultComponent
    default SimpleService simpleService_SoapClientImpl(
            HttpClient httpClient,
            SoapClientTelemetryFactory telemetry,
            @Tag(SimpleService.class) SoapServiceConfig config,
            @Tag(SimpleService.class) @Nullable Function<SoapEnvelope, SoapEnvelope> envelopeProcessor) {
        try {
            return new $SimpleService_SoapClientImpl(httpClient, telemetry, config, envelopeProcessor);
        } catch (Exception e) {
            throw new IllegalStateException(
                "Kora internal error: failed to create generated SOAP client implementation", e);
        }
    }
}
```

Consequences worth internalising:

- The method prefix is the service name with a lower-cased first letter (`simpleService_…`).
- **The client is registered as the interface type.** Inject `SimpleService`.
- Both components are `@DefaultComponent`, so your own component of the same type/tag replaces them
  rather than colliding.
- `SoapServiceConfig` is registered **tagged with the interface class**. Any code that resolves it —
  a hand-built client, a test — must use `@Tag(SimpleService.class)`.
- The envelope processor is `@Nullable` and tagged, which is the supported customisation seam
  (§6). No component → `Function.identity()`.

The KSP generator emits the same two members with `envelopeProcessor: Function<SoapEnvelope, SoapEnvelope>?`.

### 3.2 `$SimpleService_SoapClientImpl`

Again the shape, not byte-for-byte output — the real file also carries `@Generated`, and the
null/emptiness checks around the fault detail are spelled out more defensively:

```java
public class $SimpleService_SoapClientImpl implements SimpleService {

    private final Function<SoapEnvelope, SoapEnvelope> envelopeProcessor;
    private final JAXBContext jaxb;
    private final SoapRequestExecutor testRequestExecutor;   // one per @WebMethod

    public $SimpleService_SoapClientImpl(HttpClient httpClient,
                                         SoapClientTelemetryFactory telemetry,
                                         SoapServiceConfig config) throws JAXBException {
        this(httpClient, telemetry, config, Function.identity());
    }

    public $SimpleService_SoapClientImpl(HttpClient httpClient,
                                         SoapClientTelemetryFactory telemetry,
                                         SoapServiceConfig config,
                                         Function<SoapEnvelope, SoapEnvelope> envelopeProcessor)
            throws JAXBException {
        this.jaxb = JAXBContext.newInstance(
            io.koraframework.soap.client.common.envelope.ObjectFactory.class,
            com.example.generated.soap.ObjectFactory.class);
        this.envelopeProcessor = envelopeProcessor != null ? envelopeProcessor : Function.identity();
        this.testRequestExecutor = new SoapRequestExecutor(
            httpClient,
            telemetry,
            new JakartaSoapEnvelopeMapper(jaxb),
            config,
            "soapClient.SimpleService",
            new SoapMethodDescriptor("com.example.generated.soap.SimpleService",
                                     "SimpleService", "test",
                                     "http://example.com/simple/service/test"));
    }

    @Override
    public TestResponse test(TestRequest request) throws TestError1Msg, TestError2Msg {
        var __requestEnvelope = this.envelopeProcessor.apply(new SoapEnvelope(request));
        var __response = this.testRequestExecutor.call(__requestEnvelope);
        if (__response instanceof SoapResult.Failure __failure) {
            var __fault = __failure.fault();
            if (__fault.getDetail() != null && !__fault.getDetail().getAny().isEmpty()) {
                var __detail = __fault.getDetail().getAny().get(0);
                if (__detail instanceof TestError1 __error) {
                    throw new TestError1Msg(__failure.faultMessage(), __error);
                } else if (__detail instanceof TestError2 __error) {
                    throw new TestError2Msg(__failure.faultMessage(), __error);
                }
                throw new SoapFaultException(__failure.faultMessage(), __fault);
            }
            throw new SoapFaultException(__failure.faultMessage(), __fault);
        }
        var __success = (SoapResult.Success) __response;
        return (TestResponse) __success.body();
    }
}
```

**The contract shape, stated plainly:** the generated method *overrides the WSDL interface method*.
Its return type is the WSDL payload type; there is no `SoapResult`, no wrapper, no `Optional`, no
future. `SoapResult` exists only between `SoapRequestExecutor.call(...)` and the unwrapping code above.

Both generators build the method as an override of the interface method
(`MethodSpec.overriding(method)` in Java, `KModifier.OVERRIDE` in KSP) and there is **no** `Async`,
`Reactive`, `Mono`, `CompletionStage` or `suspend` variant anywhere in either generator. A signature
that returns anything other than the SOAP body payload (for example a wsdl2java `-asyncMethods`
`Response<T>` / `Future<?>`) would be mapped with the same `(ReturnType) __success.body()` cast and
produce a client that fails at runtime — leave async generation off, as the Kora examples do.

---

## 4. Request and response mapping

The generator picks one of three request shapes per method.

| Interface shape | Generated request code |
|---|---|
| `@RequestWrapper(className = "…TestRequestWrapper")` (document/wrapped) | Builds the wrapper, calls `setX(...)` per `@WebParam`, wrapping values through `ObjectFactory.createXY(...)` when such a factory method exists |
| Enclosing type has `@SOAPBinding(style = RPC)` | Generates a nested `@XmlRootElement` `<Operation>Request` class with one public field per non-`OUT` `@WebParam`, using `partName` as the element name |
| Neither, single parameter (document/bare) | `new SoapEnvelope(param)` directly |

In all three the envelope is passed through `this.envelopeProcessor.apply(...)` before the call.

Response mapping mirrors it:

| Interface shape | Generated response code |
|---|---|
| `@ResponseWrapper` + `@WebResult` | Casts the body to the wrapper, returns `wrapper.getX()`, unwrapping `JAXBElement.getValue()` when the wrapper accessor is a `JAXBElement`. Returns `null` if the wrapper or the accessor is `null` |
| `@ResponseWrapper` without `@WebResult` | Assigns each non-`IN` `@WebParam` `Holder.value` from the wrapper |
| Bare return type | `return (TestResponse) __success.body();` |
| `void` + RPC style | Walks the response DOM children and unmarshals each into the matching `Holder` by `partName` |

`jakarta.xml.ws.Holder<T>` out-parameters are therefore fully supported, and a `void` RPC operation
communicates its results through them.

---

## 5. Runtime: `SoapRequestExecutor`

`SoapRequestExecutor.call(SoapEnvelope)` is the whole transport path:

1. Opens a `SoapClientObservation` and binds it plus the OpenTelemetry context via `ScopedValue`
   (this is what replaced 1.x's `Context` — there is nothing to pass and nothing to clean up).
2. Marshals the envelope with the `SoapEnvelopeMapper` (`JakartaSoapEnvelopeMapper`, JAXB).
3. `HttpClientRequest.post(url)` with body content type `text/xml` and
   `requestTimeout = config.timeout()`; adds `SOAPAction` only when `@WebMethod.action` was non-empty.
4. Branches on the HTTP status code:

| Status | Behaviour |
|---|---|
| `200` | Body unmarshalled; `SoapResult.Success(envelope.getBody().getAny().get(0))` |
| `200` + `Content-Type: multipart/*` | Multipart parsed, XOP `cid:` references resolved through `JakartaXopAttachmentUnmarshaller`, then `Success` |
| `500` | Body unmarshalled as a `SoapFault`; `SoapResult.Failure(fault, "<faultcode> <faultstring>")` |
| anything else | `SoapInvalidHttpResponseException(code, body)` — the message carries the first 500 bytes of the body |

5. `IOException` and `HttpClientException` are wrapped in `SoapException`.
6. `observation.end()` in a `finally` records the metric and closes the span.

```java
public sealed interface SoapResult {
    record Success(Object body) implements SoapResult {}
    record Failure(SoapFault fault, String faultMessage) implements SoapResult {}
}
```

**MTOM / XOP.** Multipart *responses* are parsed automatically: `MultipartParserUtils` splits the
parts, the `start` part is unmarshalled as the envelope, and `xop:Include href="cid:…"` resolves to
the matching part — a `byte[]`-typed element arrives populated with the attachment bytes. This needs
no configuration. The request side is always a single `text/xml` body.

**Concurrency.** The generated client is a graph singleton and safe to share: it holds an immutable
`JAXBContext` (thread-safe by the JAXB contract) and creates a fresh `Marshaller`/`Unmarshaller` per
call inside `JakartaSoapEnvelopeMapper`. There is no per-call mutable state on the client itself.

---

## 6. The envelope-processor seam

SOAP clients do **not** use `@InterceptWith` — that is the declarative HTTP client's mechanism. The
extension point is a `Function<SoapEnvelope, SoapEnvelope>` tagged with the service interface:

```java
@Module
public interface SoapEnvelopeModule {

    @Tag(SimpleService.class)
    default Function<SoapEnvelope, SoapEnvelope> simpleServiceEnvelopeProcessor() {
        return envelope -> {
            envelope.getHeader().getAny().add(buildCorrelationHeader());  // org.w3c.dom.Element or JAXB object
            return envelope;
        };
    }
}
```

```kotlin
@Module
interface SoapEnvelopeModule {

    @Tag(SimpleService::class)
    fun simpleServiceEnvelopeProcessor(): Function<SoapEnvelope, SoapEnvelope> =
        Function { envelope ->
            envelope.header.any.add(buildCorrelationHeader())
            envelope
        }
}
```

`io.koraframework.soap.client.common.util.SoapEnvelopeProcessorsUtils.wssAuth(username, password)`
returns a ready-made processor that appends a WS-Security `UsernameToken` with `Username` and a
`PasswordText` (plaintext) child. Use it only over TLS.

`SoapEnvelope` exposes `getHeader().getAny()`, `getBody().getAny()`, `getAny()` and
`getOtherAttributes()`, so any header element can be added.

If you genuinely need a differently constructed client, provide the interface type yourself and call
the four-argument constructor — but then resolve the config with the tag the generated module used:

```java
@Module
public interface SoapModule {

    default SimpleService simpleService(HttpClient httpClient,
                                        SoapClientTelemetryFactory telemetryFactory,
                                        @Tag(SimpleService.class) SoapServiceConfig config) {
        try {
            return new $SimpleService_SoapClientImpl(httpClient, telemetryFactory, config,
                                                     SoapEnvelopeProcessorsUtils.wssAuth("user", "secret"));
        } catch (JAXBException e) {
            throw new IllegalStateException(e);
        }
    }
}
```

Your method has no `@DefaultComponent`, so it wins over the generated one. Prefer the tagged
processor — it needs no reference to a `$`-prefixed generated type.

---

## 7. Gradle wiring

### 7.1 Coordinates

| Artifact | Role |
|---|---|
| `io.koraframework:kora-bom` | Platform; every other Kora coordinate stays version-less |
| `io.koraframework:soap-client` | Runtime. `api`-exports `http-client-common`, `telemetry-common`, `jakarta.xml.ws-api`, `jakarta.xml.bind-api`, `org.glassfish.jaxb:jaxb-runtime`, `commons-codec` |
| `io.koraframework:annotation-processors` | Java. Aggregates `soap-client-annotation-processor` — do not list it separately |
| `io.koraframework:symbol-processors` | Kotlin KSP. Aggregates `soap-client-symbol-processor` |
| one of `http-client-ok` / `http-client-apache` / `http-client-jdk` | Supplies the `HttpClient` the generated module requires. Each brings its own transport library |
| `io.koraframework:config-hocon` or `config-yaml` | Required — the generated module reads `Config` |

The migrated Kora examples also list `io.koraframework:json-common`; SOAP does not need it — add it
only if the service handles JSON as well.

The Java SOAP example uses `http-client-apache` and the Kotlin one `http-client-ok`; any of the
three transports works.

### 7.2 The `wsdl2java` block

The framework itself invokes `org.apache.cxf.tools.wsdlto.WSDLToJava` directly from an isolated
Gradle configuration pinned to **CXF `4.2.3`** (`gradle/libs.versions.toml`), alongside
`jakarta.xml.ws-api 4.0.3`, `jakarta.xml.bind-api 4.0.5`, `jakarta.jws-api 3.0.0` and
`org.glassfish.jaxb:jaxb-runtime 4.0.9`.

Applications do not need that plumbing: both migrated 2.0 examples use the
[`com.github.bjornvester.wsdl2java`](https://github.com/bjornvester/wsdl2java-gradle-plugin) plugin
at `2.0.2` and pin **`cxfVersion = "4.0.2"`** inside it. The two numbers are not in conflict — they
are different CXF *toolchains*, one inside Kora's own build and one inside your build — but they do
differ, so use `4.0.2` unless you have a reason to move: that is the combination the migrated
examples are verified against on Gradle 9.5.1 and JDK 25. Either way it is CXF 4.x, which emits
jakarta namespaces.

Only the runtime coordinates matter for the generated code: whatever CXF version generates the
sources, they compile against the `jakarta.*` APIs that `soap-client` brings in.

Options that matter:

| Option | Why |
|---|---|
| `useJakarta = true` | **Mandatory.** `false` emits `javax.jws` and the Kora processor produces nothing |
| `wsdlDir` | Where the `.wsdl` files live, conventionally `src/main/resources/wsdl` |
| `packageName` | Package of the generated interface and models. Changing it later requires `clean` + `--no-build-cache` |
| `generatedSourceDir` | Output root; the plugin registers it on the Java source set |
| `markGenerated = true` | Adds `@Generated` to the CXF output |
| `includesWithOptions` | Per-WSDL `wsdl2java` CLI options, typically `-wsdlLocation` so the generated `@WebServiceClient` does not embed a local path |

### 7.3 Kotlin specifics

`wsdl2java` emits **Java**. KSP only sees it if the directory is on the Java source set:

```kotlin
sourceSets.main {
    java.srcDir(layout.buildDirectory.dir("generated/sources/wsdl2java/java"))
}
```

`ksp("io.koraframework:symbol-processors:${property("koraVersion")}")` is enough — the migrated
Kotlin example no longer declares `kspTest`, and it dropped `kotlinx-coroutines-jdk8` because there
are no `suspend` SOAP contracts to support.

### 7.4 Build commands

```shell
./gradlew wsdl2java            # CXF generation only
./gradlew clean classes        # full chain, including the Kora processor
./gradlew kspKotlin --console=plain    # Kotlin: see KSP diagnostics first
```

After renaming `packageName` or the project's own package:

```shell
./gradlew clean --continue
./gradlew classes testClasses --continue --no-build-cache
```

`wsdl2java` does not delete its previous output and the build-cache key ignores a changed
`packageName`, so the old and new packages end up in one source set and javac reports
`package … does not exist` for files under `build/generated/` that you never wrote. Editing generated
sources is never the fix.

---

## 8. Testing

The client is an ordinary graph component, so `@KoraAppTest` injects it and a mock HTTP server stands
in for the SOAP service:

```java
@KoraAppTest(Application.class)
class SimpleServiceTests implements KoraAppTestConfigModifier {

    @TestComponent
    private SimpleService service;

    @Override
    public KoraConfigModification config() {
        return KoraConfigModification.ofSystemProperty("SOAP_CLIENT_URL", mockServerUri);
    }

    @Test
    void callsService() {
        var request = new TestRequest();
        request.setVal1("1");

        var response = service.test(request);

        assertEquals("1", response.getVal1());
    }
}
```

The wire format is worth knowing when writing the mock's expectations:

```xml
<ns2:Envelope xmlns:ns2="http://schemas.xmlsoap.org/soap/envelope/"
              xmlns:ns3="http://example.com/simple/service">
    <ns2:Header/>
    <ns2:Body>
        <ns3:TestRequest>
            <val1>1</val1>
            <val2>2</val2>
        </ns3:TestRequest>
    </ns2:Body>
</ns2:Envelope>
```

Assert against a **fault** response by returning HTTP `500` with a `<soap:Fault>` body and expecting
the typed `@WebFault` exception, or `SoapFaultException` when the detail matches nothing declared.
