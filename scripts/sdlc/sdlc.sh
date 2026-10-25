#!/usr/bin/env bash
# Robotrader SDLC driver — thin wrapper around sdlc.py.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$SCRIPT_DIR/sdlc.py" "$@"
