# Configuration Guide

The backend reads all configuration from environment variables (or a
local `.env` file — see `backend/.env.example`), through one typed
`Settings` object (`app/core/config.py`). Nothing described below is
hardcoded anywhere in the application; every value has a documented
default and can be overridden per deployment.

Copy the example file to get started:

```bash
cd backend
cp .env.example .env
```

## General

| Variable | Default | Meaning |
|---|---|---|
| `ENVIRONMENT` | `development` | Free-text label, not currently branched on anywhere. |
| `CORS_ORIGINS` | `http://localhost:3000` | Comma-separated list of origins allowed to call this API from a browser. |
| `UPLOAD_TEMP_DIR` | `tmp/audio` | Where uploaded audio is written. Temporary storage — see `docs/architecture.md`'s Storage Layer notes. |
| `MAX_UPLOAD_SIZE_MB` | `25` | Upload ceiling, matching the OpenAI Whisper API's own limit. |

## Transcription (Whisper)

| Variable | Default | Meaning |
|---|---|---|
| `OPENAI_API_KEY` | *(unset)* | Required for `/api/upload/{id}/transcribe` and `/api/analyze` to transcribe audio. Without it, both return `503 provider_misconfigured`. |
| `WHISPER_MODEL` | `whisper-1` | Which OpenAI Whisper model to call. |

## LLM provider (Milestone 5.1)

Reasoning (the six `ReasoningResult` dimensions) and coaching both
require an LLM provider. Leaving `LLM_PROVIDER` unset is a fully
supported, zero-config state: `/api/analyze` still works, returning the
four deterministic metrics and their score contribution; reasoning
modules and the Coaching Engine return the specific, documented
`NO_PROVIDER_CONFIGURED` error/status instead of crashing.

| Variable | Default | Meaning |
|---|---|---|
| `LLM_PROVIDER` | *(empty)* | One of `openai`, `anthropic`, `gemini`, `ollama`, or empty for metric-only mode. An unrecognized value fails loudly at startup (first use) — see `app/llm/providers/factory.py`. |
| `LLM_MODEL` | *(empty → provider default)* | Which model to call. Defaults per provider if left blank: `gpt-4o-mini` (openai), `claude-sonnet-5` (anthropic), `gemini-2.0-flash` (gemini), `llama3.1` (ollama). |
| `LLM_TEMPERATURE` | `0.3` | Sampling temperature, applied uniformly regardless of which provider is selected. |
| `LLM_TIMEOUT_SECONDS` | `30` | Hard per-call timeout (`TimeoutPolicy`), enforced above the provider layer — a hung vendor call can never block a request forever. |
| `LLM_MAX_RETRIES` | `3` | Bounded retry count (`RetryPolicy`) for transient provider failures. `1` disables retries. Timeouts and schema/parsing failures are never retried (see `app/llm/reasoner.py`). |

### Per-vendor credentials

There is no single shared `API_KEYS` value — OpenAI, Anthropic, and
Gemini each require a distinct secret, and Ollama typically requires
none. One field per vendor instead:

| Variable | Used by | Notes |
|---|---|---|
| `OPENAI_API_KEY` | `LLM_PROVIDER=openai` (and Whisper transcription, see above) | Shared with transcription — one OpenAI key covers both uses. |
| `ANTHROPIC_API_KEY` | `LLM_PROVIDER=anthropic` | |
| `GOOGLE_API_KEY` | `LLM_PROVIDER=gemini` | Gemini Developer API key (not a Vertex AI service account). |
| `OLLAMA_BASE_URL` | `LLM_PROVIDER=ollama` | Default `http://localhost:11434`. No API key — point this at a reachable Ollama server (local or self-hosted) instead. |

If `LLM_PROVIDER` is set to a vendor whose credential is missing, the
server logs a warning and behaves exactly like `LLM_PROVIDER` was left
unset (metric-only mode) — this is a deliberate, graceful degradation,
not a startup failure. Check `GET /health/providers` to confirm what a
running deployment is actually configured with.

## Example `.env` files

**Metric-only (no LLM, e.g. local frontend development):**

```env
OPENAI_API_KEY=sk-...        # only needed for transcription
```

**OpenAI for both transcription and reasoning/coaching:**

```env
OPENAI_API_KEY=sk-...
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o-mini
```

**Anthropic for reasoning/coaching, OpenAI for transcription only:**

```env
OPENAI_API_KEY=sk-...
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...
LLM_MODEL=claude-sonnet-5
```

**Local Ollama, no cloud LLM dependency at all:**

```env
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
LLM_MODEL=llama3.1
# transcription still needs OPENAI_API_KEY today — see docs/deployment.md
```

## Where each value is used

- `app/core/config.py` — the single `Settings` object; every field
  above corresponds one-to-one to an attribute there.
- `app/llm/providers/factory.py` — `build_provider(settings)` selects
  and constructs the adapter `LLM_PROVIDER` names.
- `app/core/dependencies.py` — `get_llm_provider()`,
  `get_retry_policy()`, `get_timeout_policy()` wire `Settings` into the
  running application via FastAPI dependency injection.
