"""
End-to-end tests for POST /analyze (Milestone 5): the full pipeline —
Audio -> Transcription -> Metric Analysis -> Shared Reasoning Pass ->
Coaching -> Report Builder -> JSON response — driven entirely through
the HTTP layer via FastAPI's TestClient, the same "HTTP-level tests,
substitute a fake provider via dependency_overrides" approach
test_transcription.py's TestTranscribeEndpoint already established.

No real network call anywhere in this file: transcription is faked via
`app.dependency_overrides[get_transcription_provider]` (exactly as
test_transcription.py does), and the LLM is faked via
`app.dependency_overrides[get_llm_provider]` — a plain `LLMProvider`
stand-in returning canned, schema-valid JSON text, never touching
`app.llm`'s own already-tested pipeline internals.

See tests/README.md for how this file fits into the overall suite.
"""

import json

from fastapi.testclient import TestClient

from app.core.dependencies import get_llm_provider, get_transcription_provider
from app.main import app
from app.transcription.errors import TranscriptionError, TranscriptionErrorReason
from app.transcription.models import RawTranscriptionResult, TranscriptSegment

FAKE_TRANSCRIPT_TEXT = (
    "So, um, I think the the plan is solid and we should move forward with it. "
    "We should move forward with the plan. Right. The plan is solid, I think. "
    "Let's move forward."
)

FAKE_TRANSCRIPTION_RESULT = RawTranscriptionResult(
    provider="fake_whisper",
    model="fake-model",
    text=FAKE_TRANSCRIPT_TEXT,
    language="en",
    duration_seconds=25.0,
    segments=[TranscriptSegment(start=0.0, end=25.0, text=FAKE_TRANSCRIPT_TEXT)],
)

_REASONING_PASS_JSON = json.dumps(
    {
        "structure": {"label": "clear_structure", "explanation": "Has a clear point.", "evidence": []},
        "clarity": {"label": "clear", "explanation": "Easy to follow.", "evidence": []},
        "logical_flow": {"label": "coherent_flow", "explanation": "Ideas connect.", "evidence": []},
        "topic_drift": {"label": "on_topic", "explanation": "Stays on topic.", "evidence": []},
        "confidence": {"label": "somewhat_hesitant", "explanation": "Some hedging.", "evidence": []},
        "conciseness": {"label": "somewhat_padded", "explanation": "A bit repetitive.", "evidence": []},
    }
)

_COACHING_JSON = json.dumps(
    {
        "strengths": [{"message": "Clear structure throughout.", "based_on_module": "structure"}],
        "weaknesses": [{"message": "Frequent filler words.", "based_on_module": "filler_words"}],
        "recommendations": [
            {
                "message": "Pause instead of saying 'um'.",
                "based_on_module": "filler_words",
                "priority": 1,
            }
        ],
        "suggested_exercises": [
            {
                "title": "Record and review",
                "description": "Record a two-minute practice and count your filler words.",
                "based_on_module": "filler_words",
            }
        ],
        "next_practice_focus": "Reduce filler word usage.",
        "executive_summary": "A clearly structured session with some filler-word habits to address.",
    }
)


class FakeTranscriptionProvider:
    def __init__(self, result: RawTranscriptionResult | None = None, error: TranscriptionError | None = None) -> None:
        self._result = result
        self._error = error

    async def transcribe(self, audio_path, content_type) -> RawTranscriptionResult:
        if self._error is not None:
            raise self._error
        assert self._result is not None
        return self._result


class FakeLLMProvider:
    """
    Satisfies the LLMProvider Protocol (app/llm/provider.py). Returns
    one canned response per call, in order — the pipeline makes exactly
    two LLM calls per /analyze request (ReasoningPass, then
    CoachingEngine), so `responses` is supplied in that order, the same
    "one response per call, popped in order" convention
    test_llm_reasoner.py's own FakeProvider already uses.
    """

    provider_name = "fake"
    model_name = "fake-model"
    version = "0.0.1-test"

    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self.prompts_received: list[str] = []

    async def generate(self, prompt: str) -> str:
        self.prompts_received.append(prompt)
        return self._responses.pop(0)


def _upload_and_analyze(client: TestClient, filename: str = "speech.wav", content_type: str = "audio/wav"):
    return client.post(
        "/api/analyze",
        files={"file": (filename, b"RIFF-fake-audio-bytes" * 20, content_type)},
    )


class TestAnalyzeFullPipeline:
    """Both a transcription provider and an LLM provider are configured — the complete, undegraded pipeline."""

    def _configure_full_pipeline(self) -> FakeLLMProvider:
        app.dependency_overrides[get_transcription_provider] = lambda: FakeTranscriptionProvider(
            result=FAKE_TRANSCRIPTION_RESULT
        )
        llm_provider = FakeLLMProvider(responses=[_REASONING_PASS_JSON, _COACHING_JSON])
        app.dependency_overrides[get_llm_provider] = lambda: llm_provider
        return llm_provider

    def test_returns_201_with_a_complete_communication_report(self, client: TestClient) -> None:
        self._configure_full_pipeline()

        response = _upload_and_analyze(client)

        assert response.status_code == 201
        body = response.json()
        assert set(body.keys()) >= {
            "transcript_id",
            "generated_at",
            "executive_summary",
            "transcript",
            "score",
            "analysis",
            "coaching",
            "prompt_versions",
        }

    def test_transcript_field_matches_what_was_actually_transcribed(self, client: TestClient) -> None:
        # Milestone 6: the one approved, additive exception to the
        # otherwise-frozen backend — the frontend's Transcript Viewer has
        # no other source for this text.
        self._configure_full_pipeline()

        response = _upload_and_analyze(client)

        assert response.json()["transcript"] == FAKE_TRANSCRIPT_TEXT

    def test_analysis_report_contains_all_ten_modules_ok(self, client: TestClient) -> None:
        self._configure_full_pipeline()

        response = _upload_and_analyze(client)

        modules = response.json()["analysis"]["modules"]
        assert len(modules) == 10
        assert all(m["status"] == "ok" for m in modules.values())

    def test_metric_module_values_reflect_the_real_transcript(self, client: TestClient) -> None:
        self._configure_full_pipeline()

        response = _upload_and_analyze(client)

        filler_words = response.json()["analysis"]["modules"]["filler_words"]
        assert filler_words["metric"]["value"] >= 1  # the fixture transcript contains "um"

    def test_reasoning_modules_carry_the_llm_provided_labels(self, client: TestClient) -> None:
        self._configure_full_pipeline()

        response = _upload_and_analyze(client)

        structure = response.json()["analysis"]["modules"]["structure"]
        assert structure["reasoning"]["label"] == "clear_structure"

    def test_score_is_present_and_bounded(self, client: TestClient) -> None:
        self._configure_full_pipeline()

        response = _upload_and_analyze(client)

        score = response.json()["score"]
        assert 0.0 <= score["overall_score"] <= 100.0
        assert score["band"] in {"excellent", "strong", "developing", "needs_work"}
        assert len(score["module_scores"]) == 10
        assert score["unscored_modules"] == []

    def test_coaching_report_matches_the_fake_llm_content(self, client: TestClient) -> None:
        self._configure_full_pipeline()

        response = _upload_and_analyze(client)

        coaching = response.json()["coaching"]
        assert coaching["next_practice_focus"] == "Reduce filler word usage."
        assert coaching["recommendations"][0]["based_on_module"] == "filler_words"

    def test_executive_summary_is_present_at_the_top_level(self, client: TestClient) -> None:
        self._configure_full_pipeline()

        response = _upload_and_analyze(client)

        assert "filler-word" in response.json()["executive_summary"] or response.json()["executive_summary"]

    def test_reasoning_pass_is_called_exactly_once_regardless_of_six_reasoning_modules(
        self, client: TestClient
    ) -> None:
        llm_provider = self._configure_full_pipeline()

        _upload_and_analyze(client)

        # Exactly 2 total LLM calls for the whole request: one combined
        # ReasoningPass call (not six) plus one CoachingEngine call.
        assert len(llm_provider.prompts_received) == 2


class TestAnalyzeMetricOnlyDegradedPath:
    """Transcription is configured, but no LLM provider is — the disclosed, documented degraded path."""

    def test_no_llm_provider_returns_503_from_coaching(self, client: TestClient) -> None:
        app.dependency_overrides[get_transcription_provider] = lambda: FakeTranscriptionProvider(
            result=FAKE_TRANSCRIPTION_RESULT
        )
        # get_llm_provider is left at its real, unconfigured default (None).

        response = _upload_and_analyze(client)

        assert response.status_code == 503
        assert response.json()["detail"]["error"] == "no_provider_configured"


class TestAnalyzeErrorPropagation:
    def test_unsupported_audio_format_returns_400_before_any_transcription(self, client: TestClient) -> None:
        app.dependency_overrides[get_transcription_provider] = lambda: FakeTranscriptionProvider(
            result=FAKE_TRANSCRIPTION_RESULT
        )

        response = client.post(
            "/api/analyze",
            files={"file": ("malware.exe", b"not audio", "application/octet-stream")},
        )

        assert response.status_code == 400
        assert response.json()["detail"]["error"] == "unsupported_format"

    def test_transcription_provider_error_returns_502(self, client: TestClient) -> None:
        app.dependency_overrides[get_transcription_provider] = lambda: FakeTranscriptionProvider(
            error=TranscriptionError(TranscriptionErrorReason.PROVIDER_ERROR, "boom")
        )

        response = _upload_and_analyze(client)

        assert response.status_code == 502
        assert response.json()["detail"]["error"] == "provider_error"

    def test_transcription_not_configured_returns_503(self, client: TestClient) -> None:
        # Neither provider overridden — the real OpenAIWhisperProvider,
        # genuinely unconfigured (OPENAI_API_KEY cleared by conftest.py).
        response = _upload_and_analyze(client)

        assert response.status_code == 503
        assert response.json()["detail"]["error"] == "provider_misconfigured"

    def test_near_empty_transcript_returns_422(self, client: TestClient) -> None:
        app.dependency_overrides[get_transcription_provider] = lambda: FakeTranscriptionProvider(
            result=RawTranscriptionResult(
                provider="fake",
                model="fake",
                text="hi",
                duration_seconds=1.0,
                segments=[TranscriptSegment(start=0.0, end=1.0, text="hi")],
            )
        )
        llm_provider = FakeLLMProvider(responses=[])
        app.dependency_overrides[get_llm_provider] = lambda: llm_provider

        response = _upload_and_analyze(client)

        assert response.status_code == 422
        assert response.json()["detail"]["error"] == "transcript_empty"
        # The guard fires before any LLM call is ever made.
        assert llm_provider.prompts_received == []
