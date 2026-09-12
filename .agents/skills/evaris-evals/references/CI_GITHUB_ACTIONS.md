# CI wiring reference — GitHub Actions

Template for `.github/workflows/evals.yml`. Before creating it, check the repo
for existing CI (`.github/workflows/`, `.gitlab-ci.yml`, `Jenkinsfile`) and
follow the existing conventions where they conflict with this template.

**Secrets are never written into the YAML.** Configure in the repo settings:

- Secrets: `EVARIS_API_TOKEN` (a dedicated **full-access** publish token),
  plus the model provider key(s) the evals need (e.g. `OPENAI_API_KEY`).
- Variables: `EVARIS_PROJECT_ID` (non-secret), or inline it below.

```yaml
name: evals

on:
  pull_request:
    paths:
      - "evals/**"
      - ".github/workflows/evals.yml"
  workflow_dispatch:

jobs:
  evals:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-node@v4
        with:
          node-version: 22

      - uses: astral-sh/setup-uv@v5
        with:
          python-version: "3.12"

      - name: Install eval dependencies
        run: uv sync

      - name: Run evals
        run: uv run inspect eval evals/ --log-dir logs --limit 20
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
          AGENT_API_URL: ${{ vars.AGENT_API_URL }}

      - name: Publish to Evaris
        # `if: always()` publishes failed and interrupted evals too — partial
        # results stay reviewable and the run status reflects the real outcome.
        # `uv run` exposes the project venv so the CLI detects the inspect version.
        if: always()
        run: uv run npx --yes evaris publish "$(ls -t logs/*.eval | head -1)" --project "$EVARIS_PROJECT_ID" --name "ci-${GITHUB_SHA::7}"
        env:
          EVARIS_API_TOKEN: ${{ secrets.EVARIS_API_TOKEN }}
          EVARIS_PROJECT_ID: ${{ vars.EVARIS_PROJECT_ID }}

      - name: Upload eval logs
        uses: actions/upload-artifact@v4
        if: always()
        with:
          name: eval-logs
          path: logs/
```

Notes:

- `evaris publish` accepts one log file or a directory containing exactly one.
  The `ls -t | head -1` picks the newest log when a run produced several; drop
  it when there is only ever one.
- `--limit 20` keeps CI cost bounded; remove it once the suite is stable.
- Keep `if: always()` on the artifact upload so failed runs are debuggable.
- Self-hosted Evaris: add `EVARIS_API_URL: ${{ vars.EVARIS_API_URL }}` to the
  publish step env.
- For other CI systems (GitLab, Jenkins, CircleCI): same three phases —
  uv setup, `uv run inspect eval`, `npx evaris publish` — with the token in the
  platform's secret store. Ask the user before creating files for a CI system
  the repo doesn't already use.
