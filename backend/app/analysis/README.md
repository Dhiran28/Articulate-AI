# Communication Intelligence Engine (Sprint 4.2 foundation, Sprint 4.3 metric modules)

This package is the "AI Analysis Layer" ADR 002 named and ADR 003
designed. Sprint 4.2 built its foundation — the module contract, a
registry, and a runner, with no real modules yet. Sprint 4.3 added the
first four real modules: **all four are Metric modules — deterministic,
side-effect-free, no LLM, no scoring/coaching language, no report
generation.** The six Reasoning dimensions and any LLM integration
(`app/llm/`) remain unbuilt. See `docs/decisions/003-*.md` for the full
architecture and the ten evaluation dimensions this is built to
eventually house.

## Folder structure

```
backend/app/analysis/
├── models.py     # ModuleType, ModuleStatus, ResultMetadata, MetricResult,
│                 # ReasoningResult, ModuleErrorDetail, ModuleResult, AnalysisReport
├── errors.py     # AnalysisErrorReason, AnalysisError
├── registry.py   # ModuleRegistry, DuplicateModuleError, MODULE_REGISTRY
├── engine.py     # AnalysisEngine
└── modules/
    ├── base.py           # AnalysisModule — the one interface every module implements
    ├── filler_words.py   # FillerWordModule
    ├── hesitations.py    # HesitationModule
    ├── repetitions.py    # RepetitionModule
    └── speaking_pace.py  # SpeakingPaceModule
```

Nothing here is wired into `app/main.py` yet — there's no API route that
calls `AnalysisEngine`, and none of the four modules below are registered
into the shared `MODULE_REGISTRY` singleton. That wiring is application
startup's job, not a module's own — deliberately left for the sprint
that actually builds the route. Tests construct fresh, isolated
`ModuleRegistry()` instances instead (see `tests/test_metric_modules.py`).

## The module contract

Every module — regardless of what it eventually evaluates — implements
one `AnalysisModule` interface (`modules/base.py`):

- `module_name: str` — unique; `ModuleRegistry` rejects a second module
  registered under a name already in use.
- `module_type: ModuleType` — `METRIC` or `REASONING`. A convention for
  reporting and (later) dispatch, not a constraint the interface itself
  enforces.
- `metadata: dict` — free-form static info the module exposes about
  itself (version, description). Distinct from `ResultMetadata`, which
  describes a *result*, not the module.
- `async def analyze(transcript) -> ModuleResult` — the module's one
  entry point.

Every module has the same shape on purpose, including modules that will
eventually need an LLM. ADR 003 requires that reasoning modules not each
make their own independent LLM call by default — but that's an
implementation detail of *how* a future reasoning module's `analyze()`
coordinates with a shared component (built when LLM integration actually
lands), not a different interface at the registry/engine level. Keeping
one contract now is what lets the registry and engine stay completely
agnostic to that mechanism.

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
2. `AnalysisEngine.run(transcript_id, transcript)`:
   - Guards against an empty/near-empty transcript up front
     (`AnalysisErrorReason.TRANSCRIPT_EMPTY`), before any module runs.
   - Delegates to `ModuleRegistry.execute(transcript)`.
3. `ModuleRegistry.execute()` runs every registered module, in
   registration order, against the same transcript. No module sees
   another module's output. A module that raises is caught and turned
   into a `failed` `ModuleResult` (`AnalysisErrorReason.MODULE_ERROR`) —
   it never stops the rest of the modules from running.
4. `AnalysisEngine` assembles every returned `ModuleResult` into one
   `AnalysisReport`, keyed by `module_name`.

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

## How a future module gets added

1. Write a class implementing `AnalysisModule` (`module_name`,
   `module_type`, `metadata`, `async def analyze()`) — the four files
   under `modules/` above are working reference implementations of
   exactly this shape.
2. Register it: `MODULE_REGISTRY.register(YourModule())`, typically at
   application startup (not built yet — see above).
3. Nothing else changes — `ModuleRegistry.execute()` and
   `AnalysisEngine.run()` have no knowledge of any specific module by
   name; they only ever iterate whatever is currently registered. This
   is the additive property ADR 003 §1 requires: adding module eleven
   never means editing module four, the registry, or the engine. Adding
   the four Sprint 4.3 modules didn't touch `registry.py` or `engine.py`
   at all — the strongest evidence so far that the property holds.

Registering a second module under a name already in use raises
`DuplicateModuleError` immediately, rather than silently shadowing the
first one.
