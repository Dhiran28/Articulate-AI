"""
CoachingEngine's error vocabulary (Milestone 5) — same reason/message
pattern as every other error hierarchy in this codebase.

NOTHING_TO_COACH is this package's own condition (ADR 003 §7 named it
as the Coaching Engine's required behavior when every CIE module
failed). The five LLM_*/PROMPT_NOT_FOUND/NO_PROVIDER_CONFIGURED values
deliberately share identical string values with LLMErrorReason
(app/llm/errors.py) and AnalysisErrorReason (app/analysis/errors.py) —
the same "translation is a direct, lossless one-line mapping" pattern
used everywhere else an LLMError crosses into a domain-specific error
type (see app/analysis/modules/reasoning_base.py and registry.py).
"""

from enum import Enum


class CoachingErrorReason(str, Enum):
    NOTHING_TO_COACH = "nothing_to_coach"
    LLM_TIMEOUT = "llm_timeout"
    LLM_PROVIDER_ERROR = "llm_provider_error"
    LLM_INVALID_RESPONSE = "llm_invalid_response"
    LLM_SCHEMA_ERROR = "llm_schema_error"
    PROMPT_NOT_FOUND = "prompt_not_found"
    NO_PROVIDER_CONFIGURED = "no_provider_configured"


class CoachingError(Exception):
    """
    Raised for whole-request coaching failures — there is exactly one
    LLM call behind CoachingEngine.generate() (mirroring ReasoningPass's
    own one-call design), so unlike the CIE's per-module isolation,
    there is no smaller unit of coaching output that can fail
    independently. A caller (the /analyze route) maps this to an HTTP
    status the same way TranscriptionError and AudioValidationError
    already are.
    """

    def __init__(self, reason: CoachingErrorReason, message: str) -> None:
        self.reason = reason
        self.message = message
        super().__init__(message)
