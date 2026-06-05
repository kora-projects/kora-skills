#!/usr/bin/env python3
"""
Generate a validated service template for Kora AOP.

Usage:
    python generate_validated_service.py --package com.example.service --class-name OrdersService

Output:
    Creates a Java service with @Validate on methods and Validator injection.
"""

import argparse
from pathlib import Path

TEMPLATE = """// Service using @Validate aspect on a method. Class is NOT final → aspect can subclass.
// Combine with a global ErrorInterceptor (see kora-server) that maps ViolationException to 400.
// Replace `{package}` with your package.

package {package};

import ru.tinkoff.kora.common.Component;
import ru.tinkoff.kora.validation.common.Validator;
import ru.tinkoff.kora.validation.common.annotation.NotBlank;
import ru.tinkoff.kora.validation.common.annotation.Valid;
import ru.tinkoff.kora.validation.common.annotation.Validate;

import java.util.UUID;

@Component
public class {class_name} {{                          // NOT final

    private final Validator<CreateOrder> bodyValidator;       // auto-injected from @Valid

    public {class_name}(Validator<CreateOrder> bodyValidator) {{
        this.bodyValidator = bodyValidator;
    }}

    // Approach 1 — declarative: @Validate on the method aspect-validates args and return value.
    @Validate
    public Order create(@Valid CreateOrder body, @NotBlank String tenantId) {{
        return new Order(UUID.randomUUID(), body.sku(), body.quantity(), tenantId);
    }}

    // Approach 2 — imperative: control over failure handling, fail-fast, etc.
    public Order createManual(CreateOrder body) {{
        bodyValidator.validateAndThrow(body);          // throws ViolationException
        return new Order(UUID.randomUUID(), body.sku(), body.quantity(), "default");
    }}
}}

// Placeholder DTOs — replace with your actual types
record CreateOrder(String sku, int quantity) {{}}
record Order(UUID id, String sku, int quantity, String tenantId) {{}}
"""


def main():
    parser = argparse.ArgumentParser(description="Generate validated service template")
    parser.add_argument("--package", required=True, help="Java package name")
    parser.add_argument("--class-name", required=True, help="Service class name")
    parser.add_argument("--output", default="ValidatedService.java.template", help="Output file name")

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
