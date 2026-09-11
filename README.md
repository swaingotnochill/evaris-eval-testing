# evaris-eval-smoke

Production smoke test for the Evaris user flow:

```text
LangChain agent → Inspect eval → .eval artifact → publish with a PAT → Evaris ingest → runs UI
```

This repo runs the support-refund smoke eval (a LangChain tool-calling agent
scored by `model_graded_qa`) in GitHub Actions and publishes the resulting
`.eval` log to a real Evaris deployment using a personal access token — the
exact flow a customer's CI runner would use. If the workflow is green, the
whole publish path (auth → project access → artifact upload → queue ingest →
run list) works end to end.

## One-time setup

1. **Deploy Evaris** and make sure migrations have run for that environment
   (see `deploy-worker.yml` / `db-*-migrate.yml` in the backend repo).
2. **Create a personal access token**: sign in to the Evaris web app →
   Settings → API Tokens → Create token (e.g. `gha-eval-smoke`).
3. **Find your project id**: in the web app, Settings → API Tokens → copy
   the project id (looks like `proj_...`).
4. **Configure this repo** on GitHub:

   | Where | Name | Value |
   |---|---|---|
   | Secret | `EVARIS_API_TOKEN` | the PAT from step 2 |
   | Secret | `ZAI_API_KEY` | model API key (Z.ai) |
   | Variable | `EVARIS_API_URL` | e.g. `https://evaris-api-prod.<account>.workers.dev` |
   | Variable | `EVARIS_PROJECT_ID` | `proj_...` from step 3 |
   | Variable (optional) | `INSPECT_EVAL_MODEL` | default `openai-api/zai/glm-4.5` |
   | Variable (optional) | `LANGCHAIN_AGENT_MODEL` | default `glm-4.5` |
   | Variable (optional) | `OPENAI_BASE_URL` | default `https://api.z.ai/api/paas/v4` |

5. Push this repo, then run **Actions → Eval smoke → Run workflow**. The
   published run should appear in the runs list within a minute or two.

## Layout

- `agents/support_agent.py` — LangChain support-refund agent with order,
  policy, refund, and escalation tools.
- `evals/` — Inspect task + 5-sample dataset.
- `scripts/run-eval.sh` — runs `inspect eval`, leaves logs in `logs/`.
- Publishes with the [`evaris`](https://www.npmjs.com/package/evaris) CLI
  (`npx evaris publish`), which handles create-run → artifact upload →
  complete → ingest-wait. That package is the same one Evaris users install.
- `.github/workflows/eval.yml` — manual + weekly scheduled run.

## Local run

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cat > .env <<'EOF'
ZAI_API_KEY=...
OPENAI_BASE_URL=https://api.z.ai/api/paas/v4
EVARIS_API_URL=https://<your-deployment>
EVARIS_API_TOKEN=eva_...
EVARIS_PROJECT_ID=proj_...
EOF

bash scripts/run-eval.sh
npx evaris publish logs/
```

## The `evaris` package

Publishing uses the public `evaris` npm package (CLI + TypeScript SDK, built
from `sdk/typescript` in the backend repo). Before the first workflow run,
publish it once from the backend repo: add an `NPM_TOKEN` secret with publish
rights, then push a `sdk-v0.1.0` tag (or run the "Publish SDK" workflow).
