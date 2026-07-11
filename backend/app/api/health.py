from fastapi import APIRouter

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
