#!/usr/bin/env python3
"""
OpenAPI specification linter for the Kora 2.x `kora` generator (client modes).

Read-only: the script parses a spec and reports. It never writes, generates or runs Gradle.

Beyond generic OpenAPI checks it reports the two Kora 2.0 client facts that fail silently at
runtime rather than at build time:

  * the client config key, which lower-cases the first letter of the generated API class name
    (tag `pet` -> PetApi -> `<clientConfigPrefix>.petApi`);
  * enum values whose generated constant name differs from the wire value, so only
    `fromValue(raw)` parses them and `Enum.valueOf` / `enumValueOf` throws on valid data.

Usage:
    python3 validate_openapi.py --spec openapi.yaml
    python3 validate_openapi.py --spec openapi.yaml --client-config-prefix httpClient.pet
    python3 validate_openapi.py --spec openapi.yaml --strict --json
"""

import argparse
import json
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("Error: PyYAML not installed. Run: pip install pyyaml")
    sys.exit(1)


HTTP_METHODS = ["get", "put", "post", "delete", "options", "head", "patch", "trace"]

# Kora 2.0 accepts exactly these; java-reactive-*, java-async-*, kotlin-suspend-* and
# kotlin-reactive-* were removed (CodegenMode in io.koraframework:openapi-generator).
CLIENT_MODES = ["java-client", "kotlin-client"]

# A generated enum constant is a normalised Java/Kotlin identifier. Only a value that already
# looks like one has any chance of matching, so anything else definitely needs fromValue().
UPPER_SNAKE = re.compile(r"^[A-Z][A-Z0-9_]*$")


def to_api_name(tag: str) -> str:
    """Approximate the generated *Api class name for an OpenAPI tag.

    The generator does not override toApiName, so this is camelize(sanitizeName(tag)) + "Api",
    with untagged operations collected into DefaultApi. Exotic tags may camelize differently;
    the report tells the reader to confirm against the generated @HttpClient.
    """
    parts = [p for p in re.split(r"[^A-Za-z0-9]+", tag or "") if p]
    if not parts:
        return "DefaultApi"
    camel = "".join(p[0].upper() + p[1:] for p in parts)
    if camel[0].isdigit():
        camel = "_" + camel
    return camel + "Api"


def uncapitalize(name: str) -> str:
    return name[:1].lower() + name[1:] if name else name


class OpenAPIValidator:
    """Validates an OpenAPI specification for Kora 2.x client generation."""

    def __init__(self, spec_path: str, strict: bool = False, client_config_prefix: str = None):
        self.spec_path = Path(spec_path)
        self.strict = strict
        self.client_config_prefix = client_config_prefix
        self.errors = []
        self.warnings = []
        self.notes = []
        self.client_config_keys = {}
        self.spec = None

    # ------------------------------------------------------------------ loading

    def load_spec(self) -> bool:
        if not self.spec_path.exists():
            self.errors.append(f"Specification file not found: {self.spec_path}")
            return False

        suffix = self.spec_path.suffix.lower()
        if suffix not in (".yaml", ".yml", ".json"):
            # Parse anyway - specs are routinely kept with other extensions (.template, none at
            # all) and the loader below handles both YAML and JSON.
            self.warnings.append(
                f"Unexpected file extension {self.spec_path.suffix!r}; parsing it as YAML/JSON"
            )

        try:
            with open(self.spec_path, "r", encoding="utf-8") as f:
                # YAML 1.1 is a superset of JSON, so one loader handles both.
                self.spec = yaml.safe_load(f)
        except yaml.YAMLError as e:
            self.errors.append(f"YAML/JSON parsing error: {e}")
            return False

        if not isinstance(self.spec, dict):
            self.errors.append("Specification root is not a mapping")
            return False
        return True

    # --------------------------------------------------------------- generic 3.x

    def validate_version(self) -> None:
        openapi_version = str(self.spec.get("openapi", ""))

        if not openapi_version:
            if "swagger" in self.spec:
                self.errors.append(
                    "This is a Swagger 2.0 document. Convert it to OpenAPI 3.x before generating."
                )
            else:
                self.errors.append("Missing 'openapi' field. Is this a valid OpenAPI 3.x spec?")
            return

        if not openapi_version.startswith("3."):
            if self.strict:
                self.errors.append(
                    f"OpenAPI version {openapi_version} not supported. Use 3.x for the kora generator."
                )
            else:
                self.warnings.append(
                    f"OpenAPI version {openapi_version} may have limited support. Consider 3.x"
                )

    def validate_info(self) -> None:
        info = self.spec.get("info") or {}

        if not info:
            self.errors.append("Missing 'info' section")
            return
        if not info.get("title"):
            self.errors.append("Missing 'info.title' - required for code generation")
        if not info.get("version"):
            self.errors.append("Missing 'info.version' - required for code generation")

    def _operations(self):
        """Yield (path, method, operation) for every operation in the document."""
        for path, path_item in (self.spec.get("paths") or {}).items():
            if not isinstance(path_item, dict):
                continue
            for method in HTTP_METHODS:
                operation = path_item.get(method)
                if isinstance(operation, dict):
                    yield path, method, operation

    def validate_paths(self) -> None:
        paths = self.spec.get("paths") or {}

        if not paths:
            self.warnings.append("No paths defined - no client methods will be generated")
            return

        for path in paths:
            if not str(path).startswith("/"):
                self.errors.append(f"Path must start with '/': {path}")

        seen_operation_ids = {}
        for path, method, operation in self._operations():
            where = f"{method.upper()} {path}"

            operation_id = operation.get("operationId")
            if not operation_id:
                self.errors.append(
                    f"Missing operationId for {where} - the generator derives the client method "
                    f"name, its response types and its per-operation config key from it"
                )
            elif operation_id in seen_operation_ids:
                self.errors.append(
                    f"Duplicate operationId '{operation_id}': {seen_operation_ids[operation_id]} "
                    f"and {where}"
                )
            else:
                seen_operation_ids[operation_id] = where

            responses = operation.get("responses") or {}
            if not responses:
                self.errors.append(f"No responses defined for {where}")

    def validate_components(self) -> None:
        schemas = ((self.spec.get("components") or {}).get("schemas")) or {}

        if not schemas:
            self.warnings.append("No schemas defined - no models will be generated")
            return

        for name, schema in schemas.items():
            if not isinstance(schema, dict):
                continue
            ref = schema.get("$ref")
            if ref and len(schema) == 1 and ref.split("/")[-1] == name:
                self.errors.append(f"Self-referencing schema: {name}")

    # ------------------------------------------------------------ Kora 2.x rules

    def report_client_config_keys(self) -> None:
        """Derive the HOCON section each generated client will read.

        This is the single most expensive mistake in a 1.x -> 2.0 migration: the generator
        lower-cases the first letter of the API class name, an unknown HOCON section is ignored
        without a warning, and the client then has no `url` and hangs until requestTimeout.
        """
        tags = set()
        untagged = False
        for _, _, operation in self._operations():
            operation_tags = operation.get("tags") or []
            if operation_tags:
                tags.update(str(t) for t in operation_tags)
            else:
                untagged = True

        if untagged:
            tags.add("")

        if not tags:
            return

        prefix = self.client_config_prefix
        for tag in sorted(tags):
            api_name = to_api_name(tag)
            key = uncapitalize(api_name)
            self.client_config_keys[tag or "(untagged)"] = f"{prefix}.{key}" if prefix else key

        if prefix:
            self.notes.append(
                "Client config sections for clientConfigPrefix="
                f"'{prefix}' (confirm against the generated @HttpClient value):"
            )
        else:
            self.notes.append(
                "Generated API classes and the name appended to clientConfigPrefix "
                "(pass --client-config-prefix for full keys):"
            )
        for tag in sorted(tags):
            label = tag or "(untagged)"
            self.notes.append(
                f"    tag {label!r} -> {to_api_name(tag)} -> {self.client_config_keys[label]}"
            )

        self.notes.append(
            "The generator prints the same mapping after generation "
            "('Generated Kora OpenAPI HTTP clients and config paths')."
        )

    def _iter_enums(self, node, trail):
        """Walk the document yielding (json-pointer-ish trail, enum values)."""
        if isinstance(node, dict):
            values = node.get("enum")
            if isinstance(values, list) and values:
                yield trail, values
            for key, value in node.items():
                if key != "enum":
                    yield from self._iter_enums(value, f"{trail}.{key}")
        elif isinstance(node, list):
            for index, value in enumerate(node):
                yield from self._iter_enums(value, f"{trail}[{index}]")

    def validate_enums(self) -> None:
        offenders = []
        for trail, values in self._iter_enums(self.spec, "$"):
            bad = [v for v in values if not (isinstance(v, str) and UPPER_SNAKE.fullmatch(v))]
            if bad:
                sample = ", ".join(repr(v) for v in bad[:4])
                more = "" if len(bad) <= 4 else f", +{len(bad) - 4} more"
                offenders.append(f"{trail}: {sample}{more}")

        if offenders:
            self.warnings.append(
                "Enum values whose generated constant name differs from the wire value - parse "
                "them with MyEnum.fromValue(raw); Enum.valueOf / enumValueOf throws on valid data:"
            )
            for offender in offenders[:10]:
                self.warnings.append(f"    {offender}")
            if len(offenders) > 10:
                self.warnings.append(f"    (+{len(offenders) - 10} more enum locations)")

    def validate_security_schemes(self) -> None:
        schemes = ((self.spec.get("components") or {}).get("securitySchemes")) or {}
        if not schemes:
            return

        needs_provider = []
        scheme_notes = []
        for name, scheme in schemes.items():
            if not isinstance(scheme, dict):
                self.errors.append(f"Security scheme '{name}' is not a mapping")
                continue

            scheme_type = scheme.get("type", "")
            tag = (name[:1].upper() + name[1:]) if name else name

            if scheme_type == "http":
                http_scheme = str(scheme.get("scheme", "")).lower()
                if http_scheme == "basic":
                    scheme_notes.append(
                        f"    {name}: basic -> ApiSecurity.{tag}; credentials at "
                        f"<securityConfigPrefix>.{name}.username / .password"
                    )
                elif http_scheme == "bearer":
                    needs_provider.append((name, tag, "bearer"))
                else:
                    self.warnings.append(
                        f"HTTP scheme '{http_scheme}' on '{name}' is not one the generator wires; "
                        f"handle it with your own interceptor"
                    )

            elif scheme_type == "apiKey":
                in_value = scheme.get("in", "")
                if in_value not in ("header", "query", "cookie"):
                    self.errors.append(f"Invalid apiKey 'in' value: {in_value!r} for '{name}'")
                else:
                    scheme_notes.append(
                        f"    {name}: apiKey in {in_value} -> ApiSecurity.{tag}; credential at "
                        f"<securityConfigPrefix>.{name}"
                    )

            elif scheme_type == "oauth2":
                if not scheme.get("flows"):
                    self.warnings.append(f"OAuth2 scheme without flows: {name}")
                needs_provider.append((name, tag, "oauth2"))

            else:
                self.warnings.append(
                    f"Security scheme type {scheme_type!r} on '{name}' has no generated mapping; "
                    f"generation may fail or the scheme may need a hand-written interceptor"
                )

        for name, tag, _ in needs_provider:
            scheme_notes.append(
                f"    {name}: -> ApiSecurity.{tag}; no credential config, the token comes from "
                f"your HttpClientTokenProvider"
            )

        if scheme_notes:
            self.notes.append(
                "Security schemes (the tag capitalises the scheme name; the config key uses it "
                "verbatim):"
            )
            self.notes.extend(sorted(scheme_notes))

        for name, tag, kind in needs_provider:
            self.warnings.append(
                f"Scheme '{name}' ({kind}) generates the tag ApiSecurity.{tag} but NO token "
                f"provider - the application must supply "
                f"@Tag(ApiSecurity.{tag}.class) HttpClientTokenProvider or the graph will not build. "
                f"If this service does not use it, the provider must return null."
            )

    def validate_kora_compatibility(self) -> None:
        for path, method, operation in self._operations():
            where = f"{method.upper()} {path}"

            request_body = operation.get("requestBody") or {}
            content = request_body.get("content") or {}
            if len(content) > 1:
                self.warnings.append(
                    f"Multiple request content types for {where} ({', '.join(sorted(content))}) - "
                    f"the generator uses one of them"
                )

    # --------------------------------------------------------------- entry point

    def validate(self) -> bool:
        if not self.load_spec():
            return False

        validators = [
            self.validate_version,
            self.validate_info,
            self.validate_paths,
            self.validate_components,
            self.validate_enums,
            self.validate_security_schemes,
            self.validate_kora_compatibility,
            self.report_client_config_keys,
        ]

        for validator in validators:
            try:
                validator()
            except Exception as e:  # a malformed spec must not crash the linter
                self.errors.append(f"Validation error in {validator.__name__}: {e}")

        if self.strict and self.warnings:
            return False
        return len(self.errors) == 0

    def report(self) -> str:
        lines = [
            f"OpenAPI Validation Report (Kora 2.x client): {self.spec_path}",
            "=" * 72,
        ]

        if self.errors:
            lines.append(f"\nERRORS ({len(self.errors)}):")
            lines.extend(f"  - {error}" for error in self.errors)

        if self.warnings:
            lines.append(f"\nWARNINGS ({len(self.warnings)}):")
            lines.extend(f"  - {warning}" for warning in self.warnings)

        if self.notes:
            lines.append("\nNOTES:")
            lines.extend(f"  {note}" for note in self.notes)

        if not self.errors and not self.warnings:
            lines.append("\nNo issues found.")

        lines.append("")
        if self.errors:
            lines.append("Result: FAILED - fix the errors before generating")
        elif self.warnings and self.strict:
            lines.append("Result: FAILED - warnings are errors under --strict")
        elif self.warnings:
            lines.append("Result: PASSED with warnings")
        else:
            lines.append("Result: PASSED")

        return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Validate an OpenAPI specification for Kora 2.x client generation"
    )
    parser.add_argument(
        "--spec", "-s", required=True,
        help="Path to the OpenAPI specification file (YAML or JSON)",
    )
    parser.add_argument(
        "--client-config-prefix", "-p", default=None,
        help="The configOptions.clientConfigPrefix value, so the report can print full HOCON keys",
    )
    parser.add_argument(
        "--mode", choices=CLIENT_MODES, default=None,
        help="Intended client mode; only java-client and kotlin-client exist in Kora 2.0",
    )
    parser.add_argument("--strict", action="store_true", help="Treat warnings as errors")
    parser.add_argument("--json", action="store_true", help="Output the report as JSON")

    args = parser.parse_args()

    validator = OpenAPIValidator(args.spec, args.strict, args.client_config_prefix)
    is_valid = validator.validate()

    if args.json:
        print(json.dumps({
            "valid": is_valid,
            "spec_path": str(args.spec),
            "mode": args.mode,
            "client_config_prefix": args.client_config_prefix,
            "client_config_keys": validator.client_config_keys,
            "errors": validator.errors,
            "warnings": validator.warnings,
            "notes": validator.notes,
            "strict": args.strict,
        }, indent=2, ensure_ascii=False))
    else:
        print(validator.report())

    sys.exit(0 if is_valid else 1)


if __name__ == "__main__":
    main()
