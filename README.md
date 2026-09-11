# evaris-eval-testing

Smoke test for the Evaris user flow, kept as simple as possible:

```text
Inspect eval (2 questions, real model API) → evaris publish (PAT) → Evaris runs UI
```

## One-time setup

1. A running Evaris deployment (e.g. production). In its web app: Settings →
   API Tokens → create a token, and copy the project id shown on the same page.
2. Push this repo to GitHub, then from the repo root:

   ```bash
   gh secret set ZAI_API_KEY          # model API key (Z.ai)
   gh secret set EVARIS_API_TOKEN     # personal access token from the web app
   gh variable set EVARIS_API_URL --body "https://<your-evaris-api-origin>"
   gh variable set EVARIS_PROJECT_ID --body "proj_..."
   ```

3. Actions → **Eval smoke** → Run workflow. The run appears in the Evaris
   runs list within a minute or two, with 2 scored samples.

## Layout

- `evals/evals.py` — the whole eval: two `Sample`s, default solver (one real
  model call each), `includes()` scoring. No agent, no dataset file.
- `scripts/run-eval.sh` — `inspect eval ...`, logs to `logs/`.
- `.github/workflows/eval.yml` — weekly cron + manual dispatch; publishes
  with `npx evaris@latest publish logs/` (the public `evaris` npm package).

## Local run

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export ZAI_API_KEY=...
bash scripts/run-eval.sh
npx evaris@latest publish logs/
```

(`evaris` reads `EVARIS_API_URL`, `EVARIS_API_TOKEN`, `EVARIS_PROJECT_ID`
from the environment; `publish --help` for flags.)
