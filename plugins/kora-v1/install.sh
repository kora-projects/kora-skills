#!/bin/bash
set -e

# Kora Skill Installer
# Installs kora-v1 skill to agent-specific directories

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_NAME="kora-v1"
SKILL_SOURCE="${SCRIPT_DIR}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

echo_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

echo_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Detect agent and install to appropriate directory
install_skill() {
    local dest_dir="$1"
    local agent_name="$2"
    
    echo_info "Installing ${SKILL_NAME} for ${agent_name}..."
    
    mkdir -p "${dest_dir}"
    
    # Copy skill files
    cp -r "${SKILL_SOURCE}/skills" "${dest_dir}/" 2>/dev/null || true
    cp "${SKILL_SOURCE}/SKILL.md" "${dest_dir}/" 2>/dev/null || true
    
    echo_info "${SKILL_NAME} installed to ${dest_dir}"
}

# Main installation logic
main() {
    echo_info "Kora Skill Installer"
    echo "========================"
    
    # Check for source files
    if [ ! -f "${SKILL_SOURCE}/SKILL.md" ]; then
        echo_error "SKILL.md not found in ${SKILL_SOURCE}"
        exit 1
    fi
    
    if [ ! -d "${SKILL_SOURCE}/skills" ]; then
        echo_error "skills/ directory not found in ${SKILL_SOURCE}"
        exit 1
    fi
    
    # Detect installed agents and install to each
    local installed=0
    
    # Claude Code (~/.claude/skills/)
    if command -v claude &> /dev/null || [ -d "${HOME}/.claude" ]; then
        install_skill "${HOME}/.claude/skills/${SKILL_NAME}" "Claude Code"
        installed=$((installed + 1))
    fi
    
    # OpenAI Codex (~/.agents/skills/)
    if [ -d "${HOME}/.agents" ]; then
        install_skill "${HOME}/.agents/skills/${SKILL_NAME}" "OpenAI Codex"
        installed=$((installed + 1))
    fi

    # OMP / OpenCode-compatible agents (~/.omp/skills/)
    if [ -d "${HOME}/.omp" ]; then
        install_skill "${HOME}/.omp/skills/${SKILL_NAME}" "OMP"
        installed=$((installed + 1))
    fi

    # OpenClaw / OpenClaude-compatible agents (~/.openclaude/skills/)
    if [ -d "${HOME}/.openclaude" ]; then
        install_skill "${HOME}/.openclaude/skills/${SKILL_NAME}" "OpenClaw"
        installed=$((installed + 1))
    fi
    
    # Pi Coding Agent (~/.pi/skills/)
    if [ -d "${HOME}/.pi" ]; then
        install_skill "${HOME}/.pi/skills/${SKILL_NAME}" "Pi Coding Agent"
        installed=$((installed + 1))
    fi
    
    # Cursor (~/.cursor/skills/)
    if [ -d "${HOME}/.cursor" ]; then
        install_skill "${HOME}/.cursor/skills/${SKILL_NAME}" "Cursor"
        installed=$((installed + 1))
    fi
    
    if [ ${installed} -eq 0 ]; then
        echo_warn "No supported agents detected. Installing to default location..."
        install_skill "${HOME}/.local/share/skills/${SKILL_NAME}" "Default"
        installed=1
    fi
    
    echo ""
    echo_info "Installation complete!"
    echo ""
    echo "Next steps:"
    echo "  1. Restart your AI coding agent"
    echo "  2. Ask: 'Help me build a Kora microservice'"
    echo "  3. The agent will activate the kora-v1 skill"
    echo ""
    echo "Documentation:"
    echo "  - Kora Docs: https://kora-projects.github.io/kora-docs"
    echo "  - Examples: https://github.com/kora-projects/kora-examples"
    echo "  - Templates: https://github.com/kora-projects/kora-java-template"
}

main "$@"
