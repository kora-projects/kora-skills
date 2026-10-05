#!/usr/bin/env python3
"""
Kora 2.x Gradle Validator

Read-only check of Gradle build files for Kora Framework 2.x projects. It never writes anything.

It looks for the wiring whose absence produces a confusing failure rather than a clear one:
  - the BOM (io.koraframework:kora-bom) instead of the removed ru.tinkoff.kora:kora-parent
  - the annotation processor (Java) or KSP symbol processor (Kotlin), without which nothing is
    generated and the only symptom is "cannot find symbol: ApplicationGraph"
  - a Java 25 toolchain, since Kora 2.0 artifacts are Java 25 class files
  - the KSP generated-source directory on the Kotlin source set
  - leftover 1.x coordinates and artifacts that no longer exist in 2.0

Prefer --project over --file for multi-module builds: only --project can read the root
subprojects/allprojects block, so it can tell wiring that is genuinely missing from wiring that is
inherited. --file never reports missing BOM/processor wiring as an error for that reason.

Usage:
    python3 validate_gradle.py --project /path/to/project
    python3 validate_gradle.py --project /path/to/project --json
    python3 validate_gradle.py --file build.gradle
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List

KORA_GROUP = "io.koraframework"
KORA_BOM = "io.koraframework:kora-bom"
JAVA_PROCESSOR = "io.koraframework:annotation-processors"
KSP_PROCESSOR = "io.koraframework:symbol-processors"
REQUIRED_JAVA_RELEASE = 25

# Artifacts that existed in Kora 1.x and do not exist in 2.0.
REMOVED_ARTIFACTS = {
    "kora-parent": "replaced by io.koraframework:kora-bom",
    "json-module": "renamed to io.koraframework:json-common",
    "cache-redis": "split into cache-redis-common + cache-redis-lettuce",
    "http-client-async": "removed in 2.0",
    "database-r2dbc": "removed in 2.0 — repositories are synchronous JDBC",
    "database-vertx": "removed in 2.0 — repositories are synchronous JDBC",
    "s3-client-minio": "removed in 2.0 — use s3-client-aws or experimental s3-client-kora",
    "mapstruct-extension": "renamed to mapstruct-java-extension (Java); Kotlin maps with Konvert (konvert-ksp-extension)",
}


class Finding:
    def __init__(self, level: str, message: str):
        self.level = level
        self.message = message

    def as_dict(self) -> Dict[str, str]:
        return {"level": self.level, "message": self.message}


class InheritedConfig:
    """What a root build's subprojects/allprojects block already supplies to every subproject.

    Without this, every subproject of a correctly configured multi-module build would be reported
    as missing the BOM and the processor.
    """

    def __init__(self):
        self.bom = False
        self.java_processor = False
        self.ksp_processor = False
        self.toolchain = False
        self.ksp_source_set = False
        self.processor_extends_bom = False

    @staticmethod
    def from_root(content: str) -> "InheritedConfig":
        cfg = InheritedConfig()
        if "subprojects" not in content and "allprojects" not in content:
            return cfg
        cfg.bom = KORA_BOM in content
        cfg.java_processor = JAVA_PROCESSOR in content
        cfg.ksp_processor = KSP_PROCESSOR in content
        cfg.toolchain = bool(
            re.search(r"JavaLanguageVersion\.of\(\s*\d+\s*\)", content)
            or re.search(r"jvmToolchain\(\s*\d+\s*\)", content)
        )
        cfg.ksp_source_set = "build/generated/ksp/main/kotlin" in content
        cfg.processor_extends_bom = "annotationProcessor.extendsFrom(koraBom)" in content
        return cfg

    @property
    def any(self) -> bool:
        return self.bom or self.java_processor or self.ksp_processor


class GradleValidator:
    """Read-only validator for a Kora 2.x Gradle build file."""

    def __init__(self, json_output: bool = False):
        self.json_output = json_output
        self.results: Dict[str, List[Finding]] = {}
        self.inherited = InheritedConfig()
        # --file cannot see a root build, so a subproject's "missing" wiring may simply be
        # inherited. --project reads the root first and knows the difference.
        self.project_mode = False

    # -- helpers -----------------------------------------------------------------

    @staticmethod
    def _is_kotlin_dsl(path: Path) -> bool:
        return path.name.endswith(".kts")

    @staticmethod
    def _declares(content: str, *needles: str) -> bool:
        return any(n in content for n in needles)

    @staticmethod
    def _uses_kotlin_plugin(content: str) -> bool:
        return GradleValidator._declares(
            content,
            'kotlin("jvm")',
            "org.jetbrains.kotlin.jvm",
            "com.google.devtools.ksp",
        )

    @staticmethod
    def _is_root_only(content: str) -> bool:
        """A root build that only configures subprojects has no dependencies of its own."""
        return "subprojects" in content and "sourceSets" not in content

    # Kora declarations whose presence means this module needs a processor of its own.
    _KORA_MARKERS = re.compile(
        r"io\.koraframework\.common\.annotation|@KoraApp|@KoraSubmodule|@Module\b|@Component\b"
    )

    @classmethod
    def _declares_kora_annotations(cls, module_dir: Path) -> bool:
        """Does this Gradle module actually contain Kora annotations in its sources?

        A subproject holding only plain interfaces needs no processor and no BOM, and flagging it
        produces noise on builds that are in fact correct.
        """
        src = module_dir / "src"
        if not src.is_dir():
            return True  # unknown — assume it matters rather than staying silent
        for path in list(src.rglob("*.java")) + list(src.rglob("*.kt")):
            try:
                if cls._KORA_MARKERS.search(path.read_text(errors="ignore")):
                    return True
            except OSError:
                continue
        return False

    def _missing_level(self, content: str) -> str:
        """How loudly to complain about missing BOM/processor wiring.

        Only --project can tell a genuinely missing dependency from one supplied by a root
        subprojects block, so --file never escalates past a warning.
        """
        if self.inherited.any or not self.project_mode:
            return "warning"
        if KORA_GROUP in content or "koraBom" in content:
            return "error"
        return "warning"

    # -- checks ------------------------------------------------------------------

    def _check_legacy_group(self, content: str, findings: List[Finding]):
        if "ru.tinkoff.kora" in content:
            findings.append(Finding(
                "error",
                "Found 'ru.tinkoff.kora' — Kora 2.0 publishes under 'io.koraframework'"
            ))

    def _check_removed_artifacts(self, content: str, findings: List[Finding]):
        for artifact, note in REMOVED_ARTIFACTS.items():
            if re.search(rf"[:\"']{re.escape(artifact)}[:\"']", content):
                findings.append(Finding(
                    "error", f"Artifact '{artifact}' does not exist in Kora 2.0 — {note}"
                ))

    def _check_bom(self, content: str, findings: List[Finding], root_only: bool):
        if KORA_BOM in content:
            if re.search(rf"{re.escape(KORA_BOM)}:\d", content):
                findings.append(Finding(
                    "info",
                    "Kora version is hardcoded next to the BOM — prefer a koraVersion property "
                    "in gradle.properties so every module stays aligned"
                ))
            return
        if root_only or self.inherited.bom:
            return
        findings.append(Finding(
            self._missing_level(content),
            f"Missing the Kora BOM platform ({KORA_BOM})"
        ))

    def _check_processor(self, content: str, findings: List[Finding], kotlin: bool):
        if kotlin:
            if KSP_PROCESSOR not in content:
                if not self.inherited.ksp_processor:
                    findings.append(Finding(
                        self._missing_level(content),
                        f"Missing the KSP processor ({KSP_PROCESSOR}). Without it nothing is "
                        "generated and the only symptom is 'unresolved reference: "
                        "ApplicationGraph'"
                    ))
                return
            # ksp is not covered by the BOM platform, so it needs its own version
            if not re.search(rf"{re.escape(KSP_PROCESSOR)}:", content):
                findings.append(Finding(
                    "warning",
                    "The ksp configuration is not covered by the BOM platform — give "
                    f"{KSP_PROCESSOR} an explicit version"
                ))
            if "kspTest" not in content and not self.inherited.ksp_processor:
                findings.append(Finding(
                    "info",
                    "No kspTest processor — test sources that declare Kora annotations "
                    "(a test @KoraApp, @KoraAppTest) will not be processed"
                ))
        else:
            if JAVA_PROCESSOR not in content:
                if not self.inherited.java_processor:
                    findings.append(Finding(
                        self._missing_level(content),
                        f"Missing the annotation processor ({JAVA_PROCESSOR}). Without it "
                        "nothing is generated and the only symptom is 'cannot find symbol: "
                        "ApplicationGraph'"
                    ))
                return
            if "testAnnotationProcessor" not in content and not self.inherited.java_processor:
                findings.append(Finding(
                    "info",
                    "No testAnnotationProcessor — test sources that declare Kora annotations "
                    "(a test @KoraApp, @KoraAppTest) will not be processed"
                ))

    def _check_bom_wiring(self, content: str, findings: List[Finding], kotlin: bool):
        if "koraBom" not in content:
            return
        if (not kotlin
                and "annotationProcessor.extendsFrom(koraBom)" not in content
                and not self.inherited.processor_extends_bom):
            findings.append(Finding(
                "warning",
                "The koraBom configuration is declared but annotationProcessor does not extend "
                "it — the processor dependency will have no version"
            ))

    def _check_java_version(self, content: str, findings: List[Finding], root_only: bool):
        toolchain = re.search(r"JavaLanguageVersion\.of\(\s*(\d+)\s*\)", content)
        if toolchain:
            version = int(toolchain.group(1))
            if version < REQUIRED_JAVA_RELEASE:
                findings.append(Finding(
                    "error",
                    f"Java toolchain is {version}; Kora 2.0 artifacts are Java "
                    f"{REQUIRED_JAVA_RELEASE} class files"
                ))
            return

        legacy = re.search(r"JavaVersion\.VERSION_(\d+)", content)
        if legacy:
            version = int(legacy.group(1))
            level = "error" if version < REQUIRED_JAVA_RELEASE else "info"
            findings.append(Finding(
                level,
                f"sourceCompatibility/targetCompatibility is {version} — prefer a toolchain: "
                f"java {{ toolchain {{ languageVersion = "
                f"JavaLanguageVersion.of({REQUIRED_JAVA_RELEASE}) }} }}"
            ))
            return

        if re.search(r"jvmToolchain\(\s*(\d+)\s*\)", content):
            version = int(re.search(r"jvmToolchain\(\s*(\d+)\s*\)", content).group(1))
            if version < REQUIRED_JAVA_RELEASE:
                findings.append(Finding(
                    "error",
                    f"Kotlin jvmToolchain is {version}; Kora 2.0 requires "
                    f"{REQUIRED_JAVA_RELEASE}"
                ))
            return

        if not root_only and not self.inherited.toolchain:
            findings.append(Finding(
                "warning",
                f"No Java toolchain declared — Kora 2.0 needs Java {REQUIRED_JAVA_RELEASE}"
            ))

    def _check_ksp_source_set(self, content: str, findings: List[Finding], kotlin: bool):
        if not kotlin:
            return
        if "build/generated/ksp/main/kotlin" not in content and not self.inherited.ksp_source_set:
            findings.append(Finding(
                "warning",
                "The KSP output directory is not on the main source set — add "
                'sourceSets.main { kotlin.srcDir("build/generated/ksp/main/kotlin") }'
            ))

    @staticmethod
    def _uncommented(content: str) -> str:
        """Drop // line comments so commented-out samples are not read as configuration."""
        return "\n".join(
            line for line in content.splitlines() if not line.lstrip().startswith("//")
        )

    def _check_submodule_flag(self, content: str, findings: List[Finding]):
        content = self._uncommented(content)
        java_flag = "kora.app.submodule.enabled" in content and "compilerArgs" in content
        ksp_flag = 'arg("kora.app.submodule.enabled"' in content
        if java_flag or ksp_flag:
            findings.append(Finding(
                "info",
                "kora.app.submodule.enabled is set — only needed when a test @KoraApp extends "
                "the production @KoraApp, and it belongs on the MAIN compilation"
            ))

    def _check_application_plugin(self, content: str, findings: List[Finding], root_only: bool):
        if root_only:
            return
        has_app = self._declares(content, 'id "application"', 'id("application")')
        has_main = "mainClass" in content
        if has_app and not has_main:
            findings.append(Finding("warning", "application plugin applied but mainClass is not set"))
        if has_main and "ApplicationKt" not in content and self._uses_kotlin_plugin(content):
            findings.append(Finding(
                "warning",
                "Kotlin project: a top-level `fun main()` compiles into <package>.ApplicationKt — "
                "mainClass must name that class, not the @KoraApp interface"
            ))

    # -- driver ------------------------------------------------------------------

    def validate_file(self, file_path: Path) -> bool:
        findings: List[Finding] = []

        if not file_path.exists():
            findings.append(Finding("error", f"File not found: {file_path}"))
            self.results[str(file_path)] = findings
            return False

        content = file_path.read_text()
        kotlin = self._is_kotlin_dsl(file_path) or self._uses_kotlin_plugin(content)
        root_only = self._is_root_only(content)
        needs_kora = self._declares_kora_annotations(file_path.parent)

        self._check_legacy_group(content, findings)
        self._check_removed_artifacts(content, findings)

        if root_only:
            findings.append(Finding(
                "info", "Root build: only the subprojects/allprojects configuration is checked"
            ))
        elif not needs_kora:
            findings.append(Finding(
                "info",
                "No Kora annotations in this module's sources — BOM and processor checks skipped"
            ))
        else:
            self._check_bom(content, findings, root_only)
            self._check_processor(content, findings, kotlin)
            self._check_bom_wiring(content, findings, kotlin)
            self._check_ksp_source_set(content, findings, kotlin)

        self._check_java_version(content, findings, root_only)
        self._check_submodule_flag(content, findings)
        self._check_application_plugin(content, findings, root_only)

        self.results[str(file_path)] = findings
        return not any(f.level == "error" for f in findings)

    def validate_project(self, project_path: Path) -> bool:
        if not project_path.exists():
            self.results[str(project_path)] = [
                Finding("error", f"Project directory not found: {project_path}")
            ]
            return False

        gradle_files = sorted(
            p for p in list(project_path.rglob("build.gradle"))
            + list(project_path.rglob("build.gradle.kts"))
            if "build" not in p.relative_to(project_path).parts
        )

        if not gradle_files:
            self.results[str(project_path)] = [
                Finding("error", "No build.gradle or build.gradle.kts files found")
            ]
            return False

        self.project_mode = True

        # A root subprojects/allprojects block configures every subproject, so read it first.
        for candidate in ("build.gradle", "build.gradle.kts"):
            root = project_path / candidate
            if root.exists():
                self.inherited = InheritedConfig.from_root(root.read_text())
                break

        all_valid = True
        for gradle_file in gradle_files:
            if not self.validate_file(gradle_file):
                all_valid = False
        return all_valid

    # -- output ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "valid": not any(
                f.level == "error" for findings in self.results.values() for f in findings
            ),
            "files": {
                path: [f.as_dict() for f in findings]
                for path, findings in self.results.items()
            },
        }

    def report(self):
        if self.json_output:
            print(json.dumps(self.to_dict(), indent=2))
            return

        for path, findings in self.results.items():
            print(f"\n{path}")
            if not findings:
                print("  all checks passed")
                continue
            for level in ("error", "warning", "info"):
                for finding in findings:
                    if finding.level == level:
                        print(f"  [{level}] {finding.message}")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Validate Gradle build files for a Kora Framework 2.x project (read-only)"
    )
    parser.add_argument("--project", type=Path, help="Project directory to validate")
    parser.add_argument("--file", type=Path, help="A single build.gradle / build.gradle.kts")
    parser.add_argument("--json", action="store_true", help="Emit JSON")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if not args.project and not args.file:
        print("Error: pass --project or --file", file=sys.stderr)
        return 2

    validator = GradleValidator(json_output=args.json)
    success = (validator.validate_project(args.project) if args.project
               else validator.validate_file(args.file))
    validator.report()

    if not args.json:
        print("\nValidation passed" if success else "\nValidation failed")

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
