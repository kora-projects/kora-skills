#!/usr/bin/env python3
"""
Generate a validated service template for Kora AOP (Kotlin).

Usage:
    python generate_validated_service_kt.py --package com.example.service --class-name OrdersService

Output:
    Creates a Kotlin service with @Validate on methods and Validator injection.
"""

import argparse
from pathlib import Path

TEMPLATE = """// Kotlin service using @Validate aspect on a method. Class must be `open`.
// Combine with a global ErrorInterceptor (see kora-server) that maps ViolationException to 400.
// Replace `{package}` with your package.

package {package}

import ru.tinkoff.kora.common.Component
import ru.tinkoff.kora.validation.common.Validator
import ru.tinkoff.kora.validation.common.annotation.NotBlank
import ru.tinkoff.kora.validation.common.annotation.Valid
import ru.tinkoff.kora.validation.common.annotation.Validate
import java.util.UUID

@Component
open class {class_name}(                          // open, not final
    private val bodyValidator: Validator<CreateOrder>       // auto-injected from @Valid
) {{

    // Approach 1 — declarative: @Validate on the method aspect-validates args and return value.
    @Validate
    open fun create(@Valid body: CreateOrder, @NotBlank tenantId: String): Order {{
        return Order(UUID.randomUUID(), body.sku, body.quantity, tenantId)
    }}

    // Approach 2 — imperative: control over failure handling, fail-fast, etc.
    open fun createManual(body: CreateOrder): Order {{
        bodyValidator.validateAndThrow(body)          // throws ViolationException
        return Order(UUID.randomUUID(), body.sku, body.quantity, "default")
    }}
}}

// Placeholder DTOs — replace with your actual types
open class CreateOrder(val sku: String, val quantity: Int)
open class Order(val id: UUID, val sku: String, val quantity: Int, val tenantId: String)
"""


def main():
    parser = argparse.ArgumentParser(description="Generate validated service template (Kotlin)")
    parser.add_argument("--package", required=True, help="Kotlin package name")
    parser.add_argument("--class-name", required=True, help="Service class name")
    parser.add_argument("--output", default="ValidatedService.kt.template", help="Output file name")

    args = parser.parse_args()

    content = TEMPLATE.format(
        package=args.package,
        class_name=args.class_name
    )

    output_path = Path(args.output)
    output_path.write_text(content)
    print(f"Generated {output_path}")


if __name__ == "__main__":
    main()
