#!/usr/bin/env bash
# Launch a cold-start SDLC agent through Claude Code or the Antigravity CLI.
#
#   scripts/sdlc/run-agent.sh <role> <brief-file>
#
# Cold start is structural: this script never passes --continue/-c.
# Set SDLC_AGENT_CWD to the worktree path to run the agent there.
set -euo pipefail

ROLE="${1:-}"
BRIEF="${2:-}"
if [ -z "$ROLE" ] || [ -z "$BRIEF" ]; then
  echo "usage: run-agent.sh <role> <brief-file>" >&2
  exit 2
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

if [ ! -f "$REPO_ROOT/sdlc/agents/$ROLE.md" ]; then
  echo "error: unknown role '$ROLE' (no sdlc/agents/$ROLE.md)" >&2
  exit 2
fi

if [ -f "$REPO_ROOT/sdlc/config.env" ]; then
  set -a
  # shellcheck disable=SC1091
  . "$REPO_ROOT/sdlc/config.env"
  set +a
fi

# Accept a brief path relative to the agent's working directory.
if [ ! -f "$BRIEF" ] && [ -n "${SDLC_AGENT_CWD:-}" ] && [ -f "$SDLC_AGENT_CWD/$BRIEF" ]; then
  BRIEF="$SDLC_AGENT_CWD/$BRIEF"
fi
if [ ! -f "$BRIEF" ]; then
  echo "error: brief not found: $BRIEF" >&2
  exit 2
fi
BRIEF="$(cd "$(dirname "$BRIEF")" && pwd)/$(basename "$BRIEF")"

CLI="${SDLC_CLI:-auto}"
if [ "$CLI" = "auto" ]; then
  if [ -n "${CLAUDECODE:-}" ] && command -v agy >/dev/null 2>&1; then
    CLI="agy"
  elif command -v claude >/dev/null 2>&1; then
    CLI="claude"
  elif command -v agy >/dev/null 2>&1; then
    CLI="agy"
  else
    echo "error: neither claude nor agy is on PATH" >&2
    exit 2
  fi
fi

if [ -n "${SDLC_AGENT_CWD:-}" ]; then
  cd "$SDLC_AGENT_CWD"
fi

PROMPT="$(cat "$BRIEF")"
echo "[sdlc] cold agent: role=$ROLE cli=$CLI cwd=$PWD" >&2

case "$CLI" in
  claude)
    if [ -n "${CLAUDECODE:-}" ] && [ "${SDLC_ALLOW_NESTED_CLAUDE:-0}" != "1" ]; then
      echo "error: refusing to nest claude inside a Claude Code session." >&2
      echo "       set SDLC_CLI=agy, or SDLC_ALLOW_NESTED_CLAUDE=1 to override." >&2
      exit 2
    fi
    exec claude -p "$PROMPT" \
      --agent "$ROLE" \
      --output-format json \
      --permission-mode "${SDLC_CLAUDE_PERMISSION_MODE:-auto}"
    ;;
  agy)
    AGY_ARGS=(--agent "$ROLE" --output-format json)
    if [ -n "${SDLC_AGY_MODEL:-}" ]; then
      AGY_ARGS+=(--model "$SDLC_AGY_MODEL")
    fi
    if [ -n "${SDLC_AGY_MODE:-}" ]; then
      AGY_ARGS+=(--mode "$SDLC_AGY_MODE")
    fi
    if [ "${SDLC_AGY_DANGEROUSLY_SKIP_PERMISSIONS:-false}" = "true" ]; then
      AGY_ARGS=(--dangerously-skip-permissions "${AGY_ARGS[@]}")
    fi
    exec agy -p "$PROMPT" "${AGY_ARGS[@]}"
    ;;
  *)
    echo "error: SDLC_CLI must be auto, claude, or agy (got '$CLI')" >&2
    exit 2
    ;;
esac
