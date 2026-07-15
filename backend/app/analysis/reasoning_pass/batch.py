"""
ReasoningPass (Sprint 4.5.1): the one component that actually talks to
the LLM on behalf of every current reasoning dimension — the piece ADR
003 §1 named and Sprint 4.5's own completion notes disclosed as an
explicit, deliberate gap. This closes that gap.

Where Sprint 4.5 had six reasoning modules each independently calling
`LLMReasoner.reason()` (six calls per analysis), this sprint replaces
that with exactly one call: `ReasoningPass.run()` gathers the transcript
and every deterministic sub-signal every dimension needs (via
signals.py), builds one combined prompt, calls `LLMReasoner.reason()`
once against one combined schema (`BatchedReasoningResult`, below), and
returns the single validated result. The six concrete reasoning modules
(`app/analysis/modules/{structure,clarity,logical_flow,topic_drift,
confidence,conciseness}.py`) no longer call the LLM at all — they read
their own section out of this result (see
`app/analysis/modules/section_reasoning_base.py`).
"""

from typing import Any

from pydantic import BaseModel

from app.llm.reasoner import LLMReasoner

from ..models import AnalysisContext, ReasoningResult
from .signals import compute_hedge_signal, extract_speaking_pace_hints


class BatchedReasoningResult(BaseModel):
    """
    The one JSON shape `ReasoningPass` validates the combined LLM
    response against — one key per current reasoning dimension, each a
    plain `ReasoningResult` (models.py), the same schema every reasoning
    module validated against individually before this sprint. Because
    this is a single pydantic model, `app/llm/schema_validator.py`'s
    existing `validate_schema()` validates the *entire* combined response
    — and, since each field is itself a `ReasoningResult`, every section
    — in one pass; no per-module second validation step exists anywhere
    in this pipeline (Sprint 4.5.1's "no duplicated validation"
    requirement).

    Adding a seventh reasoning dimension later means adding one field
    here, one section to the combined prompt (`prompts/analysis/
    reasoning_pass_v1.md`), and one new section-reading module — the
    same "additive, not a rewrite" property every other extensibility
    point in this codebase holds itself to.
    """

    structure: ReasoningResult
    clarity: ReasoningResult
    logical_flow: ReasoningResult
    topic_drift: ReasoningResult
    confidence: ReasoningResult
    conciseness: ReasoningResult


class ReasoningPass:
    """
    Constructed once (with an injected `LLMReasoner`) and shared across
    every analysis request — the same "one instance, injected, not
    constructed per-module" shape `DefaultLLMReasoner` itself already
    has. `ModuleRegistry` (registry.py) owns calling `run()` exactly
    once per `execute()` call, before any reasoning module's own
    `analyze()` runs, and handing every reasoning module the result via
    `AnalysisContext.reasoning_context` — see registry.py's own comments
    for why that's the correct place to inject it rather than widening
    `AnalysisContext` again.
    """

    def __init__(self, reasoner: LLMReasoner, prompt_id: str = "reasoning_pass_v1") -> None:
        self._reasoner = reasoner
        self.prompt_id = prompt_id

    async def run(self, context: AnalysisContext) -> BatchedReasoningResult:
        """
        Builds the one combined prompt context and makes the one LLM
        call for this analysis request. Raises whatever `LLMError`
        subclass `LLMReasoner.reason()` raises (timeout, provider
        failure, invalid JSON, schema mismatch, unknown prompt id) —
        this method never catches those itself. `ModuleRegistry` is
        responsible for catching it and translating a single failure
        here into every currently-registered reasoning module failing
        together (ADR 003 §7's batch-level failure mode) — the honest
        cost of one shared call replacing six independent ones.
        """
        template_context = self._build_template_context(context)
        return await self._reasoner.reason(self.prompt_id, template_context, BatchedReasoningResult)

    def _build_template_context(self, context: AnalysisContext) -> dict[str, Any]:
        transcript_text = context.transcript.processed_transcript.text
        hedge_word_count, hedge_word_examples = compute_hedge_signal(transcript_text)
        words_per_minute, average_sentence_length = extract_speaking_pace_hints(context.metrics)

        template_context: dict[str, Any] = {
            "transcript": transcript_text,
            "hedge_word_count": str(hedge_word_count),
            "hedge_word_examples": hedge_word_examples,
            "words_per_minute": words_per_minute,
            "average_sentence_length": average_sentence_length,
        }

        # Milestone 5.1: an optional, purely diagnostic key —
        # `LLMReasoner.reason()` reads it for its call log if present and
        # never requires it (see reasoner.py's own docstring). Routed
        # through `AnalysisContext.reasoning_context` (Sprint 4.5's
        # already-existing extensibility hook) rather than widening
        # `AnalysisContext` with a new field, since `AnalysisEngine.run()`
        # already accepts a `reasoning_context` passthrough for exactly
        # this kind of addition (see engine.py).
        session_id = context.reasoning_context.get("session_id")
        if session_id is not None:
            template_context["session_id"] = session_id

        return template_context
