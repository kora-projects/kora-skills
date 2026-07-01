# SOAP Client Telemetry Reference

**Complete telemetry configuration for Kora SOAP clients.**

---

## Logging

### Configuration

```hocon
soapClient {
    PaymentService {
        telemetry {
            logging {
                enabled = true
            }
        }
    }
}

logging.level {
    "ru.tinkoff.kora.soap.client.common.SoapRequestExecutor" = "DEBUG"
    "com.example.generated.PaymentService" = "DEBUG"
}
```

## Metrics

### Configuration

```hocon
soapClient {
    PaymentService {
        telemetry {
            metrics {
                enabled = true
                slo = [1, 5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000]
                tags {
                    environment = "production"
                    team = "payments"
                }
            }
        }
    }
}
```

### Metrics Emitted

`kora.soap.client.requests` (Counter)

Total SOAP requests.

**Tags:**
- `soap_service` — Service name (e.g., `PaymentService`)
- `soap_method` — Method name (e.g., `processPayment`)
- `status` — `success` or `error`

`kora.soap.client.duration` (DistributionSummary)

Request duration with SLO buckets.

**Tags:**
- `soap_service` — Service name
- `soap_method` — Method name
- `status` — `success` or `error`

`kora.soap.client.faults` (Counter)

SOAP faults by fault code.

**Tags:**
- `soap_service` — Service name
- `soap_method` — Method name
- `fault_code` — SOAP fault code (e.g., `INSUFFICIENT_FUNDS`)

---

## Tracing

### Configuration

```hocon
soapClient {
    PaymentService {
        telemetry {
            tracing {
                enabled = true
                attributes {
                    "payment.provider" = "bank-api"
                    "criticality" = "high"
                    "team" = "payments"
                }
            }
        }
    }
}
```