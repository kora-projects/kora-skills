#!/usr/bin/env python3
"""
Generate a cache service template for Kora AOP.

Usage:
    python generate_cache_service.py --package com.example.cache --class-name OrderCache --cache-name orders.cache

Output:
    Creates a Java cache interface and service with @Cacheable + @CachePut + @CacheInvalidate.
"""

import argparse
from pathlib import Path

TEMPLATE = """// Typed cache + service using all four cache annotations.
// Replace `{package}` with your package.
// Replace KeyType and ValueType with your actual types (e.g., UUID, OrderDto)

package {package};

import ru.tinkoff.kora.cache.annotation.Cache;
import ru.tinkoff.kora.cache.annotation.CacheInvalidate;
import ru.tinkoff.kora.cache.annotation.CachePut;
import ru.tinkoff.kora.cache.annotation.Cacheable;
import ru.tinkoff.kora.cache.caffeine.CaffeineCache;
import ru.tinkoff.kora.common.Component;

// Remove this import if not using UUID as your key type
import java.util.UUID;

// 1. Typed cache interface — Kora generates the impl and registers it as a component.
@Cache("{cache_name}")
public interface {class_name} extends CaffeineCache<KeyType, ValueType> {{

    // For a composite key, define an inner record and use it as K:
    //
    //   @Cache("{cache_name}")
    //   public interface {class_name} extends CaffeineCache<{class_name}.Key, ValueType> {{
    //       record Key(UUID tenantId, UUID orderId) {{}}
    //   }}
}}

// 2. Service using all four cache annotations.
@Component
class {service_class_name} {{                                          // non-final

    private final {class_name} cache;
    private final {service_class_name}Repository repo;

    public {service_class_name}({class_name} cache, {service_class_name}Repository repo) {{
        this.cache = cache;
        this.repo  = repo;
    }}

    @Cacheable({class_name}.class)                               // read-through
    public ValueType get(KeyType id) {{
        return repo.find(id);
    }}

    @CachePut({class_name}.class)                                // write-through; key = first arg (id)
    public ValueType save(KeyType id, ValueType dto) {{
        return repo.save(dto);
    }}

    @CacheInvalidate({class_name}.class)                         // evict the entry for id
    public void delete(KeyType id) {{
        repo.delete(id);
    }}

    @CacheInvalidate(value = {class_name}.class, allEntries = true)  // flush entire cache
    public void flush() {{
        // use sparingly — invalidates ALL entries
    }}
}}

// Placeholder types — replace with your actual DTO and repository
// Replace KeyType and ValueType with your actual types
record ValueDto(KeyType id, String data) {{}}

interface {service_class_name}Repository {{
    ValueType find(KeyType id);
    ValueType save(ValueType dto);
    void delete(KeyType id);
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
    parser = argparse.ArgumentParser(description="Generate cache service template")
    parser.add_argument("--package", required=True, help="Java package name")
    parser.add_argument("--class-name", required=True, help="Cache interface name")
    parser.add_argument("--service-class", default=None, help="Service class name (default: <CacheClass>Service)")
    parser.add_argument("--cache-name", default="cache.default", help="Cache config name")
    parser.add_argument("--output", default="OrderCache.java.template", help="Output file name")

    args = parser.parse_args()

    service_class = args.service_class if args.service_class else f"{args.class_name}Service"

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
