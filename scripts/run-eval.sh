#!/usr/bin/env bash
# Run an eval task against a real model API; logs land in $LOG_DIR (default logs/).
# Default eval is the LangChain support agent; INSPECT_EVAL_FILE=smoke.py for
# the cheap pipeline check.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

if [[ -f .env ]]; then
  set -a
  source .env
  set +a
fi

# The OpenAI-compatible provider reads OPENAI_API_KEY / OPENAI_BASE_URL; the
# LangChain agent model reads the same pair.
if [[ -n "${ZAI_API_KEY:-}" && -z "${OPENAI_API_KEY:-}" ]]; then
  export OPENAI_API_KEY="$ZAI_API_KEY"
fi
export OPENAI_BASE_URL="${OPENAI_BASE_URL:-https://api.z.ai/api/paas/v4}"

MODEL="${INSPECT_EVAL_MODEL:-openai/glm-4.5}"
EVAL_FILE="${INSPECT_EVAL_FILE:-support_refund_smoke.py}"
LOG_DIR="${INSPECT_LOG_DIR:-logs}"

# Task files import agents/ from the repo root.
export PYTHONPATH="$REPO_ROOT${PYTHONPATH:+:$PYTHONPATH}"

mkdir -p "$LOG_DIR"

# Z.ai is OpenAI chat-completions compatible only; inspect's newer OpenAI
# provider would otherwise try the Responses API and 404.
inspect eval "evals/$EVAL_FILE" --model "$MODEL" -M responses_api=false \
  --log-dir "$LOG_DIR" --limit 5
