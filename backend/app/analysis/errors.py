from enum import Enum


class AnalysisErrorReason(str, Enum):
    """
    Machine-readable cause of an analysis failure — same reason/message
    pattern as AudioValidationReason (app/audio/errors.py) and
    TranscriptionErrorReason (app/transcription/errors.py).

    Two of these are raised as an `AnalysisError` (a whole-request guard
    that stops the engine before any module runs); the rest are only
    ever set on an individual `ModuleResult` (see analysis/models.py) and
    never raised, because one module's failure must never take down the
    rest of the report (ADR 003 §7).
    """

    # Raised as AnalysisError — stops the whole request before any
    # module runs.
    TRANSCRIPT_EMPTY = "transcript_empty"

    # Set on a ModuleResult by a Metric module that validated its own
    # required input and found it unusable (e.g. duration_seconds is
    # None, breaking a words-per-minute division).
    METRIC_INPUT_INVALID = "metric_input_invalid"

    # Set on a ModuleResult by a reasoning module (or ReasoningPass, once
    # built) that classified an LLM call as having failed outright
    # (timeout, connection error, rate limit).
    LLM_PROVIDER_ERROR = "llm_provider_error"

    # Set on a ModuleResult when an LLM response came back but didn't
    # match the expected structured shape. Never force-parsed or guessed
    # at — see ADR 003 §5/§7.
    LLM_MALFORMED_RESPONSE = "llm_malformed_response"

    # Set on a ModuleResult for a BatchedReasoningModule when no
    # ReasoningPass exists to run it yet. This is Sprint 4.2's honest
    # scaffolding gap (see engine.py) — a distinct, named reason rather
    # than the module silently being skipped or faked.
    REASONING_PASS_UNAVAILABLE = "reasoning_pass_unavailable"

    # Set on a ModuleResult when a module raised an exception the engine
    # had to catch itself, rather than the module classifying and
    # reporting its own failure. A safety net, not a module's own
    # diagnosis — see AnalysisEngine._run_module.
    MODULE_ERROR = "module_error"


class AnalysisError(Exception):
    """
    Raised only for whole-engine guard conditions that mean no module
    should run at all (currently just TRANSCRIPT_EMPTY). Deliberately
    not used for an individual module's failure — that's represented as
    data (a `failed` ModuleResult), not an exception, so one module
    failing can never look like the whole analysis request failing.
    """

    def __init__(self, reason: AnalysisErrorReason, message: str) -> None:
        self.reason = reason
        self.message = message
        super().__init__(message)
