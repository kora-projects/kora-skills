#!/usr/bin/env python3
"""
Generate a cache service template for Kora AOP (Kotlin).

Usage:
    python generate_cache_service_kt.py --package com.example.cache --class-name OrderCache --cache-name orders.cache

Output:
    Creates a Kotlin cache interface and service with @Cacheable + @CachePut + @CacheInvalidate.
"""

import argparse
from pathlib import Path

TEMPLATE = """// Kotlin typed cache + service using all four cache annotations.
// Replace `{package}` with your package.
// Class must be `open` for aspects to work.

package {package}

import ru.tinkoff.kora.cache.annotation.Cache
import ru.tinkoff.kora.cache.annotation.CacheInvalidate
import ru.tinkoff.kora.cache.annotation.CachePut
import ru.tinkoff.kora.cache.annotation.Cacheable
import ru.tinkoff.kora.cache.caffeine.CaffeineCache
import ru.tinkoff.kora.common.Component
import java.util.UUID

// 1. Typed cache interface — Kora generates the impl and registers it as a component.
// Replace KeyType and ValueType with your actual types (e.g., UUID, OrderDto)
@Cache("{cache_name}")
interface {class_name} : CaffeineCache<KeyType, ValueType> {{

    // For a composite key, define an inner data class and use it as K:
    //
    //   @Cache("{cache_name}")
    //   interface {class_name} : CaffeineCache<{class_name}.Key, ValueType> {{
    //       data class Key(val tenantId: UUID, val orderId: UUID)
    //   }}
}}

// 2. Service using all four cache annotations.
@Component
open class {service_class_name}(                                                // open, not final

    private val cache: {class_name},
    private val repository: {service_class_name}Repository

) {{

    @Cacheable({class_name}::class)                                       // read-through
    open fun get(id: KeyType): ValueType {{
        return repository.find(id)
    }}

    @CachePut({class_name}::class)                                        // write-through; key = first arg (id)
    open fun save(id: KeyType, dto: ValueType): ValueType {{
        return repository.save(dto)
    }}

    @CacheInvalidate({class_name}::class)                                 // evict the entry for id
    open fun delete(id: KeyType) {{
        repository.delete(id)
    }}

    @CacheInvalidate(value = {class_name}::class, allEntries = true)      // flush entire cache
    open fun flush() {{
        // use sparingly — invalidates ALL entries
    }}
}}

// Placeholder types — replace with your actual DTO and repository
// Replace KeyType and ValueType with your actual types
data class ValueDto(val id: KeyType, val data: ValueType)

interface {service_class_name}Repository {{
    fun find(id: KeyType): ValueType
    fun save(dto: ValueType): ValueType
    fun delete(id: KeyType)
}}

// Config snippet (HOCON) — add to your application.conf:
//
// {cache_name}.config {{
//   expireAfterWrite  = "10m"
//   expireAfterAccess = "5m"
//   initialSize       = 100
//   maximumSize       = 10000
// }}
"""


def main():
    parser = argparse.ArgumentParser(description="Generate cache service template (Kotlin)")
    parser.add_argument("--package", required=True, help="Kotlin package name")
    parser.add_argument("--class-name", required=True, help="Cache interface name")
    parser.add_argument("--service-class", help="Service class name (default: <CacheClass>Service)")
    parser.add_argument("--cache-name", default="orders.cache", help="Cache config name")
    parser.add_argument("--output", default="OrderCache.kt.template", help="Output file name")

    args = parser.parse_args()

    service_class = args.service_class or f"{args.class_name}Service"

    content = TEMPLATE.format(
        package=args.package,
        class_name=args.class_name,
        service_class_name=service_class,
        cache_name=args.cache_name
    )

    output_path = Path(args.output)
    output_path.write_text(content)
    print(f"Generated {output_path}")


if __name__ == "__main__":
    main()
