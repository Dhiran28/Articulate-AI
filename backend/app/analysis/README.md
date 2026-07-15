# Communication Intelligence Engine (Sprint 4.2 foundation → Sprint 4.5 reasoning modules)

This package is the "AI Analysis Layer" ADR 002 named and ADR 003
designed. Sprint 4.2 built its foundation — the module contract, a
registry, and a runner. Sprint 4.3 added the four deterministic Metric
modules. Sprint 4.5 added the six semantic Reasoning modules, on top of
`app/llm/`'s abstraction layer (Sprint 4.4), plus the interface and
execution-order changes those modules required. See `docs/decisions/003-*.md`
for the full architecture, the ten evaluation dimensions, and — important
— that ADR's Sprint 4.5 revision note disclosing a gap against its own
approved batching requirement (see "The batching gap" near the bottom of
this file).

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
│   ├── base.py            # AnalysisModule — the one interface every module implements
│   ├── filler_words.py    # FillerWordModule (Metric)
│   ├── hesitations.py     # HesitationModule (Metric)
│   ├── repetitions.py     # RepetitionModule (Metric)
│   ├── speaking_pace.py   # SpeakingPaceModule (Metric)
│   ├── reasoning_base.py  # _BaseReasoningModule — shared orchestration for every Reasoning module
│   ├── structure.py       # StructureModule (Reasoning)
│   ├── clarity.py         # ClarityModule (Reasoning)
│   ├── logical_flow.py    # LogicalFlowModule (Reasoning)
│   ├── topic_drift.py     # TopicDriftModule (Reasoning)
│   ├── confidence.py      # ConfidenceModule (Reasoning)
│   └── conciseness.py     # ConcisenessModule (Reasoning)
└── reasoning_pass/
    ├── README.md
    └── prompts/
        ├── analysis/      # six real, frontmatter-annotated prompts, one per Reasoning module
        ├── coaching/      # reserved — empty until the Coaching Engine exists (ADR 003 §2)
        └── rewrite/       # reserved — empty until a rewrite module exists
```

Nothing here is wired into `app/main.py` yet — there's no API route that
calls `AnalysisEngine`, and none of the ten modules above are registered
into the shared `MODULE_REGISTRY` singleton, nor are the six reasoning
prompts registered into a `PromptRegistry`. That wiring is application
startup's job, not a module's own — deliberately left for the sprint
that actually builds the route. Tests construct fresh, isolated
`ModuleRegistry()` (and, for reasoning modules, a fake `LLMReasoner`)
instances instead — see `tests/test_metric_modules.py` and
`tests/test_reasoning_modules.py`.

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

Every module still has the same one-interface shape on purpose,
including the six that now call an LLM. ADR 003 requires that reasoning
modules not each make their own independent LLM call by default — Sprint
4.5 did not implement that requirement yet (see "The batching gap"
below); keeping one `AnalysisModule` contract regardless is what will let
a future batching mechanism be adopted without another interface-level
change to the registry or engine.

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
3. **`ModuleRegistry.execute()` runs in two phases (Sprint 4.5 change):**
   - **Phase 1 — every METRIC module**, in registration order among
     themselves, each given an `AnalysisContext` whose `metrics` dict is
     empty. Each result is collected into a `metrics` dict as it
     completes.
   - **Phase 2 — every REASONING module**, in registration order among
     themselves, each given an `AnalysisContext` whose `metrics` dict now
     holds every Metric module's result from phase 1.
   - No module ever calls another module directly — a Reasoning module
     that wants a Metric module's output reads it off `context.metrics`,
     never by importing or invoking that module itself. A module that
     raises is caught and turned into a `failed` `ModuleResult`
     (`AnalysisErrorReason.MODULE_ERROR`) in either phase — it never
     stops the rest of the modules from running.
4. `AnalysisEngine` assembles every returned `ModuleResult` into one
   `AnalysisReport`, keyed by `module_name`. The overall order is now
   "every metric result, then every reasoning result" — not strict flat
   registration order across types, a disclosed, tested consequence of
   the two-phase change above.

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

## The six Reasoning modules (Sprint 4.5)

All six share the same shape: a thin subclass of `_BaseReasoningModule`
(`modules/reasoning_base.py`) supplying only `prompt_id` and
`_build_template_context()`. `_BaseReasoningModule.analyze()` handles
everything identical across all six: call `self._reasoner.reason(self.prompt_id,
template_context, ReasoningResult)`, catch any `LLMError` and translate
it into a `failed` `ModuleResult` (`LLMErrorReason` and
`AnalysisErrorReason` deliberately share identical string values, so
this is a one-line, lossless mapping — see `errors.py`), otherwise
return an `ok` `ModuleResult` carrying the validated `ReasoningResult`.
Every module validates against that *same* shared `ReasoningResult`
schema (`label`/`explanation`/`evidence`) — no bespoke per-module output
shape, which structurally rules out any module smuggling in a numeric
score.

| Module | `module_name` | `prompt_id` | What it evaluates | Extra template context beyond `$transcript` |
|---|---|---|---|---|
| `StructureModule` | `structure` | `structure_v1` | Whether the transcript has a recognizable structural shape. | none |
| `ClarityModule` | `clarity` | `clarity_v1` | How easy the transcript is to follow. | none |
| `LogicalFlowModule` | `logical_flow` | `logical_flow_v1` | Whether consecutive ideas connect logically. | none |
| `TopicDriftModule` | `topic_drift` | `topic_drift_v1` | Whether the speaker stays on topic. | none |
| `ConfidenceModule` | `confidence` | `confidence_v1` | How confidently the speaker comes across. | `$hedge_word_count` / `$hedge_word_examples` — a local, regex-based hedge-phrase count computed in Python, **no LLM call**, fed to the prompt as a starting signal for the model's own judgment. Never appears in the returned `ModuleResult`. |
| `ConcisenessModule` | `conciseness` | `conciseness_v1` | Whether the speaker communicates efficiently. | `$words_per_minute` / `$average_sentence_length`, read from `context.metrics["speaking_pace"]` when that Metric module ran and succeeded; `"unknown"` otherwise. Never calls `SpeakingPaceModule` itself. |

Prompts live under `reasoning_pass/prompts/analysis/` — see that
directory's own files and `reasoning_pass/README.md` for the JSON
frontmatter metadata every prompt file carries (`id`, `version`, `type`,
`expected_output`, `model_hints`) and for `coaching/`/`rewrite/`'s
reserved-empty status.

## The batching gap (read before wiring these modules into a real request)

ADR 003, after Sprint 4.1's approval, requires that reasoning modules
**not** each independently call the LLM by default — that all six should
share **one combined structured-output request**. Sprint 4.5's six
modules do **not** do this: each one calls the shared `LLMReasoner`
independently, so analyzing one transcript through all six costs six
separate LLM calls, not one. This satisfies Sprint 4.5's own literal
requirement ("all semantic reasoning must flow through the shared
LLMReasoner abstraction") but is a disclosed, deliberate deviation from
ADR 003's separate batching commitment — building that batching
mechanism (`ReasoningPass`, `contribute()`/`interpret()`) is real,
separate infrastructure work left for a future sprint. See
`docs/decisions/003-*.md`'s Sprint 4.5 revision note for the full
reasoning and the named tradeoffs.

## How a future module gets added

1. Write a class implementing `AnalysisModule` (`module_name`,
   `module_type`, `metadata`, `async def analyze(context)`) — the ten
   files under `modules/` above are working reference implementations,
   split into two families: the four Metric modules (plain computation
   over `context.transcript`) and the six Reasoning modules (subclass
   `reasoning_base._BaseReasoningModule` instead of implementing
   `analyze()` directly).
2. Register it: `MODULE_REGISTRY.register(YourModule())`, typically at
   application startup (not built yet — see above). A Reasoning module
   additionally needs an `LLMReasoner` instance injected at construction
   time, and its prompt registered into a `PromptRegistry` under its
   `prompt_id`.
3. Nothing else changes — `ModuleRegistry.execute()` and
   `AnalysisEngine.run()` have no knowledge of any specific module by
   name; they only ever iterate whatever is currently registered,
   dispatching purely on `module_type` for phase ordering. This is the
   additive property ADR 003 §1 requires: adding module eleven never
   means editing module ten, the registry, or the engine. Adding all six
   Sprint 4.5 reasoning modules didn't touch `registry.py`'s or
   `engine.py`'s module-agnostic logic, only extended `execute()` once,
   generically, for the two-phase order every module (present and
   future) now benefits from.

Registering a second module under a name already in use raises
`DuplicateModuleError` immediately, rather than silently shadowing the
first one.
