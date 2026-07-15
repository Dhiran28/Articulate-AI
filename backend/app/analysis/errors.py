from enum import Enum


class AnalysisErrorReason(str, Enum):
    """
    Machine-readable cause of an analysis failure — same reason/message
    pattern as AudioValidationReason (app/audio/errors.py) and
    TranscriptionErrorReason (app/transcription/errors.py).

    TRANSCRIPT_EMPTY is raised as an AnalysisError — a whole-request
    guard that stops the engine before any module runs. Every other
    value here is only ever set on an individual ModuleResult.error
    (see models.py) and never raised, because one module's failure must
    never take down the rest of the report (ADR 003 §7).
    """

    # Raised as AnalysisError — stops the whole request before any
    # module runs.
    TRANSCRIPT_EMPTY = "transcript_empty"

    # Set by a Metric module that validated its own required input and
    # found it unusable (e.g. duration_seconds is None, breaking a
    # words-per-minute division). No metric module exists yet — this
    # sprint only reserves the reason for when one does.
    METRIC_INPUT_INVALID = "metric_input_invalid"

    # Reserved for when reasoning modules and their LLM integration
    # exist (a future sprint — see ADR 003 §6's "app/llm/ seam" and
    # Sprint 4.2's explicit "no LLM code" constraint). Not raised by
    # anything in this sprint.
    LLM_PROVIDER_ERROR = "llm_provider_error"
    LLM_MALFORMED_RESPONSE = "llm_malformed_response"

    # Set by the engine (not the module) when a module raised an
    # exception the engine had to catch itself, rather than the module
    # classifying and reporting its own failure. A safety net, not a
    # module's own diagnosis — see ModuleRegistry.execute / AnalysisEngine.
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
