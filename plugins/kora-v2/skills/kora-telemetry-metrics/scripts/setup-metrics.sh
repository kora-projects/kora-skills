#!/usr/bin/env bash
# Kora 2.0 telemetry metrics — setup helper.
#
# Prints (and optionally appends) the dependency and configuration snippets a Kora 2.0
# service needs for Micrometer metrics. Dry run is the DEFAULT: nothing is written unless
# you pass --apply, because appending a second `dependencies { }` block to a build file is
# not something a script should do behind your back.
#
# Usage:
#   ./setup-metrics.sh                 # dry run — print what would change
#   ./setup-metrics.sh --apply         # append the dependency block to the build file
#   ./setup-metrics.sh --project DIR   # operate on DIR instead of the current directory
#   ./setup-metrics.sh --help

set -euo pipefail

APPLY=0
PROJECT_DIR="."

usage() {
    cat <<'USAGE'
Kora 2.0 telemetry metrics setup helper.

  -a, --apply           Append the dependency block to the build file.
                        Without this flag the script only prints (dry run).
  -p, --project DIR     Project root to inspect (default: current directory).
  -h, --help            Show this help.

The script never edits application.conf — the config it prints contains decisions
(ports, which components to instrument) that must not be guessed.
USAGE
}

while [ $# -gt 0 ]; do
    case "$1" in
        -a|--apply)   APPLY=1; shift ;;
        -p|--project)
            if [ $# -lt 2 ]; then
                echo "ERROR: --project requires a directory argument." >&2
                usage >&2
                exit 2
            fi
            PROJECT_DIR="$2"; shift 2 ;;
        -h|--help)    usage; exit 0 ;;
        *)            echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
    esac
done

if [ ! -d "$PROJECT_DIR" ]; then
    echo "ERROR: not a directory: $PROJECT_DIR" >&2
    exit 1
fi

cd "$PROJECT_DIR"

if [ -f "build.gradle.kts" ]; then
    BUILD_FILE="build.gradle.kts"
    BUILD_TYPE="kotlin"
elif [ -f "build.gradle" ]; then
    BUILD_FILE="build.gradle"
    BUILD_TYPE="groovy"
else
    echo "ERROR: no build.gradle or build.gradle.kts in $(pwd)." >&2
    echo "       Run this from your Kora project root, or pass --project DIR." >&2
    exit 1
fi

echo "Project:    $(pwd)"
echo "Build file: $BUILD_FILE ($BUILD_TYPE DSL)"
if [ "$APPLY" -eq 1 ]; then
    echo "Mode:       APPLY — the build file will be modified"
else
    echo "Mode:       DRY RUN — nothing will be written (pass --apply to write)"
fi
echo

# ---------------------------------------------------------------- sanity checks

if grep -q "ru\.tinkoff\.kora" "$BUILD_FILE" 2>/dev/null; then
    echo "WARNING: $BUILD_FILE still references ru.tinkoff.kora."
    echo "         Kora 2.0 uses the io.koraframework group and the io.koraframework:kora-bom"
    echo "         BOM; ru.tinkoff.kora:kora-parent does not exist in 2.0. Migrate the whole"
    echo "         build file before adding metrics."
    echo
fi

if grep -q "micrometer-registry-prometheus" "$BUILD_FILE" 2>/dev/null; then
    echo "WARNING: $BUILD_FILE declares io.micrometer:micrometer-registry-prometheus directly."
    echo "         io.koraframework:micrometer-module already brings it (Micrometer 1.17.1)."
    echo "         Remove the explicit dependency to avoid a version clash."
    echo
fi

if grep -q "io\.koraframework:micrometer-module" "$BUILD_FILE" 2>/dev/null; then
    echo "micrometer-module is already declared in $BUILD_FILE — skipping the dependency step."
    DEPS_NEEDED=0
else
    DEPS_NEEDED=1
fi

# ---------------------------------------------------------------- dependency block

if [ "$BUILD_TYPE" = "kotlin" ]; then
    read -r -d '' DEPS_BLOCK <<'BLOCK' || true

// Kora 2.0 telemetry metrics. Versions come from io.koraframework:kora-bom.
dependencies {
    implementation(platform("io.koraframework:kora-bom:${property("koraVersion")}"))
    ksp("io.koraframework:symbol-processors:${property("koraVersion")}")

    implementation("io.koraframework:micrometer-module")
    implementation("io.koraframework:http-server-undertow")
}
BLOCK
else
    read -r -d '' DEPS_BLOCK <<'BLOCK' || true

// Kora 2.0 telemetry metrics. Versions come from io.koraframework:kora-bom.
dependencies {
    koraBom platform("io.koraframework:kora-bom:$koraVersion")
    annotationProcessor "io.koraframework:annotation-processors"

    implementation "io.koraframework:micrometer-module"
    implementation "io.koraframework:http-server-undertow"
}
BLOCK
fi

if [ "$DEPS_NEEDED" -eq 1 ]; then
    echo "--- dependencies to add to $BUILD_FILE ---"
    printf '%s\n' "$DEPS_BLOCK"
    echo "--- end ---"
    echo

    if [ "$APPLY" -eq 1 ]; then
        printf '\n%s\n' "$DEPS_BLOCK" >> "$BUILD_FILE"
        echo "Appended the dependency block to $BUILD_FILE."
        echo "Review it: Gradle allows several dependencies { } blocks, but merging it into"
        echo "the existing one is usually cleaner."
        echo
    fi
fi

# ---------------------------------------------------------------- config + next steps

cat <<'NEXT'
Remaining steps (not automated — these are decisions, not boilerplate):

1. Put the version in gradle.properties:

       koraVersion=2.0.0.RC2

2. Add MetricsModule to your @KoraApp interface:

       @KoraApp
       public interface Application extends
               HoconConfigModule,
               LogbackModule,
               MetricsModule,                      // io.koraframework.micrometer.module
               UndertowPublicHttpServerModule {    // brings the system server with it

           static void main(String[] args) {
               KoraApplication.run(ApplicationGraph::graph);
           }
       }

3. ENABLE METRICS IN application.conf. This is the step everyone misses: in Kora 2.0
   TelemetryConfig.MetricsConfig.enabled() defaults to FALSE, so without these lines the
   /metrics endpoint answers 200 and shows the JVM meters while no component metric is
   ever recorded.

       httpServer {
         port = 8080
         system.port = 8085           # /metrics + probes live here
         telemetry.metrics.enabled = true
       }

       httpClient.<name>.telemetry.metrics.enabled = true
       jdbc.telemetry.metrics.enabled = true

   The 1.x keys privateApiHttpPort / privateApiHttpMetricsPath do not exist in 2.0 and are
   ignored without a warning.

4. Inject MeterRegistry into a @Component for custom meters:

       @Component
       public final class MetricsService {
           private final Counter created;

           public MetricsService(MeterRegistry registry) {
               this.created = Counter.builder("user.creation.total").register(registry);
           }
       }

5. Verify — read the BODY, not the status code, because /metrics always answers 200:

       curl -s http://localhost:8085/metrics | head -1
       #   "# Metric Scraper disabled"  -> MetricsModule is missing from @KoraApp

       curl -s http://localhost:8080/your/route > /dev/null
       curl -s http://localhost:8085/metrics | grep -c '^http_server_request_duration'
       #   0  -> httpServer.telemetry.metrics.enabled is still false

Reference: ../SKILL.md and ../references/metrics-config-reference.md
Templates:  ../assets/
NEXT
