#!/usr/bin/env bash
# Run the support-refund smoke eval and leave .eval logs in $LOG_DIR (default logs/).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

if [[ -f .env ]]; then
  set -a
  source .env
  set +a
fi

# inspect's `zai` provider (openai-api/zai/<model>) reads ZAI_* vars; the
# LangChain agent reads OPENAI_* vars. Map whichever is set.
if [[ -n "${ZAI_API_KEY:-}" && -z "${OPENAI_API_KEY:-}" ]]; then
  export OPENAI_API_KEY="$ZAI_API_KEY"
fi
if [[ -n "${OPENAI_BASE_URL:-}" && -z "${ZAI_BASE_URL:-}" ]]; then
  export ZAI_BASE_URL="$OPENAI_BASE_URL"
fi

MODEL="${INSPECT_EVAL_MODEL:-openai-api/zai/glm-4.5}"
LOG_DIR="${INSPECT_LOG_DIR:-logs}"

export PYTHONPATH="$REPO_ROOT${PYTHONPATH:+:$PYTHONPATH}"

mkdir -p "$LOG_DIR"

inspect eval evals/evals.py \
  --model "$MODEL" \
  --log-dir "$LOG_DIR" \
  --limit 5
