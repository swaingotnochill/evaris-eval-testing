# Inspect AI setup reference

Inspect AI is a Python framework (UK AI Security Institute). Evals are Python
files; the system under test can be written in any language as long as it is
reachable over HTTP (or callable as a subprocess).

## Environment

- Python 3.10+ (3.12 recommended).
- Manage deps with uv: `uv init --bare --python 3.12 && uv add "inspect-ai>=0.3,<0.4"`.
- Evaris parses inspect-ai **0.3.x** log archives. Version 0.4+ logs are not
  supported yet (runs surface a compatibility warning; stick to `>=0.3,<0.4`).
- Model credentials are plain env vars: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`,
  etc. Select models with `--model openai/gpt-4o-mini` style ids.

## Repository layout

```
evals/
  my_eval.py        # one Task per file
  datasets/         # optional JSON/CSV datasets
logs/               # .eval output (gitignore it)
pyproject.toml      # uv-managed; inspect-ai + httpx pinned
```

Add `.venv/`, `logs/`, and `.env` to `.gitignore` if not present.

## Anatomy of an eval that tests an HTTP agent

```python
import os

from inspect_ai import Task, task
from inspect_ai.dataset import json_dataset
from inspect_ai.scorer import Includes, match
from inspect_ai.solver import generate, use_tools
from inspect_ai.tool import tool


@tool
def ask_agent():
    """Tool wrapper around the agent under test's HTTP API."""

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
def support_refund():
    return Task(
        dataset=json_dataset("evals/datasets/support_refund.json"),
        solver=[use_tools([ask_agent()]), generate()],
        scorer=match(),
    )
```

Dataset JSON rows look like
`{"input": "Can I get a refund for order 1234?", "target": "yes"}`.

## Scorers worth knowing

- `match()` — exact/normalized match against `target`.
- `includes()` — target substring appears in the completion.
- `model_graded FACT` style LLM judges (`model_graded_qa()`) for open-ended
  answers (costs extra model calls).
- Custom Python scorers for exact product logic (status codes, JSON fields).

## Running

```bash
# iterate: small sample first
uv run inspect eval evals/support_refund.py --log-dir logs --limit 5

# full run
uv run inspect eval evals/support_refund.py --log-dir logs

# pick a model / multiple epochs
uv run inspect eval evals/support_refund.py --model openai/gpt-4o-mini --epochs 2
```

Each run writes one `logs/<timestamp>/…eval` file — that file is what
`evaris publish` uploads.

## Viewing locally vs Evaris

`uv run inspect view` opens Inspect's local viewer for quick iteration.
Publishing to Evaris gives the team shared history, per-sample transcripts,
event traces, and API/CLI access to results — both can coexist.
