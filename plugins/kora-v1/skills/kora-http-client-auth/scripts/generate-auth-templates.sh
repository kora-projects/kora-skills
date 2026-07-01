#!/bin/bash

# Script to generate auth interceptor files from templates
# Usage: ./scripts/generate-auth-templates.sh <package> [config-prefix]

set -e

if [ -z "$1" ]; then
    echo "Usage: $0 <package-name> [config-prefix]"
    echo "Example: $0 com.example.client external.api"
    exit 1
fi

PACKAGE=$1
CONFIG_PREFIX=${2:-external.api}
OUTPUT_DIR="src/main/java/$(echo $PACKAGE | tr '.' '/')"

echo "Generating auth templates..."
echo "Package: $PACKAGE"
echo "Config prefix: $CONFIG_PREFIX"
echo "Output directory: $OUTPUT_DIR"

# Create output directory
mkdir -p "$OUTPUT_DIR"

# Function to generate file from template
generate() {
    local template=$1
    local output=$2
    echo "Generating $output..."
    sed -e "s/\${package}/$PACKAGE/g" \
        -e "s/\${config\.prefix}/$CONFIG_PREFIX/g" \
        "assets/$template" > "$OUTPUT_DIR/$output"
}

# Generate interceptors (class names match the template contents)
generate "BearerAuthInterceptor.java.template" "BearerAuthClientInterceptor.java"
generate "BasicAuthInterceptor.java.template" "BasicAuthClientInterceptor.java"
generate "ApiKeyInterceptor.java.template" "ApiKeyClientInterceptor.java"

# Generate token management
generate "TokenCache.java.template" "TokenCache.java"
generate "HttpClientTokenProvider.java.template" "HttpClientTokenProvider.java"
generate "OAuth2ClientCredentialsProvider.java.template" "OAuth2ClientCredentialsProvider.java"

echo ""
echo "Generated files:"
ls -la "$OUTPUT_DIR"/*.java
echo ""
echo "Next steps:"
echo "1. Review generated files in $OUTPUT_DIR"
echo "2. Add configuration to application.conf:"
echo ""
echo "  $CONFIG_PREFIX {"
echo "    url = \"https://api.example.com\""
echo "    # ... other config"
echo "  }"
echo ""
echo "3. Add the transport module to your @KoraApp:"
echo "   @KoraApp"
echo "   public interface Application extends OkHttpClientModule {}"
echo ""
echo "4. Attach interceptors with @InterceptWith on the @HttpClient interface or method."
echo ""
echo "NOTE: There is no ru.tinkoff.kora:http-client-auth artifact."
echo "      Auth lives in http-client-common; prefer the built-in"
echo "      Basic/ApiKey/Bearer interceptors over the generated custom ones."
