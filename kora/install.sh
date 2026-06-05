#!/bin/bash
# Kora Developer — Claude Code Skill Installer
#
# This script installs the Kora skills into your Claude Code skills directory.
# The Kora skill set provides specialized assistance for building microservices
# on the Kora framework — compile-time DI for Java/Kotlin.
#
# Usage: ./install.sh [target-directory]
# Example: ./install.sh ~/.claude/skills

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_TARGET="$HOME/.claude/skills"
TARGET_DIR="${1:-$DEFAULT_TARGET}"
SKILL_NAME="kora"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   Kora Developer — Claude Code Skills Installer          ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""

# Check if target directory exists
if [ ! -d "$TARGET_DIR" ]; then
    echo -e "${YELLOW}⚠️  Skills directory does not exist:${NC} $TARGET_DIR"
    echo "   Creating directory..."
    mkdir -p "$TARGET_DIR"
fi

# Check if skill already exists
if [ -d "$TARGET_DIR/$SKILL_NAME" ]; then
    echo -e "${YELLOW}⚠️  Skill already exists at $TARGET_DIR/$SKILL_NAME${NC}"
    echo "   Removing old version..."
    rm -rf "$TARGET_DIR/$SKILL_NAME"
fi

# Copy skill files
echo -e "${GREEN}📦 Copying skill files...${NC}"
cp -r "$SCRIPT_DIR" "$TARGET_DIR/$SKILL_NAME"

# Remove git files if present
rm -rf "$TARGET_DIR/$SKILL_NAME/.git"

echo ""
echo -e "${GREEN}✅ Kora Developer skill installed successfully!${NC}"
echo ""
echo -e "${BLUE}📍 Installed to:${NC} $TARGET_DIR/$SKILL_NAME"
echo ""
echo -e "${BLUE}📚 Available commands:${NC}"
echo ""
echo "   ${YELLOW}/kora${NC}              — Main meta-skill (10 principles, navigation)"
echo "   ${YELLOW}/kora-bootstrap${NC}    — Project scaffolding, DI, config"
echo "   ${YELLOW}/kora-database${NC}     — JDBC, Cassandra, repositories, @Query"
echo "   ${YELLOW}/kora-http-server${NC}  — REST controllers, routing"
echo "   ${YELLOW}/kora-http-client${NC}  — HTTP clients, interceptors"
echo "   ${YELLOW}/kora-openapi${NC}      — OpenAPI codegen (server/client)"
echo "   ${YELLOW}/kora-aop${NC}          — Validation, logging, resilience, cache"
echo "   ${YELLOW}/kora-kafka${NC}        — Kafka producers/consumers"
echo "   ${YELLOW}/kora-telemetry${NC}    — Metrics (Micrometer), tracing (OpenTelemetry)"
echo "   ${YELLOW}/kora-grpc${NC}         — gRPC server/client"
echo "   ${YELLOW}/kora-s3${NC}           — S3 object storage (AWS, MinIO)"
echo "   ${YELLOW}/kora-testing${NC}      — Integration tests, Testcontainers"
echo "   ${YELLOW}/kora-mapstruct${NC}    — DTO ↔ Entity mappers"
echo "   ${YELLOW}/kora-json${NC}         — JSON serialization"
echo "   ${YELLOW}/kora-journal${NC}      — Continuous improvement journal"
echo ""
echo -e "${BLUE}🔗 Documentation:${NC}"
echo "   • Kora Docs:    https://github.com/kora-projects/kora-docs"
echo "   • Examples:     https://github.com/kora-projects/kora-examples"
echo "   • Kora GitHub:  https://github.com/kora-projects/kora"
echo ""
echo -e "${BLUE}💡 Tip:${NC} Type ${YELLOW}/kora${NC} in Claude Code to get started!"
echo ""
