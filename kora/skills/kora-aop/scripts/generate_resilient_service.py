#!/usr/bin/env python3
"""
Generate a resilient service template for Kora AOP.

Usage:
    python generate_resilient_service.py --package com.example.service --class-name InventoryService

Output:
    Creates a Java service with @Timeout + @Retry + @CircuitBreaker + @Fallback.
"""

import argparse
from pathlib import Path

TEMPLATE = """// Outbound call wrapped with @Timeout + @Retry + @CircuitBreaker + @Fallback.
// Aspect order (top to bottom) matters — see references/resilient.md.
// Replace `{package}` with your package.

package {package};

import ru.tinkoff.kora.common.Component;
import ru.tinkoff.kora.resilient.circuitbreaker.annotation.CircuitBreaker;
import ru.tinkoff.kora.resilient.fallback.annotation.Fallback;
import ru.tinkoff.kora.resilient.retry.annotation.Retry;
import ru.tinkoff.kora.resilient.timeout.annotation.Timeout;

@Component
public class {class_name} {{                                         // NOT final

    private final {class_name}Client client;

    public {class_name}({class_name}Client client) {{
        this.client = client;
    }}

    // Semantics with this stacking:
    //   1. @Timeout caps the WHOLE chain (including retries and fallback).
    //   2. @CircuitBreaker short-circuits when open — @Retry doesn't even run.
    //   3. @Retry retries the underlying call until success or attempts exhausted.
    //   4. @Fallback provides a value if all retries fail.
    @Timeout("{config_name}")
    @CircuitBreaker("{config_name}")
    @Retry("{config_name}")
    @Fallback(value = "{config_name}", method = "fallbackMethod()")
    public ResponseType mainMethod(String param) {{
        return client.call(param);
    }}

    // Fallback method — same class, signature-compatible return type.
    protected ResponseType fallbackMethod(String param) {{
        return ResponseType.FALLBACK;
    }}

    // Per-attempt timeout instead: swap order — @Retry outside @Timeout.
    @Retry("{config_name}")
    @Timeout("{config_name}.perAttempt")
    public ResponseType checkPerAttempt(String param) {{
        return client.call(param);
    }}

    // Placeholder dependency — replace with your actual client
    private static class {class_name}Client {{
        ResponseType call(String param) {{
            return ResponseType.OK;
        }}
    }}

    // Placeholder response type — replace with your actual type
    public enum ResponseType {{ OK, FALLBACK }}
}}
"""


def main():
    parser = argparse.ArgumentParser(description="Generate resilient service template")
    parser.add_argument("--package", required=True, help="Java package name")
    parser.add_argument("--class-name", required=True, help="Service class name")
    parser.add_argument("--config-name", default="service.resilience", help="Config key name")
    parser.add_argument("--output", default="ResilientService.java.template", help="Output file name")

    args = parser.parse_args()

    content = TEMPLATE.format(
        package=args.package,
        class_name=args.class_name,
        config_name=args.config_name
    )

    output_path = Path(args.output)
    output_path.write_text(content)
    print(f"Generated {output_path}")


if __name__ == "__main__":
    main()
