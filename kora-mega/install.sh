#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_NAME="kora-mega"

echo "Installing ${SKILL_NAME} skill..."

# Create destination directory
DEST_DIR="${HOME}/.claude/skills/${SKILL_NAME}"
mkdir -p "${DEST_DIR}"

# Copy skill files from skills/kora-developer/
cp -r "${SCRIPT_DIR}/skills/kora-developer/assets" "${DEST_DIR}/" 2>/dev/null || true
cp -r "${SCRIPT_DIR}/skills/kora-developer/references" "${DEST_DIR}/" 2>/dev/null || true
cp -r "${SCRIPT_DIR}/skills/kora-developer/scripts" "${DEST_DIR}/" 2>/dev/null || true
cp -r "${SCRIPT_DIR}/skills/kora-developer/evals" "${DEST_DIR}/" 2>/dev/null || true
cp "${SCRIPT_DIR}/skills/kora-developer/SKILL.md" "${DEST_DIR}/" 2>/dev/null || true
cp "${SCRIPT_DIR}/skills/kora-developer/README.md" "${DEST_DIR}/" 2>/dev/null || true

echo "${SKILL_NAME} skill installed successfully to ${DEST_DIR}"
