# ADR 004: User-Ready Backend (v1.0) — Coaching, Scoring, Reporting, Public API

**Status:** Implemented (Milestone 5); provider adapters, configuration, health, logging, and prompt versioning added in Milestone 5.1 (see §7).
**Scope:** Everything ADR 003 deferred as "not built this sprint" — the Coaching Engine, an Overall Communication Score, a unified report schema, and one public HTTP endpoint that runs the complete pipeline. Builds entirely on top of ADR 002 (Audio/Transcription) and ADR 003 (Communication Intelligence Engine) without modifying either's existing interfaces.

---

## 0. Where this picks up

Sprint 4.5.1 left the backend at: a working `AnalysisEngine` producing a structured, evidence-backed `AnalysisReport` across ten dimensions, with one shared `ReasoningPass` LLM call, and no concrete `LLMProvider`, no Coaching Engine, no scoring, and no route wiring it all together — every piece existed, none of them were reachable from outside a test file. Milestone 5 closes that gap: one public endpoint, `POST /analyze`, that accepts audio and returns a complete report.

## 1. Overall architecture

Three new engines, one new route, connected in a straight line:

| Component | Input | Output | Job |
|---|---|---|---|
| **Coaching Engine** (`app/coaching/`) | `AnalysisReport` | `CoachingReport` | Turn descriptive analysis into strengths, weaknesses, actionable recommendations, suggested exercises, next practice focus, and a raw executive summary — ADR 003 §1/§2's deferred second engine, now built. |
| **Communication Summary Generator** (`app/coaching/summary.py`) | `CoachingReport` | `str` | Deterministically format the Coaching Engine's raw `executive_summary` for dashboard display (length, whitespace) — no LLM call of its own. |
| **Scoring Engine** (`app/scoring/`) | `AnalysisReport` | `CommunicationScore` | A transparent, documented, weighted 0-100 score with a full per-module breakdown — see §4. |
| **Report Builder** (`app/reporting/`) | the three outputs above + `AnalysisReport` | `CommunicationReport` | Pure assembly, no logic of its own — the single response shape for `POST /analyze`. |
| **`POST /analyze`** (`app/api/analyze.py`) | one audio file | `CommunicationReport` | Orchestrates the full pipeline (§2) through existing services/engines' public interfaces only. |

**Every existing interface is reused unmodified.** `AudioService`, `TranscriptionService`, `TranscriptProcessor`, `AnalysisEngine`, `ModuleRegistry`, `ReasoningPass`, and `LLMReasoner` are called exactly as their own sprints left them — this milestone added zero parameters, zero new required arguments, and zero behavior changes to any of them. The only pre-existing file whose *content* changed is `reasoning_pass_v1.md` (the prompt text now constrains each reasoning dimension's `label` to a fixed three-value vocabulary — see §4), which is prompt content, not code, and doesn't touch `ReasoningPass`, `BatchedReasoningResult`, or any Python interface.

## 2. Data flow

```
Audio file
  │
  ▼
AudioService.ingest()              — validate + store (unchanged, ADR 002)
  │
  ▼
TranscriptionService.transcribe_asset()   — raw transcript (unchanged, ADR 002)
  │
  ▼
TranscriptProcessor.process()      — processed transcript + metadata (unchanged, Sprint 3.5)
  │
  ▼
AnalysisEngine.run()               — Metric phase, then (if configured) ONE
  │                                   ReasoningPass call, then Reasoning phase
  │                                   (unchanged, Sprint 4.2-4.5.1)
  ▼
AnalysisReport
  │
  ├──────────────► ScoringEngine.score()      → CommunicationScore
  │
  ▼
CoachingEngine.generate()          — ONE LLM call over the finished report,
  │                                   never the transcript (new, this milestone)
  ▼
CoachingReport
  │
  ▼
CommunicationSummaryGenerator.generate()   → executive_summary (str, no LLM call)
  │
  ▼
ReportBuilder.build()              — assembles analysis + score + coaching +
  │                                   executive_summary
  ▼
CommunicationReport  →  JSON response
```

Total LLM calls per `/analyze` request: **two** — one `ReasoningPass` call (all six reasoning dimensions, Sprint 4.5.1) and one `CoachingEngine` call. Never six, never more than two, regardless of how many modules are registered — both call sites make exactly one call each, by construction (`ModuleRegistry.execute()` calls `ReasoningPass.run()` at most once; `CoachingEngine.generate()` calls `LLMReasoner.reason()` at most once), and this is asserted directly in `tests/test_analyze_endpoint.py`.

## 3. Per-module failure isolation still holds, end to end

ADR 003 §7's per-module isolation and ADR-003's Sprint-4.5.1 batch-failure tradeoff both propagate unchanged into `/analyze`:

- A Metric module crashing doesn't affect any other module (`MODULE_ERROR`, unchanged).
- A missing/misconfigured LLM provider fails every REASONING module with `NO_PROVIDER_CONFIGURED` — the four Metric modules and their score contribution are unaffected. `AnalysisReport` is never entirely empty just because reasoning couldn't run.
- The Coaching Engine, however, is a **whole-request** failure mode, not a per-module one: there is exactly one LLM call behind it, covering the entire coaching output at once, so a failure there (no provider, LLM timeout, malformed response) fails the `/analyze` request itself with a specific HTTP status (503/504/502/422 — see `app/api/analyze.py`'s reason-to-status maps), rather than a partial `CommunicationReport` with a missing `coaching` field. This is a deliberate, disclosed asymmetry: `AnalysisReport` degrades gracefully because it's a *collection* of independent module results; `CoachingReport` doesn't, because it's one LLM's single, integrated read of the whole picture — there's no meaningful "half a coaching report."

**Consequence, disclosed plainly:** with no `LLMProvider` configured (the honest state of this codebase today — see §6), `POST /analyze` returns HTTP 503 with `{"error": "no_provider_configured"}`, not a 201 with a metrics-only report. This was a deliberate choice over silently returning a report with an empty or null `coaching` field: `CommunicationReport.coaching` is a required field, not optional, because a caller (a future frontend) should never have to guess whether a missing coaching section means "nothing to report" versus "the server forgot to include it." A future sprint that wants a genuinely metrics-only response mode would need to make `coaching` explicitly optional in `CommunicationReport` and thread that choice through the route — not built here, and not assumed.

## 4. The Overall Communication Score — the transparent, documented algorithm

Full detail lives in `app/scoring/weights.py` and `app/scoring/dimension_scores.py`'s own docstrings (the actual, checkable source of truth); this section is the summary.

**The core problem:** six of the ten evaluation dimensions are semantic judgments from an LLM (`ReasoningResult.label`), which ADR 003 deliberately gives no numeric score field at all — "no scores" was a structural requirement of the CIE's descriptive-only output contract, not a style preference, and this milestone does not reopen that decision. So a numeric Overall Communication Score has to come from *outside* the CIE, interpreting its output rather than extending it.

**The resolution:** `reasoning_pass_v1.md` was updated (prompt content only) to constrain each of the six reasoning dimensions to pick from a fixed, three-value label vocabulary per dimension (e.g. confidence: `confident` / `somewhat_hesitant` / `uncertain`), always ordered strongest to weakest. `app/scoring/` then maps every dimension — reasoning and metric alike — onto a bounded 0-100 sub-score:

- **The four Metric modules** get a documented formula each (filler-word rate against a ceiling, ratio of long-to-total pauses, repetition count against a ceiling, and a symmetric falloff around a "comfortable" 120-160 wpm pace band). Every ceiling/band is a plain, round, disclosed heuristic — not fit to a dataset, because none exists yet for this product.
- **The six Reasoning modules** map their three-value label onto the same three anchor scores every dimension shares: 100 / 60 / 20. An unrecognized label (the model deviating from the prompt's constraint) falls back to the neutral 60, disclosed as a soft interpretation, not the "never silently repair" discipline `app/llm` applies to hard JSON/schema failures.

**The weighting is not arbitrary — it's anchored to the product's own stated mission** ("an AI-powered communication coach focused on structural thinking, not grammar"): the three dimensions that most directly *are* "structural thinking" (structure, logical_flow, clarity) get the highest weight (15.0 each); the three other semantic dimensions get a middle weight (10.0 each); the four deterministic fluency/delivery metrics — explicitly the "grammar" the mission says this product is *not* about — get the lowest weight (6.25 each). All ten sum to exactly 100.0, checked by an assertion at import time.

**A module that failed or never ran is excluded, not zeroed** — its documented weight is redistributed proportionally among whatever did succeed, so a missing LLM provider (every REASONING module failing) still produces a meaningful score from the four Metric modules alone, rather than an artificially crushed one.

**Full transparency:** `CommunicationScore.module_scores` exposes every module's raw sub-score, its nominal (documented) weight, its effective (post-renormalization) weight, and a human-readable `driver` string explaining what produced the sub-score — a caller can audit the entire computation from the API response alone, never just trust the final number.

## 5. What this milestone explicitly discloses as not solved

- **No concrete `LLMProvider` exists.** *(Resolved by Milestone 5.1 — see §7 below. Left here, struck through in spirit rather than deleted, so this document's own history stays honest about what was true at the end of Milestone 5.)* `get_llm_provider()` (app/core/dependencies.py) returned `None` unconditionally — the same disclosed gap every LLM-related sprint since 4.4 had named rather than silently worked around. `/analyze` fully worked for the four Metric modules and their score contribution with zero LLM dependency; the reasoning dimensions and the Coaching Engine degraded to specific, documented errors.
- **The scoring weights and per-metric thresholds are disclosed heuristics, not empirically validated ones.** See §4 and `app/scoring/weights.py`'s own docstring for the full, honest accounting of where "not arbitrary" stops meaning "derived from data" (no labeled dataset exists) and starts meaning "derived from a stated, checkable reason."
- **No authentication in front of `/analyze`.** Named in ADR 003 §7 as an open gap for both LLM-calling engines; still open here. `/analyze` is reachable by anyone who can reach this server, exactly like `/api/upload` and `/api/upload/{id}/transcribe` already are.
- **No persistence of `CommunicationReport`.** The response is returned and not stored anywhere server-side — ADR 002's "Storage Layer" stance on leaving durable persistence open is unchanged by this milestone.
- **The Coaching Engine's whole-request failure mode** (§3) means there is currently no way to get a partial report (analysis + score, no coaching) via this one endpoint if coaching fails. Disclosed as a real product-shape decision, not an oversight — see §3's last paragraph for what a future sprint would need to change to support it.

## 6. Testing

`tests/test_scoring.py`, `test_coaching.py`, `test_reporting.py` — unit-level, no HTTP layer, no real LLM (fakes satisfying `LLMReasoner`/`LLMProvider`, the same pattern used throughout this codebase since Sprint 4.4). `tests/test_analyze_endpoint.py` — full end-to-end, through `TestClient`, with both `get_transcription_provider` and `get_llm_provider` substituted via `app.dependency_overrides` (the same seam `test_transcription.py`'s `TestTranscribeEndpoint` already established), covering: the complete undegraded pipeline, the exactly-two-LLM-calls assertion, the no-LLM-provider degraded path (503), and every upstream error propagating through with the correct HTTP status (audio validation, transcription failure, near-empty transcript).

## 7. Implementation note (Milestone 5.1) — production backend finalization

Milestone 5.1 closes every remaining gap §5 disclosed except the deliberately-still-open ones (no auth, no persistence, heuristic weights) — those are unchanged and remain open by choice, not oversight.

**Real provider adapters.** Four `LLMProvider` implementations now exist in the new `app/llm/providers/` subpackage — OpenAI (Chat Completions), Anthropic (Messages API), Google Gemini (`google-genai`), and Ollama (plain HTTP against a local/self-hosted server, no extra SDK dependency). None of them required a change to `LLMProvider`, `LLMReasoner`, or any file under `app/llm/` above the new `providers/` subdirectory — exactly what ADR 003 §3 and this package's own README always said adding a real provider would look like. See `app/llm/README.md`'s "Provider adapters and selection" section for the full picture.

**Configuration, not code, selects a provider.** `app/core/config.py`'s `Settings` gained `llm_provider`, `llm_model`, `anthropic_api_key`, `google_api_key`, `ollama_base_url`, `llm_temperature`, `llm_timeout_seconds`, and `llm_max_retries` — every one environment-driven, none hardcoded. `app/llm/providers/factory.py`'s `build_provider(settings)` is the single function that turns that configuration into a real adapter (or `None`, or a loud `UnknownProviderError` for a typo'd provider name — see that module's own docstring for the three-way distinction). `app/core/dependencies.py`'s `get_llm_provider()` calls it; nothing else in the DI chain built in Milestone 5 changed (`get_llm_reasoner()`, `get_reasoning_pass()`, `get_module_registry()`, `get_coaching_engine()` all still take an `LLMProvider | None`/`LLMReasoner | None` exactly as before).

**The degraded, no-LLM path this milestone documented in §3/§5 is unchanged in shape, only in how it's reached.** Leaving `LLM_PROVIDER` unset is still the zero-config default (identical to Milestone 5's own default behavior); the *new* degraded case is `LLM_PROVIDER` set to a real vendor with its credential missing, which also resolves to `get_llm_provider() -> None` — logged as a warning, not a crash. `/analyze`'s HTTP contract (503 `no_provider_configured` from the Coaching Engine when no provider is available) is identical in both cases.

**`RetryPolicy`/`TimeoutPolicy` are now configuration-driven too.** `DefaultLLMReasoner` (app/llm/reasoner.py) always accepted them as constructor overrides; Milestone 5.1 adds `get_retry_policy()`/`get_timeout_policy()` (`app/core/dependencies.py`, both `@lru_cache`d) that build them from `Settings.llm_max_retries`/`llm_timeout_seconds` instead of `DefaultLLMReasoner`'s own hardcoded defaults (`max_attempts=3`, `timeout_seconds=30.0`) — the `MAX_RETRIES`/`TIMEOUT` configuration this milestone asked for applies uniformly no matter which of the four providers is selected, since both policies live above the provider layer, not inside any adapter.

**`GET /health/providers`** (`app/api/health.py`) reports which provider is configured, which model, and whether it's actually usable (`available: bool`) — without ever making a live vendor call. Deliberately static/config-based: a liveness/readiness endpoint polled every few seconds by a load balancer shouldn't itself generate billed LLM traffic or add vendor round-trip latency to every poll. `POST /analyze` remains the real, end-to-end proof that a provider works.

**Logging.** `DefaultLLMReasoner.reason()` (the one seam both `ReasoningPass` and `CoachingEngine` call through) now logs one line per call — session id, provider, model, prompt id, prompt version, latency, token usage (when the vendor's response includes it), and, on failure, the classified `LLMErrorReason` — rather than duplicating a log statement in each caller. Session id correlation is opt-in and non-breaking: `context.get("session_id")` is read only if present (both `ReasoningPass` and `CoachingEngine` now supply it — the transcript/asset id in both cases — via the same "extra key in the template context dict" mechanism, never a new required parameter). Token usage is captured via a diagnostic, non-Protocol `last_usage` attribute each adapter sets after a successful call and `DefaultLLMReasoner` reads immediately afterward — safe even for a cached, shared provider instance, since nothing else runs on the event loop between that call returning and the log line reading it. `app/api/analyze.py` adds its own request-level start/completion/failure-per-stage log lines on top, at the route boundary.

**Prompt versioning in the final report.** `CommunicationReport` gained a `prompt_versions: PromptVersions` field (`{"reasoning_pass": "1.0.0", "coaching": "1.0.0"}` today) — read directly from `PromptRegistry`'s already-loaded metadata for the two known prompt ids, in the route, not threaded through any engine's return value. `ReportBuilder.build()`'s new `prompt_versions` parameter is optional (defaults to "nothing known"), so it's additive to that method's existing contract, not a breaking change.

**Testing.** `tests/test_llm_providers.py` — each of the four adapters, with only the vendor SDK's one network-calling method monkeypatched (`chat.completions.create`, `messages.create`, `aio.models.generate_content`, `httpx.AsyncClient.post`), plus the factory's selection/validation logic and the new `Settings` fields; no real network call anywhere. `tests/test_health.py` — `/health/providers` across every configuration state (unset, configured+available, configured+missing credential, unrecognized provider, Ollama's no-credential case). `tests/test_llm_reasoner.py` gained a `TestDefaultLLMReasonerLogging` class asserting the consolidated log line's fields via `caplog`. Full suite: 328 passed, up from Milestone 5's 284.

## 8. Implementation note (Milestone 6) — one approved exception: `transcript`

Milestone 6 ("Frontend MVP") is explicitly scoped to build against this backend without modifying its architecture — "backend v1.0 has been approved and frozen." One gap surfaced immediately: the Results page's required "Transcript viewer" has no data to render, because `CommunicationReport` describes *judgments about* a transcript (metrics, reasoning labels/evidence, coaching) but never returns the transcript's own text. There is no workaround on the frontend side — the browser never sees the words spoken until the backend transcribes them, and the backend never returned them back.

Presented as an explicit choice, not a silent decision: build the viewer from reasoning modules' `evidence` excerpts only (fully respecting the freeze), skip the feature for this milestone, or add one new field. **The user chose the third option.** `CommunicationReport.transcript: str` was added — populated in `app/api/analyze.py` from `processed_transcript.processed_transcript.text`, text the route already had in hand for `AnalysisEngine.run()` on the very same line. See `app/reporting/README.md` and `app/reporting/models.py`'s own docstring for the full accounting. Confirmed additive, not a redesign: no existing field, response shape, endpoint path, or engine interface changed; `ReportBuilder.build()` gained one new required parameter, and every pre-existing call site (all of `tests/test_reporting.py`, `tests/test_analyze_endpoint.py`) was updated to supply it. Full suite after this change: 329 passed.
