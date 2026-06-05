#!/usr/bin/env python3
"""
Generate a validated DTO template for Kora AOP (Kotlin).

Usage:
    python generate_validated_dto_kt.py --package com.example.dto --class-name CreateOrder

Output:
    Creates a Kotlin open class with @Valid and built-in validators.
"""

import argparse
from pathlib import Path

TEMPLATE = """// Kotlin data class with built-in validators. Generates a Validator<{class_name}> component.
// Replace `{package}` with your package.
// Class must be `open` for @Valid to work (compile-time AOP requires subclassing).

package {package}

import jakarta.annotation.Nullable
import ru.tinkoff.kora.validation.common.annotation.NotBlank
import ru.tinkoff.kora.validation.common.annotation.NotEmpty
import ru.tinkoff.kora.validation.common.annotation.Pattern
import ru.tinkoff.kora.validation.common.annotation.Range
import ru.tinkoff.kora.validation.common.annotation.Size
import ru.tinkoff.kora.validation.common.annotation.Valid

@Valid
open class {class_name}(
    @field:NotBlank @field:Size(max = 64) val sku: String,
    @field:Range(from = 1, to = 1000) val quantity: Int,
    @field:Pattern(regexp = "^[A-Z]{{3}}$") val currency: String,
    @field:NotEmpty val tags: List<@NotBlank String>,
    @field:Valid val billing: Address,                    // nested @Valid → also generates Validator<Address>
    @Nullable val note: String?                           // opt-out of implicit @NotNull
) {{

    @Valid
    open class Address(
        @field:NotBlank val line1: String,
        @Nullable val line2: String?,
        @field:Pattern(regexp = "^[A-Z]{{2}}$") val country: String
    )
}}

// Note: In Kotlin, use `open` for aspect codegen. For records, consider using `data class` with explicit `open` modifier:
//   @Valid open data class {class_name}(...) {{ ... }}
// However, `data class` + `open` has limitations with aspect weaving — prefer `open class` for AOP targets.
"""


def main():
    parser = argparse.ArgumentParser(description="Generate validated DTO template (Kotlin)")
    parser.add_argument("--package", required=True, help="Kotlin package name")
    parser.add_argument("--class-name", required=True, help="DTO class name")
    parser.add_argument("--output", default="ValidatedDto.kt.template", help="Output file name")

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
