import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import analyze, health, transcribe, upload
from app.core.config import get_settings

logger = logging.getLogger(__name__)

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
app.include_router(upload.router)
app.include_router(transcribe.router)
app.include_router(analyze.router)


@app.get("/")
def root() -> dict[str, str]:
    """Minimal root endpoint confirming the API is reachable."""
    return {"message": "Articulate AI API is running"}


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Release Candidate 1 safety net: every route above already converts
    its own anticipated domain errors (AudioValidationError,
    TranscriptionError, AnalysisError, ScoringError, CoachingError) into a
    clean `{"error": ..., "message": ...}` HTTPException — see each
    route's own `_*_REASON_TO_STATUS` map. Those maps are all
    dict-lookups keyed by an enum, though, and an RC1 audit found a few
    theoretical gaps where a future drift between an error-reason enum
    and its status map (or an edge case like a malformed prompt
    template) could raise a plain KeyError/ValueError instead of the
    domain exception a route expects — which, with no handler like this
    one, would otherwise reach the client as an unstructured 500 with a
    raw stack trace.

    This handler is the last line of defense for exactly that case: it
    never fires for a request that's already been turned into a clean
    HTTPException (FastAPI only reaches a generic `Exception` handler
    once nothing more specific has handled it), logs the real exception
    server-side with a traceback for debugging, and returns the same
    `{"error": ..., "message": ...}` shape every other error response
    uses — so a client never has to special-case "this failure didn't
    have a clean reason" from "this one did."
    """
    logger.exception(
        "unhandled_exception path=%s method=%s",
        request.url.path,
        request.method,
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_error",
            "message": "An unexpected error occurred while processing this request.",
        },
    )
