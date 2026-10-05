#!/usr/bin/env python3
"""
OpenAPI specification checker for the Kora 2.x `kora` generator.

Read-only: this script never writes, moves or deletes anything, and never runs Gradle. It parses
the spec and reports issues that the generator turns into build failures, missing output, or
runtime bugs that only show up against real data.

Checks specific to Kora 2.0:
  * only java-client / java-server / kotlin-client / kotlin-server generator modes exist
  * status-code range responses (4XX, 5XX) take the real status as the record's first component
  * security scheme names become ApiSecurity.<Tag> markers — the tag is reported so extractors
    can be annotated correctly (ordinal SecurityRequirementTagN is Kora 1.x and never matches)
  * enum wire values that differ from the generated constant names must be parsed with
    fromValue(), never Enum.valueOf()
  * server security schemes are limited to apiKey (header/query/cookie), http basic/bearer,
    oauth2 and openIdConnect

Usage:
    python3 validate_openapi.py --spec openapi.yaml
    python3 validate_openapi.py --spec openapi.yaml --mode kotlin-server
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
    print("Error: PyYAML not installed. Run: pip install pyyaml", file=sys.stderr)
    sys.exit(2)


# CodegenMode in io.koraframework:openapi-generator.
SUPPORTED_MODES = ("java-client", "java-server", "kotlin-client", "kotlin-server")

# Kora 1.x-era mode names that are invalid in 2.0, mapped to their 2.0 replacement.
REMOVED_MODES = {
    "java-async-server": "java-server",
    "java-reactive-server": "java-server",
    "java-reactive-client": "java-client",
    "kotlin-suspend-server": "kotlin-server",
    "kotlin-reactive-server": "kotlin-server",
    "kotlin-suspend-client": "kotlin-client",
    "kotlin-reactive-client": "kotlin-client",
}

HTTP_METHODS = ("get", "put", "post", "delete", "options", "head", "patch", "trace")

RANGE_CODE = re.compile(r"^[1-5]XX$")


def camelize(name, lower_first=True):
    """Approximate the generator's toVarName()/camelize() for reporting purposes."""
    if re.fullmatch(r"[A-Z0-9_]*", name or ""):
        return name
    parts = [p for p in re.split(r"[^0-9A-Za-z$]+", name or "") if p]
    if not parts:
        return name or ""
    out = parts[0]
    out = out[:1].lower() + out[1:] if lower_first else out[:1].upper() + out[1:]
    for part in parts[1:]:
        out += part[:1].upper() + part[1:]
    return out


def security_tag_name(scheme_name):
    """components.securitySchemes.<name> -> the generated ApiSecurity.<Tag> marker."""
    varname = camelize(scheme_name, lower_first=True)
    return varname[:1].upper() + varname[1:] if varname else scheme_name


def api_class_name(tag):
    """An OpenAPI tag -> the generated <Tag>Api* class prefix."""
    if not tag:
        return "DefaultApi"
    return camelize(tag, lower_first=False) + "Api"


def enum_constant_name(value):
    """Approximate toEnumVarName() for the fromValue vs valueOf comparison."""
    text = str(value)
    if not text:
        return "EMPTY"
    return re.sub(r"[^0-9A-Za-z]+", "_", text).upper().strip("_") or "EMPTY"


class OpenAPIChecker:
    def __init__(self, spec_path, mode=None, strict=False):
        self.spec_path = Path(spec_path)
        self.mode = mode
        self.strict = strict
        self.errors = []
        self.warnings = []
        self.notes = []
        self.spec = None

    # ---------------------------------------------------------------- loading

    def load(self):
        if not self.spec_path.exists():
            self.errors.append("Specification file not found: %s" % self.spec_path)
            return False
        # ".template" wrappers are common in skill assets; look past them for the real suffix.
        suffixes = [s.lower() for s in self.spec_path.suffixes if s.lower() != ".template"]
        suffix = suffixes[-1] if suffixes else ""
        try:
            text = self.spec_path.read_text(encoding="utf-8")
            if suffix == ".json":
                self.spec = json.loads(text)
            else:
                if suffix not in (".yaml", ".yml"):
                    self.warnings.append(
                        "Unrecognised extension '%s'; parsing as YAML (a superset of JSON)"
                        % (self.spec_path.suffix or "<none>")
                    )
                self.spec = yaml.safe_load(text)
        except yaml.YAMLError as e:
            self.errors.append("YAML parsing error: %s" % e)
            return False
        except json.JSONDecodeError as e:
            self.errors.append("JSON parsing error: %s" % e)
            return False
        if not isinstance(self.spec, dict):
            self.errors.append("Top-level document is not a mapping — this is not an OpenAPI spec")
            return False
        return True

    # ----------------------------------------------------------------- checks

    def check_mode(self):
        if self.mode is None:
            return
        if self.mode in REMOVED_MODES:
            self.errors.append(
                "Generator mode '%s' was removed in Kora 2.0 — use '%s'. Kora 2.0 contracts are "
                "synchronous; there are no reactive/async/suspend server or client modes."
                % (self.mode, REMOVED_MODES[self.mode])
            )
        elif self.mode not in SUPPORTED_MODES:
            self.errors.append(
                "Generator mode '%s' is not supported. Supported modes: %s"
                % (self.mode, ", ".join(SUPPORTED_MODES))
            )

    def check_version(self):
        version = self.spec.get("openapi", "")
        if not version:
            self.errors.append("Missing 'openapi' field — the kora generator needs an OpenAPI 3.x spec")
        elif not str(version).startswith("3."):
            self.errors.append("OpenAPI version '%s' is not supported; use 3.x" % version)

    def check_info(self):
        info = self.spec.get("info") or {}
        if not info:
            self.errors.append("Missing 'info' section")
            return
        if not info.get("title"):
            self.errors.append("Missing 'info.title'")
        if not info.get("version"):
            self.errors.append("Missing 'info.version'")

    def operations(self):
        for path, item in (self.spec.get("paths") or {}).items():
            if not isinstance(item, dict):
                continue
            for method in HTTP_METHODS:
                op = item.get(method)
                if isinstance(op, dict):
                    yield path, method, op

    def check_operations(self):
        paths = self.spec.get("paths") or {}
        if not paths:
            self.warnings.append("No paths defined — the generator will emit no controller")
            return

        for path in paths:
            if not str(path).startswith("/"):
                self.errors.append("Path must start with '/': %s" % path)

        seen_ids = {}
        untagged = []
        for path, method, op in self.operations():
            where = "%s %s" % (method.upper(), path)

            operation_id = op.get("operationId")
            if not operation_id:
                self.errors.append(
                    "Missing operationId for %s — it becomes the delegate method name and the "
                    "generated response type prefix" % where
                )
            else:
                if operation_id in seen_ids:
                    self.errors.append(
                        "Duplicate operationId '%s' (%s and %s) — generated method and response "
                        "type names would collide" % (operation_id, seen_ids[operation_id], where)
                    )
                seen_ids[operation_id] = where

            tags = op.get("tags") or []
            if not tags:
                untagged.append(where)

            responses = op.get("responses") or {}
            if not responses:
                self.errors.append("No responses defined for %s — nothing to return" % where)
            for code in responses:
                if RANGE_CODE.match(str(code)):
                    self.notes.append(
                        "%s declares the status-code range '%s': its record takes the real status as "
                        "the first component (like 'default'); pass a code inside the range." % (where, code)
                    )

            if len(responses) == 1:
                only = next(iter(responses))
                self.notes.append(
                    "%s declares a single response ('%s'), so its generated type is a record/data "
                    "class directly — there is no sealed interface and no per-status nested type."
                    % (where, only)
                )

            body = op.get("requestBody") or {}
            content = body.get("content") or {}
            if len(content) > 1:
                self.warnings.append(
                    "%s declares %d request content types; the generator uses the first one (%s)"
                    % (where, len(content), next(iter(content)))
                )

        if untagged:
            self.warnings.append(
                "%d operation(s) have no 'tags' and will be generated into DefaultApiController / "
                "DefaultApiDelegate: %s" % (len(untagged), ", ".join(untagged[:5]))
            )

        tags = sorted({t for _, _, op in self.operations() for t in (op.get("tags") or [])})
        for tag in tags:
            base = api_class_name(tag)
            self.notes.append(
                "tag '%s' -> %sController / %sDelegate / %sResponses" % (tag, base, base, base)
            )

    def check_security(self):
        components = self.spec.get("components") or {}
        schemes = components.get("securitySchemes") or {}
        used = set()
        for _, _, op in self.operations():
            for requirement in op.get("security") or []:
                used.update(requirement.keys())
        for requirement in self.spec.get("security") or []:
            used.update(requirement.keys())

        if not schemes:
            if used:
                self.errors.append(
                    "Operations reference security schemes %s but components.securitySchemes is "
                    "empty — ApiSecurity will not be generated" % sorted(used)
                )
            return

        for name, scheme in schemes.items():
            if not isinstance(scheme, dict):
                continue
            tag = security_tag_name(name)
            self.notes.append(
                "securityScheme '%s' -> tag @Tag(ApiSecurity.%s.class) / @Tag(ApiSecurity.%s::class)"
                % (name, tag, tag)
            )

            kind = scheme.get("type", "")
            if kind == "apiKey":
                location = scheme.get("in", "")
                if location not in ("header", "query", "cookie"):
                    self.errors.append(
                        "apiKey scheme '%s' has in='%s'; the Kora server generator supports only "
                        "header, query or cookie" % (name, location)
                    )
                if not scheme.get("name"):
                    self.errors.append("apiKey scheme '%s' is missing 'name'" % name)
            elif kind == "http":
                http_scheme = str(scheme.get("scheme", "")).lower()
                if http_scheme not in ("basic", "bearer"):
                    self.errors.append(
                        "http scheme '%s' uses scheme='%s'; the Kora server generator supports "
                        "basic and bearer" % (name, http_scheme)
                    )
            elif kind == "oauth2":
                if not scheme.get("flows"):
                    self.warnings.append("oauth2 scheme '%s' declares no flows" % name)
                self.notes.append(
                    "oauth2 scheme '%s' requires HttpServerPrincipalExtractor<String, "
                    "PrincipalWithScopes>; the generated interceptor checks principal.scopes()" % name
                )
            elif kind == "openIdConnect":
                self.notes.append("openIdConnect scheme '%s' is read from the Authorization header" % name)
            else:
                self.errors.append(
                    "Security scheme '%s' has unsupported type '%s' for a Kora server" % (name, kind)
                )

        unknown = used - set(schemes.keys())
        if unknown:
            self.errors.append(
                "Operations reference undeclared security schemes: %s" % sorted(unknown)
            )

    def walk_schemas(self):
        """Yield (name, schema) for every named schema and every nested property schema."""
        schemas = ((self.spec.get("components") or {}).get("schemas")) or {}

        def walk(prefix, node):
            if not isinstance(node, dict):
                return
            yield prefix, node
            for key, child in (node.get("properties") or {}).items():
                yield from walk("%s.%s" % (prefix, key), child)
            if isinstance(node.get("items"), dict):
                yield from walk("%s[]" % prefix, node["items"])
            for combinator in ("allOf", "oneOf", "anyOf"):
                for index, child in enumerate(node.get(combinator) or []):
                    yield from walk("%s.%s[%d]" % (prefix, combinator, index), child)

        for name, schema in schemas.items():
            yield from walk(name, schema)

    def check_enums(self):
        reported = False
        for where, schema in self.walk_schemas():
            values = schema.get("enum")
            if not values or schema.get("type") not in (None, "string"):
                continue
            differing = [v for v in values if str(v) != enum_constant_name(v)]
            if differing and not reported:
                reported = True
                self.warnings.append(
                    "Generated enums expose fromValue(raw); the wire values differ from the "
                    "generated constant names, so Enum.valueOf(raw) throws on valid input. "
                    "First offender: %s -> wire %s, constants %s"
                    % (
                        where,
                        [str(v) for v in differing[:3]],
                        [enum_constant_name(v) for v in differing[:3]],
                    )
                )

    def check_discriminators(self):
        schemas = ((self.spec.get("components") or {}).get("schemas")) or {}
        for name, schema in schemas.items():
            if not isinstance(schema, dict):
                continue
            discriminator = schema.get("discriminator")
            if not isinstance(discriminator, dict):
                continue
            prop = discriminator.get("propertyName")
            if not prop:
                self.errors.append("Schema '%s' has a discriminator without propertyName" % name)
                continue
            properties = schema.get("properties") or {}
            if prop not in properties:
                self.errors.append(
                    "Schema '%s' declares discriminator propertyName '%s' but has no such property"
                    % (name, prop)
                )
            if prop not in (schema.get("required") or []):
                self.warnings.append(
                    "Schema '%s' does not list discriminator property '%s' in 'required'; it is "
                    "the field that selects the variant" % (name, prop)
                )
            mapping = discriminator.get("mapping") or {}
            if not mapping:
                self.warnings.append(
                    "Schema '%s' has a discriminator with no 'mapping'; the sealed hierarchy is "
                    "derived from the mapping entries" % name
                )
            for key, ref in mapping.items():
                target = str(ref).rsplit("/", 1)[-1]
                if target not in schemas:
                    self.errors.append(
                        "Schema '%s' discriminator mapping '%s' points at unknown schema '%s'"
                        % (name, key, target)
                    )

    # ---------------------------------------------------------------- driving

    def run(self):
        if not self.load():
            return False
        for check in (
            self.check_mode,
            self.check_version,
            self.check_info,
            self.check_operations,
            self.check_security,
            self.check_enums,
            self.check_discriminators,
        ):
            try:
                check()
            except Exception as e:  # a malformed spec must not crash the checker
                self.errors.append("Checker '%s' failed: %s" % (check.__name__, e))
        if self.strict:
            self.errors.extend(self.warnings)
            self.warnings = []
        return not self.errors

    def report(self):
        lines = ["Kora 2.x OpenAPI check: %s" % self.spec_path, "=" * 60]
        if self.mode:
            lines.append("mode: %s" % self.mode)
        if self.errors:
            lines.append("")
            lines.append("ERRORS (%d):" % len(self.errors))
            lines.extend("  - %s" % e for e in self.errors)
        if self.warnings:
            lines.append("")
            lines.append("WARNINGS (%d):" % len(self.warnings))
            lines.extend("  - %s" % w for w in self.warnings)
        if self.notes:
            lines.append("")
            lines.append("GENERATED NAMES (%d):" % len(self.notes))
            lines.extend("  - %s" % n for n in self.notes)
        lines.append("")
        if self.errors:
            lines.append("Result: FAILED — fix the errors before generating")
        elif self.warnings:
            lines.append("Result: PASSED with warnings")
        else:
            lines.append("Result: PASSED")
        return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Read-only OpenAPI check for the Kora 2.x `kora` generator"
    )
    parser.add_argument("--spec", "-s", required=True, help="Path to the OpenAPI file (YAML or JSON)")
    parser.add_argument(
        "--mode",
        "-m",
        default=None,
        help="Generator mode to validate against: %s" % ", ".join(SUPPORTED_MODES),
    )
    parser.add_argument("--strict", action="store_true", help="Treat warnings as errors")
    parser.add_argument("--json", action="store_true", help="Emit the report as JSON")
    args = parser.parse_args()

    checker = OpenAPIChecker(args.spec, mode=args.mode, strict=args.strict)
    ok = checker.run()

    if args.json:
        print(
            json.dumps(
                {
                    "valid": ok,
                    "spec": str(args.spec),
                    "mode": args.mode,
                    "strict": args.strict,
                    "errors": checker.errors,
                    "warnings": checker.warnings,
                    "generatedNames": checker.notes,
                },
                indent=2,
            )
        )
    else:
        print(checker.report())

    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
