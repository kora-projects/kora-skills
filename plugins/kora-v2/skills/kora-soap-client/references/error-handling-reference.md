# SOAP Client Error Handling — Kora 2.0

Every exception type here exists in
`io.koraframework.soap.client.common.exception` in the Kora 2.0 `soap-client` module. Nothing on this
page is inherited from the Kora 1.x API surface — several 1.x names were renamed or re-parented.

---

## 1. Hierarchy

```
java.lang.RuntimeException
└── io.koraframework.soap.client.common.exception.SoapException
    ├── SoapFaultException                  // SOAP Fault not matched by a declared WSDL fault
    ├── SoapInvalidHttpResponseException    // HTTP status other than 200 or 500
    ├── SoapRequestMarshallingException     // JAXB could not marshal the request envelope
    └── SoapResponseUnmarshallingException  // JAXB could not unmarshal the response
```

Separately, and **not** under `SoapException`:

```
java.lang.Exception
└── <generated @WebFault exception>         // e.g. TestError1Msg — one per <wsdl:fault>
```

Two renames from Kora 1.x that a package-only migration will not catch:

| Kora 1.x | Kora 2.x |
|---|---|
| `InvalidHttpResponseSoapException` | `SoapInvalidHttpResponseException` |
| `SoapRequestMarshallingException` / `SoapResponseUnmarshallingException` extend `RuntimeException` | both extend `SoapException` |

Because the marshalling exceptions are now inside the hierarchy, a single `catch (SoapException e)`
covers **all** SOAP-layer failures. In 1.x it did not.

---

## 2. Where each one comes from

| Exception | Raised by | Trigger |
|---|---|---|
| `SoapRequestMarshallingException` | `JakartaSoapEnvelopeMapper.marshal` | `JAXBException` while marshalling the request envelope |
| `SoapResponseUnmarshallingException` | `JakartaSoapEnvelopeMapper.unmarshal` | `JAXBException` while unmarshalling the response or a multipart part |
| `SoapInvalidHttpResponseException` | `SoapRequestExecutor.call` | HTTP status is neither `200` nor `500` |
| `SoapFaultException` | generated client method | HTTP `500` whose `<soap:Fault>` detail matches no declared fault type |
| generated `@WebFault` exception | generated client method | HTTP `500` whose fault detail deserialises to that fault's `getFaultInfo()` type |
| `SoapException` (base, wrapping) | `SoapRequestExecutor.call` | `IOException` or `HttpClientException` from the transport |

---

## 3. `SoapFaultException` and `SoapFault`

```java
public class SoapFaultException extends SoapException {
    public SoapFaultException(String message, SoapFault fault) { … }
    public SoapFault getFault();
}
```

The message is `"<faultcode> <faultstring>"`, built by the executor.

`io.koraframework.soap.client.common.envelope.SoapFault` is a JAXB type, so its accessors follow the
XML element names — **lower-case, not camel-cased**:

| Accessor | Type | XML element |
|---|---|---|
| `getFaultcode()` | `javax.xml.namespace.QName` | `<faultcode>` |
| `getFaultstring()` | `String` | `<faultstring>` |
| `getFaultactor()` | `String` | `<faultactor>` |
| `getDetail()` | `SoapFaultDetail` | `<detail>` |

`getDetail()` returns `null` when the fault carried no `<detail>` element. `SoapFaultDetail.getAny()`
itself never returns `null` — it lazily creates the list — but it is empty when nothing was
unmarshalled, so both checks are needed.

`getFaultcode()` is a `QName`: compare with `getLocalPart()`, or use `toString()` for logging, and do
not assume it is a plain string. That `QName` is **`javax.xml.namespace.QName`** from the JDK's
`java.xml` module — one of the few `javax.*` names that is correct in Kora 2.0 code and must not be
"migrated" to a `jakarta` package.

```java
catch (SoapFaultException e) {
    var fault = e.getFault();
    var code = fault.getFaultcode();                // QName, e.g. {http://…}Server
    log.warn("SOAP fault {}: {}", code.getLocalPart(), fault.getFaultstring());

    var detail = fault.getDetail();
    if (detail != null && !detail.getAny().isEmpty()) {
        var first = detail.getAny().get(0);          // a JAXB object, if the type is known to the context
    }
}
```

---

## 4. Typed WSDL faults

A `<wsdl:fault>` makes `wsdl2java` generate a checked exception annotated `@WebFault`, with a
`getFaultInfo()` returning the fault payload type. The generated client compares the first element of
`fault.getDetail().getAny()` against each declared fault's payload type and throws the matching
exception; only when nothing matches does it fall back to `SoapFaultException`.

```java
try {
    var response = service.test(request);
    return response.getVal1();
} catch (TestError1Msg e) {              // declared in the WSDL — checked
    var info = e.getFaultInfo();         // typed payload
    return fallbackFor(info);
} catch (SoapFaultException e) {         // fault, but not one the contract declares
    throw new IllegalStateException("Unexpected SOAP fault: " + e.getMessage(), e);
}
```

Catch order matters: the typed fault is **not** a `SoapException`, so `catch (SoapException)` will not
swallow it, but `catch (Exception)` will. Put the typed faults first and keep them distinct.

---

## 5. `SoapInvalidHttpResponseException`

Raised for any status code other than `200` and `500` — an HTML error page from a proxy, a `404`, a
`503`. It carries **no** status-code or body accessor; the constructor formats them into the message:

```java
new SoapInvalidHttpResponseException(code, responseBody);
// message: "Invalid http response code for SOAP request: 503\n<first 500 bytes of the body>"
```

So do not write `e.getStatusCode()` or `e.getResponseBody()` — those do not exist. If you need the
status code for branching, get it from telemetry (`http.response.status_code` is on the span and on
`rpc.client.call.duration`) or add an HTTP client interceptor.

---

## 6. Transport failures

`SoapRequestExecutor` wraps transport errors:

```java
} catch (IOException | HttpClientException e) {
    throw new SoapException(e);
}
```

There is therefore **no bare `ConnectException`** to catch at the SOAP layer. Inspect the cause:

```java
catch (SoapException e) {
    var cause = e.getCause();
    if (cause instanceof HttpClientTimeoutException) {
        // soapClient.<Service>.timeout or the transport read timeout elapsed
    } else if (cause instanceof HttpClientConnectionException) {
        // DNS / TCP / TLS failure — wrong url, service down, firewall
    }
    throw e;
}
```

`io.koraframework.http.client.common.exception.HttpClientException` is the abstract base;
`HttpClientConnectionException`, `HttpClientTimeoutException`, `HttpClientResponseException`,
`HttpClientEncoderException`, `HttpClientDecoderException` and `HttpClientUnknownException` are its
subtypes.

---

## 7. Complete catch template

```java
import io.koraframework.soap.client.common.exception.*;

try {
    var response = service.test(request);
    return Result.ok(response.getVal1());

} catch (TestError1Msg e) {                          // 1. declared WSDL faults, most specific first
    return Result.businessError(e.getFaultInfo());

} catch (SoapFaultException e) {                     // 2. undeclared SOAP fault
    return Result.unexpectedFault(e.getFault().getFaultcode().getLocalPart());

} catch (SoapInvalidHttpResponseException e) {       // 3. not a SOAP response at all
    return Result.serviceUnavailable(e.getMessage());

} catch (SoapRequestMarshallingException e) {        // 4. our request is malformed — never retry
    throw new IllegalArgumentException("Invalid SOAP request payload", e);

} catch (SoapResponseUnmarshallingException e) {     // 5. their response is malformed
    throw new IllegalStateException("Unparseable SOAP response", e);

} catch (SoapException e) {                          // 6. transport: inspect e.getCause()
    return Result.transportFailure(e);
}
```

```kotlin
try {
    val response = service.test(request)
    Result.ok(response.val1)
} catch (e: TestError1Msg) {
    Result.businessError(e.faultInfo)
} catch (e: SoapFaultException) {
    Result.unexpectedFault(e.fault.faultcode.localPart)
} catch (e: SoapInvalidHttpResponseException) {
    Result.serviceUnavailable(e.message)
} catch (e: SoapRequestMarshallingException) {
    throw IllegalArgumentException("Invalid SOAP request payload", e)
} catch (e: SoapResponseUnmarshallingException) {
    throw IllegalStateException("Unparseable SOAP response", e)
} catch (e: SoapException) {
    Result.transportFailure(e)
}
```

The response object and its fields come from a Java contract, so from Kotlin they are platform types
— `response.val1` is `String?`. Treat every payload field as nullable unless the WSDL marks it
required and you have verified the generated model.

---

## 8. Which failures may be retried

| Failure | Retry? |
|---|---|
| `HttpClientConnectionException` cause | Yes — transient network |
| `HttpClientTimeoutException` cause | Only if the operation is idempotent |
| `SoapInvalidHttpResponseException` with `5xx` in the message | Usually yes |
| `SoapInvalidHttpResponseException` with `4xx` | No — the request or the URL is wrong |
| `SoapResponseUnmarshallingException` | No — the contract and the peer disagree |
| `SoapRequestMarshallingException` | Never — the request is malformed locally |
| Typed `@WebFault` / `SoapFaultException` | Never — these are business outcomes |

Do not hand-roll a retry loop. Use the Kora 2.0 resilience aspects on the component that wraps the
call — string names became typed specification interfaces in 2.0:

```java
@RetrySpec("resilient.retry.soapClient")
public interface SoapClientRetry extends Retry {}
```

```java
@Component
public class CustomerService {          // not final — AOP generates a subclass

    private final SimpleService service;

    public CustomerService(SimpleService service) {
        this.service = service;
    }

    @Retryable(SoapClientRetry.class)
    public TestResponse lookup(TestRequest request) {
        return service.test(request);
    }
}
```

`@Retryable`, `@CircuitBreakable`, `@Timeout` and `@RateLimited` all take a specification **class**,
not a name string. A `final` class (Kotlin: a class that is not `open`) fails the build with
`AOP aspect cannot be applied to class '…' because the class is final`. Full API and configuration:
[`kora-aop-resilient`](../../kora-aop-resilient/SKILL.md).

---

## 9. Logging failures safely

SOAP payloads routinely carry personal data, card numbers and credentials. The client logs full
envelopes only at `TRACE` (see [telemetry-reference.md](telemetry-reference.md)), so the risk in your
own `catch` blocks is what *you* write:

```java
// Do not: the request object stringifies the whole payload
log.error("SOAP call failed for request {}", request, e);

// Do: identity and outcome, no payload
log.error("SOAP call failed: service={} method={} fault={}",
          "SimpleService", "test", e.getMessage(), e);
```

`SoapFaultException.getMessage()` is `"<faultcode> <faultstring>"` — service-authored text, safe to
log. `SoapInvalidHttpResponseException.getMessage()` embeds up to 500 bytes of the peer's response
body, which may not be; log it at `DEBUG` if the peer is untrusted.
