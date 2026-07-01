#!/usr/bin/env python3
"""
Kora Gradle Validator

Validates build.gradle files for Kora framework projects.

Usage:
    python validate_gradle.py --project /path/to/project
    python validate_gradle.py --file build.gradle
    python validate_gradle.py --file build.gradle --json
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple


class GradleValidator:
    """Validates Gradle build files for Kora projects."""

    REQUIRED_PLUGINS = ["java", "application"]
    REQUIRED_CONFIGURATIONS = ["koraBom"]
    REQUIRED_DEPENDENCIES = ["kora-parent", "annotation-processors"]

    def __init__(self, verbose: bool = False, json_output: bool = False):
        self.verbose = verbose
        self.json_output = json_output
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.info: List[str] = []

    def validate_file(self, file_path: Path) -> bool:
        """Validate a single build.gradle file."""
        if not file_path.exists():
            self.errors.append(f"File not found: {file_path}")
            return False

        content = file_path.read_text()
        filename = file_path.name

        print(f"\n🔍 Validating {filename}...")

        # Run validations
        self._check_plugins(content, filename)
        self._check_configurations(content, filename)
        self._check_kora_bom(content, filename)
        self._check_java_version(content, filename)
        self._check_encoding(content, filename)
        self._check_quotes(content, filename)

        # Print results
        self._print_results()

        return len(self.errors) == 0

    def validate_project(self, project_path: Path) -> bool:
        """Validate all build.gradle files in a project."""
        if not project_path.exists():
            self.errors.append(f"Project directory not found: {project_path}")
            return False

        print(f"\n🔍 Validating project: {project_path}")

        # Find all build.gradle files
        gradle_files = list(project_path.rglob("build.gradle"))
        gradle_files += list(project_path.rglob("build.gradle.kts"))

        if not gradle_files:
            self.errors.append("No build.gradle files found")
            return False

        all_valid = True
        for gradle_file in gradle_files:
            # Skip build directories
            if "build" in str(gradle_file):
                continue

            if not self.validate_file(gradle_file):
                all_valid = False

            # Reset for next file
            self.errors = []
            self.warnings = []
            self.info = []

        return all_valid

    def _check_plugins(self, content: str, filename: str):
        """Check for required plugins."""
        # Check for java plugin
        if 'id "java"' not in content and 'id("java")' not in content:
            if "kotlin" not in filename:
                self.errors.append("Missing 'java' plugin")

        # Check for application plugin (only in root/app modules)
        if 'id "application"' not in content and 'id("application")' not in content:
            if "kotlin" not in filename:
                self.warnings.append("Missing 'application' plugin (required for runnable projects)")

    def _check_configurations(self, content: str, filename: str):
        """Check for required configurations."""
        if "koraBom" not in content:
            self.errors.append("Missing 'koraBom' configuration")

        if "annotationProcessor.extendsFrom(koraBom)" not in content:
            self.warnings.append("Missing 'annotationProcessor.extendsFrom(koraBom)'")

    def _check_kora_bom(self, content: str, filename: str):
        """Check for Kora BOM dependency."""
        # Check for kora-parent platform
        if "kora-parent" not in content:
            self.errors.append("Missing Kora BOM dependency (kora-parent)")

        # Check for annotation processors
        if "annotation-processors" not in content:
            self.errors.append("Missing annotation-processors dependency")

        # Check for koraVersion variable
        if "koraVersion" not in content and "koraVersion" not in filename:
            # Check if version is hardcoded
            if 'platform("ru.tinkoff.kora:kora-parent:' in content:
                self.info.append("Consider using koraVersion property instead of hardcoded version")

    def _check_java_version(self, content: str, filename: str):
        """Check Java version configuration."""
        if "JavaVersion.VERSION_25" not in content and "JavaVersion.VERSION_17" not in content:
            if "java {" in content or "java {" not in content:
                self.warnings.append("Java version not explicitly set (recommended: VERSION_25)")

    def _check_encoding(self, content: str, filename: str):
        """Check for UTF-8 encoding configuration."""
        if 'options.encoding("UTF-8")' not in content:
            self.warnings.append("Missing UTF-8 encoding configuration")

    def _check_quotes(self, content: str, filename: str):
        """Check for proper quote usage (double quotes required)."""
        if filename.endswith(".kts"):
            return  # Kotlin DSL uses different syntax

        # Find single quotes in string values
        single_quote_pattern = r"['][^'\n]*[']"
        matches = re.findall(single_quote_pattern, content)

        # Filter out comments and acceptable uses
        problematic = []
        for match in matches:
            if "'" in match and not match.startswith("'"):
                problematic.append(match)

        # Check for common single quote issues
        if "applicationName = '" in content:
            self.errors.append("Use double quotes for applicationName (not single quotes)")

        if "mainClass = '" in content:
            self.errors.append("Use double quotes for mainClass (not single quotes)")

    def _get_results_dict(self) -> Dict[str, Any]:
        """Get results as dictionary for JSON output."""
        return {
            "valid": len(self.errors) == 0,
            "errors": self.errors,
            "warnings": self.warnings,
            "info": self.info
        }

    def _print_results(self):
        """Print validation results."""
        if self.json_output:
            print(json.dumps(self._get_results_dict(), indent=2))
            return

        if self.errors:
            print("\nErrors:")
            for error in self.errors:
                print(f"  • {error}")

        if self.warnings:
            print("\n Warnings:")
            for warning in self.warnings:
                print(f"  • {warning}")

        if self.info:
            print("\nℹ️  Info:")
            for info in self.info:
                print(f"  • {info}")

        if not self.errors and not self.warnings:
            print("All checks passed!")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Validate Gradle build files for Kora projects"
    )
    parser.add_argument(
        "--project",
        type=Path,
        help="Project directory to validate"
    )
    parser.add_argument(
        "--file",
        type=Path,
        help="Specific build.gradle file to validate"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose output"
    )
    return parser.parse_args()


def main():
    args = parse_args()

    if not args.project and not args.file:
        print("Error: Either --project or --file must be specified")
        return 1

    validator = GradleValidator(verbose=args.verbose, json_output=args.json)

    if args.project:
        success = validator.validate_project(args.project)
    else:
        success = validator.validate_file(args.file)

    if not args.json:
        if success:
            print("\nValidation passed!")
        else:
            print("\nValidation failed!")

    return 0 if success else 1


if __name__ == "__main__":
    exit(main())
