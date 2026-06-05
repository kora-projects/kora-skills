#!/usr/bin/env python3
"""
Generate a validated DTO template for Kora AOP.

Usage:
    python generate_validated_dto.py --package com.example.dto --class-name CreateOrder

Output:
    Creates a Java record with @Valid and built-in validators.
"""

import argparse
from pathlib import Path

TEMPLATE = """// DTO with built-in validators. Generates a Validator<{class_name}> component.
// Replace `{package}` with your package.

package {package};

import jakarta.annotation.Nullable;
import ru.tinkoff.kora.validation.common.annotation.NotBlank;
import ru.tinkoff.kora.validation.common.annotation.NotEmpty;
import ru.tinkoff.kora.validation.common.annotation.Pattern;
import ru.tinkoff.kora.validation.common.annotation.Range;
import ru.tinkoff.kora.validation.common.annotation.Size;
import ru.tinkoff.kora.validation.common.annotation.Valid;

import java.util.List;

@Valid
public record {class_name}(

    @NotBlank @Size(max = 64) String sku,

    @Range(from = 1, to = 1000) int quantity,

    @Pattern(regexp = "^[A-Z]{{3}}$") String currency,

    @NotEmpty List<@NotBlank String> tags,

    @Valid Address billing,                    // nested @Valid → also generates Validator<Address>

    @Nullable String note                      // opt-out of implicit @NotNull
) {{

    @Valid
    public record Address(
        @NotBlank String line1,
        @Nullable String line2,
        @Pattern(regexp = "^[A-Z]{{2}}$") String country
    ) {{}}
}}
"""


def main():
    parser = argparse.ArgumentParser(description="Generate validated DTO template")
    parser.add_argument("--package", required=True, help="Java package name")
    parser.add_argument("--class-name", required=True, help="DTO class name")
    parser.add_argument("--output", default="ValidatedDto.java.template", help="Output file name")

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
