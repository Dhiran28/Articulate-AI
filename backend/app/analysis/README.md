# Communication Intelligence Engine (Sprint 4.2 foundation → Sprint 4.5.1 batched reasoning)

This package is the "AI Analysis Layer" ADR 002 named and ADR 003
designed. Sprint 4.2 built its foundation — the module contract, a
registry, and a runner. Sprint 4.3 added the four deterministic Metric
modules. Sprint 4.5 added the six semantic Reasoning modules, on top of
`app/llm/`'s abstraction layer (Sprint 4.4). Sprint 4.5.1 replaced Sprint
4.5's six independent LLM calls with one shared `ReasoningPass` — closing
the batching gap Sprint 4.5 disclosed rather than silently deviated
around. See `docs/decisions/003-*.md` for the full architecture and the
ten evaluation dimensions.

## Folder structure

```
backend/app/analysis/
├── models.py     # ModuleType, ModuleStatus, ResultMetadata, MetricResult,
│                 # ReasoningResult, ModuleErrorDetail, ModuleResult,
│                 # AnalysisContext, AnalysisReport
├── errors.py     # AnalysisErrorReason, AnalysisError
├── registry.py   # ModuleRegistry, DuplicateModuleError, MODULE_REGISTRY
├── engine.py     # AnalysisEngine
├── modules/
│   ├── base.py                     # AnalysisModule — the one interface every module implements
│   ├── filler_words.py             # FillerWordModule (Metric)
│   ├── hesitations.py              # HesitationModule (Metric)
│   ├── repetitions.py              # RepetitionModule (Metric)
│   ├── speaking_pace.py            # SpeakingPaceModule (Metric)
│   ├── reasoning_base.py           # _BaseReasoningModule — the "deep analysis" escape hatch (ADR 003 §1), unused by any concrete module today
│   ├── section_reasoning_base.py   # _SectionReasoningModule — shared orchestration for every current Reasoning module
│   ├── structure.py                # StructureModule (Reasoning)
│   ├── clarity.py                  # ClarityModule (Reasoning)
│   ├── logical_flow.py             # LogicalFlowModule (Reasoning)
│   ├── topic_drift.py              # TopicDriftModule (Reasoning)
│   ├── confidence.py               # ConfidenceModule (Reasoning)
│   └── conciseness.py              # ConcisenessModule (Reasoning)
└── reasoning_pass/
    ├── README.md
    ├── batch.py       # ReasoningPass, BatchedReasoningResult — the one LLM call per analysis
    ├── signals.py     # compute_hedge_signal, extract_speaking_pace_hints — deterministic sub-signals fed into the combined prompt
    └── prompts/
        ├── analysis/      # reasoning_pass_v1.md — the one combined prompt covering all six dimensions
        ├── coaching/      # reserved — empty until the Coaching Engine exists (ADR 003 §2)
        └── rewrite/       # reserved — empty until a rewrite module exists
```

Nothing here is wired into `app/main.py` yet — there's no API route that
calls `AnalysisEngine`, and none of the ten modules above are registered
into the shared `MODULE_REGISTRY` singleton, nor is `reasoning_pass_v1.md`
registered into a `PromptRegistry`, nor does `MODULE_REGISTRY` have a
`ReasoningPass` configured. That wiring is application startup's job, not
a module's own — deliberately left for the sprint that actually builds
the route. Tests construct fresh, isolated `ModuleRegistry()` (optionally
with a `ReasoningPass` backed by a fake `LLMReasoner`) instances instead
— see `tests/test_metric_modules.py`, `tests/test_reasoning_modules.py`,
and `tests/test_reasoning_pass.py`.

## The module contract

Every module — Metric or Reasoning — implements one `AnalysisModule`
interface (`modules/base.py`):

- `module_name: str` — unique; `ModuleRegistry` rejects a second module
  registered under a name already in use.
- `module_type: ModuleType` — `METRIC` or `REASONING`. A convention for
  reporting and dispatch (Sprint 4.5's two-phase registry execution, see
  below, is the first place this actually drives behavior).
- `metadata: dict` — free-form static info the module exposes about
  itself (version, description). Distinct from `ResultMetadata`, which
  describes a *result*, not the module.
- `async def analyze(context: AnalysisContext) -> ModuleResult` — the
  module's one entry point.

**Sprint 4.5 change:** `analyze()` used to take a bare
`TranscriptProcessingResult`. It now takes an `AnalysisContext`
(`models.py`) — `transcript` (unchanged), `metrics` (every
already-completed Metric module's `ModuleResult`, keyed by
`module_name`), and `reasoning_context` (an open, currently-unused
extensibility hook). This is a genuine, disclosed breaking change: every
Sprint 4.3 Metric module and every existing test was updated in the same
sprint to match. A Metric module always sees an empty `metrics` dict
(nothing has run before it); a Reasoning module sees every Metric
module's finished result, which is what lets `ConcisenessModule` read
`speaking_pace`'s output as supporting context (see below) without
calling that module directly.

Every module still has the same one-interface shape on purpose. ADR 003
requires that reasoning modules not each make their own independent LLM
call by default — as of Sprint 4.5.1 (see "The six Reasoning modules"
below), none of them do: `AnalysisModule`'s contract stayed identical
through that change, which is exactly why keeping one interface,
regardless of what's behind a module's `analyze()`, was worth doing in
Sprint 4.2.

## Result schemas

`ModuleResult` separates what Sprint 4.2 was asked to keep distinct:

- `ResultMetadata` — provenance (which module, what type, when).
- `MetricResult` — a Metric module's successful output (`value`/`unit`/`details`).
- `ReasoningResult` — a Reasoning module's successful output (`label`/`explanation`/`evidence`).
- `ModuleErrorDetail` — why a module's result is `failed`.

A `ModuleResult` always carries `metadata`, and exactly one of
`metric` / `reasoning` / `error` — enforced by a validator, not just a
convention, so a malformed result is rejected at construction time
rather than discovered later by a caller guessing which field to read.

## Data flow

1. A caller holds a `TranscriptProcessingResult` (Sprint 3.6's output)
   and an id to label the report with.
2. `AnalysisEngine.run(transcript_id, transcript, reasoning_context=None)`:
   - Guards against an empty/near-empty transcript up front
     (`AnalysisErrorReason.TRANSCRIPT_EMPTY`), before any module runs.
   - Delegates to `ModuleRegistry.execute(transcript, reasoning_context)`.
3. **`ModuleRegistry.execute()` runs in two phases with one batched LLM
   step between them:**
   - **Phase 1 — every METRIC module**, in registration order among
     themselves, each given an `AnalysisContext` whose `metrics` dict is
     empty. Each result is collected into a `metrics` dict as it
     completes.
   - **Between phases (Sprint 4.5.1) — if any REASONING module is
     registered**, the registry calls its configured `ReasoningPass`
     **exactly once** and stashes the validated `BatchedReasoningResult`
     into `reasoning_context` under a shared key. If no `ReasoningPass`
     is configured, or the one call itself fails, every REASONING
     module is given a `failed` `ModuleResult` directly, without
     `analyze()` ever being called (see "The six Reasoning modules"
     below for the two failure reasons involved).
   - **Phase 2 — every REASONING module**, in registration order among
     themselves (skipped for any module already failed in the step
     above), each given an `AnalysisContext` whose `metrics` dict holds
     every Metric result from phase 1 and whose `reasoning_context`
     carries the batched result.
   - No module ever calls another module directly — a Reasoning module
     reads the batched result or a Metric module's output off
     `context`, never by importing or invoking that module itself. A
     module that raises is caught and turned into a `failed`
     `ModuleResult` (`AnalysisErrorReason.MODULE_ERROR`) in either phase
     — it never stops the rest of the modules from running.
4. `AnalysisEngine` assembles every returned `ModuleResult` into one
   `AnalysisReport`, keyed by `module_name`. The overall order is "every
   metric result, then every reasoning result" — not strict flat
   registration order across types.

An empty registry is a valid, ordinary case — `run()` still returns a
well-formed `AnalysisReport` with an empty `modules` dict, not an error.

## The four Metric modules (Sprint 4.3)

Every module here follows the same three rules, enforced by construction
rather than just by convention:

- **Deterministic and side-effect-free.** Each module reads only the
  `TranscriptProcessingResult` it's given and returns a `MetricResult` —
  no file I/O, no network calls, no database writes, no LLM calls, no
  reaching into another module's output. `async def analyze()` is
  required by the `AnalysisModule` interface, but the body of every one
  of these four is plain synchronous computation; nothing here actually
  awaits anything.
- **Reuses Sprint 3.5's output wherever the arithmetic allows it**,
  rather than recalculating from raw timestamps. Every pause any of
  these modules reports on is read from `ProcessedSegment.pause_before_seconds`
  (Sprint 3.5 already computed it); words-per-minute and average pause
  duration are plain division over `TranscriptMetadata` fields Sprint
  3.5 already populated. Where a module needs *itemized* detail Sprint
  3.5's aggregate counts don't retain (which specific word, which
  segment), it recomputes that one thing and says so in its docstring —
  see `filler_words.py` and `repetitions.py`.
- **No scores, no bands, no coaching language.** Everything returned is
  a count, a rate, a location, or a list — never a judgment like
  "moderate" or "you should." That's the Coaching Engine's job, and it
  doesn't exist yet either (ADR 003 §1).

### FillerWordModule (`module_name = "filler_words"`)

Scans `processed_transcript.segments` against a configurable dictionary
of filler words (defaults to the same nine-word list
`TranscriptProcessor` uses, so the default total matches
`TranscriptMetadata.disfluencies.filler_words` exactly). Returns the
total count as `metric.value`, plus in `details`: `frequency_per_100_words`
(relative to `TranscriptMetadata.word_count`), `top_fillers` (ranked by
count), `occurrences` (every instance, with its segment index and
timestamps), and the `dictionary` actually used.

### HesitationModule (`module_name = "hesitations"`)

Scoped to *silent* pauses only — filled hesitation sounds ("um," "uh")
are `FillerWordModule`'s job, the same boundary ADR 003 §2 draws.
Every pause it reports comes directly from
`ProcessedSegment.pause_before_seconds`; its pause count matches
`TranscriptMetadata.disfluencies.pauses` exactly. Adds a second,
stricter `long_pause_threshold_seconds` (default 1.5s, configurable) to
classify a subset of Sprint 3.5's already-detected pauses as "long," and
buckets every pause into the early/middle/late third of the transcript
(`distribution`) by timestamp alone — no judgment about why a pause
happened.

### RepetitionModule (`module_name = "repetitions"`)

Detects two different things, deliberately scoped differently:
**immediate repetitions** ("the the") — adjacent identical words within
one segment, recomputed from scratch (not reused from Sprint 3.5's bare
count) because this module needs the itemized instances, but the total
still matches `TranscriptMetadata.disfluencies.repeated_words` exactly —
and **repeated phrases** ("the plan is" appearing twice) — exact n-gram
matches (configurable lengths, default 2/3/4 words) anywhere in the
transcript, deliberately *not* scoped to a single segment, since a whole
phrase repeating across two segments is real signal, not a boundary
artifact. This is exact string matching only — it does not detect the
same idea restated in different words; that requires semantic judgment
and belongs to a future reasoning module.

### SpeakingPaceModule (`module_name = "speaking_pace"`)

Words per minute (`TranscriptMetadata.word_count` over
`duration_seconds`) and average pause duration
(`total_pause_seconds` over `disfluencies.pauses`) are both plain
division over fields Sprint 3.5 already computed. Average sentence
length (splitting `processed_transcript.text` on `. ! ?`) and longest
pause (the max of every segment's `pause_before_seconds`) are the two
things this module computes itself, since Sprint 3.5 didn't need them.
Returns a classified `METRIC_INPUT_INVALID` failure — not a crash —
when `duration_seconds` is missing or non-positive, since words-per-minute
is undefined without it.

## The six Reasoning modules (Sprint 4.5, batched Sprint 4.5.1)

All six share the same shape: a thin subclass of `_SectionReasoningModule`
(`modules/section_reasoning_base.py`) supplying only `module_name` and
`section_key`. **None of them call an LLM.** Each one's `analyze()`
reads its own field off the `BatchedReasoningResult` that
`ModuleRegistry` already ran `ReasoningPass` to produce exactly once
per analysis (see "Data flow" above and `reasoning_pass/batch.py`),
confirms it's a real `ReasoningResult` (defensive — a validated batch
can't actually be missing a field, since `BatchedReasoningResult`
requires all six), and returns it wrapped in a `ModuleResult`. Every
module's output is the same shared `ReasoningResult` schema
(`label`/`explanation`/`evidence`) it always was — no bespoke
per-module output shape, structurally ruling out a smuggled-in numeric
score.

| Module | `module_name` | `section_key` | What it evaluates |
|---|---|---|---|
| `StructureModule` | `structure` | `structure` | Whether the transcript has a recognizable structural shape. |
| `ClarityModule` | `clarity` | `clarity` | How easy the transcript is to follow. |
| `LogicalFlowModule` | `logical_flow` | `logical_flow` | Whether consecutive ideas connect logically. |
| `TopicDriftModule` | `topic_drift` | `topic_drift` | Whether the speaker stays on topic. |
| `ConfidenceModule` | `confidence` | `confidence` | How confidently the speaker comes across. |
| `ConcisenessModule` | `conciseness` | `conciseness` | Whether the speaker communicates efficiently. |

The deterministic sub-signals `ConfidenceModule` and `ConcisenessModule`
used to compute/read themselves (a local hedge-word count; the
`speaking_pace` metric's words-per-minute and average sentence length)
moved to `reasoning_pass/signals.py` — computed once, by `ReasoningPass`,
and folded into the one combined prompt, rather than once per module.

The one combined prompt lives at
`reasoning_pass/prompts/analysis/reasoning_pass_v1.md` — see that file
and `reasoning_pass/README.md` for the JSON frontmatter metadata it
carries (`id`, `version`, `type`, `expected_output`, `model_hints`) and
for `coaching/`/`rewrite/`'s reserved-empty status. The six per-dimension
prompt files Sprint 4.5 originally shipped were retired when this
combined prompt replaced them — kept as one file, not six, per Sprint
4.5.1's "no duplicated prompts" requirement.

## Batching (Sprint 4.5.1) — how "one call, not six" actually works

ADR 003, after Sprint 4.1's approval, requires that reasoning modules
**not** each independently call the LLM by default — that all six share
**one combined structured-output request**. Sprint 4.5 shipped without
this (disclosed explicitly at the time); Sprint 4.5.1 built it:

- **`ReasoningPass`** (`reasoning_pass/batch.py`) is the only thing in
  this codebase that calls `LLMReasoner.reason()` on behalf of these six
  dimensions. It gathers the transcript and every deterministic
  sub-signal (`signals.py`), builds one prompt, and validates the whole
  response against one schema, `BatchedReasoningResult` — one field per
  dimension, each a `ReasoningResult`.
- **`ModuleRegistry` calls it at most once per `execute()` call**,
  regardless of how many REASONING modules are registered (see
  `tests/test_analysis_engine.py::TestReasoningPassIntegration` for the
  exact assertion), and hands every registered REASONING module its own
  section via `AnalysisContext.reasoning_context`.
- **Two degraded paths, both per-module rather than a whole-request
  failure:** no `ReasoningPass` configured (`NO_PROVIDER_CONFIGURED` per
  module), or the one call itself fails (every REASONING module fails
  together with the same translated reason — ADR 003 §7's named
  "batch-level failure" tradeoff, now real). Metric modules are
  unaffected either way.
- **The "deep analysis" escape hatch survives.** `_BaseReasoningModule`
  (`modules/reasoning_base.py`) — Sprint 4.5's original per-module
  orchestration — is kept, unused by any concrete module today, for a
  future dimension whose needs don't fit the shared batched prompt (see
  `tests/test_reasoning_base_escape_hatch.py`).
- **Measured, not just claimed:** `tests/test_reasoning_pass_benchmarks.py`
  compares call count (6 → 1, exact) and simulated wall-clock latency
  (~6x faster, against a fake reasoner — no real provider exists yet).

See `docs/decisions/003-*.md`'s Sprint 4.5.1 implementation note for the
full design writeup.

## How a future module gets added

1. Write a class implementing `AnalysisModule` (`module_name`,
   `module_type`, `metadata`, `async def analyze(context)`) — the ten
   files under `modules/` above are working reference implementations,
   split into three families: the four Metric modules (plain computation
   over `context.transcript`), the six current Reasoning modules
   (subclass `section_reasoning_base._SectionReasoningModule`, add one
   field to `BatchedReasoningResult` and one section to the combined
   prompt), and the "deep analysis" escape hatch (subclass
   `reasoning_base._BaseReasoningModule` for a dimension that needs its
   own independent LLM call instead of joining the shared batch).
2. Register it: `MODULE_REGISTRY.register(YourModule())`, typically at
   application startup (not built yet — see above). A batched Reasoning
   module needs no constructor arguments; a "deep analysis" module still
   needs its own `LLMReasoner` injected, same as Sprint 4.5.
3. Nothing else changes — `ModuleRegistry.execute()` and
   `AnalysisEngine.run()` have no knowledge of any specific module by
   name; they only ever iterate whatever is currently registered,
   dispatching purely on `module_type` for phase ordering. This is the
   additive property ADR 003 §1 requires: adding module eleven never
   means editing module ten, the registry, or the engine.

Registering a second module under a name already in use raises
`DuplicateModuleError` immediately, rather than silently shadowing the
first one.
