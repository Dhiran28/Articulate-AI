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

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",")]

    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    """
    Cached settings accessor.

    FastAPI's dependency-injection system calls this on every request that
    depends on it; lru_cache ensures the .env file is only parsed once per
    process instead of on every request.
    """
    return Settings()
