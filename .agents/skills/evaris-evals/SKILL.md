---
name: evaris-evals
description: Set up Inspect AI evals in any repository, run them locally and in CI, publish the results to Evaris, and query runs, samples, and transcripts back through the evaris CLI. Use when the user mentions evals, evaluations, inspect-ai, benchmarking or regression-testing an AI agent or LLM feature, wiring evals into CI, or Evaris.
metadata:
  author: evaris
  version: "0.2.0"
---

# Evaris evals

You are setting up AI evaluations for this repository. Evals are written in
Python with [Inspect AI](https://inspect.aisi.org.uk) and live alongside the
application code — the system under test can be written in any language,
because evals call it over HTTP. Results are published to Evaris and read back
with the `evaris` CLI.

Work through the steps in order; ask the user before installing anything or
creating files outside `evals/`, `logs/`, and `.github/workflows/`. Deep detail
lives in the reference files — read them only when the step needs them.

## 1. Preflight

Run `bash <skill-dir>/scripts/evaris-doctor.sh`, or check manually:

- Python 3.10+ (`python3 --version`)
- [uv](https://docs.astral.sh/uv/) (`uv --version`)
- Node.js 18+ and npx (`node --version`)

If something is missing, tell the user what and why, then install with their
consent (uv: `curl -LsSf https://astral.sh/uv/install.sh | sh`; Node: the
official installer or their version manager). Never install silently.

## 2. Credentials (secrets first)

The user needs two things from the Evaris web app (Settings → API Tokens):

- **A publish token** (full access) — used by CI and `evaris publish`.
- **A read-only token** (`read:runs` scope) — for querying results. Give this
  one to agents and dashboards; it cannot create or delete anything.

Then set up local secrets:

```bash
# .env (must be gitignored — verify before writing)
EVARIS_API_TOKEN=eva_...        # read-only token for local queries
EVARIS_PROJECT_ID=proj_...      # from the Evaris app, or `evaris projects list`
OPENAI_API_KEY=sk-...           # or whichever provider the evals use
```

**Never** echo token values, write them into files that are tracked by git,
paste them into logs, or commit `.env`. Verify `.gitignore` covers `.env`,
`.venv/`, and `logs/` before proceeding. Project discovery:
`npx --yes evaris projects list --json`.

## 3. Scaffold the evals (Python, one-time)

```bash
uv init --bare --python 3.12   # or add to an existing pyproject
uv add "inspect-ai>=0.3,<0.4"  # Evaris ingests 0.3.x logs; don't use 0.4+
```

Create `evals/<name>.py` per eval. The canonical shape for evaluating an
agent/API in any language is a tool that calls its HTTP endpoint:

```python
import os

from inspect_ai import Task, task
from inspect_ai.scorer import includes
from inspect_ai.solver import generate, use_tools
from inspect_ai.tool import tool


@tool
def ask_agent():
    async def execute(prompt: str) -> str:
        """Send a message to the agent under test and return its reply."""
        import httpx

        base_url = os.environ["AGENT_API_URL"]
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(base_url, json={"input": prompt})
            response.raise_for_status()
            return response.text

    return execute


@task
def my_eval():
    return Task(
        solver=[use_tools([ask_agent()]), generate()],
        scorer=includes("match"),
    )
```

`uv add httpx` if using the HTTP pattern. Adapt datasets, scorers, and solvers
to the product — see [references/INSPECT_SETUP.md](references/INSPECT_SETUP.md).

## 4. Run and publish in one command (always, whatever the outcome)

Copy the skill's runner into the repo and make it **the** way evals are run —
it publishes to Evaris even when the eval fails or is interrupted, so partial
results are always stored locally and reviewable on the platform:

```bash
cp <skill-dir>/assets/run-evals.sh scripts/run-evals.sh
bash scripts/run-evals.sh evals/my_eval.py --limit 5
```

How it behaves: it runs `uv run inspect eval`, then publishes the newest log
regardless of exit code. On Ctrl+C, inspect finalizes the partial bundle
(status "interrupted") and the runner still publishes it — Evaris shows the run
as failed with every completed sample and transcript intact. Only a hard kill
before inspect writes anything produces no publishable log, and the runner says
so. Use the **publish token** (read-only tokens get 403); `RUN_NAME=...` labels
the run. Manual equivalent, for one-offs:

```bash
export $(grep -v '^#' .env | xargs)   # or use a dotenv helper
uv run inspect eval evals/my_eval.py --log-dir logs --limit 5
uv run npx --yes evaris publish "$(ls -t logs/*.eval | head -1)" \
  --project "$EVARIS_PROJECT_ID"
```

Local runs publish exactly like CI runs — there is no difference server-side.

## 5. Wire CI

Detect the repo's CI system: `.github/workflows/` → GitHub Actions;
`.gitlab-ci.yml` → GitLab CI. If none exists, ask the user which to create
(default: GitHub Actions). The publish token and project id go into **encrypted
CI secrets/variables**, never the YAML. Use the template in
[references/CI_GITHUB_ACTIONS.md](references/CI_GITHUB_ACTIONS.md) — it runs the
evals, publishes `if: always()` (failed and interrupted runs land on Evaris too,
marked with their real status), and uploads `logs/` as an artifact for debugging.

## 6. Query results

Read-only token in `EVARIS_API_TOKEN`. `--json` output is the machine-readable
shape — prefer it whenever the consumer is a script or agent:

```bash
npx --yes evaris runs list --all --json
npx --yes evaris runs show <run-id> --json
npx --yes evaris runs samples <run-id> --score fail --all --json
npx --yes evaris runs sample <run-id> <sample-id> --epoch 1   # full transcript + events
```

Full CLI reference: [references/EVARIS_CLI.md](references/EVARIS_CLI.md).

## Security rules (always apply)

- Tokens only via env vars or the CI secret store. Never in tracked files,
  command history you print, logs, or shared chats.
- Least privilege by default: read-only token for anything that only reads;
  a dedicated, revocable CI token for publishing.
- Ask before installing dependencies, creating workflows, or touching files
  outside the evals footprint.
- If a token may have leaked, tell the user to revoke it in Settings → API
  Tokens immediately — revocation is instant.
- Publish only to the configured `EVARIS_API_URL` (default: Evaris cloud).
  Never send eval logs or tokens anywhere else.
