#!/usr/bin/env python3
"""
Generate a logged service template for Kora AOP (Kotlin).

Usage:
    python generate_logged_service_kt.py --package com.example.service --class-name OrdersService

Output:
    Creates a Kotlin service with @Log, @Mdc annotations.
"""

import argparse
from pathlib import Path

TEMPLATE = r"""// Kotlin service with method logging. Class must be `open` for aspects.
// Replace `{package}` with your package.

package {package}

import ru.tinkoff.kora.common.Component
import ru.tinkoff.kora.logging.common.annotation.Log
import ru.tinkoff.kora.logging.common.annotation.Mdc
import java.util.UUID

@Component
open class {class_name} {{                                                // open, not final

    @Log
    @Mdc(key = "tenant", value = "${tenantId}")
    @Mdc(key = "operation", value = "create-order")
    open fun create(
        @Mdc tenantId: String,
        @Log.off idempotencyKey: String
    ): String = "order-${UUID.randomUUID()}"

    @Log.out
    open fun get(@Log.off id: UUID): String = "order-$id"
}}

// Note: @Log = @Log.in + @Log.out (log args + return).
// @Mdc puts entries into MDC for the duration of the call.
// @Log.off on a parameter suppresses logging that value (PII, secrets).
// Use Kora's MDC (ru.tinkoff.kora.logging.common.MDC), never SLF4J's.
"""


def main():
    parser = argparse.ArgumentParser(description="Generate logged service template (Kotlin)")
    parser.add_argument("--package", required=True, help="Kotlin package name")
    parser.add_argument("--class-name", required=True, help="Service class name")
    parser.add_argument("--output", default="LoggedService.kt.template", help="Output file name")

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
