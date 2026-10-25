#!/usr/bin/env bash
# Install the canonical SDLC agent profiles into Claude Code and Antigravity CLI.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$SCRIPT_DIR/install_agents.py" "$@"
