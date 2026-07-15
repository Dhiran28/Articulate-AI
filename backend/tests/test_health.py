"""
Tests for /health (liveness) and /health/providers (Milestone 5.1's LLM
provider health surface). No real vendor call happens anywhere here —
/health/providers only ever constructs a provider's client object (never
calls .generate()); see app/api/health.py's own docstring for why a
health endpoint deliberately never makes a live call.
"""

from fastapi.testclient import TestClient


class TestLivenessCheck:
    def test_health_returns_ok(self, client: TestClient) -> None:
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


class TestProviderHealth:
    def test_no_provider_configured_reports_unavailable(self, client: TestClient) -> None:
        response = client.get("/health/providers")
        assert response.status_code == 200
        body = response.json()
        assert body["configured_provider"] is None
        assert body["configured_model"] is None
        assert body["available"] is False
        assert "metric-only" in body["detail"]

    def test_configured_provider_with_credential_reports_available(
        self, client: TestClient, monkeypatch
    ) -> None:
        monkeypatch.setenv("LLM_PROVIDER", "openai")
        monkeypatch.setenv("OPENAI_API_KEY", "sk-fake-key")

        response = client.get("/health/providers")

        assert response.status_code == 200
        body = response.json()
        assert body["configured_provider"] == "openai"
        assert body["configured_model"] == "gpt-4o-mini"
        assert body["available"] is True

    def test_configured_provider_missing_credential_reports_unavailable(
        self, client: TestClient, monkeypatch
    ) -> None:
        monkeypatch.setenv("LLM_PROVIDER", "anthropic")

        response = client.get("/health/providers")

        assert response.status_code == 200
        body = response.json()
        assert body["configured_provider"] == "anthropic"
        assert body["available"] is False
        assert "credential is missing" in body["detail"]

    def test_unrecognized_provider_reports_unavailable_not_a_500(
        self, client: TestClient, monkeypatch
    ) -> None:
        monkeypatch.setenv("LLM_PROVIDER", "not-a-real-vendor")

        response = client.get("/health/providers")

        assert response.status_code == 200
        body = response.json()
        assert body["available"] is False
        assert "not-a-real-vendor" in body["detail"]

    def test_ollama_configured_needs_no_credential(self, client: TestClient, monkeypatch) -> None:
        monkeypatch.setenv("LLM_PROVIDER", "ollama")

        response = client.get("/health/providers")

        assert response.status_code == 200
        body = response.json()
        assert body["configured_provider"] == "ollama"
        assert body["available"] is True

    def test_explicit_model_is_reflected_when_available(self, client: TestClient, monkeypatch) -> None:
        monkeypatch.setenv("LLM_PROVIDER", "openai")
        monkeypatch.setenv("OPENAI_API_KEY", "sk-fake-key")
        monkeypatch.setenv("LLM_MODEL", "gpt-5")

        response = client.get("/health/providers")

        assert response.json()["configured_model"] == "gpt-5"
