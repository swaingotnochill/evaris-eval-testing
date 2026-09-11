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
3. **Find your project id**: with the web app open on the runs page, look at
   the network tab for the `/v1/setup/bootstrap` response — the value of
   `project.public_id` (looks like `proj_...`).
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
- `publish/publish.mjs` — dependency-free publisher (create run → upload
  artifact → complete → poll ingest), mirroring the Evaris SDK's publish flow.
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
node publish/publish.mjs logs/
```

## Why a standalone publisher (not the Evaris SDK)?

The Evaris TypeScript SDK (`sdk/typescript` in the backend repo) is not
published to npm yet — it is only consumable inside the monorepo. Until it is
(add a `package.json` + publish workflow there, then swap this script for
`pnpm inspect:publish`), this repo publishes with plain `fetch` against the
same OpenAPI-documented endpoints, so the smoke test needs nothing installed
and still exercises the identical wire contract.
