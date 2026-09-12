#!/usr/bin/env bash
# Run evals and publish the resulting log to Evaris WHATEVER the outcome —
# success, error, or interrupt — so partial results are always stored locally
# and reviewable on the platform.
#
# Usage:
#   bash scripts/run-evals.sh evals/my_eval.py [--limit 5] [more inspect-args...]
# Env:
#   EVARIS_API_TOKEN   publish token (full access) — required
#   EVARIS_PROJECT_ID  project id — required
#   RUN_NAME           optional run name (default: the log file name)
#   LOG_DIR            log directory (default: logs)
set -u

cd "$(dirname "$0")/.."
LOG_DIR="${LOG_DIR:-logs}"

# --- repo-specific setup -----------------------------------------------------
# Local runs keep secrets in .env; CI provides the same vars directly.
if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  . ./.env
  set +a
fi
# The z.ai key serves both the LangChain agent and the inspect judge.
if [ -n "${ZAI_API_KEY:-}" ] && [ -z "${OPENAI_API_KEY:-}" ]; then
  export OPENAI_API_KEY="$ZAI_API_KEY"
fi
export OPENAI_BASE_URL="${OPENAI_BASE_URL:-https://api.z.ai/api/paas/v4}"
# --- end repo-specific setup -------------------------------------------------

: "${EVARIS_PROJECT_ID:?EVARIS_PROJECT_ID must be set}"
: "${EVARIS_API_TOKEN:?EVARIS_API_TOKEN must be set (a full-access publish token)}"

# Repo defaults when the caller passes no --model: z.ai via the OpenAI-
# compatible provider. z.ai is chat-completions only, so responses_api=false
# stops inspect's OpenAI provider from hitting the (404) Responses API.
if ! [[ " $* " == *" --model "* ]]; then
  set -- "$@" --model "${INSPECT_EVAL_MODEL:-openai/glm-4.5}" -M responses_api=false
fi
# No TTY (CI, pipes): stream progress as log lines instead of the full-screen view.
DISPLAY_ARGS=""
if [ ! -t 1 ]; then
  DISPLAY_ARGS="--display log"
fi

PREVIOUS=$(ls -t "$LOG_DIR"/*.eval 2>/dev/null | head -1 || true)

# Let inspect handle Ctrl+C/SIGTERM itself: it finalizes the bundle with every
# sample completed so far (header status "interrupted"). This script survives
# the signal so it can still publish that partial log.
trap 'echo "==> interrupted; inspect is finalizing the partial log" >&2' INT TERM

echo "==> uv run inspect eval $* $DISPLAY_ARGS"
uv run inspect eval "$@" $DISPLAY_ARGS --log-dir "$LOG_DIR"
EVAL_EXIT=$?

LATEST=$(ls -t "$LOG_DIR"/*.eval 2>/dev/null | head -1 || true)
if [ -z "$LATEST" ] || [ "$LATEST" = "$PREVIOUS" ]; then
  echo "==> this run produced no log (killed before inspect wrote anything); nothing to publish" >&2
  exit "${EVAL_EXIT:-1}"
fi

# Publish even when the eval failed or was interrupted — Evaris marks the run
# by the eval's real status and keeps completed samples reviewable. `uv run`
# puts the project venv on PATH so the CLI can detect the inspect-ai version.
echo "==> publishing $LATEST to Evaris"
uv run npx --yes evaris publish "$LATEST" --project "$EVARIS_PROJECT_ID" \
  --name "${RUN_NAME:-$(basename "$LATEST" .eval)}" \
  || echo "==> publish failed — check EVARIS_API_TOKEN / EVARIS_API_URL" >&2

exit "${EVAL_EXIT:-0}"
