from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.config import Settings, get_settings
from app.llm.providers.factory import UnknownProviderError, build_provider

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check() -> dict[str, str]:
    """
    Liveness check.

    Returns 200 with a static payload whenever the process is up and able
    to handle requests. Used by local dev, load balancers, and (later)
    container orchestration to know the service is alive. Deliberately has
    no dependency on the database or any external service — a "readiness"
    check that verifies those can be added separately once they exist.
    """
    return {"status": "ok"}


class ProviderHealth(BaseModel):
    """
    What `/health/providers` reports about the LLM layer — enough for an
    operator to tell "reasoning and coaching will work on this deployment"
    apart from "this is intentionally running metric-only" apart from
    "this is misconfigured," without reading server logs.
    """

    configured_provider: str | None
    configured_model: str | None
    available: bool
    detail: str


@router.get("/health/providers", response_model=ProviderHealth)
def provider_health(settings: Settings = Depends(get_settings)) -> ProviderHealth:
    """
    Reports which LLM provider this deployment is configured for and
    whether it's actually usable — `available=True` means a real
    `LLMProvider` was constructed (a client object with credentials
    attached), not that a live call to the vendor succeeded.

    Deliberately makes no network call to any vendor. A health/liveness
    endpoint that's likely to be polled every few seconds by a load
    balancer or container orchestrator shouldn't itself generate billed
    LLM traffic or add several hundred milliseconds of vendor round-trip
    latency to every poll — the same reasoning `/health` above already
    follows for the database/external-service case. `POST /analyze`
    itself is still the real, end-to-end proof that a provider works.

    Calls `build_provider()` directly rather than depending on
    `get_llm_provider()` (app/core/dependencies.py) for two reasons:
    it's `@lru_cache`d (this endpoint should reflect the *current*
    environment, not whatever was cached at the first request that
    happened to need it), and an unrecognized `LLM_PROVIDER` would
    otherwise raise `UnknownProviderError` during FastAPI's dependency
    resolution — a 500 from a health check, exactly the ungraceful
    outcome a health endpoint exists to avoid. Recomputing it here and
    catching that case turns it into a clear, still-200,
    `available: false` payload instead.
    """
    provider_name = settings.llm_provider.strip().lower() or None

    try:
        provider = build_provider(settings)
    except UnknownProviderError as exc:
        return ProviderHealth(
            configured_provider=provider_name,
            configured_model=settings.llm_model or None,
            available=False,
            detail=str(exc),
        )

    if provider is not None:
        return ProviderHealth(
            configured_provider=provider.provider_name,
            configured_model=provider.model_name,
            available=True,
            detail=f"{provider.provider_name} provider adapter v{provider.version} is configured.",
        )

    if provider_name is None:
        return ProviderHealth(
            configured_provider=None,
            configured_model=None,
            available=False,
            detail="No LLM_PROVIDER is configured. Running in metric-only mode: "
            "Reasoning modules and the Coaching Engine will return "
            "NO_PROVIDER_CONFIGURED.",
        )

    return ProviderHealth(
        configured_provider=provider_name,
        configured_model=settings.llm_model or None,
        available=False,
        detail=f"LLM_PROVIDER={provider_name} is set but its credential is missing. "
        "Reasoning modules and the Coaching Engine will return "
        "NO_PROVIDER_CONFIGURED.",
    )
