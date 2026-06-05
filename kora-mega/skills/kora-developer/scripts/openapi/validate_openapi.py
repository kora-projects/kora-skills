#!/usr/bin/env python3
"""
OpenAPI Specification Validator for Kora OpenAPI Generator

Validates OpenAPI 3.x specifications before code generation.
Checks for common issues that may cause generation failures.

Usage:
    python validate_openapi.py --spec openapi.yaml
    python validate_openapi.py --spec openapi.yaml --strict
"""

import argparse
import json
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("Error: PyYAML not installed. Run: pip install pyyaml")
    sys.exit(1)


class OpenAPIValidator:
    """Validates OpenAPI specifications for Kora code generation."""

    def __init__(self, spec_path: str, strict: bool = False):
        self.spec_path = Path(spec_path)
        self.strict = strict
        self.errors = []
        self.warnings = []
        self.spec = None

    def load_spec(self) -> bool:
        """Load and parse OpenAPI specification."""
        if not self.spec_path.exists():
            self.errors.append(f"Specification file not found: {self.spec_path}")
            return False

        try:
            with open(self.spec_path, 'r', encoding='utf-8') as f:
                if self.spec_path.suffix in ['.yaml', '.yml']:
                    self.spec = yaml.safe_load(f)
                elif self.spec_path.suffix == '.json':
                    with open(self.spec_path, 'r', encoding='utf-8') as json_f:
                        self.spec = json.load(json_f)
                else:
                    self.errors.append(f"Unsupported file format: {self.spec_path.suffix}")
                    return False
            return True
        except yaml.YAMLError as e:
            self.errors.append(f"YAML parsing error: {e}")
            return False
        except json.JSONDecodeError as e:
            self.errors.append(f"JSON parsing error: {e}")
            return False

    def validate_version(self) -> bool:
        """Check OpenAPI version compatibility."""
        openapi_version = self.spec.get('openapi', '')

        if not openapi_version:
            self.errors.append("Missing 'openapi' field. Is this a valid OpenAPI 3.x spec?")
            return False

        if not openapi_version.startswith('3.'):
            if self.strict:
                self.errors.append(f"OpenAPI version {openapi_version} not supported. Use 3.x for Kora generator.")
                return False
            else:
                self.warnings.append(f"OpenAPI version {openapi_version} may have limited support. Consider 3.x")

        return True

    def validate_info(self) -> bool:
        """Check required info section."""
        info = self.spec.get('info', {})

        if not info:
            self.errors.append("Missing 'info' section")
            return False

        if not info.get('title'):
            self.errors.append("Missing 'info.title' - required for code generation")
            return False

        if not info.get('version'):
            self.errors.append("Missing 'info.version' - required for code generation")
            return False

        return True

    def validate_paths(self) -> bool:
        """Check paths section."""
        paths = self.spec.get('paths', {})

        if not paths:
            self.warnings.append("No paths defined - nothing will be generated")
            return True

        for path, path_item in paths.items():
            if not path.startswith('/'):
                self.errors.append(f"Path must start with '/': {path}")

            if not isinstance(path_item, dict):
                continue

            for method in ['get', 'post', 'put', 'delete', 'patch', 'options', 'head']:
                operation = path_item.get(method, {})
                if not operation:
                    continue

                # Check operationId
                if not operation.get('operationId'):
                    self.errors.append(f"Missing operationId for {method.upper()} {path}")

                # Check responses
                responses = operation.get('responses', {})
                if not responses:
                    self.errors.append(f"No responses defined for {method.upper()} {path}")

        return True

    def validate_components(self) -> bool:
        """Check components section."""
        components = self.spec.get('components', {})
        schemas = components.get('schemas', {})

        if not schemas:
            self.warnings.append("No schemas defined - no DTOs will be generated")
            return True

        for name, schema in schemas.items():
            if not isinstance(schema, dict):
                continue

            # Check for circular references (basic check)
            if '$ref' in schema and len(schema) == 1:
                ref = schema['$ref']
                if ref.startswith('#/components/schemas/'):
                    ref_name = ref.split('/')[-1]
                    if ref_name == name:
                        self.errors.append(f"Self-referencing schema: {name}")

        return True

    def validate_security_schemes(self) -> bool:
        """Check security schemes for Kora compatibility."""
        components = self.spec.get('components', {})
        security_schemes = components.get('securitySchemes', {})

        if not security_schemes:
            return True

        for name, scheme in security_schemes.items():
            scheme_type = scheme.get('type', '')

            if scheme_type == 'http':
                scheme_value = scheme.get('scheme', '')
                if scheme_value not in ['bearer', 'basic']:
                    self.warnings.append(f"HTTP scheme '{scheme_value}' may have limited support: {name}")

            elif scheme_type == 'apiKey':
                in_value = scheme.get('in', '')
                if in_value not in ['header', 'query', 'cookie']:
                    self.errors.append(f"Invalid apiKey 'in' value: {in_value} for {name}")

            elif scheme_type == 'oauth2':
                flows = scheme.get('flows', {})
                if not flows:
                    self.warnings.append(f"OAuth2 scheme without flows: {name}")

        return True

    def validate_kora_compatibility(self) -> bool:
        """Check Kora-specific compatibility issues."""
        # Check for unsupported features
        paths = self.spec.get('paths', {})

        for path, path_item in paths.items():
            if not isinstance(path_item, dict):
                continue

            for method in ['get', 'post', 'put', 'delete', 'patch']:
                operation = path_item.get(method, {})
                if not operation:
                    continue

                # Check for requestBody with multiple content types
                request_body = operation.get('requestBody', {})
                if request_body:
                    content = request_body.get('content', {})
                    if len(content) > 1 and self.strict:
                        self.warnings.append(
                            f"Multiple content types for {method.upper()} {path} - "
                            f"Kora uses first one"
                        )

        return True

    def validate(self) -> bool:
        """Run all validations."""
        if not self.load_spec():
            return False

        validators = [
            self.validate_version,
            self.validate_info,
            self.validate_paths,
            self.validate_components,
            self.validate_security_schemes,
            self.validate_kora_compatibility,
        ]

        for validator in validators:
            try:
                validator()
            except Exception as e:
                self.errors.append(f"Validation error in {validator.__name__}: {e}")

        return len(self.errors) == 0

    def report(self) -> str:
        """Generate validation report."""
        lines = []
        lines.append(f"OpenAPI Validation Report: {self.spec_path}")
        lines.append("=" * 60)

        if self.errors:
            lines.append(f"\nERRORS ({len(self.errors)}):")
            for error in self.errors:
                lines.append(f"  - {error}")

        if self.warnings:
            lines.append(f"\n WARNINGS ({len(self.warnings)}):")
            for warning in self.warnings:
                lines.append(f"  - {warning}")

        if not self.errors and not self.warnings:
            lines.append("\nNo issues found!")

        lines.append("")
        if self.errors:
            lines.append("Result: FAILED - Fix errors before code generation")
        elif self.warnings:
            lines.append("Result: PASSED with warnings")
        else:
            lines.append("Result: PASSED")

        return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description='Validate OpenAPI specification for Kora code generation'
    )
    parser.add_argument(
        '--spec', '-s',
        required=True,
        help='Path to OpenAPI specification file (YAML or JSON)'
    )
    parser.add_argument(
        '--strict',
        action='store_true',
        help='Treat warnings as errors'
    )
    parser.add_argument(
        '--json',
        action='store_true',
        help='Output report as JSON'
    )

    args = parser.parse_args()

    validator = OpenAPIValidator(args.spec, args.strict)
    is_valid = validator.validate()
    report = validator.report()

    if args.json:
        output = {
            'valid': is_valid,
            'spec_path': str(args.spec),
            'errors': validator.errors,
            'warnings': validator.warnings,
            'strict': args.strict
        }
        print(json.dumps(output, indent=2))
    else:
        print(report)

    sys.exit(0 if is_valid else 1)


if __name__ == '__main__':
    main()
