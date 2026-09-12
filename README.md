# evaris-eval-testing — skill-agent-test branch

Clean slate for manually testing the **evaris-evals agent skill**: the evals,
the run script, and the CI workflow have been removed on this branch. `main`
still has the previous setup.

Kept on purpose:

- `agents/support_agent.py` — the LangChain agent under test.
- `requirements.txt` — its Python dependencies.
- `.env` (gitignored) — local secrets (`EVARIS_API_TOKEN`,
  `EVARIS_PROJECT_ID`, `ZAI_API_KEY`).

To test the skill here: install it with
`npx skills add <skills-repo-owner>/<skills-repo>` (or from a local checkout),
then ask your agent to set up inspect-ai evals for this repo, run a small
sample locally, and publish the newest log to Evaris.
