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

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",")]


@lru_cache
def get_settings() -> Settings:
    """
    Cached settings accessor.

    FastAPI's dependency-injection system calls this on every request that
    depends on it; lru_cache ensures the .env file is only parsed once per
    process instead of on every request.
    """
    return Settings()
