from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import health
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
)

# Allow the Next.js frontend (running on a different origin in dev) to call
# this API from the browser. Origins are read from config rather than
# hardcoded so production origins can be set via environment variables.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)


@app.get("/")
def root() -> dict[str, str]:
    """Minimal root endpoint confirming the API is reachable."""
    return {"message": "Articulate AI API is running"}
