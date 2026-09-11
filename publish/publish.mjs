#!/usr/bin/env node
/**
 * Standalone Evaris publisher with zero npm dependencies.
 *
 * Mirrors the SDK publish flow (sdk/typescript/src/inspect/publish.ts in the
 * evaris-backend-service repo): create run → upload artifact → complete run
 * (queues ingest) → poll until the run leaves `ingesting`. Kept dependency
 * free on purpose: the Evaris SDK is not published to npm yet, and this way
 * the smoke repo exercises the same HTTP contract with nothing to install.
 *
 * Usage:
 *   node publish/publish.mjs <log-dir> --project <project-id> [options]
 * Options (env fallbacks in parentheses):
 *   --project <id>       Evaris project public id (EVARIS_PROJECT_ID) — required
 *   --api-url <url>      API origin (EVARIS_API_URL, default http://localhost:8787)
 *   --api-token <token>  Personal access token (EVARIS_API_TOKEN) — required
 *   --name <name>        Run name (default: <log-file-stem>-<timestamp>)
 *   --timeout <seconds>  Ingest poll timeout, 0 to skip polling (default 180)
 */
import { execFile } from "node:child_process";
import { createHash } from "node:crypto";
import { readdir, readFile, stat } from "node:fs/promises";
import { basename, join } from "node:path";
import { promisify } from "node:util";

const execFileAsync = promisify(execFile);

function parseArgs(argv) {
  const options = {
    "api-url": process.env.EVARIS_API_URL ?? "http://localhost:8787",
    "api-token": process.env.EVARIS_API_TOKEN,
    name: undefined,
    project: process.env.EVARIS_PROJECT_ID,
    timeout: "180",
  };
  const positionals = [];
  for (let i = 0; i < argv.length; i++) {
    const arg = argv[i];
    if (arg.startsWith("--")) {
      const key = arg.slice(2);
      const value = argv[++i];
      if (value === undefined) throw new Error(`Missing value for --${key}.`);
      options[key] = value;
    } else {
      positionals.push(arg);
    }
  }
  return { options, positionals };
}

const sha256Hex = (bytes) => createHash("sha256").update(bytes).digest("hex");

/** Newest .eval log in the directory (a failed earlier run may have left one). */
async function newestEvalLog(logDir) {
  const entries = await readdir(logDir, { withFileTypes: true });
  const files = entries.filter((entry) => entry.isFile() && entry.name.endsWith(".eval"));
  if (files.length === 0) {
    throw new Error(`No .eval logs found in ${logDir}.`);
  }
  let newest = null;
  for (const file of files) {
    const stats = await stat(join(logDir, file.name));
    if (!newest || stats.mtimeMs > newest.mtimeMs) {
      newest = { name: file.name, mtimeMs: stats.mtimeMs };
    }
  }
  return newest.name;
}

/** Best-effort inspect-ai version for the run manifest source. */
async function inspectAiVersion() {
  try {
    const { stdout } = await execFileAsync("python3", [
      "-c",
      "from importlib.metadata import version; print(version('inspect_ai'))",
    ]);
    return stdout.trim() || "unknown";
  } catch {
    return process.env.INSPECT_AI_VERSION ?? "unknown";
  }
}

async function api(baseUrl, token, method, path, body, rawBody) {
  const response = await fetch(`${baseUrl.replace(/\/$/, "")}${path}`, {
    method,
    headers: {
      Authorization: `Bearer ${token}`,
      ...(body !== undefined ? { "content-type": "application/json" } : {}),
    },
    body: rawBody ?? (body !== undefined ? JSON.stringify(body) : undefined),
  });
  if (!response.ok) {
    const text = await response.text().catch(() => "");
    throw new Error(`${method} ${path} failed: ${response.status} ${text.slice(0, 300)}`);
  }
  if (response.status === 204) return undefined;
  return response.json();
}

async function main() {
  const { options, positionals } = parseArgs(process.argv.slice(2));
  const logDir = positionals[0];
  if (!logDir) throw new Error("Usage: node publish/publish.mjs <log-dir> --project <project-id>");
  if (!options.project) throw new Error("--project or EVARIS_PROJECT_ID is required.");
  if (!options["api-token"]) throw new Error("--api-token or EVARIS_API_TOKEN is required.");

  const fileName = await newestEvalLog(logDir);
  const bytes = await readFile(join(logDir, fileName));
  const stats = await stat(join(logDir, fileName));
  const checksum = sha256Hex(bytes);
  const contentType = fileName.endsWith(".json") || fileName.endsWith(".json.gz")
    ? "application/json"
    : "application/octet-stream";
  const runName =
    options.name ?? `${fileName.replace(/\.eval$/, "")}-${new Date().toISOString().slice(0, 16)}`;
  const apiUrl = options["api-url"];
  const token = options["api-token"];
  const projectId = options.project;
  const startedAt = new Date().toISOString();

  const run = await api(apiUrl, token, "POST", "/v1/runs", {
    project_id: projectId,
    execution_mode: "external",
    name: runName,
    tags: { repo: "evaris-eval-smoke" },
  });

  try {
    const upload = await api(
      apiUrl,
      token,
      "POST",
      `/v1/runs/${run.run_id}/artifacts/upload-url`,
      {
        type: "inspect_eval_log",
        file_name: basename(fileName),
        content_type: contentType,
        size_bytes: stats.size,
        checksum_sha256: checksum,
      },
    );

    const putResponse = await fetch(
      `${apiUrl.replace(/\/$/, "")}/v1/runs/${run.run_id}/artifact-uploads/${upload.artifact_id}`,
      {
        method: "PUT",
        // The upload target's headers (e.g. content-type) accompany the bytes.
        headers: { Authorization: `Bearer ${token}`, ...upload.headers },
        body: bytes,
      },
    );
    if (!putResponse.ok) {
      const text = await putResponse.text().catch(() => "");
      throw new Error(`Artifact upload failed: ${putResponse.status} ${text.slice(0, 300)}`);
    }

    const artifact = {
      type: "inspect_eval_log",
      uri: upload.uri,
      content_type: contentType,
      size_bytes: stats.size,
      checksum_sha256: checksum,
      created_at: new Date(stats.mtime).toISOString(),
      producer: "evaris-eval-smoke",
    };
    const artifactManifest = {
      schema_version: "2026-06-11",
      run_id: run.run_id,
      artifact,
    };
    const completed = await api(apiUrl, token, "POST", `/v1/runs/${run.run_id}/complete`, {
      schema_version: "2026-06-11",
      run_id: run.run_id,
      project_id: projectId,
      execution_mode: "external",
      producer: { name: "evaris-eval-smoke", version: "1.0.0" },
      source: { name: "inspect_ai", version: await inspectAiVersion() },
      status: "succeeded",
      started_at: startedAt,
      completed_at: new Date().toISOString(),
      artifact_manifest: artifactManifest,
      summary: { artifact_count: 1, artifact_bytes: stats.size },
      checksums: { artifact_manifest_sha256: sha256Hex(JSON.stringify(artifactManifest)) },
    });

    console.log(JSON.stringify(completed, null, 2));

    const timeoutMs = Number(options.timeout) * 1000;
    if (timeoutMs > 0) {
      await waitForIngest(apiUrl, token, run.run_id, timeoutMs);
    }
  } catch (error) {
    // Best-effort cleanup so a failed publish doesn't orphan a 'created' run.
    await api(apiUrl, token, "DELETE", `/v1/runs/${run.run_id}`).catch(() => undefined);
    throw error;
  }
}

async function waitForIngest(apiUrl, token, runId, timeoutMs) {
  const deadline = Date.now() + timeoutMs;
  let status = "unknown";
  while (Date.now() < deadline) {
    const run = await api(apiUrl, token, "GET", `/v1/runs/${runId}`);
    status = run.status;
    if (status !== "created" && status !== "ingesting") {
      console.log(`Ingest finished: ${status}`);
      if (status === "failed") {
        throw new Error(`Run ${runId} failed after ingest.`);
      }
      return;
    }
    await new Promise((resolve) => setTimeout(resolve, 5000));
  }
  console.warn(`WARNING: run ${runId} still '${status}' after ${timeoutMs / 1000}s; not failing the workflow.`);
}

main().catch((error) => {
  console.error(error instanceof Error ? error.message : String(error));
  process.exitCode = 1;
});
