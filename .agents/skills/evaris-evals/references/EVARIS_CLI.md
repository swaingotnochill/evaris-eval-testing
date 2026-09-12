# Evaris CLI reference

`npx --yes evaris <command>` (or `npm i -g evaris`). Auth via env or flags:
`EVARIS_API_TOKEN` / `--api-token` (required), `EVARIS_API_URL` / `--api-url`
(default: the Evaris cloud API), `EVARIS_PROJECT_ID` / `--project`.

Tokens: create in the Evaris web app under Settings → API Tokens. **Read-only**
tokens (scope `read:runs`) work for every command except `publish`.

## Publishing (requires a full-access token)

```bash
evaris publish <log-file-or-dir> --project <project-id> [--name <run-name>] [--no-wait] [--timeout 180]
```

Uploads exactly one `.eval` log (a directory must contain exactly one — when
`logs/` holds several, pass the newest: `"$(ls -t logs/*.eval | head -1)"`),
then waits for Evaris to ingest it. `--no-wait` returns once ingest is queued.
Local runs publish exactly like CI runs; there is no difference server-side.

## Reading results (read-only token is enough)

Every command takes `--json` for machine-readable output — prefer it in scripts
and agents. `--all` follows pagination (capped at 5000 rows).

```bash
evaris projects list [--json]
# Projects the token can see. Needed for --project ids.

evaris runs list [--project <id>] [--limit <n>] [--all] [--json]
# Newest-first runs. --project can be omitted when the token sees exactly one
# project; otherwise the command lists the options and asks for --project.
# JSON shape: { "runs": [...], "next_cursor": string | null }

evaris runs show <run-id> [--json]
# One run: status, eval header (task, model), scores, metrics, warnings.
# JSON includes the full eval_header.

evaris runs samples <run-id> [--score pass|partial|fail] [--limit <n>] [--all] [--json]
# Per-sample rows: id, epoch, target, completed, message/token counts, scores.
# JSON shape: { "samples": [...], "next_cursor": string | null }

evaris runs sample <run-id> <sample-id> [--epoch 1]
# The full sample document: input, message transcript (user/assistant/tool),
# model events (the trace), scores with explanations, attachments, metadata.
# Always printed as JSON.
```

## Reading results over HTTP instead

The CLI hits the public REST API — usable from any language:

```bash
curl -H "Authorization: Bearer $EVARIS_API_TOKEN" \
  "$EVARIS_API_URL/v1/runs?project_id=$EVARIS_PROJECT_ID&limit=20"
```

Endpoints: `GET /v1/projects`, `GET /v1/runs`, `GET /v1/runs/{id}`,
`GET /v1/runs/{id}/samples`, `GET /v1/runs/{id}/samples/{sample_id}?epoch=1`.
Cursor pagination via `next_cursor`; responses are JSON; the OpenAPI spec is at
`GET /openapi.json` on any deployment.

## Exit codes and errors

- Missing token/project: exit 1 with the requirement in the message.
- API errors print `API request failed (<status> <statusText>): <server detail>`
  — 401 means bad/revoked token, 403 read-only token on a write, 404 wrong
  project id (or no access), 429 rate limited (respect `Retry-After`).
