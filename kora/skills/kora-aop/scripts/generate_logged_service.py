#!/usr/bin/env python3
"""
Generate a logged service template for Kora AOP.

Usage:
    python generate_logged_service.py --package com.example.service --class-name UserService

Output:
    Creates a Java service with @Log and @Mdc annotations.
"""

import argparse
from pathlib import Path

TEMPLATE = """// Service with method logging using @Log and @Mdc.
// Replace `{package}` with your package.

package {package};

import ru.tinkoff.kora.common.Component;
import ru.tinkoff.kora.logging.common.annotation.Log;
import ru.tinkoff.kora.logging.common.annotation.Mdc;

import java.util.Optional;

@Component
public class {class_name} {{                                        // non-final

    private final {class_name}Repository repository;

    public {class_name}({class_name}Repository repository) {{
        this.repository = repository;
    }}

    // Log entry + exit with args and result at TRACE/DEBUG level.
    @Log
    public Optional<Entity> findById(String id) {{
        return repository.findById(id);
    }}

    // Log only entry (not exit) — useful for fire-and-forget.
    @Log.in
    public void trackEvent(String eventType, @Mdc("user_id") String userId) {{
        // @Mdc puts userId into SLF4J MDC context for structured logging
        // All log statements in this method (and child calls) include user_id
    }}

    // Log only result (not entry) — useful when args contain PII.
    @Log.result
    public String generateToken(String userId) {{
        // args not logged, only result at TRACE/DEBUG
        return "token-" + userId;
    }}

    // Suppress specific parameter from logging.
    @Log
    public void update(
        String id,
        @Log.off String secretToken,          // never logged
        @Mdc("operation") String operation    // added to MDC
    ) {{
        // ...
    }}

    // Selective field logging with @Log.off on method + @Log.out.
    @Log.out
    @Log.off                                  // suppress args, log only result
    public byte[] downloadFile(String fileId) {{
        // args not logged (might be large), only result marker
        return new byte[0];
    }}
}}

// Placeholder dependency — replace with your actual repository
interface {class_name}Repository {{
    Optional<Entity> findById(String id);
}}

record Entity(String id, String data) {{}}

// Config snippet (HOCON) — add to your application.conf:
//
// logging {{
//   level = "INFO"                            // INFO shows boundary markers only
//   // level = "DEBUG"                        // DEBUG shows args + result data
// }}
//
// Note: @Log output depends on log level:
// - TRACE/DEBUG: shows `> {{data: {{...}}}}` and `< {{data: {{...}}}}`
// - INFO: shows `>` and `<` markers only (safe for production)
// - WARN+: nothing
"""


def main():
    parser = argparse.ArgumentParser(description="Generate logged service template")
    parser.add_argument("--package", required=True, help="Java package name")
    parser.add_argument("--class-name", required=True, help="Service class name")
    parser.add_argument("--output", default="LoggedService.java.template", help="Output file name")

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
