"""
Shared pytest fixtures for the backend test suite.

See tests/README.md for the full test catalog: what each file covers,
what's mocked vs. real, and how to run everything.
"""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core import dependencies
from app.core.config import get_settings
from app.main import app


@pytest.fixture(autouse=True)
def _isolated_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[None]:
    """
    Runs before and after every single test, automatically.

    Two things it guards against:

    1. Cross-test state leakage. get_blob_store, get_record_store, and
       get_transcription_provider (app/core/dependencies.py) are
       @lru_cache'd singletons *by design* — that's what lets an asset
       uploaded in one request still be found by a later request that
       transcribes it. In a test suite, that same caching would let
       state leak between unrelated tests unless it's reset. This
       fixture points UPLOAD_TEMP_DIR at a fresh pytest tmp_path and
       clears every cache before AND after each test, so each test gets
       its own empty store regardless of what ran before it.

    2. Accidentally calling the real OpenAI API. A developer's real
       .env (needed to actually run the app locally) may have a real
       OPENAI_API_KEY in it. Without explicitly clearing it here, that
       key would leak into test runs — at best making the
       "provider not configured" tests fail for the wrong reason, at
       worst causing a test to make a real, billed API call by
       accident. Tests that need a "configured" provider set the key
       explicitly themselves or substitute a fake provider via
       app.dependency_overrides instead.
    """
    monkeypatch.setenv("UPLOAD_TEMP_DIR", str(tmp_path / "audio"))
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    get_settings.cache_clear()
    dependencies.get_blob_store.cache_clear()
    dependencies.get_record_store.cache_clear()
    dependencies.get_transcription_provider.cache_clear()

    yield

    app.dependency_overrides.clear()
    get_settings.cache_clear()
    dependencies.get_blob_store.cache_clear()
    dependencies.get_record_store.cache_clear()
    dependencies.get_transcription_provider.cache_clear()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def uploaded_asset_id(client: TestClient) -> str:
    """
    A ready-made uploaded asset id, for tests that only care about what
    happens *after* upload (transcription, processing) and don't want to
    repeat the upload boilerplate themselves.
    """
    response = client.post(
        "/api/upload",
        files={"file": ("speech.wav", b"RIFF-fake-audio-bytes" * 20, "audio/wav")},
    )
    assert response.status_code == 201
    return response.json()["id"]
