"""
Tests for POST /api/upload and GET /api/upload/{id} (Sprint 3.2/3.3).

See tests/README.md for how this file fits into the overall suite.
"""

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings


class TestUploadAccepts:
    """Valid uploads across all four supported formats, plus content-type leniency."""

    def test_accepts_wav(self, client: TestClient) -> None:
        response = client.post(
            "/api/upload", files={"file": ("speech.wav", b"fake-wav-bytes", "audio/wav")}
        )
        assert response.status_code == 201
        body = response.json()
        assert body["format"] == "wav"
        assert body["status"] == "stored"
        assert body["size_bytes"] == len(b"fake-wav-bytes")

    def test_accepts_mp3(self, client: TestClient) -> None:
        response = client.post(
            "/api/upload", files={"file": ("speech.mp3", b"fake-mp3-bytes", "audio/mpeg")}
        )
        assert response.status_code == 201
        assert response.json()["format"] == "mp3"

    def test_accepts_webm(self, client: TestClient) -> None:
        response = client.post(
            "/api/upload", files={"file": ("speech.webm", b"fake-webm-bytes", "audio/webm")}
        )
        assert response.status_code == 201
        assert response.json()["format"] == "webm"

    def test_accepts_m4a_with_a_browser_quirky_content_type(self, client: TestClient) -> None:
        """
        Different browsers/OSes report .m4a uploads with different
        Content-Type headers (audio/mp4, audio/x-m4a, audio/m4a). This
        uses a non-"canonical" one deliberately, to guard the leniency
        app/audio/validation.py documents.
        """
        response = client.post(
            "/api/upload", files={"file": ("speech.m4a", b"fake-m4a-bytes", "audio/x-m4a")}
        )
        assert response.status_code == 201
        assert response.json()["format"] == "m4a"

    def test_accepts_generic_content_type_by_trusting_the_extension(self, client: TestClient) -> None:
        """
        Some OS file pickers report application/octet-stream for
        anything. The extension alone should still be trusted when the
        content-type is this generic/uninformative.
        """
        response = client.post(
            "/api/upload",
            files={"file": ("speech.wav", b"fake-wav-bytes", "application/octet-stream")},
        )
        assert response.status_code == 201


class TestUploadValidation:
    """Rejections — the checks in app/audio/validation.py and streaming.py."""

    def test_rejects_unsupported_extension(self, client: TestClient) -> None:
        response = client.post(
            "/api/upload",
            files={"file": ("malware.exe", b"not audio", "application/octet-stream")},
        )
        assert response.status_code == 400
        assert response.json()["detail"]["error"] == "unsupported_format"

    def test_rejects_content_type_that_contradicts_the_extension(self, client: TestClient) -> None:
        """A .wav file explicitly claiming a different, non-generic audio content-type should be rejected, not silently trusted."""
        response = client.post(
            "/api/upload", files={"file": ("speech.wav", b"fake bytes", "audio/webm")}
        )
        assert response.status_code == 400
        assert response.json()["detail"]["error"] == "unsupported_format"

    def test_rejects_empty_file(self, client: TestClient) -> None:
        response = client.post("/api/upload", files={"file": ("speech.wav", b"", "audio/wav")})
        assert response.status_code == 400
        assert response.json()["detail"]["error"] == "empty_file"

    def test_rejects_oversized_file(self, client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
        """
        Uses a 1 MB configured ceiling rather than the real 25 MB
        default, so this test doesn't need to allocate and upload a
        25+ MB payload just to prove the limit is enforced.
        """
        monkeypatch.setenv("MAX_UPLOAD_SIZE_MB", "1")
        get_settings.cache_clear()

        oversized = b"a" * (2 * 1024 * 1024)  # 2 MB, over the 1 MB test limit
        response = client.post(
            "/api/upload", files={"file": ("speech.wav", oversized, "audio/wav")}
        )
        assert response.status_code == 413
        assert response.json()["detail"]["error"] == "file_too_large"


class TestGetUpload:
    def test_returns_previously_uploaded_metadata(
        self, client: TestClient, uploaded_asset_id: str
    ) -> None:
        response = client.get(f"/api/upload/{uploaded_asset_id}")
        assert response.status_code == 200
        assert response.json()["id"] == uploaded_asset_id

    def test_returns_404_for_unknown_id(self, client: TestClient) -> None:
        response = client.get("/api/upload/does-not-exist")
        assert response.status_code == 404
        assert response.json()["detail"]["error"] == "not_found"
