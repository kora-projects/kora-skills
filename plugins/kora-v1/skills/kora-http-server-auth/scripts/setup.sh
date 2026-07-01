#!/bin/bash

# Kora HTTP Server Auth - setup helper
# Copies an HttpServerPrincipalExtractor template into a target project and prints the
# wiring steps. Assumes an OpenAPI-generated ApiSecurity contract (see
# kora-openapi-generator-server).

set -e

PROJECT_ROOT="${1:-.}"
LANG_KIND="${2:-java}" # java | kotlin
PKG_PATH="${3:-com/example/auth}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ASSETS_DIR="$SCRIPT_DIR/../assets"

if [ ! -d "$PROJECT_ROOT" ]; then
    echo "Error: project root '$PROJECT_ROOT' does not exist" >&2
    exit 1
fi

if [ "$LANG_KIND" = "kotlin" ]; then
    SRC_DIR="$PROJECT_ROOT/src/main/kotlin/$PKG_PATH"
    EXT="kt"
else
    SRC_DIR="$PROJECT_ROOT/src/main/java/$PKG_PATH"
    EXT="java"
fi

mkdir -p "$SRC_DIR"

cp "$ASSETS_DIR/ApiKeyExtractor.$EXT.template"   "$SRC_DIR/ApiKeyExtractor.$EXT"
cp "$ASSETS_DIR/BasicAuthExtractor.$EXT.template" "$SRC_DIR/BasicAuthExtractor.$EXT"
echo "Copied ApiKeyExtractor.$EXT and BasicAuthExtractor.$EXT into $SRC_DIR"

cat <<'EOF'

Next steps:
1. Replace ${package} in the copied files with your real package.
2. Replace the unqualified 'ApiSecurity' reference with your generated api package class.
3. Ensure dependencies (BOM version inherited from kora-parent):

   dependencies {
       koraBom platform("ru.tinkoff.kora:kora-parent:1.2.17")
       annotationProcessor "ru.tinkoff.kora:annotation-processors"   // mandatory
       implementation "ru.tinkoff.kora:http-server-undertow"
       implementation "ru.tinkoff.kora:json-module"
       implementation "ru.tinkoff.kora:config-hocon"
   }

   (Kotlin: ksp "ru.tinkoff.kora:symbol-processors" instead of annotationProcessor.)

4. Configure the secret in application.conf:

   auth { apiKey { value = ${API_KEY} } }

5. Add an error HttpServerInterceptor (@Tag(HttpServerModule.class)) that maps
   SecurityException to HTTP 401/403. See references/openapi-security-reference.md.
EOF
