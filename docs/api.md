# API Documentation

The backend is a FastAPI service. Interactive, always-current docs are
served by FastAPI itself at `http://localhost:8000/docs` (Swagger UI)
and `http://localhost:8000/redoc` whenever the server is running — this
file is a narrative companion, not a replacement for those.

Base URL (local development): `http://localhost:8000`

## Endpoints at a glance

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Liveness check. |
| `GET` | `/health/providers` | LLM provider configuration/health (Milestone 5.1). |
| `POST` | `/api/upload` | Upload an audio file. |
| `GET` | `/api/upload/{asset_id}` | Fetch a previously uploaded asset's metadata. |
| `POST` | `/api/upload/{asset_id}/transcribe` | Transcribe a previously uploaded asset. |
| `POST` | `/api/analyze` | The single public analysis API — audio in, full report out. |

---

## `GET /health`

Liveness check. No dependencies on storage or the LLM layer — used by
load balancers / container orchestration to confirm the process is up.

```
curl http://localhost:8000/health
```

```json
{ "status": "ok" }
```

## `GET /health/providers`

Reports which LLM provider this deployment is configured for and
whether it's usable — without making a live call to any vendor (see
`app/api/health.py`'s own docstring for why).

```
curl http://localhost:8000/health/providers
```

Not configured:

```json
{
  "configured_provider": null,
  "configured_model": null,
  "available": false,
  "detail": "No LLM_PROVIDER is configured. Running in metric-only mode: Reasoning modules and the Coaching Engine will return NO_PROVIDER_CONFIGURED."
}
```

Configured and usable:

```json
{
  "configured_provider": "openai",
  "configured_model": "gpt-4o-mini",
  "available": true,
  "detail": "openai provider adapter v1.0.0 is configured."
}
```

## `POST /api/upload`

Uploads one audio file (`multipart/form-data`, field name `file`).
Accepted formats: `.wav`, `.mp3`, `.webm`, `.m4a`, `.ogg` (content-type
is cross-checked against the extension). Max size: `MAX_UPLOAD_SIZE_MB`
(default 25 MB).

```
curl -F "file=@speech.wav" http://localhost:8000/api/upload
```

```json
{ "id": "635c56bf-d825-452c-a998-6c8ee98173c4", "filename": "speech.wav", "content_type": "audio/wav", "size_bytes": 481324 }
```

Errors: `400 unsupported_format`, `400 empty_file`, `413 file_too_large`.

## `GET /api/upload/{asset_id}`

Fetches a previously uploaded asset's metadata. `404 asset_not_found` if
the id is unknown.

## `POST /api/upload/{asset_id}/transcribe`

Transcribes a previously uploaded asset via the configured
`TranscriptionProvider` (OpenAI Whisper today). Returns the raw
transcription plus the processed transcript and its metadata.

Errors: `404 asset_not_found`, `503 provider_misconfigured` (no
`OPENAI_API_KEY`), `502 provider_error`.

## `POST /api/analyze`

The single public analysis API (Milestone 5). Accepts one audio file
directly — a caller doesn't need to call `/api/upload` or `/transcribe`
first — and runs the complete pipeline: transcription, the four
deterministic metrics, the shared reasoning pass (one LLM call across
all six reasoning dimensions), the Overall Communication Score,
coaching (one more LLM call), and report assembly. The response's
`transcript` field (Milestone 6) is the verbatim processed transcript
text — see ADR 004 §8 for why this one field was added after the
backend was otherwise frozen.

```
curl -F "file=@speech.wav" http://localhost:8000/api/analyze
```

Response: `201 Created`, a `CommunicationReport` (see below).

```json
{
  "transcript_id": "635c56bf-d825-452c-a998-6c8ee98173c4",
  "generated_at": "2026-07-15T13:13:57.080026Z",
  "executive_summary": "A clearly structured, on-topic session with frequent filler words and mild repetition to work on.",
  "transcript": "So, um, I think the plan is solid and we should move forward with it...",
  "prompt_versions": { "reasoning_pass": "1.0.0", "coaching": "1.0.0" },
  "score": {
    "overall_score": 77.6,
    "band": "strong",
    "module_scores": [
      { "module_name": "structure", "score": 100.0, "nominal_weight": 15.0, "effective_weight": 15.0, "driver": "clear_structure" },
      { "module_name": "filler_words", "score": 69.7, "nominal_weight": 6.25, "effective_weight": 6.25, "driver": "3.03 filler words per 100 words spoken" }
    ],
    "unscored_modules": []
  },
  "analysis": { "transcript_id": "...", "generated_at": "...", "modules": { "...": "see app/analysis/README.md for the full ModuleResult shape" } },
  "coaching": {
    "transcript_id": "...",
    "generated_at": "...",
    "strengths": [{ "message": "Clear structure throughout.", "based_on_module": "structure" }],
    "weaknesses": [{ "message": "Frequent filler words.", "based_on_module": "filler_words" }],
    "recommendations": [{ "message": "Pause instead of saying 'um'.", "based_on_module": "filler_words", "priority": 1 }],
    "suggested_exercises": [{ "title": "Record and review", "description": "...", "based_on_module": "filler_words" }],
    "next_practice_focus": "Reduce filler word usage.",
    "executive_summary": "A clearly structured, on-topic session with frequent filler words and mild repetition to work on.",
    "unavailable": []
  }
}
```

Note: `executive_summary` appears twice in this response, for two different
reasons — the top-level `executive_summary` is the dashboard-formatted
version (`CommunicationSummaryGenerator`), while `coaching.executive_summary`
is the raw text the coaching LLM call produced before that formatting step.
The frontend only renders the top-level one; `coaching.executive_summary` is
kept for traceability/debugging.

### Error responses

Every error across every route (including `/analyze`) uses the same
shape:

```json
{ "detail": { "error": "<machine_readable_reason>", "message": "<human-readable text>" } }
```

`/analyze`'s reason → status mapping:

| HTTP status | `error` | Stage | Meaning |
|---|---|---|---|
| 400 | `unsupported_format` / `empty_file` | Audio | Bad upload. |
| 413 | `file_too_large` | Audio | Over `MAX_UPLOAD_SIZE_MB`. |
| 404 | `asset_not_found` | Transcription | (Not reachable via `/analyze` itself — its own upload always succeeds first.) |
| 503 | `provider_misconfigured` | Transcription | No `OPENAI_API_KEY`. |
| 502 | `provider_error` | Transcription | Whisper call failed. |
| 422 | `transcript_empty` | Analysis | Fewer than 3 words transcribed. |
| 500 | `no_scorable_modules` | Scoring | Every module failed (should not happen in practice — Metric modules have no LLM dependency). |
| 500 | `no_scorer_for_module` | Scoring | A module is weighted but has no matching scoring function — a deployment/config bug, not a runtime condition. |
| 422 | `nothing_to_coach` | Coaching | Every analysis module failed. |
| 503 | `no_provider_configured` | Coaching | No `LLM_PROVIDER` configured, or its credential is missing. |
| 502 | `llm_provider_error` / `llm_invalid_response` / `llm_schema_error` | Coaching | The LLM call failed or returned something unusable. |
| 504 | `llm_timeout` | Coaching | The LLM call exceeded `LLM_TIMEOUT_SECONDS`. |
| 500 | `prompt_not_found` | Coaching | Misconfigured prompt registry — a deployment bug, not a runtime condition. |
| 500 | `internal_error` | Any | RC1 safety net (`app/main.py`'s generic exception handler): any exception not already covered by one of the specific reasons above. The response body still uses the same `{"error", "message"}` shape; the real exception is logged server-side, never included in the response. |

See `docs/decisions/003-communication-intelligence-engine-architecture.md`
and `docs/decisions/004-user-ready-backend-v1.md` for the full design
behind these shapes.
