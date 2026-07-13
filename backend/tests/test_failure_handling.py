"""
Cross-cutting failure-handling tests.

See tests/README.md for how this file fits into the overall suite.

These don't re-test individual failure scenarios already covered
elsewhere (e.g. test_upload.py already checks that an empty file returns
400). Instead they test the *shape and consistency* of failure handling
across the whole pipeline: every defined error reason is actually wired
to an HTTP status, and every error response follows the same contract
regardless of which stage produced it.
"""

import pytest
from fastapi.testclient import TestClient

from app.api.transcribe import _REASON_TO_STATUS as TRANSCRIBE_REASON_TO_STATUS
from app.api.upload import _REASON_TO_STATUS as UPLOAD_REASON_TO_STATUS
from app.audio.errors import AudioValidationReason
from app.transcription.errors import TranscriptionErrorReason


def _unsupported_format(client: TestClient):
    return client.post(
        "/api/upload", files={"file": ("bad.exe", b"x", "application/octet-stream")}
    )


def _empty_file(client: TestClient):
    return client.post("/api/upload", files={"file": ("empty.wav", b"", "audio/wav")})


def _upload_not_found(client: TestClient):
    return client.get("/api/upload/does-not-exist")


def _transcribe_not_found(client: TestClient):
    return client.post("/api/upload/does-not-exist/transcribe")


class TestErrorReasonCoverage:
    """
    Regression guard against "added a new error reason but forgot to
    map it to an HTTP status" — an easy mistake to make as this project
    grows more failure modes. If either test below fails, a route's
    _REASON_TO_STATUS dict is missing an entry for a reason its own
    error module defines.
    """

    def test_every_audio_validation_reason_has_a_status_code(self) -> None:
        for reason in AudioValidationReason:
            assert reason in UPLOAD_REASON_TO_STATUS, (
                f"{reason} has no mapped HTTP status in app/api/upload.py"
            )

    def test_every_transcription_error_reason_has_a_status_code(self) -> None:
        for reason in TranscriptionErrorReason:
            assert reason in TRANSCRIBE_REASON_TO_STATUS, (
                f"{reason} has no mapped HTTP status in app/api/transcribe.py"
            )


class TestErrorResponseShape:
    """
    Every failure across the pipeline returns the same
    {"detail": {"error": "<reason>", "message": "<friendly text>"}}
    shape — never a bare string, never a raw exception — so a frontend
    can rely on one consistent contract no matter which stage failed.
    """

    @pytest.mark.parametrize(
        "make_request",
        [_unsupported_format, _empty_file, _upload_not_found, _transcribe_not_found],
        ids=["unsupported_format", "empty_file", "upload_not_found", "transcribe_not_found"],
    )
    def test_error_response_has_consistent_shape(self, client: TestClient, make_request) -> None:
        response = make_request(client)
        assert response.status_code >= 400

        body = response.json()
        assert "detail" in body
        detail = body["detail"]
        assert isinstance(detail, dict)
        assert isinstance(detail.get("error"), str) and detail["error"]
        assert isinstance(detail.get("message"), str) and detail["message"]

    def test_error_messages_never_leak_raw_exception_text(self, client: TestClient) -> None:
        """
        Sanity check for the "never show raw technical text" principle
        this project applies consistently (see e.g. the frontend's
        lib/microphoneError.ts). A real regression here would look like
        an error message containing a Python traceback, an exception
        class name, or a file path.
        """
        response = _unsupported_format(client)
        message = response.json()["detail"]["message"]
        assert "Traceback" not in message
        assert "Error" not in message
        assert ".py" not in message
