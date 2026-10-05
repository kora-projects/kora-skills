#!/usr/bin/env bash
#
# Add Kora 2.x JDK scheduling (io.koraframework:scheduling-jdk) to an existing Kora project:
#   * the scheduling-jdk dependency in build.gradle / build.gradle.kts
#   * a ScheduledJobs source file from this skill's assets/
#   * a scheduling { ... } block in application.conf / application.yaml
#
# It never touches the @KoraApp interface — adding `SchedulingJdkModule` there is a manual step,
# reported at the end.

set -euo pipefail

PROJECT_ROOT="."
LANG_KIND="java"
PACKAGE="com.example.app.jobs"
DRY_RUN=0

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ASSETS_DIR="$(dirname "$SCRIPT_DIR")/assets"

usage() {
    cat <<'USAGE'
Usage: setup-jdk.sh [options] [project-root]

Adds Kora 2.x JDK scheduling to a project.

Options:
  --lang java|kotlin   Source language for the generated job class (default: java)
  --package <pkg>      Package for the generated job class (default: com.example.app.jobs)
  --dry-run, -n        Print what would change and exit without writing anything
  --help, -h           Show this help

Positional:
  project-root         Project directory (default: current directory)

Examples:
  setup-jdk.sh --dry-run .
  setup-jdk.sh --lang kotlin --package com.acme.billing.jobs ~/projects/billing
USAGE
}

while [ $# -gt 0 ]; do
    case "$1" in
        --lang)     LANG_KIND="${2:-}"; shift 2 ;;
        --lang=*)   LANG_KIND="${1#*=}"; shift ;;
        --package)  PACKAGE="${2:-}"; shift 2 ;;
        --package=*) PACKAGE="${1#*=}"; shift ;;
        --dry-run|-n) DRY_RUN=1; shift ;;
        --help|-h)  usage; exit 0 ;;
        -*)         echo "Error: unknown option '$1'" >&2; usage >&2; exit 2 ;;
        *)          PROJECT_ROOT="$1"; shift ;;
    esac
done

case "$LANG_KIND" in
    java|kotlin) ;;
    *) echo "Error: --lang must be 'java' or 'kotlin', got '$LANG_KIND'" >&2; exit 2 ;;
esac

if [ ! -d "$PROJECT_ROOT" ]; then
    echo "Error: project root '$PROJECT_ROOT' does not exist" >&2
    exit 1
fi

if [ "$LANG_KIND" = "java" ]; then
    TEMPLATE="$ASSETS_DIR/ScheduledJobs.java.template"
    SRC_ROOT="$PROJECT_ROOT/src/main/java"
    TARGET_NAME="ScheduledJobs.java"
    DEP_GROOVY='    implementation "io.koraframework:scheduling-jdk"'
    DEP_KTS='    implementation("io.koraframework:scheduling-jdk")'
else
    TEMPLATE="$ASSETS_DIR/ScheduledJobs.kt.template"
    SRC_ROOT="$PROJECT_ROOT/src/main/kotlin"
    TARGET_NAME="ScheduledJobs.kt"
    DEP_GROOVY='    implementation "io.koraframework:scheduling-jdk"'
    DEP_KTS='    implementation("io.koraframework:scheduling-jdk")'
fi

if [ ! -f "$TEMPLATE" ]; then
    echo "Error: template not found: $TEMPLATE" >&2
    exit 1
fi

PACKAGE_PATH="${PACKAGE//.//}"
JOBS_DIR="$SRC_ROOT/$PACKAGE_PATH"
TARGET_FILE="$JOBS_DIR/$TARGET_NAME"
RESOURCES_DIR="$PROJECT_ROOT/src/main/resources"

if [ "$DRY_RUN" -eq 1 ]; then
    echo "DRY RUN — nothing will be written."
    echo
fi

echo "Kora 2.x JDK scheduling setup"
echo "  project : $PROJECT_ROOT"
echo "  language: $LANG_KIND"
echo "  package : $PACKAGE"
echo

act() {
    # act <description> <command...>   — runs the command unless --dry-run
    local description="$1"; shift
    if [ "$DRY_RUN" -eq 1 ]; then
        echo "  would: $description"
    else
        "$@"
        echo "  done : $description"
    fi
}

# ---------------------------------------------------------------- dependency

insert_dependency() {
    local build_file="$1" dep_line="$2" tmp
    tmp="$(mktemp)"
    awk -v dep="$dep_line" '
        !inserted && /^[[:space:]]*dependencies[[:space:]]*\{/ { print; print dep; inserted = 1; next }
        { print }
    ' "$build_file" > "$tmp"
    mv "$tmp" "$build_file"
}

BUILD_FILE=""
DEP_LINE=""
if [ -f "$PROJECT_ROOT/build.gradle.kts" ]; then
    BUILD_FILE="$PROJECT_ROOT/build.gradle.kts"
    DEP_LINE="$DEP_KTS"
elif [ -f "$PROJECT_ROOT/build.gradle" ]; then
    BUILD_FILE="$PROJECT_ROOT/build.gradle"
    DEP_LINE="$DEP_GROOVY"
fi

echo "Dependency"
if [ -z "$BUILD_FILE" ]; then
    echo "  skip : no build.gradle or build.gradle.kts in $PROJECT_ROOT — add manually:"
    echo "         $DEP_GROOVY"
elif grep -q "scheduling-jdk" "$BUILD_FILE"; then
    echo "  ok   : scheduling-jdk already declared in $(basename "$BUILD_FILE")"
elif ! grep -qE '^[[:space:]]*dependencies[[:space:]]*\{' "$BUILD_FILE"; then
    echo "  skip : no 'dependencies {' block in $(basename "$BUILD_FILE") — add manually:"
    echo "         $DEP_LINE"
else
    act "add scheduling-jdk to $(basename "$BUILD_FILE")" insert_dependency "$BUILD_FILE" "$DEP_LINE"
fi

if [ -n "$BUILD_FILE" ]; then
    if [ "$LANG_KIND" = "java" ] && ! grep -q "annotation-processors" "$BUILD_FILE"; then
        echo "  warn : 'io.koraframework:annotation-processors' not found — without it no job is generated"
    fi
    if [ "$LANG_KIND" = "kotlin" ] && ! grep -q "symbol-processors" "$BUILD_FILE"; then
        echo "  warn : 'io.koraframework:symbol-processors' not found on ksp — without it no job is generated"
    fi
    if ! grep -q "kora-bom" "$BUILD_FILE"; then
        echo "  warn : 'io.koraframework:kora-bom' not found — artifact versions must come from the BOM"
    fi
fi
echo

# ---------------------------------------------------------------- job source

write_job_source() {
    local template="$1" target="$2" package="$3"
    mkdir -p "$(dirname "$target")"
    sed "s/com\.example\.app\.jobs/${package}/g" "$template" > "$target"
}

echo "Job source"
if [ -f "$TARGET_FILE" ]; then
    echo "  ok   : $TARGET_FILE already exists — left untouched"
else
    act "create $TARGET_FILE" write_job_source "$TEMPLATE" "$TARGET_FILE" "$PACKAGE"
fi
echo

# ---------------------------------------------------------------- config

CONF_HOCON="$RESOURCES_DIR/application.conf"
CONF_YAML=""
for candidate in "$RESOURCES_DIR/application.yaml" "$RESOURCES_DIR/application.yml"; do
    if [ -f "$candidate" ]; then
        CONF_YAML="$candidate"
        break
    fi
done

append_hocon() {
    local file="$1"
    mkdir -p "$(dirname "$file")"
    cat >> "$file" <<'HOCON'

scheduling {
  jdk.shutdownWait = 30s

  telemetry {
    logging.enabled = false
    metrics.enabled = false
    tracing.enabled = true
  }

  jobs.cleanup {
    initialDelay = 30s
    delay = 5m
  }
}
HOCON
}

append_yaml() {
    local file="$1"
    cat >> "$file" <<'YAML'

scheduling:
  jdk:
    shutdownWait: "30s"
  telemetry:
    logging:
      enabled: false
    metrics:
      enabled: false
    tracing:
      enabled: true
  jobs:
    cleanup:
      initialDelay: "30s"
      delay: "5m"
YAML
}

echo "Configuration"
if [ -n "$CONF_YAML" ]; then
    if grep -qE '^scheduling:' "$CONF_YAML"; then
        echo "  ok   : 'scheduling:' section already present in $(basename "$CONF_YAML")"
    else
        act "append scheduling section to $CONF_YAML" append_yaml "$CONF_YAML"
    fi
elif [ -f "$CONF_HOCON" ]; then
    if grep -qE '^scheduling[[:space:]]*\{|^scheduling\.' "$CONF_HOCON"; then
        echo "  ok   : 'scheduling' section already present in application.conf"
    else
        act "append scheduling section to $CONF_HOCON" append_hocon "$CONF_HOCON"
    fi
else
    act "create $CONF_HOCON with a scheduling section" append_hocon "$CONF_HOCON"
fi
echo

# ---------------------------------------------------------------- next steps

cat <<NEXT
Next steps (manual):
  1. Extend SchedulingJdkModule on your @KoraApp interface:

       @KoraApp
       public interface Application extends HoconConfigModule, LogbackModule, SchedulingJdkModule { }

  2. Review $TARGET_FILE and delete the annotations you do not need.
  3. Note the 2.x config keys: 'scheduling.jdk.shutdownWait' (not 'scheduling.shutdownWait'),
     and there is NO 'scheduling.threads' key — runs are virtual threads; cap them with
     'scheduling.jdk.executionParallelism' if needed (default unlimited; the snapshot-era
     'scheduling.jdk.maxConcurrentExecutions' is ignored).
     Annotations are @ScheduleJdkAtFixedRate / @ScheduleJdkWithFixedDelay / @ScheduleJdkOnce /
     @ScheduleJdkWithCron; a config-declared job can be switched off with 'enabled = false'.
  4. Job metrics and logging default to disabled — enable them under scheduling.telemetry
     if you expect to see them.
NEXT
