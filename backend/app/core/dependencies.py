"""
FastAPI dependency providers.

Sprint 3.4 asked for the transcription provider to be wired in via
dependency injection specifically so OpenAI Whisper can later be swapped
for Local Whisper, Deepgram, or AssemblyAI without touching
TranscriptionService or the /transcribe route — only what
get_transcription_provider() returns needs to change.

The upload endpoints (app/api/upload.py) previously built their own
private, module-level singletons instead of going through this file. They
were moved here — not to change their behavior, but because the new
/transcribe endpoint needs to look up assets created via POST /api/upload,
which only works if both routes share the exact same AudioService /
RecordStore instances.

Sprint 3.5 added get_transcript_processor for the Transcript Processor
stage (app/transcript_processing/) that turns a RawTranscriptionResult
into a ProcessedTranscript + TranscriptMetadata — see that package's
processor.py for why "processing" here never means "cleaning."

Every dependency function that has its own dependencies (get_audio_service,
get_transcription_service) declares them as `Depends(...)` parameters,
rather than calling e.g. get_blob_store() directly in its body. That
distinction matters more than it looks: FastAPI's app.dependency_overrides
(used in tests to substitute a fake provider) only intercepts calls that
go through FastAPI's own dependency resolution. A plain Python function
call inside a function body bypasses it entirely. An earlier draft of
this file called get_transcription_provider() directly from
get_transcription_service()'s body, which worked fine at runtime but
silently made get_transcription_provider un-overridable in tests — caught
during this sprint's own verification (see the Sprint 3.4 explanation),
not by inspection. Chaining Depends() throughout is what makes the
override actually reach every level of the tree.
"""

from functools import lru_cache
from pathlib import Path

from fastapi import Depends

from app.analysis.engine import AnalysisEngine
from app.analysis.modules.clarity import ClarityModule
from app.analysis.modules.conciseness import ConcisenessModule
from app.analysis.modules.confidence import ConfidenceModule
from app.analysis.modules.filler_words import FillerWordModule
from app.analysis.modules.hesitations import HesitationModule
from app.analysis.modules.logical_flow import LogicalFlowModule
from app.analysis.modules.repetitions import RepetitionModule
from app.analysis.modules.speaking_pace import SpeakingPaceModule
from app.analysis.modules.structure import StructureModule
from app.analysis.modules.topic_drift import TopicDriftModule
from app.analysis.reasoning_pass.batch import ReasoningPass
from app.analysis.registry import ModuleRegistry
from app.audio.service import AudioService
from app.coaching.engine import CoachingEngine
from app.coaching.summary import CommunicationSummaryGenerator
from app.core.config import get_settings
from app.llm.prompt_registry import PromptRegistry
from app.llm.provider import LLMProvider
from app.llm.reasoner import DefaultLLMReasoner, LLMReasoner
from app.reporting.builder import ReportBuilder
from app.scoring.engine import ScoringEngine
from app.storage.blob_store import AudioBlobStore, LocalTempBlobStore
from app.storage.record_store import InMemoryRecordStore, RecordStore
from app.transcription.providers.base import TranscriptionProvider
from app.transcription.providers.openai_whisper import OpenAIWhisperProvider
from app.transcription.service import TranscriptionService
from app.transcript_processing.processor import TranscriptProcessor


@lru_cache
def get_blob_store() -> AudioBlobStore:
    settings = get_settings()
    return LocalTempBlobStore(Path(settings.upload_temp_dir))


@lru_cache
def get_record_store() -> RecordStore:
    return InMemoryRecordStore()


def get_audio_service(
    blob_store: AudioBlobStore = Depends(get_blob_store),
    record_store: RecordStore = Depends(get_record_store),
) -> AudioService:
    # Not itself cached: constructing it is cheap (it just wraps the two
    # already-cached singletons above), and per-request construction is
    # what lets FastAPI substitute either singleton via
    # dependency_overrides at test time.
    settings = get_settings()
    return AudioService(blob_store, record_store, settings.max_upload_size_bytes)


@lru_cache
def get_transcription_provider() -> TranscriptionProvider:
    """
    The dependency-injection seam Sprint 3.4 asked for. This is the one
    place that decides which TranscriptionProvider backs the /transcribe
    endpoint today. Swapping OpenAI Whisper for Local Whisper, Deepgram,
    or AssemblyAI later means changing what this function constructs (or
    branching on a new config value, e.g. a TRANSCRIPTION_PROVIDER
    setting, once more than one is real) — TranscriptionService and the
    route stay exactly as they are.

    In tests, override this directly via
    `app.dependency_overrides[get_transcription_provider] = ...` to
    substitute a fake provider without a real API key or network access —
    see the Sprint 3.4 verification notes for a working example.
    """
    settings = get_settings()
    return OpenAIWhisperProvider(api_key=settings.openai_api_key, model=settings.whisper_model)


def get_transcription_service(
    audio_service: AudioService = Depends(get_audio_service),
    blob_store: AudioBlobStore = Depends(get_blob_store),
    provider: TranscriptionProvider = Depends(get_transcription_provider),
) -> TranscriptionService:
    return TranscriptionService(audio_service, blob_store, provider)


@lru_cache
def get_transcript_processor() -> TranscriptProcessor:
    # No sub-dependencies of its own (it's a pure function over whatever
    # RawTranscriptionResult it's given), so a plain cached singleton is
    # enough — there's no provider-style swapping to support here yet.
    return TranscriptProcessor()


# ---------------------------------------------------------------------------
# Milestone 5 — Communication Intelligence Engine, LLM reasoning, coaching,
# scoring, and reporting.
#
# Disclosed gap: get_llm_provider() below returns None. No concrete
# LLMProvider exists anywhere in this codebase — app/llm/ (Sprint 4.4) was
# explicitly scoped to contain no vendor SDK, and no later sprint has added
# one. This is not an oversight specific to this milestone; it is the same,
# already-named gap every LLM-related sprint since 4.4 has disclosed rather
# than silently worked around. The effect on this milestone's /analyze
# endpoint: the four deterministic Metric modules, the Overall Communication
# Score's fluency-tier contribution, and the report's structural skeleton
# all work with zero LLM dependency; every REASONING module and the
# Coaching Engine degrade to a documented, specific error
# (NO_PROVIDER_CONFIGURED) rather than crashing or silently producing
# nothing — see ModuleRegistry.execute() and CoachingEngine.generate().
# Wiring in a real provider is exactly one function to change, below, per
# app/llm/README.md's "Future provider integration" section — nothing else
# in this dependency chain needs to change when that happens.
# ---------------------------------------------------------------------------


@lru_cache
def get_llm_provider() -> LLMProvider | None:
    """
    The one seam a future sprint fills in to make reasoning/coaching
    live: construct and return a real `LLMProvider` implementation here
    (see app/llm/README.md's "Future provider integration"). Returns
    `None` today — see this section's header comment for why that's a
    disclosed gap, not a bug.
    """
    return None


@lru_cache
def get_prompt_registry() -> PromptRegistry:
    """
    Loads every real prompt this application ships with — the one
    combined reasoning prompt (reasoning_pass_v1) and the one coaching
    prompt (coaching_v1) — from their real locations under
    app/analysis/reasoning_pass/prompts/, per ADR 003 §3. Built and
    populated even when no provider is configured (get_llm_provider() is
    None): a `PromptRegistry` with nothing to look prompts up on behalf
    of is still cheap to build, and doing so unconditionally means
    wiring in a real provider later requires no change here at all.
    """
    registry = PromptRegistry()
    prompts_root = Path(__file__).resolve().parent.parent / "analysis" / "reasoning_pass" / "prompts"
    registry.discover_directory(prompts_root / "analysis")
    registry.discover_directory(prompts_root / "coaching")
    return registry


def get_llm_reasoner(
    provider: LLMProvider | None = Depends(get_llm_provider),
    prompt_registry: PromptRegistry = Depends(get_prompt_registry),
) -> LLMReasoner | None:
    """
    `LLMReasoner | None`, not a required `LLMReasoner` — `DefaultLLMReasoner`'s
    own constructor raises `NoProviderConfiguredError` immediately if
    handed `provider=None` (see app/llm/reasoner.py), which would make
    this dependency itself unusable as a FastAPI dependency (it would
    raise on every single request that touches it, including the
    metric-only parts of /analyze that don't need it at all). Returning
    `None` here and letting each consumer (`ReasoningPass`,
    `CoachingEngine`) decide how to degrade — per-module for analysis,
    a single named error for coaching — is what keeps the metric-only
    path of /analyze fully functional with no LLM configured.
    """
    if provider is None:
        return None
    return DefaultLLMReasoner(provider, prompt_registry)


def get_reasoning_pass(
    reasoner: LLMReasoner | None = Depends(get_llm_reasoner),
) -> ReasoningPass | None:
    if reasoner is None:
        return None
    return ReasoningPass(reasoner)


def get_module_registry(
    reasoning_pass: ReasoningPass | None = Depends(get_reasoning_pass),
) -> ModuleRegistry:
    """
    Registers all ten Communication Intelligence Engine modules — the
    four Sprint 4.3 Metric modules and the six Sprint 4.5/4.5.1 Reasoning
    modules — the "one place production code registers a real module"
    registry.py's own module docstring anticipated back in Sprint 4.2,
    now finally populated. Constructed fresh per request (cheap — module
    construction does no I/O) rather than cached, so
    `app.dependency_overrides[get_reasoning_pass]` in tests reaches a
    freshly-wired registry instead of a stale cached one.
    """
    registry = ModuleRegistry(reasoning_pass=reasoning_pass)
    for module in (
        FillerWordModule(),
        HesitationModule(),
        RepetitionModule(),
        SpeakingPaceModule(),
        StructureModule(),
        ClarityModule(),
        LogicalFlowModule(),
        TopicDriftModule(),
        ConfidenceModule(),
        ConcisenessModule(),
    ):
        registry.register(module)
    return registry


def get_analysis_engine(
    registry: ModuleRegistry = Depends(get_module_registry),
) -> AnalysisEngine:
    return AnalysisEngine(registry=registry)


def get_coaching_engine(
    reasoner: LLMReasoner | None = Depends(get_llm_reasoner),
) -> CoachingEngine:
    # CoachingEngine accepts reasoner=None directly (see
    # app/coaching/engine.py) and raises a specific, documented
    # CoachingError(NO_PROVIDER_CONFIGURED) only if generate() is
    # actually called — so this dependency is always constructible,
    # never raises during dependency resolution itself.
    return CoachingEngine(reasoner)


@lru_cache
def get_scoring_engine() -> ScoringEngine:
    # No sub-dependencies — ScoringEngine only ever reads an
    # AnalysisReport it's handed, never anything DI-provided.
    return ScoringEngine()


@lru_cache
def get_summary_generator() -> CommunicationSummaryGenerator:
    return CommunicationSummaryGenerator()


@lru_cache
def get_report_builder() -> ReportBuilder:
    return ReportBuilder()
