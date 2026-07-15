# `app/analysis/reasoning_pass/`

Home of the Communication Intelligence Engine's shared batched reasoning
call (Sprint 4.5.1) and its prompt library (Sprint 4.5, per ADR 003 §3).

```
reasoning_pass/
  batch.py       # ReasoningPass, BatchedReasoningResult — the one LLM call per analysis
  signals.py     # compute_hedge_signal, extract_speaking_pace_hints — deterministic sub-signals fed into the combined prompt
  prompts/
    analysis/     reasoning_pass_v1.md — the one combined prompt covering all six dimensions
    coaching/     coaching_v1.md — the Coaching Engine's one prompt (app/coaching/, Milestone 5)
    rewrite/      reserved — empty until a "rewrite my answer" module exists
```

## `ReasoningPass`

`ReasoningPass.run(context)` is the only thing in this codebase that
calls `LLMReasoner.reason()` on behalf of the six current reasoning
dimensions (`app/analysis/modules/{structure,clarity,logical_flow,
topic_drift,confidence,conciseness}.py`). It gathers the transcript,
folds in the deterministic sub-signals from `signals.py` (hedge-word
count for CONFIDENCE, speaking-pace hints for CONCISENESS), builds one
prompt, and validates the whole response against `BatchedReasoningResult`
— one call, one schema, one validation pass, covering all six
dimensions. `ModuleRegistry` (`app/analysis/registry.py`) owns calling
`run()` at most once per `execute()` call and routing the result to
every registered reasoning module — see that file's own docstring for
the exact two-phase-plus-batch-step sequencing and its two degraded
paths (no `ReasoningPass` configured; the one call itself failing).

## Prompts

Prompts are grouped by *what kind of output they produce*, not by which
module uses them: `analysis/` prompts always resolve to a
`BatchedReasoningResult` (or, for a future "deep analysis" module using
the escape hatch in `modules/reasoning_base.py`, a plain
`ReasoningResult`) — label/explanation/evidence, no scores, no coaching
language. `coaching/coaching_v1.md` (Milestone 5, `app/coaching/`)
resolves to `CoachingContent` — strengths, weaknesses, recommendations,
suggested exercises, next practice focus, and an executive summary —
consumed by `CoachingEngine`, never by anything in this package or
`app/analysis/`. `rewrite/` prompts will eventually resolve to rewritten
text (e.g. "say this more concisely") — a distinct output shape from
both of the above, and out of scope for both the CIE and the Coaching
Engine as currently designed.

**Sprint 4.5.1 change:** the six per-dimension prompt files Sprint 4.5
shipped (`structure_v1.md`, `clarity_v1.md`, ...) were retired and
replaced with one combined file, `reasoning_pass_v1.md`, covering all
six dimensions in a single prompt — kept as one file, not six, per this
sprint's "no duplicated prompts" requirement.

## Metadata

Every prompt file under `prompts/` opens with a JSON frontmatter block
(id, version, type, expected_output, model_hints) before its body — see
`app/llm/prompt_loader.py`'s `PromptMetadata` for the enforced shape.

## Registering the prompts

**Milestone 5:** `app/core/dependencies.py`'s `get_prompt_registry()`
registers both real prompt directories (`prompts/analysis/` and
`prompts/coaching/`) at application startup via
`PromptRegistry.discover_directory()` (see `app/llm/prompt_registry.py`)
— the manual wiring this package's own tests still do by hand against a
fixtures directory is now also done for real, once, in the DI layer that
backs `POST /analyze`.
