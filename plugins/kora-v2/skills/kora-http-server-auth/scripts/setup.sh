#!/bin/bash
#
# Kora 2.0 HTTP Server Auth — setup helper.
#
# Copies HttpServerPrincipalExtractor templates into a target project and prints the wiring steps.
# Assumes an OpenAPI-generated ApiSecurity (see the kora-openapi-generator-server skill).

set -euo pipefail

usage() {
    cat <<'USAGE'
Usage: setup.sh [--dry-run] [PROJECT_ROOT] [java|kotlin] [PACKAGE_PATH]

Arguments:
  PROJECT_ROOT   Project to copy into            (default: .)
  java|kotlin    Language variant                (default: java)
  PACKAGE_PATH   Slash-separated package path    (default: com/example/auth)

Options:
  --dry-run      Print what would be written; create and copy nothing.
  -h, --help     Show this message.

Examples:
  setup.sh --dry-run ../my-service kotlin com/acme/api/auth
  setup.sh ../my-service java com/acme/api/auth
USAGE
}

DRY_RUN=0
ARGS=()
for arg in "$@"; do
    case "$arg" in
        --dry-run) DRY_RUN=1 ;;
        -h|--help) usage; exit 0 ;;
        -*) echo "Error: unknown option '$arg'" >&2; usage >&2; exit 2 ;;
        *) ARGS+=("$arg") ;;
    esac
done

PROJECT_ROOT="${ARGS[0]:-.}"
LANG_KIND="${ARGS[1]:-java}"
PKG_PATH="${ARGS[2]:-com/example/auth}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ASSETS_DIR="$SCRIPT_DIR/../assets"

case "$LANG_KIND" in
    java)   SRC_ROOT="src/main/java";   EXT="java" ;;
    kotlin) SRC_ROOT="src/main/kotlin"; EXT="kt" ;;
    *) echo "Error: language must be 'java' or 'kotlin', got '$LANG_KIND'" >&2; exit 2 ;;
esac

if [ ! -d "$PROJECT_ROOT" ]; then
    echo "Error: project root '$PROJECT_ROOT' does not exist" >&2
    exit 1
fi

SRC_DIR="$PROJECT_ROOT/$SRC_ROOT/$PKG_PATH"
PKG_NAME="${PKG_PATH//\//.}"
TEMPLATES=("ApiKeyExtractor" "BasicAuthExtractor")

for name in "${TEMPLATES[@]}"; do
    if [ ! -f "$ASSETS_DIR/$name.$EXT.template" ]; then
        echo "Error: missing template $ASSETS_DIR/$name.$EXT.template" >&2
        exit 1
    fi
done

if [ "$DRY_RUN" -eq 1 ]; then
    echo "DRY RUN — nothing will be created."
    echo "  would create directory: $SRC_DIR"
    for name in "${TEMPLATES[@]}"; do
        echo "  would write:            $SRC_DIR/$name.$EXT   (package $PKG_NAME)"
    done
    exit 0
fi

mkdir -p "$SRC_DIR"
for name in "${TEMPLATES[@]}"; do
    target="$SRC_DIR/$name.$EXT"
    if [ -e "$target" ]; then
        echo "Skipping $target — already exists" >&2
        continue
    fi
    cp "$ASSETS_DIR/$name.$EXT.template" "$target"
    echo "Wrote $target"
done

cat <<EOF

Next steps
==========
1. Replace \${package} in the copied files with: $PKG_NAME

2. Replace the unqualified 'ApiSecurity' reference with the class generated from your OpenAPI
   contract (it lives in your generated api package). Open that generated file and copy the
   extractor parameter type verbatim — for a single scheme it is
   HttpServerPrincipalExtractor<String, Principal>, and for an oauth2 scheme
   HttpServerPrincipalExtractor<String, PrincipalWithScopes>. Adjust the @Tag to your security
   scheme's name, PascalCased (apiKeyAuth -> ApiSecurity.ApiKeyAuth).

3. Dependencies — Kora 2.0 requires JVM 25 and resolves from plain mavenCentral():

   // gradle.properties
   koraVersion=2.0.0.RC2

   dependencies {
       koraBom platform("io.koraframework:kora-bom:\$koraVersion")
       annotationProcessor "io.koraframework:annotation-processors"   // Kotlin: ksp "io.koraframework:symbol-processors"

       implementation "io.koraframework:http-server-undertow"
       implementation "io.koraframework:json-common"
       implementation "io.koraframework:config-hocon"
       implementation "io.koraframework:logging-logback"
   }

4. Configure the secret in application.conf:

   auth { apiKey { value = \${API_KEY} } }

5. Do NOT add the generated ApiSecurity (or these @Module interfaces) to your @KoraApp interface
   list — Kora discovers @Module interfaces automatically.

6. Reject by returning null; the generated interceptor answers 401 Unauthorized. Read the
   authenticated principal inside a handler with Principal.current().

7. To render auth failures as JSON, add a GLOBAL interceptor annotated
   @Tag(io.koraframework.http.server.common.HttpServer.class) — not @Tag(HttpServerModule.class),
   which compiles but is never invoked. See references/manual-auth-reference.md.

8. Add a @KoraAppTest that sends an unauthenticated request and asserts 401. A successful compile
   does not prove the interceptor is wired.
EOF
