#!/usr/bin/env bash
#
# Render the kora-http-client-auth templates into a Kora 2.0 project.
#
# Emits Kora 2.0 code only: io.koraframework packages, synchronous HttpClientTokenProvider and
# HttpClientInterceptor contracts, @HttpClient("path"). Nothing here uses ru.tinkoff.kora,
# Context or CompletionStage.

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ASSETS_DIR="$SCRIPT_DIR/../assets"

PACKAGE=""
SCHEME="oauth2"
TARGET_LANG="java"
OUT_ROOT=""
DRY_RUN=0
FORCE=0

usage() {
    cat <<'USAGE'
Usage: generate-auth-templates.sh --package <java.package> [options]

Required:
  --package <pkg>      Target package, e.g. com.example.client.auth

Options:
  --scheme <name>      oauth2 (default) | interceptor | all
                         oauth2       OAuth2 client-credentials: config, token endpoint client,
                                      token cache, provider, module. A complete, compiling set.
                         interceptor  Hand-written 401-retry interceptor + token cache.
                         all          Everything.
  --lang <name>        java (default) | kotlin
  --out <dir>          Source root. Default: src/main/java (Java) or src/main/kotlin (Kotlin)
  --force              Overwrite files that already exist
  --dry-run            Print what would be written, write nothing
  -h, --help           This message

Not generated, because each is a few lines that belong in your own @Module rather than in a file
of its own — see references/http-client-auth-reference.md:
  * Basic auth      new BasicAuthHttpClientInterceptor(config.username(), config.password())
  * API key         new ApiKeyHttpClientInterceptor(ApiKeyLocation.HEADER, "X-API-KEY", config.key())
  * Static bearer   new BearerAuthHttpClientInterceptor(config.token())

Examples:
  generate-auth-templates.sh --package com.example.client.auth
  generate-auth-templates.sh --package com.example.client.auth --lang kotlin --dry-run
  generate-auth-templates.sh --package com.example.client.auth --scheme interceptor
USAGE
}

while [ $# -gt 0 ]; do
    case "$1" in
        --package) PACKAGE="${2:-}"; shift 2 ;;
        --scheme)  SCHEME="${2:-}";  shift 2 ;;
        --lang)    TARGET_LANG="${2:-}"; shift 2 ;;
        --out)     OUT_ROOT="${2:-}"; shift 2 ;;
        --force)   FORCE=1; shift ;;
        --dry-run) DRY_RUN=1; shift ;;
        -h|--help) usage; exit 0 ;;
        *) echo "error: unknown argument '$1'" >&2; echo >&2; usage >&2; exit 2 ;;
    esac
done

if [ -z "$PACKAGE" ]; then
    echo "error: --package is required" >&2
    echo >&2
    usage >&2
    exit 2
fi

if ! printf '%s' "$PACKAGE" | grep -Eq '^[a-z_][a-z0-9_]*(\.[a-z_][a-z0-9_]*)*$'; then
    echo "error: '$PACKAGE' is not a valid package name" >&2
    exit 2
fi

case "$TARGET_LANG" in
    java)   EXT="java" ;;
    kotlin) EXT="kt" ;;
    *) echo "error: --lang must be java or kotlin (got '$TARGET_LANG')" >&2; exit 2 ;;
esac

case "$SCHEME" in
    oauth2)      TEMPLATES="OAuth2Config OAuth2AuthClient TokenCache OAuth2ClientCredentialsProvider OAuth2AuthModule" ;;
    interceptor) TEMPLATES="TokenCache CustomAuthInterceptor" ;;
    all)         TEMPLATES="OAuth2Config OAuth2AuthClient TokenCache OAuth2ClientCredentialsProvider OAuth2AuthModule CustomAuthInterceptor" ;;
    *) echo "error: --scheme must be oauth2, interceptor or all (got '$SCHEME')" >&2; exit 2 ;;
esac

if [ -z "$OUT_ROOT" ]; then
    OUT_ROOT="src/main/$TARGET_LANG"
fi

PACKAGE_PATH="$(printf '%s' "$PACKAGE" | tr '.' '/')"
OUT_DIR="$OUT_ROOT/$PACKAGE_PATH"

echo "Package : $PACKAGE"
echo "Scheme  : $SCHEME"
echo "Language: $TARGET_LANG"
echo "Output  : $OUT_DIR"
[ "$DRY_RUN" -eq 1 ] && echo "Mode    : dry run (nothing will be written)"
echo

missing=0
for name in $TEMPLATES; do
    if [ ! -f "$ASSETS_DIR/$name.$EXT.template" ]; then
        echo "error: missing template $ASSETS_DIR/$name.$EXT.template" >&2
        missing=1
    fi
done
[ "$missing" -eq 0 ] || exit 1

conflicts=0
for name in $TEMPLATES; do
    if [ -e "$OUT_DIR/$name.$EXT" ] && [ "$FORCE" -eq 0 ]; then
        echo "error: $OUT_DIR/$name.$EXT already exists (use --force to overwrite)" >&2
        conflicts=1
    fi
done
[ "$conflicts" -eq 0 ] || exit 1

if [ "$DRY_RUN" -eq 0 ]; then
    mkdir -p "$OUT_DIR"
fi

for name in $TEMPLATES; do
    target="$OUT_DIR/$name.$EXT"
    if [ "$DRY_RUN" -eq 1 ]; then
        echo "would write $target"
    else
        sed "s|\${package}|$PACKAGE|g" "$ASSETS_DIR/$name.$EXT.template" > "$target"
        echo "wrote $target"
    fi
done

cat <<NEXT

Next steps
----------
1. Dependencies (koraVersion=2.0.0.RC2 from mavenCentral()):

     koraBom platform("io.koraframework:kora-bom:\$koraVersion")
     annotationProcessor "io.koraframework:annotation-processors"   # Kotlin: ksp "io.koraframework:symbol-processors"
     implementation "io.koraframework:config-hocon"
     implementation "io.koraframework:http-client-common"
     implementation "io.koraframework:http-client-ok"               # or http-client-jdk / http-client-apache
     implementation "io.koraframework:json-common"

   There is no http-client-auth artifact, and http-client-async was removed in 2.0.
NEXT

if [ "$SCHEME" = "oauth2" ] || [ "$SCHEME" = "all" ]; then
    cat <<'NEXT'

2. Add the hand-written module to @KoraApp — @ConfigSource and @HttpClient interfaces are
   registered by their processors and must NOT be listed, but a @Module must:

     @KoraApp
     public interface Application extends
             HoconConfigModule, JsonModule, LogbackModule, OkHttpClientModule,
             OAuth2AuthModule { … }

3. Configure. maskHeaders REPLACES the default ["authorization","set-cookie","cookie"] rather than
   extending it, so restate the defaults whenever you set it:

     oauth2 {
       clientId     = "my-service-client"
       clientSecret = ${OAUTH2_CLIENT_SECRET}
       scopes       = "api:read api:write"
     }
     httpClient {
       oauth2    { url = "https://auth.example", requestTimeout = 5s }
       secureApi {
         url = "https://api.example"
         telemetry.logging { enabled = true, maskHeaders = ["authorization","set-cookie","cookie"] }
       }
     }

4. Attach the interceptor to the business client:

     @InterceptWith(BearerAuthHttpClientInterceptor.class)
     @HttpClient("httpClient.secureApi")
     public interface SecureApiClient { … }
NEXT
fi

if [ "$SCHEME" = "interceptor" ] || [ "$SCHEME" = "all" ]; then
    cat <<'NEXT'

*. CustomAuthInterceptor replaces BearerAuthHttpClientInterceptor — do not attach both to one
   client, or each will overwrite the other's Authorization header:

     @InterceptWith(CustomAuthInterceptor.class)
     @HttpClient("httpClient.secureApi")
     public interface SecureApiClient { … }

   It needs an HttpClientTokenProvider in the graph. --scheme oauth2 generates one.
NEXT
fi

cat <<'NEXT'

Then: ./gradlew clean classes
NEXT
