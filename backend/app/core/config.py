from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Centralized application configuration.

    Values are read from environment variables (or a local .env file, see
    .env.example). Keeping config in one typed object — rather than reading
    os.environ ad hoc throughout the codebase — means every setting is
    validated once at startup and is easy to find, test, and override.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Articulate AI API"
    environment: str = "development"

    # Comma-separated list of allowed frontend origins for CORS.
    # Defaults to the local Next.js dev server.
    cors_origins: str = "http://localhost:3000"

    # Where uploaded audio is written. Relative paths resolve from the
    # working directory the server was started in (backend/, per the
    # README's run instructions). See app/storage/blob_store.py — this is
    # explicitly temporary storage, not a durable/production location.
    upload_temp_dir: str = "tmp/audio"

    # 25 MB isn't arbitrary: it matches the OpenAI Whisper API's own
    # upload ceiling. Nothing in this sprint calls Whisper, but picking a
    # limit already compatible with the most likely next-sprint provider
    # avoids accepting an upload now that would just fail transcription
    # later anyway.
    max_upload_size_mb: int = 25

    # OpenAI Whisper API credentials/model. `None` by default rather than
    # an empty string, so OpenAIWhisperProvider can distinguish
    # "not configured" from "configured with an empty key" and fail with
    # a clear, specific error instead of a confusing auth failure from
    # the provider itself.
    openai_api_key: str | None = None
    whisper_model: str = "whisper-1"

    # -------------------------------------------------------------------
    # Milestone 5.1 — LLM provider selection and behavior. Every value
    # below is read from the environment (or .env); nothing about which
    # vendor is called, which model, or how long a call is allowed to run
    # is hardcoded anywhere in app/llm/providers/.
    #
    # `llm_provider` empty (the default) means exactly what
    # get_llm_provider() has meant since Sprint 4.4: no LLM configured,
    # the whole application degrades gracefully to metric-only analysis.
    # Setting it to an unrecognized name is treated as a configuration
    # mistake and fails loudly at provider-construction time (see
    # app/llm/providers/factory.py) rather than silently degrading —
    # different from "no provider selected," which is a normal, expected
    # deployment state this app has supported since day one.
    llm_provider: str = ""
    llm_model: str = ""

    # A single "API_KEYS" setting can't actually work once more than one
    # vendor is involved — OpenAI, Anthropic, and Gemini each require a
    # distinct secret, and Ollama typically requires none at all. Rather
    # than inventing a packed multi-key string a caller has to parse,
    # this keeps one clearly-named field per vendor (the same shape
    # `openai_api_key` above already established for Whisper) and adds
    # `llm_api_key_for()` below as the single lookup surface a provider
    # factory calls — the practical equivalent of "API_KEYS" from the
    # spec, disclosed here rather than silently reinterpreted.
    anthropic_api_key: str | None = None
    google_api_key: str | None = None
    ollama_base_url: str = "http://localhost:11434"

    # Applies uniformly to whichever provider is selected — one dial, not
    # four, since ADR 003/004's LLMReasoner already treats every vendor
    # identically above this layer.
    llm_temperature: float = 0.3
    llm_timeout_seconds: float = 30.0
    llm_max_retries: int = 3

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",")]

    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024

    def llm_api_key_for(self, provider: str) -> str | None:
        """
        The one place that maps a provider name to its credential. Ollama
        returns `None` deliberately — a local/self-hosted Ollama server
        normally has no API key at all; `ollama_base_url` is what actually
        varies per deployment for that provider.
        """
        return {
            "openai": self.openai_api_key,
            "anthropic": self.anthropic_api_key,
            "gemini": self.google_api_key,
            "ollama": None,
        }.get(provider)


@lru_cache
def get_settings() -> Settings:
    """
    Cached settings accessor.

    FastAPI's dependency-injection system calls this on every request that
    depends on it; lru_cache ensures the .env file is only parsed once per
    process instead of on every request.
    """
    return Settings()
