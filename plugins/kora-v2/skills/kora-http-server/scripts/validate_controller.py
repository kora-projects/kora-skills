#!/usr/bin/env python3
"""
kora-http-server validator — validates Kora HTTP controller classes.

Checks for common issues:
- Missing @HttpController or @HttpRoute annotations
- Missing @Json on POST/PUT methods
- @Path parameter name mismatch with URL path
- Missing @Tag(HttpServerModule.class) on interceptors

Usage:
    python validate_controller.py --json /path/to/Controller.java
    python validate_controller.py /path/to/Controller.java
"""

import argparse
import json
import re
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import List, Dict, Optional


@dataclass
class ValidationResult:
    """Validation result structure."""
    file: str
    valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    info: List[str] = field(default_factory=list)


def read_file(path: str) -> str:
    """Read file content."""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return ""
    except Exception as e:
        return ""


def check_http_controller_annotation(content: str) -> List[str]:
    """Check for @HttpController annotation."""
    errors = []
    if "@HttpController" not in content:
        errors.append("Missing @HttpController annotation on class")
    return errors


def check_http_route_annotations(content: str) -> List[str]:
    """Check for @HttpRoute annotations."""
    errors = []
    if "@HttpRoute" not in content:
        errors.append("No @HttpRoute methods found")
    return errors


def check_path_parameter_match(content: str) -> List[str]:
    """Check that {var} path segments have a matching @Path argument.

    @Path may name the variable explicitly (@Path("id")) or rely on the argument
    name (@Path String id). Only flag a {var} when neither an explicit @Path("var")
    nor an argument literally named 'var' is present.
    """
    warnings = []

    # Find all @HttpRoute annotations with paths
    route_pattern = r'@HttpRoute\([^)]*path\s*=\s*"([^"]+)"'
    routes = re.findall(route_pattern, content)

    # Explicit @Path("name") values
    explicit_path_params = set(re.findall(r'@Path\("([^"]+)"\)', content))
    # @Path arguments that rely on the argument name: @Path [Type] name
    implicit_path_args = set(re.findall(r'@Path\s+(?:final\s+)?[\w<>,\.\[\]]+\s+(\w+)', content))
    implicit_path_args |= set(re.findall(r'@Path\s+(\w+)\s*:', content))  # Kotlin: @Path name: Type

    known = explicit_path_params | implicit_path_args

    for route_path in routes:
        path_vars = re.findall(r'\{([^}]+)\}', route_path)
        for path_var in path_vars:
            if path_var not in known:
                warnings.append(
                    f"Path variable {{{path_var}}} has no obvious matching @Path argument "
                    f"(expected @Path(\"{path_var}\") or an argument named '{path_var}')"
                )

    return warnings


def check_json_annotation(content: str) -> List[str]:
    """Check for @Json on POST/PUT methods."""
    warnings = []

    # Find POST/PUT methods
    post_pattern = r'@HttpRoute\([^)]*method\s*=\s*HttpMethod\.(POST|PUT|PATCH)'
    post_matches = re.finditer(post_pattern, content)

    for match in post_matches:
        # Get the line number (approximate)
        line_num = content[:match.start()].count('\n') + 1

        # Check if @Json is present near this method
        # Look at next 500 characters after the match
        next_chunk = content[match.start():match.start() + 500]
        if "@Json" not in next_chunk:
            warnings.append(f"Line {line_num}: POST/PUT/PATCH method may be missing @Json annotation")

    return warnings


def check_interceptor_tag(content: str) -> List[str]:
    """Inform about interceptor registration scope.

    A global interceptor needs @Tag(HttpServerModule.class) (or ::class in Kotlin);
    controller/method interceptors are applied with @InterceptWith and do NOT need the tag.
    Only inform when an interceptor has neither, since it may then be unreachable.
    """
    info = []

    is_interceptor = (
        "implements HttpServerInterceptor" in content
        or ": HttpServerInterceptor" in content
    )
    if is_interceptor:
        has_tag = "HttpServerModule.class" in content or "HttpServerModule::class" in content
        has_intercept_with = "@InterceptWith" in content
        if not has_tag and not has_intercept_with:
            info.append(
                "Interceptor defined but not registered: add @Tag(HttpServerModule.class) "
                "for a global interceptor, or apply it with @InterceptWith on a controller/method"
            )

    return info


def validate_file(path: str) -> ValidationResult:
    """Validate a single file."""
    result = ValidationResult(file=path, valid=True)

    content = read_file(path)
    if not content:
        result.valid = False
        result.errors.append(f"Cannot read file: {path}")
        return result

    # Run all checks
    result.errors.extend(check_http_controller_annotation(content))
    result.errors.extend(check_http_route_annotations(content))
    result.warnings.extend(check_path_parameter_match(content))
    result.warnings.extend(check_json_annotation(content))
    result.info.extend(check_interceptor_tag(content))

    # Add info
    if re.search(r'@HttpController\s*\(\s*"', content):
        result.warnings.append(
            "@HttpController takes no path argument in Kora - put the prefix on each @HttpRoute(path = ...)"
        )

    if "@HttpRoute" in content:
        route_count = len(re.findall(r'@HttpRoute', content))
        result.info.append(f"Found {route_count} HTTP route(s)")

    # Set valid flag
    if result.errors:
        result.valid = False

    return result


def print_human_readable(result: ValidationResult, verbose: bool = False):
    """Print result in human-readable format."""
    if result.valid:
        print(f"✓ {result.file}: Validation passed")
    else:
        print(f"✗ {result.file}: Validation failed")

    for error in result.errors:
        print(f"  ERROR: {error}")

    for warning in result.warnings:
        print(f"  WARNING: {warning}")

    if verbose:
        for info in result.info:
            print(f"  INFO: {info}")


def main():
    parser = argparse.ArgumentParser(
        description='Validate Kora HTTP controller classes',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  %(prog)s /path/to/UserController.java
  %(prog)s --json /path/to/UserController.java
  %(prog)s --verbose /path/to/Controller.java
'''
    )
    parser.add_argument('path', help='Path to Java/Kotlin controller file')
    parser.add_argument('--json', action='store_true', help='Output as JSON')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')

    args = parser.parse_args()

    try:
        result = validate_file(args.path)

        if args.json:
            print(json.dumps(asdict(result), indent=2))
        else:
            print_human_readable(result, args.verbose)

        sys.exit(0 if result.valid else 1)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
