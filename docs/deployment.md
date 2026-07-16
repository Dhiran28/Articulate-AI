# Deployment Guide

This describes running the backend outside of local development. The
frontend (Next.js) deploys independently and isn't covered here — see
the root `README.md`'s "Running locally" section for its dev setup.

## What this backend is, today

An in-memory, single-process FastAPI service with no database and no
authentication. Every deployment consideration below should be read
against that reality — this is a backend suitable for a demo, an
internal tool, or a staging environment, not yet a multi-tenant
production service. See "Known limitations" at the end of this document
for the full, honest list.

## Running the server

Development (auto-reload):

```bash
cd backend
uvicorn app.main:app --reload
```

Production-style (no reload, explicit worker count):

```bash
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2
```

Each worker is a separate process with its own in-memory state
(uploaded assets, cached settings/providers) — see "State and
concurrency" below before running more than one worker.

## Configuration

Set environment variables directly (the platform's own mechanism —
container env vars, systemd `EnvironmentFile`, etc.) rather than
shipping a `.env` file into a production image. See
[`docs/configuration.md`](configuration.md) for every variable.

Minimum required for a working deployment:

- `OPENAI_API_KEY` — needed for transcription (`/api/upload/.../transcribe`
  and `/api/analyze` both transcribe via OpenAI Whisper today; there is
  no alternative transcription provider yet).
- `CORS_ORIGINS` — set to your real frontend origin(s), not the
  `localhost:3000` default.

Optional, for reasoning and coaching to work (otherwise `/api/analyze`
runs in metric-only mode — see `docs/configuration.md`):

- `LLM_PROVIDER` plus that provider's credential (`OPENAI_API_KEY` /
  `ANTHROPIC_API_KEY` / `GOOGLE_API_KEY` / `OLLAMA_BASE_URL`).

## Health checks

Point your orchestrator's liveness probe at `GET /health` — no
dependencies on storage or the LLM layer, returns `200` whenever the
process can serve requests.

`GET /health/providers` is a separate, informational endpoint (not
intended as a liveness/readiness probe) reporting which LLM provider is
configured and whether it's usable, without making a live vendor call.
Useful for a deploy-time smoke check or a status dashboard, not for
gating traffic — a deployment with no `LLM_PROVIDER` configured is
intentionally still healthy (metric-only mode is a supported state).

## Timeouts and retries

`LLM_TIMEOUT_SECONDS` (default 30) bounds every individual LLM call;
`LLM_MAX_RETRIES` (default 3) bounds retry attempts for transient
provider failures (timeouts and malformed/schema-invalid responses are
never retried — see `app/llm/reasoner.py`). Tune both against your
chosen provider's own typical latency and rate-limit behavior — a
slower model (e.g. a larger Anthropic or Gemini model) may need a
higher `LLM_TIMEOUT_SECONDS` than the default comfortably allows.

`POST /api/analyze` makes exactly two LLM calls per request (one shared
reasoning pass, one coaching call) — see ADR 004 §2. Expect end-to-end
latency roughly proportional to your chosen provider's per-call latency
times two, plus transcription time, plus retry/backoff overhead on any
transient failure.

## Logging

Every LLM call is logged once (INFO on success, ERROR on failure) by
`app/llm/reasoner.py`, including session id, provider, model, prompt
id/version, latency, token usage (when the vendor returns it), and — on
failure — the classified error reason. `app/api/analyze.py` logs
request start/completion and which stage failed, if any. All logging
goes to Python's standard `logging` module at the module level
(`logging.getLogger(__name__)` per file) — configure handlers/formatters
and log level via your process manager or a `logging.config` entry
point; nothing in this codebase configures handlers itself, so a plain
`uvicorn` run logs to stdout with Python's default formatting unless
you set `--log-config` or configure logging in your own entry point.

## Secrets

API keys are read from environment variables only — never committed,
never logged (log lines include model/provider/latency/token counts,
never the raw prompt, raw response, or the key itself). Use your
platform's secret manager to inject them as environment variables at
deploy time (e.g. a Kubernetes `Secret` mounted as env vars, a cloud
provider's secret manager with env injection, or a `.env` file kept out
of version control for a single-VM deployment).

## State and concurrency

`AudioBlobStore` (local temp directory) and `RecordStore` (in-memory
dict) are both process-local. Running more than one worker/replica means
an asset uploaded via one worker is invisible to another — `/api/upload`
then `/api/upload/{id}/transcribe` as two separate requests can fail
with `404 asset_not_found` if a load balancer routes them to different
workers. `POST /api/analyze` avoids this entirely (it's one request,
one worker, start to finish) and is the recommended endpoint for any
deployment running more than a single process. See ADR 002's Storage
Layer section for the shared-storage backend this would need before
horizontal scaling is safe for the two-step upload/transcribe flow.

## Known limitations (disclosed, not oversights)

- No authentication in front of any endpoint, including `/api/analyze`.
- No persistence of `CommunicationReport` — responses aren't stored
  server-side.
- No rate limiting beyond whatever your chosen LLM vendor enforces on
  their end.
- Scoring weights and per-metric thresholds are documented heuristics,
  not empirically validated against real usage data (see
  `app/scoring/weights.py`).
- Single transcription provider (OpenAI Whisper) — no fallback if it's
  unavailable.

See `docs/decisions/003-communication-intelligence-engine-architecture.md`
§7 and `docs/decisions/004-user-ready-backend-v1.md` §5 for the full,
itemized disclosure list these bullets summarize.
