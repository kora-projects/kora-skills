#!/usr/bin/env python3
"""
Generate a resilient service template for Kora AOP (Kotlin).

Usage:
    python generate_resilient_service_kt.py --package com.example.service --class-name InventoryService

Output:
    Creates a Kotlin service with @Timeout + @Retry + @CircuitBreaker + @Fallback.
"""

import argparse
from pathlib import Path

TEMPLATE = """// Kotlin outbound call wrapped with @Timeout + @Retry + @CircuitBreaker + @Fallback.
// Aspect order (top to bottom) matters — see references/resilient.md.
// Replace `{package}` with your package.
// Class must be `open` for aspects to work.

package {package}

import ru.tinkoff.kora.common.Component
import ru.tinkoff.kora.resilient.circuitbreaker.annotation.CircuitBreaker
import ru.tinkoff.kora.resilient.fallback.annotation.Fallback
import ru.tinkoff.kora.resilient.retry.annotation.Retry
import ru.tinkoff.kora.resilient.timeout.annotation.Timeout

@Component
open class {class_name}(                                              // open, not final
    private val client: {client_class}
) {{

    // Semantics with this stacking:
    //   1. @Timeout caps the WHOLE chain (including retries and fallback).
    //   2. @CircuitBreaker short-circuits when open — @Retry doesn't even run.
    //   3. @Retry retries the underlying call until success or attempts exhausted.
    //   4. @Fallback provides a value if all retries fail.
    @Timeout("{config_name}")
    @CircuitBreaker("{config_name}")
    @Retry("{config_name}")
    @Fallback(value = "{config_name}", method = "fallback")
    open fun check(sku: String): Int {{
        return client.call(sku)
    }}

    // Fallback method — same class, signature-compatible return type.
    protected open fun fallback(sku: String): Int = 0

    // Per-attempt timeout instead: swap order — @Retry outside @Timeout.
    @Retry("{config_name}")
    @Timeout("{config_name}.perAttempt")
    open fun checkPerAttempt(sku: String): Int {{
        return client.call(sku)
    }}
}}

// Placeholder dependency — replace with your actual client
open class {client_class} {{
    open fun call(sku: String): Int = 42
}}

// Config snippet (HOCON) — add to your application.conf:
//
// {config_name} {{
//   timeout = "2s"
//   circuit-breaker {{
//     failureThreshold = 5
//     successThreshold = 3
//     requestVolumeThreshold = 10
//     waitDuration = "30s"
//   }}
//   retry {{
//     attempts = 3
//     waitBetween = "100ms"
//     maxWait = "2s"
//   }}
//   fallback {{
//     enabled = true
//   }}
// }}
"""


def main():
    parser = argparse.ArgumentParser(description="Generate resilient service template (Kotlin)")
    parser.add_argument("--package", required=True, help="Kotlin package name")
    parser.add_argument("--class-name", required=True, help="Service class name")
    parser.add_argument("--client-class", default="InventoryClient", help="Client class name")
    parser.add_argument("--config-name", default="inventory.check", help="Config key name")
    parser.add_argument("--output", default="ResilientService.kt.template", help="Output file name")

    args = parser.parse_args()

    content = TEMPLATE.format(
        package=args.package,
        class_name=args.class_name,
        client_class=args.client_class,
        config_name=args.config_name
    )

    output_path = Path(args.output)
    output_path.write_text(content)
    print(f"Generated {output_path}")


if __name__ == "__main__":
    main()
