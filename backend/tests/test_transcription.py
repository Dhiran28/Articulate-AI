"""
Tests for the Transcription Service and OpenAIWhisperProvider (Sprint 3.4).

See tests/README.md for how this file fits into the overall suite.

None of these tests make a real network call to OpenAI: there's no API
key available in this environment (or typically in CI), and even if
there were, a real network call in an automated suite is slow, costs
money, and is flaky in a way a unit test shouldn't be. Instead:

  - OpenAIWhisperProvider's response-parsing logic is tested directly,
    with the OpenAI SDK's own network call monkeypatched out.
  - Route/service orchestration (asset lookup, error-to-status mapping)
    is tested by substituting a fake TranscriptionProvider via FastAPI's
    dependency_overrides — the exact seam Sprint 3.4 built for this.
"""

import httpx
import pytest
from fastapi.testclient import TestClient
from openai import APIConnectionError

from app.core.dependencies import get_transcription_provider
from app.main import app
from app.transcription.errors import TranscriptionError, TranscriptionErrorReason
from app.transcription.models import RawTranscriptionResult, TranscriptSegment
from app.transcription.providers.openai_whisper import OpenAIWhisperProvider


class _FakeSegment:
    def __init__(self, start: float, end: float, text: str) -> None:
        self.start = start
        self.end = end
        self.text = text


class _FakeVerboseResponse:
    def __init__(self, text: str, language: str, duration: float, segments: list) -> None:
        self.text = text
        self.language = language
        self.duration = duration
        self.segments = segments


class FakeProvider:
    """A TranscriptionProvider stand-in for the HTTP-level tests below."""

    def __init__(
        self,
        result: RawTranscriptionResult | None = None,
        error: TranscriptionError | None = None,
    ) -> None:
        self._result = result
        self._error = error

    async def transcribe(self, audio_path, content_type) -> RawTranscriptionResult:
        if self._error is not None:
            raise self._error
        assert self._result is not None
        return self._result


FAKE_RESULT = RawTranscriptionResult(
    provider="fake_whisper",
    model="fake-model",
    text="hello from a fake provider",
    language="en",
    duration_seconds=1.5,
    segments=[TranscriptSegment(start=0.0, end=1.5, text="hello from a fake provider")],
)


class TestOpenAIWhisperProviderResponseParsing:
    """Unit tests directly on OpenAIWhisperProvider — no HTTP layer, no real OpenAI call."""

    @pytest.fixture
    def provider(self) -> OpenAIWhisperProvider:
        return OpenAIWhisperProvider(api_key="sk-test-fake-key", model="whisper-1")

    async def test_maps_a_successful_response_into_raw_transcription_result(
        self, provider: OpenAIWhisperProvider, monkeypatch: pytest.MonkeyPatch, tmp_path
    ) -> None:
        """
        Confirms the mapping from the SDK's TranscriptionVerbose shape
        (response.text/.language/.duration/.segments[].start/.end/.text)
        into our own RawTranscriptionResult — the exact shape verified
        against the installed openai SDK during Sprint 3.4.
        """
        fake_response = _FakeVerboseResponse(
            text="the plan is solid",
            language="en",
            duration=3.2,
            segments=[
                _FakeSegment(0.0, 1.5, "the plan"),
                _FakeSegment(1.5, 3.2, "is solid"),
            ],
        )

        async def fake_create(**kwargs):
            assert kwargs["model"] == "whisper-1"
            assert kwargs["response_format"] == "verbose_json"
            return fake_response

        monkeypatch.setattr(provider._client.audio.transcriptions, "create", fake_create)

        audio_path = tmp_path / "clip.wav"
        audio_path.write_bytes(b"fake audio bytes")

        result = await provider.transcribe(audio_path, "audio/wav")

        assert result.provider == "openai_whisper"
        assert result.model == "whisper-1"
        assert result.text == "the plan is solid"
        assert result.language == "en"
        assert result.duration_seconds == 3.2
        assert [s.text for s in result.segments] == ["the plan", "is solid"]
        assert result.segments[0].start == 0.0
        assert result.segments[1].end == 3.2

    async def test_wraps_an_openai_error_as_provider_error(
        self, provider: OpenAIWhisperProvider, monkeypatch: pytest.MonkeyPatch, tmp_path
    ) -> None:
        async def fake_create(**kwargs):
            raise APIConnectionError(request=httpx.Request("POST", "https://api.openai.com"))

        monkeypatch.setattr(provider._client.audio.transcriptions, "create", fake_create)

        audio_path = tmp_path / "clip.wav"
        audio_path.write_bytes(b"fake audio bytes")

        with pytest.raises(TranscriptionError) as exc_info:
            await provider.transcribe(audio_path, "audio/wav")

        assert exc_info.value.reason == TranscriptionErrorReason.PROVIDER_ERROR
        # The friendly message must not just re-surface the raw SDK error text.
        assert "APIConnectionError" not in exc_info.value.message

    async def test_missing_api_key_fails_fast_without_calling_openai(self, tmp_path) -> None:
        provider = OpenAIWhisperProvider(api_key=None)
        audio_path = tmp_path / "clip.wav"
        audio_path.write_bytes(b"fake audio bytes")

        with pytest.raises(TranscriptionError) as exc_info:
            await provider.transcribe(audio_path, "audio/wav")

        assert exc_info.value.reason == TranscriptionErrorReason.PROVIDER_MISCONFIGURED


class TestTranscribeEndpoint:
    """HTTP-level tests, using dependency_overrides to substitute a fake provider."""

    def test_returns_the_provider_result_wrapped_by_the_processor(
        self, client: TestClient, uploaded_asset_id: str
    ) -> None:
        app.dependency_overrides[get_transcription_provider] = lambda: FakeProvider(
            result=FAKE_RESULT
        )
        response = client.post(f"/api/upload/{uploaded_asset_id}/transcribe")

        assert response.status_code == 200
        body = response.json()
        assert body["raw_transcript"]["text"] == "hello from a fake provider"
        assert body["processed_transcript"]["text"] == "hello from a fake provider"
        assert body["metadata"]["provider"] == "fake_whisper"

    def test_returns_404_for_an_unknown_asset(self, client: TestClient) -> None:
        response = client.post("/api/upload/does-not-exist/transcribe")
        assert response.status_code == 404
        assert response.json()["detail"]["error"] == "asset_not_found"

    def test_returns_503_when_provider_is_not_configured(
        self, client: TestClient, uploaded_asset_id: str
    ) -> None:
        # No dependency override, and OPENAI_API_KEY is cleared by the
        # autouse fixture in conftest.py — the real OpenAIWhisperProvider,
        # genuinely unconfigured.
        response = client.post(f"/api/upload/{uploaded_asset_id}/transcribe")
        assert response.status_code == 503
        assert response.json()["detail"]["error"] == "provider_misconfigured"

    def test_returns_502_when_the_provider_raises_a_provider_error(
        self, client: TestClient, uploaded_asset_id: str
    ) -> None:
        failing_provider = FakeProvider(
            error=TranscriptionError(TranscriptionErrorReason.PROVIDER_ERROR, "boom")
        )
        app.dependency_overrides[get_transcription_provider] = lambda: failing_provider
        response = client.post(f"/api/upload/{uploaded_asset_id}/transcribe")

        assert response.status_code == 502
        assert response.json()["detail"]["error"] == "provider_error"
