#!/usr/bin/env bash
# Preflight checks for the evaris-evals skill. Verifies tool presence and
# reports (never prints) required environment variables. Read-only.
set -u

failures=0

check() {
  # check <label> <command...>
  local label="$1"
  shift
  if "$@" >/dev/null 2>&1; then
    echo "ok      $label ($("$@" 2>/dev/null | head -n1))"
  else
    echo "MISSING $label"
    failures=$((failures + 1))
  fi
}

need_env() {
  # need_env <var> <why>
  if [ -n "${!1:-}" ]; then
    echo "ok      \$$1 is set"
  else
    echo "unset   \$$1 — $2"
  fi
}

check "python3 (3.10+)" python3 --version
check "uv" uv --version
check "node (18+)" node --version
check "npx" npx --version

echo
echo "Environment (values are never printed):"
need_env EVARIS_API_TOKEN "Evaris API token (Settings → API Tokens)"
need_env EVARIS_PROJECT_ID "project id (evaris projects list)"
need_env AGENT_API_URL "base URL of the system under test (for HTTP evals)"

if [ "$failures" -gt 0 ]; then
  echo
  echo "$failures tool(s) missing. Install with the user's consent before continuing:"
  echo "  uv:   curl -LsSf https://astral.sh/uv/install.sh | sh"
  echo "  node: https://nodejs.org/en/download (or the user's version manager)"
  exit 1
fi
