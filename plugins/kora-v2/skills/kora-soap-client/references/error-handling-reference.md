# SOAP Client Error Handling Reference

**Complete guide to SOAP error types and handling patterns.**

---

## Exception Hierarchy

```
java.lang.Exception
└── ru.tinkoff.kora.soap.client.common.SoapException
    ├── SoapRequestMarshallingException
    ├── SoapResponseUnmarshallingException
    ├── InvalidHttpResponseSoapException
    └── SoapServiceException (wraps SOAP faults)
```

---

## SoapException

Base class for all SOAP-related errors.

```java
public class SoapException extends RuntimeException {
    private final String serviceName;
    private final String methodName;
    private final String url;

    public SoapException(String serviceName, String methodName, String url, String message, Throwable cause) {
        super(message, cause);
        this.serviceName = serviceName;
        this.methodName = methodName;
        this.url = url;
    }

    public String getServiceName() { return serviceName; }
    public String getMethodName() { return methodName; }
    public String getUrl() { return url; }
}
```

**Usage:**
```java
try {
    soapClient.processPayment(request);
} catch (SoapException e) {
    logger.error("SOAP call failed: {}#{}", e.getServiceName(), e.getMethodName());
    throw e;
}
```

---

## SOAP Faults (SoapServiceException)

SOAP faults from the server are wrapped in `SoapServiceException`.

```java
try {
    soapClient.processPayment(request);
} catch (SoapServiceException e) {
    SoapFault fault = e.getSoapFault();
    
    String faultCode = fault.getFaultCode();      // "soap:Server"
    String faultString = fault.getFaultString();  // "Insufficient funds"
    String detail = fault.getDetail();            // XML detail element
    
    // Handle specific fault codes
    switch (faultCode) {
        case "INSUFFICIENT_FUNDS":
            // Business logic handling
            break;
        case "INVALID_CARD":
            // Business logic handling
            break;
        default:
            // Unknown fault
            throw e;
    }
}
```

### SoapFault Structure

```java
public class SoapFault {
    private final String faultCode;      // SOAP fault code
    private final String faultString;    // Human-readable message
    private final String faultActor;     // Who caused the fault
    private final String detail;         // Application-specific error info (XML)

    public String getFaultCode() { ... }
    public String getFaultString() { ... }
    public String getFaultActor() { ... }
    public String getDetail() { ... }
}
```

### Common SOAP Fault Codes

| Fault Code | Meaning | Handling |
|------------|---------|----------|
| `soap:Client` | Client error (bad request) | Fix request, validate input |
| `soap:Server` | Server error | Retry, fallback, alert |
| `soap:VersionMismatch` | Wrong SOAP version | Check WSDL, update client |
| `soap:MustUnderstand` | Header not understood | Check SOAP headers |

---

## SoapRequestMarshallingException

Request serialization failed.

**Causes:**
- Null required fields in DTO
- Invalid field values
- JAXB marshalling error

```java
try {
    soapClient.processPayment(request);
} catch (SoapRequestMarshallingException e) {
    logger.error("Failed to marshal request", e);
    // Log the invalid request
    logger.error("Invalid request: {}", request);
    throw new IllegalArgumentException("Invalid payment request", e);
}
```

**Prevention:**
```java
// Validate before calling
if (request.getAmount() == null || request.getAmount() <= 0) {
    throw new IllegalArgumentException("Amount must be positive");
}
if (request.getCurrency() == null) {
    throw new IllegalArgumentException("Currency is required");
}
soapClient.processPayment(request);
```

---

## SoapResponseUnmarshallingException

Response deserialization failed.

**Causes:**
- Server returns unexpected XML structure
- Missing required fields in response
- JAXB unmarshalling error

```java
try {
    PaymentResponse response = soapClient.processPayment(request);
} catch (SoapResponseUnmarshallingException e) {
    logger.error("Failed to unmarshal response", e);
    // Log raw response for debugging
    throw new IllegalStateException("Invalid response from payment service", e);
}
```

---

## InvalidHttpResponseSoapException

HTTP response is not valid SOAP.

**Causes:**
- Server returns HTML error page (404, 500, 503)
- Server returns plain text error
- Network proxy returns error page

```java
try {
    soapClient.processPayment(request);
} catch (InvalidHttpResponseSoapException e) {
    int statusCode = e.getStatusCode();  // e.g., 503
    String responseBody = e.getResponseBody();  // HTML error page
    
    logger.error("Invalid SOAP response: HTTP {}", statusCode);
    logger.error("Response body: {}", responseBody.substring(0, 500));
    
    if (statusCode == 503) {
        // Service unavailable - retry with backoff
        throw new ServiceUnavailableException("Payment service unavailable", e);
    } else if (statusCode >= 500) {
        // Server error - retry
        throw new ServerErrorException("Payment service error", e);
    } else {
        // Client error - don't retry
        throw new ClientErrorException("Invalid payment request", e);
    }
}
```

---

## ConnectException

Network-level connection failure.

**Causes:**
- Service URL incorrect
- Service is down
- Network/firewall issues
- DNS resolution failure

```java
try {
    soapClient.processPayment(request);
} catch (ConnectException e) {
    logger.error("Cannot connect to payment service", e);
    // Fallback to alternative payment provider
    return alternativePaymentProvider.process(request);
}
```

---

## Error Handling Patterns

### Pattern 1: Retry with Backoff

```java
@Component
public class PaymentServiceWithRetry {

    private final SimpleService soapClient;
    private final RetryConfig retryConfig;

    public PaymentServiceWithRetry(SimpleService soapClient, RetryConfig retryConfig) {
        this.soapClient = soapClient;
        this.retryConfig = retryConfig;
    }

    public PaymentResponse processWithRetry(PaymentRequest request) {
        int attempts = 0;
        Throwable lastException = null;

        while (attempts < retryConfig.maxAttempts) {
            try {
                return soapClient.processPayment(request);
            } catch (SoapServiceException e) {
                // Business error - don't retry
                throw e;
            } catch (Exception e) {
                // Transient error - retry
                attempts++;
                lastException = e;
                if (attempts < retryConfig.maxAttempts) {
                    Thread.sleep(retryConfig.delayMs * attempts);  // Linear backoff
                }
            }
        }

        throw new RuntimeException("Failed after " + retryConfig.maxAttempts + " attempts", lastException);
    }
}
```

### Pattern 2: Circuit Breaker

```java
@Component
public class PaymentServiceWithCircuitBreaker {

    private final SimpleService soapClient;
    private final CircuitBreaker circuitBreaker;

    public PaymentServiceWithCircuitBreaker(SimpleService soapClient) {
        this.soapClient = soapClient;
        this.circuitBreaker = new CircuitBreaker(5, 30000);  // 5 failures, 30s timeout
    }

    public PaymentResponse process(PaymentRequest request) {
        if (!circuitBreaker.allowRequest()) {
            throw new CircuitBreakerOpenException("Payment service circuit is open");
        }

        try {
            PaymentResponse response = soapClient.processPayment(request);
            circuitBreaker.recordSuccess();
            return response;
        } catch (Exception e) {
            circuitBreaker.recordFailure();
            throw e;
        }
    }
}
```

### Pattern 3: Fallback

```java
@Component
public class PaymentServiceWithFallback {

    private final SimpleService primaryClient;
    private final SimpleService backupClient;

    public PaymentServiceWithFallback(
            @Tag(Primary.class) SimpleService primaryClient,
            @Tag(Backup.class) SimpleService backupClient) {
        this.primaryClient = primaryClient;
        this.backupClient = backupClient;
    }

    public PaymentResponse process(PaymentRequest request) {
        try {
            return primaryClient.processPayment(request);
        } catch (ConnectException | InvalidHttpResponseSoapException e) {
            logger.warn("Primary payment service failed, using backup", e);
            return backupClient.processPayment(request);
        }
    }
}
```

### Pattern 4: Error Translation

```java
@Component
public class PaymentFacade {

    private final SimpleService soapClient;

    public PaymentFacade(SimpleService soapClient) {
        this.soapClient = soapClient;
    }

    public PaymentResult process(PaymentRequest request) {
        try {
            PaymentResponse response = soapClient.processPayment(request);
            return PaymentResult.success(response.getTransactionId());
        } catch (SoapServiceException e) {
            String faultCode = e.getSoapFault().getFaultCode();
            switch (faultCode) {
                case "INSUFFICIENT_FUNDS":
                    return PaymentResult.insufficientFunds();
                case "INVALID_CARD":
                    return PaymentResult.invalidCard();
                case "CARD_EXPIRED":
                    return PaymentResult.cardExpired();
                default:
                    return PaymentResult.unknownError(faultCode);
            }
        } catch (ConnectException e) {
            return PaymentResult.serviceUnavailable();
        }
    }
}
```

---

## Logging Best Practices

### DO: Log structured error information

```java
catch (SoapException e) {
    logger.error("SOAP call failed: service={}, method={}, url={}",
        e.getServiceName(),
        e.getMethodName(),
        e.getUrl(),
        e);
}
```

### DON'T: Log sensitive data

```java
// BAD - may log sensitive data
logger.error("Request: {}", request);  // May contain card numbers, passwords

// GOOD - log only non-sensitive info
logger.error("SOAP call failed: service={}, method={}",
    e.getServiceName(),
    e.getMethodName());
```
