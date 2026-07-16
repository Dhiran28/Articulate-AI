"""
RC1 hardening: app/main.py registers a process-wide `Exception` handler as
the last line of defense for any failure that isn't already converted into
a clean HTTPException by one of a route's own specific `except` clauses
(see e.g. app/api/analyze.py's several `_*_REASON_TO_STATUS` maps). An RC1
audit found a few theoretical gaps where an enum/dict-lookup drift could
raise a plain, un-classified exception instead of the domain error a route
expects to catch — which, before this handler existed, would have reached
the client as an unstructured 500 with a raw stack trace.

This test doesn't reproduce one of those specific gaps (two of the
concrete ones found are covered by their own regression tests — see
test_scoring.py's test_a_module_with_no_registered_scorer_raises_a_clean_scoring_error).
Instead it verifies the safety net itself, directly: any dependency that
raises a plain, unclassified exception mid-request still gets the same
clean `{"error", "message"}` JSON shape every other error response uses,
never a raw traceback. `get_audio_service` is overridden here purely as a
convenient, early seam to inject that failure — this isn't a claim that
AudioService itself is unreliable in production.
"""

from fastapi.testclient import TestClient

from app.core.dependencies import get_audio_service
from app.main import app


class _ExplodingAudioService:
    async def ingest(self, raw_upload):
        raise RuntimeError("simulated unexpected failure, unrelated to any real AudioValidationError")


class TestUnhandledExceptionSafetyNet:
    def test_an_unclassified_exception_still_returns_a_clean_500_not_a_raw_traceback(self) -> None:
        app.dependency_overrides[get_audio_service] = lambda: _ExplodingAudioService()
        # raise_server_exceptions=False: TestClient's default behavior is
        # to re-raise any server-side exception so a test author notices
        # unintentional 500s. Here the 500 *is* the intentional path being
        # tested, so this is disabled specifically for this one test to
        # observe the actual HTTP response the handler produces.
        client = TestClient(app, raise_server_exceptions=False)

        response = client.post(
            "/api/analyze",
            files={"file": ("speech.wav", b"RIFF-fake-audio-bytes" * 20, "audio/wav")},
        )

        assert response.status_code == 500
        body = response.json()
        assert body == {
            "error": "internal_error",
            "message": "An unexpected error occurred while processing this request.",
        }
        # The real exception's message/traceback must never leak to the client.
        assert "RuntimeError" not in response.text
        assert "simulated unexpected failure" not in response.text
