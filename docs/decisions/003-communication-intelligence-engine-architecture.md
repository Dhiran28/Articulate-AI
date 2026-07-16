# ADR 003: Communication Intelligence Engine Architecture

**Status:** Approved (Sprint 4.1), revised per approval feedback before Sprint 4.2 begins.
**Scope:** The backend layer that turns a finished, processed transcript into (1) structured, evidence-backed analysis across ten evaluation dimensions, and (2) actionable coaching recommendations derived from that analysis. This is the "AI Analysis Layer" ADR 002 named and deliberately left as a contract-only seam. No code is written in this sprint.

---

## Revision notes (post-approval)

The initial design (§ history below) was approved with two required changes, both incorporated throughout this document:

1. **Reasoning modules no longer each make their own LLM call by default.** All six reasoning dimensions are evaluated through **one combined structured-output request**, with each module consuming only its own section of that response. The design stays flexible enough that a future module needing a genuinely separate call (multi-turn reasoning, tool use — a "deep analysis" module) can still opt out of the batch and call the LLM independently.
2. **The Communication Intelligence Engine (CIE) and the Coaching Engine are now two separate systems**, not one. The CIE produces structured, evidence-backed analysis only — no prescriptive language, no "you should." The Coaching Engine is a distinct, downstream consumer that takes that structured analysis and generates the actual actionable recommendations. Neither engine's core logic depends on the other's internals — they're connected only by the `AnalysisReport` data contract, the same way Sprint 3's `TranscriptionService` and `TranscriptProcessor` are connected only by `RawTranscriptionResult`.

Both changes are structural, not cosmetic, and they interact with each other: separating analysis from coaching is what makes it obvious *why* the CIE shouldn't be writing "coaching_note" strings in the first place — that was always the Coaching Engine's job description, just not yet given its own name.

## 0. Where this picks up

Sprint 3 ends at `TranscriptProcessingResult` (`app/transcript_processing/models.py`) — raw transcript, processed transcript, metadata. That remains the CIE's entire input. Nothing about this revision changes what feeds the pipeline; it changes what happens *inside* it and what comes *out* of it.

The verbatim-transcript principle from Sprint 3.5 still applies without exception: every reasoning judgment — batched or not — reads `processed_transcript.text`, disfluencies included, never a cleaned version.

## 1. Overall architecture

There are now two engines, each with one job, connected by one data contract:

| Engine | Input | Output | Job |
|---|---|---|---|
| **Communication Intelligence Engine (CIE)** | `TranscriptProcessingResult` | `AnalysisReport` | Produce structured, evidence-backed measurement across ten dimensions. Descriptive only — never tells the user what to do about it. |
| **Coaching Engine** | `AnalysisReport` | `CoachingReport` | Turn that measurement into prioritized, actionable recommendations, each traceable back to the specific module/evidence that motivated it. |

**Why split them, architecturally and not just organizationally:** measurement and prescription are different responsibilities with different audiences. `AnalysisReport` — precise, structured, no opinion baked in — is reusable by things that aren't a coaching UI at all: a longitudinal analytics view across a user's sessions, a research export, a future comparative module (ADR 003 §6). A report full of "coaching_note" strings only ever serves one consumer. Keeping the CIE's output opinion-free is what keeps it reusable. This is the same reasoning ADR 002 used to keep the Transcription Service from normalizing its own output (§1 of that ADR) — resist collapsing two responsibilities into one class just because they currently run back-to-back.

**Inside the CIE**, the module-registry design from the original approval is unchanged in spirit: one `AnalysisModule`-shaped interface, a registry, an orchestrator, module independence. What changes is how the six reasoning dimensions get their LLM judgment:

| Concept | Responsibility |
|---|---|
| **`AnalysisModule`** (interface) | "A thing that takes a `TranscriptProcessingResult` and returns a `ModuleResult`." Used directly by the four Metric modules, and available to any future module that needs its own independent LLM call (see "deep analysis," below). |
| **`BatchedReasoningModule`** (interface, new) | Used by the six current reasoning dimensions. Splits "ask the LLM something" into two smaller steps — `contribute()` (this module's slice of one shared prompt) and `interpret()` (turn this module's slice of one shared response into its own `ModuleResult`) — so no individual module owns a network call at all. |
| **Module Registry** | Unchanged in purpose: a plain list of modules (of either shape above). Adding dimension #11 means adding one line here, regardless of which interface it implements. |
| **`ReasoningPass`** (new) | The one place that actually talks to the LLM on behalf of every `BatchedReasoningModule`: collects every registered module's `contribute()`, assembles one combined prompt, calls `LLMReasoner` exactly once, and routes each section of the response back to its owning module's `interpret()`. |
| **`LLMReasoner`** (interface, relocated) | "Prompt in, structured judgment out." Now lives in a shared `app/llm/` package rather than inside `analysis/`, specifically so the Coaching Engine can depend on the same seam without depending on anything else inside the CIE. |

**Inside the Coaching Engine**, there is deliberately no module registry, because there's exactly one input shape to reason over (`AnalysisReport`) rather than ten independent transcript-level questions. It's one focused reasoning step: read the finished analysis, produce ranked, evidence-cited recommendations. (§6 covers where this engine's own extensibility lives — it isn't "add more modules," it's a different axis entirely.)

### Why batching doesn't undo "add a module without touching existing ones"

The risk with any batched-prompt design is that the shared prompt becomes one file that every module's addition has to edit — recreating exactly the coupling the original module-registry design was built to avoid. The fix is that **`ReasoningPass` never hardcodes which modules participate.** It iterates whatever `BatchedReasoningModule`s are currently registered, asks each one for its own `contribute()` fragment, and merges them generically. Adding reasoning dimension #7 means: one new module file (its own `contribute()` + `interpret()`), one new prompt file under `reasoning_pass/prompts/`, one registry line. `ReasoningPass`'s own logic does not change, because it was never written to know the six current dimensions by name in the first place.

### The "deep analysis" escape hatch

Not every future reasoning dimension will fit a single shared structured-output call — something requiring multi-turn back-and-forth with the model, tool use, or a much longer context than the other five modules need would distort the shared prompt for everyone else. Such a module simply implements the plain `AnalysisModule` interface instead of `BatchedReasoningModule` (the same interface Metric modules use) and calls `LLMReasoner` directly, on its own, exactly like every reasoning module did in the original (pre-revision) design. `AnalysisEngine` dispatches on which interface a registered module satisfies: `BatchedReasoningModule` → routed through the shared `ReasoningPass`; plain `AnalysisModule` → called directly. Both are first-class, both are additive, neither requires touching the other.

## 2. Module responsibilities

Unchanged from the original approval in *what* each module evaluates (see the table below for a quick reference); changed in two ways: (1) six of them now implement `BatchedReasoningModule` instead of calling the LLM themselves, and (2) **no module — Metric or Reasoning — produces coaching language anymore.** A `ModuleResult` carries score/band/count fields and *evidence* (segments, timestamps, quoted excerpts) — the raw material a coaching step would need — but never a prewritten "coaching_note." Turning "filler words appeared at a moderate rate, here's the evidence" into "here's what to do about it" is the Coaching Engine's job now, not each module's.

| # | Module | Category | Interface | What it evaluates |
|---|---|---|---|---|
| 1 | Filler Words | Metric | `AnalysisModule` | Rate/band from Sprint 3.5's `disfluencies.filler_words`, with timestamped evidence. |
| 2 | Hesitations | Metric | `AnalysisModule` | Silent-pause count/duration from `disfluencies.pauses` / `total_pause_seconds`, with evidence. Scoped to silence only — filled hesitation sounds are Filler Words' job (unchanged boundary from the original design). |
| 3 | Repetitions | Metric | `AnalysisModule` | Adjacent-word repeats from `disfluencies.repeated_words`, with evidence. |
| 4 | Speaking Pace | Metric | `AnalysisModule` | Words per minute against a documented benchmark band; flags uneven pacing. |
| 5 | Structural Thinking | Reasoning | `BatchedReasoningModule` | Whether a discernible shape exists (problem→solution, claim→support→conclusion, etc.) and whether it's complete. |
| 6 | Logical Organization | Reasoning | `BatchedReasoningModule` | Whether each step follows coherently from the last; flags specific breakdown points. |
| 7 | Clarity | Reasoning | `BatchedReasoningModule` | Ambiguous referents, unexplained jargon, buried points; flags specific unclear passages. |
| 8 | Conciseness | Reasoning | `BatchedReasoningModule` | Padding/redundant restatement, distinct from disfluency noise. |
| 9 | Topic Drift | Reasoning | `BatchedReasoningModule` | Whether the speaker stays on topic; flags drifting segments. |
| 10 | Confidence Indicators | Hybrid | `BatchedReasoningModule` | Hedge-word lexical count (a small deterministic sub-signal, computed before the batched call and handed in as context) plus the LLM's contextual judgment of whether hedging undermines a key moment. |

No dimension changed what it measures. What changed is *how* six of them get their judgment (one shared call instead of six independent ones) and what they're allowed to say (evidence, not advice).

## 3. Folder structure

```
backend/app/
├── llm/                                 # Shared LLM integration seam — depended on by both engines below; depends on neither
│   ├── reasoner.py                      # LLMReasoner Protocol: prompt in, structured judgment out
│   └── openai_reasoner.py               # First implementation — reuses the AsyncOpenAI client pattern from transcription/providers/openai_whisper.py
│
├── analysis/                             # Communication Intelligence Engine (CIE) — structured analysis ONLY
│   ├── models.py                         # AnalysisReport, ModuleResult, ModuleCategory, ModuleStatus — no coaching-language field
│   ├── engine.py                         # AnalysisEngine: calls Metric/standalone modules directly, delegates BatchedReasoningModules to ReasoningPass, assembles AnalysisReport
│   ├── registry.py                       # MODULE_REGISTRY — one list, mixed interfaces, one place a module is added
│   ├── errors.py                         # AnalysisErrorReason, AnalysisError
│   ├── benchmarks.py                     # Named constants: pace bands, filler-rate bands, hedge-word lexicon
│   ├── modules/
│   │   ├── base.py                        # AnalysisModule Protocol
│   │   ├── batched.py                     # BatchedReasoningModule Protocol: contribute() + interpret()
│   │   ├── filler_words.py
│   │   ├── hesitations.py
│   │   ├── repetitions.py
│   │   ├── speaking_pace.py
│   │   ├── structural_thinking.py
│   │   ├── logical_organization.py
│   │   ├── clarity.py
│   │   ├── conciseness.py
│   │   ├── topic_drift.py
│   │   └── confidence_indicators.py
│   └── reasoning_pass/
│       ├── batch.py                       # ReasoningPass: gathers contribute() from every registered BatchedReasoningModule, builds one combined prompt, calls app/llm's LLMReasoner once, routes sections to interpret()
│       └── prompts/
│           ├── common.py                   # Shared preamble + combined-response envelope schema
│           ├── structural_thinking.py       # This module's instruction fragment + section schema
│           ├── logical_organization.py
│           ├── clarity.py
│           ├── conciseness.py
│           ├── topic_drift.py
│           └── confidence_indicators.py
│
└── coaching/                              # Coaching Engine — consumes AnalysisReport, produces recommendations. Never reads the transcript directly.
    ├── models.py                          # CoachingReport, Recommendation (priority, message, cites module + evidence)
    ├── engine.py                          # CoachingEngine.generate(AnalysisReport) -> CoachingReport
    ├── errors.py                          # CoachingErrorReason, CoachingError
    └── prompts/
        └── recommendations.py             # One prompt: whole AnalysisReport in, prioritized/cited recommendations out
```

Three things worth calling out about this layout, beyond what the original design already explained about per-module file separation:

- **`app/llm/` is new and deliberately outside both engines.** If `LLMReasoner` lived inside `analysis/`, the Coaching Engine would have to import from the CIE's package to make its own LLM call — a real dependency between two things this revision exists to keep separate. Promoting the shared seam to a sibling package (the same relationship `AudioService` and `TranscriptionService` both have to `app/storage/`, rather than to each other) keeps the separation real, not just conventional.
- **`reasoning_pass/` replaces the plain `llm/` folder the original design nested under `analysis/`.** The rename reflects what it actually does now — it's not just "where reasoning modules keep their prompts," it's the one component that performs the batched call.
- **`coaching/` has no `modules/` subfolder.** The Coaching Engine isn't a registry of independent evaluators; it's a single reasoning step over one already-structured input. Its own extensibility (§6) is a different shape than the CIE's, and forcing it into the same registry pattern would be the wrong abstraction, not a consistent one.

## 4. Data flow

1. A caller holds a `TranscriptProcessingResult` (from Sprint 3.6's transcribe endpoint). Unchanged.
2. **`AnalysisEngine.analyze(result)`** runs. Guard check up front: empty/near-empty transcript short-circuits with `TRANSCRIPT_EMPTY`, same as before.
3. The engine calls every registered **Metric** module directly (and any future standalone/"deep analysis" module implementing plain `AnalysisModule`) — no change from the original design, still zero LLM calls, still fully independent of each other.
4. Separately, the engine hands every registered **`BatchedReasoningModule`** to `ReasoningPass`, which:
   a. Calls each module's `contribute()` to collect its instruction fragment and output-section schema.
   b. Assembles one combined prompt (shared preamble + every module's fragment) and sends it through `LLMReasoner` **exactly once**.
   c. Receives one structured JSON response containing one section per participating module.
   d. Calls each module's `interpret()` with *only that module's own section* of the response, producing that module's `ModuleResult`. A module whose section is missing or fails its own schema validation is marked `failed` independently — the other modules' sections are unaffected (§7 covers the one new failure mode this doesn't protect against).
5. All `ModuleResult`s — Metric and Reasoning alike — assemble into one **`AnalysisReport`**. This is the CIE's complete output. No ranking, no recommendations, no coaching language.
6. A caller (not built this sprint) passes the finished `AnalysisReport` to **`CoachingEngine.generate(report)`**.
7. The Coaching Engine builds one prompt from the *structured report* (not the transcript — it never sees raw or processed transcript text at all, only what the CIE already extracted from it) and produces a **`CoachingReport`**: a prioritized list of recommendations, each one explicitly citing which module/evidence it's grounded in.
8. `CoachingReport` is returned to the caller (and, presumably, persisted alongside `AnalysisReport` — an open Storage Layer decision, unchanged from the original design's stance on leaving persistence open).

## 5. Prompt architecture

### CIE reasoning prompts (the batched call)

- **One combined request, not six.** `ReasoningPass` builds a single prompt: a shared preamble (`reasoning_pass/prompts/common.py` — the same framing as before: this is a spoken-communication transcript being coached on structure and delivery, disfluencies are intentional and preserved, don't penalize them unless the dimension is specifically about them) followed by each participating module's own instruction fragment and its named output section.
- **The combined response is one JSON object, one key per module**, each key's shape defined by that module's own schema (contributed via its `contribute()` call, mirroring how each module previously owned its whole prompt file). A module never sees or validates another module's section.
- **Verbatim transcript, low temperature, prompt versioning** — all unchanged from the original design. These properties don't depend on whether it's one call or six.
- **The cost/latency tradeoff named in the original design is now resolved in the other direction, and the new tradeoff introduced by resolving it that way is named explicitly in §7**: one call is cheaper and faster than six, at the cost of a wider failure blast radius when the call itself fails outright (as opposed to one module's section merely being malformed). Both tradeoffs — the original design's and this revision's — are stated in the document rather than silently chosen, consistent with how every other cost/benefit call in this project has been handled.

### Coaching Engine prompt (recommendation generation)

- **A structurally different input than any CIE prompt: the finished `AnalysisReport` itself, not transcript text.** The Coaching Engine's prompt is built entirely from already-structured, already-evidenced data — scores, bands, counts, quoted evidence excerpts the CIE extracted. This is what makes the separation real rather than nominal: the Coaching Engine *cannot* invent an observation the CIE didn't already surface, because it never has access to anything the CIE didn't already extract and hand it.
- **Every recommendation must cite the specific module (and, where applicable, evidence) that motivated it.** A recommendation with no traceable citation back to `AnalysisReport` is treated as invalid output, the same discipline as "no force-parsing a malformed response" elsewhere in this document — advice untethered from evidence is exactly as unacceptable here as a fabricated disfluency count would be in the CIE.
- **One call, by design, not a batching decision.** There's exactly one input shape (the whole report) and one output shape (a ranked recommendation list) — there was never a "six independent calls" problem to solve here in the first place.
- **Coaching Engine prompts explicitly do not need the verbatim-transcript instruction** the CIE's prompts carry, because the Coaching Engine never receives the transcript at all — a structural guarantee, not just a documented convention, since `CoachingEngine.generate()`'s only parameter is `AnalysisReport`.

## 6. Future extensibility

Unchanged from the original design: new CIE modules (Metric, batched Reasoning, or standalone "deep analysis") are additive via the registry, exactly as before — batching didn't change that guarantee (§1). What's new in this revision:

- **The Coaching Engine's extensibility axis is different from the CIE's, and that's intentional.** It isn't "add another module" — it's things like: different recommendation *tones/personas* (a terser executive-coaching voice vs. a more encouraging one), different prioritization strategies (biggest-impact-first vs. easiest-to-fix-first), or eventually multiple recommendation passes for different audiences (self-review vs. a manager's report). None of these require touching the CIE, because they only ever consume `AnalysisReport`.
- **A module that starts as `BatchedReasoningModule` can later graduate to standalone `AnalysisModule`** (or vice versa) if its needs change — e.g., if Topic Drift later needs a much longer context window than the other five batched dimensions comfortably share, it can move to its own direct `LLMReasoner` call without any of the other five modules or `ReasoningPass`'s generic logic changing. The two interfaces are a per-module choice, not a permanent commitment.
- **Batching itself could later be split into more than one group** (e.g., two combined calls of three modules each) if one shared prompt ever gets too large — this is an internal `ReasoningPass` concern and, like the original design's note on batching, doesn't change `AnalysisModule`/`BatchedReasoningModule`'s contracts.
- **Cross-module synthesis inside the CIE** (a holistic pass reasoning over all ten `ModuleResult`s together) is explicitly *not* what the Coaching Engine is — that would still be CIE-side analysis (descriptive), whereas the Coaching Engine's output is prescriptive by design. If a future need for holistic *descriptive* synthesis emerges (e.g., "how do these ten signals interact"), it belongs as an eleventh CIE module whose input is `AnalysisReport` rather than as part of the Coaching Engine.
- Everything else from the original design's extensibility section (LLM provider swap via a new `app/llm/` implementation, per-user historical trending, non-English lexicons/prompts) is unchanged.

## 7. Error handling

**CIE, Metric modules:** unchanged — defensive input validation, `METRIC_INPUT_INVALID` on malformed required fields.

**CIE, batched Reasoning modules — two distinct failure layers now, where there used to be one:**
- **Section-level failure (isolated, as before):** the combined call succeeds, but one module's section is missing or fails that module's own schema validation. Only that module's `ModuleResult` is `failed` (`LLM_MALFORMED_RESPONSE`); every other module's section parses independently and is unaffected. This preserves nearly all of the original design's failure isolation.
- **Batch-level failure (new, and the honest cost of this revision):** the combined call itself fails outright — timeout, connection error, rate limit, or a response that isn't valid JSON at all before any per-module section can even be identified. In this case, **every currently-registered `BatchedReasoningModule` fails together** for this request (`AnalysisErrorReason.BATCH_PROVIDER_ERROR` or `BATCH_MALFORMED_RESPONSE`), because there is only one call and it didn't produce anything to distribute. This is strictly a wider blast radius than the original six-independent-calls design had, and it's the direct, named tradeoff for turning six calls into one — stated plainly rather than discovered later. Mitigation: a bounded retry-with-backoff on the batch call (same policy shape as the original design's per-module retry), and the fact that Metric modules never participate in the batch means an `AnalysisReport` is never *entirely* empty even in this worst case — four of ten modules, and the report structure itself, still come back.
- Malformed or missing individual sections still never get force-parsed or guessed at — same discipline as the original design.

**Coaching Engine:**
- **Must handle a partial `AnalysisReport` gracefully.** Because CIE modules can fail independently (or, now, six at once on a batch failure), the Coaching Engine's input may have some `failed` modules mixed with `ok` ones. It generates recommendations only from what succeeded, and explicitly names what couldn't be assessed this time (e.g., "Topic drift couldn't be evaluated for this session") rather than silently pretending the report was complete or silently producing fewer recommendations with no explanation.
- **A recommendation without a valid citation back to a specific `ok` module/evidence is rejected as malformed output**, same discipline as a CIE reasoning module producing an unparseable response — `CoachingErrorReason.UNCITED_RECOMMENDATION` (or the whole response is `LLM_MALFORMED_RESPONSE` if the shape itself is broken, mirroring the CIE's own reason naming).
- **If every CIE module failed** (the worst case: `AnalysisReport` has nothing usable at all), the Coaching Engine doesn't attempt a recommendation call — it returns a distinct, explicit `NOTHING_TO_COACH` state rather than prompting an LLM with an empty report and hoping for a sensible non-answer.

**Cross-cutting, both engines:** the authentication/cost gap named in the original design's §7 still stands, and this revision makes it somewhat cheaper per request (one CIE reasoning call instead of six) but adds a second engine's LLM call on top (the Coaching Engine's one call) — net effect is roughly neutral to slightly better than the original design, but the underlying gap (no auth in front of any LLM-calling endpoint) is unchanged and still needs closing before either engine is reachable outside local development.

## 8. Example output

Two examples now, matching the two-engine split — an `AnalysisReport` (from the CIE) and, separately, the `CoachingReport` generated from it (by the Coaching Engine). Note `AnalysisReport`'s modules carry evidence but no advice; `CoachingReport`'s recommendations carry advice but always cite where it came from.

**`AnalysisReport` (CIE output — descriptive only):**

```json
{
  "transcript_id": "5b1e2f3a-...",
  "generated_at": "2026-07-27T15:10:00Z",
  "modules": {
    "filler_words": {
      "category": "metric", "status": "ok",
      "rate_per_100_words": 6.2, "band": "moderate",
      "evidence": [{ "segment_index": 3, "start": 12.4, "text": "...um, I think the the plan is solid..." }]
    },
    "speaking_pace": {
      "category": "metric", "status": "ok",
      "words_per_minute": 168, "band": "fast"
    },
    "structural_thinking": {
      "category": "reasoning", "status": "ok",
      "score": 58,
      "structure_detected": "problem → proposed solution, no explicit conclusion",
      "evidence": [{ "segment_index": 5, "note": "no summarizing statement after the proposal" }]
    },
    "topic_drift": {
      "category": "reasoning", "status": "failed",
      "reason": "llm_malformed_response",
      "message": "This module's section of the combined analysis response didn't match the expected shape."
    },
    "confidence_indicators": {
      "category": "hybrid", "status": "ok",
      "hedge_count": 4, "score": 55,
      "evidence": [{ "segment_index": 3, "text": "I think the the plan is solid" }]
    }
  }
}
```

**`CoachingReport` (Coaching Engine output — prescriptive, always cited):**

```json
{
  "transcript_id": "5b1e2f3a-...",
  "generated_at": "2026-07-27T15:10:04Z",
  "recommendations": [
    {
      "priority": 1,
      "message": "End with an explicit takeaway. Right now the plan is proposed but never summarized — the listener has to infer the conclusion themselves.",
      "based_on": { "module": "structural_thinking", "evidence": ["segment_index 5"] }
    },
    {
      "priority": 2,
      "message": "Slow down, especially in the back half — your pace is noticeably faster than a comfortable conversational range.",
      "based_on": { "module": "speaking_pace" }
    },
    {
      "priority": 3,
      "message": "You hedged ('I think') right at your central claim. State the plan plainly first, then add caveats after, so the core point lands with more confidence.",
      "based_on": { "module": "confidence_indicators", "evidence": ["segment_index 3"] }
    }
  ],
  "unavailable": [
    "Topic drift could not be assessed for this session (analysis error) — consider re-running analysis."
  ]
}
```

---

## Implementation note (Sprint 4.2)

Sprint 4.2 built the CIE's foundation — `ModuleRegistry`, `AnalysisEngine`,
and the result schemas — deliberately with **one unified `AnalysisModule`
interface** (`module_name`, `module_type`, `metadata`, `analyze()`)
rather than the two separate Protocols (`AnalysisModule` /
`BatchedReasoningModule`) sketched in §1/§3 above. This is a
simplification, not a reversal of the approved batching requirement: no
LLM code exists yet (Sprint 4.2 explicitly excluded it), so there is
nothing to batch yet either. Every module, including future reasoning
ones, still exposes the same `analyze()` entry point; "share one LLM call
across several reasoning modules" becomes an internal coordination detail
of how their `analyze()` implementations are wired to a shared component
once `app/llm/` and a batching mechanism actually get built, rather than
a distinct interface the registry and engine need to know about today.
Keeping the registry/engine batching-agnostic now avoids committing to
`contribute()`/`interpret()`'s exact shape before there's a real reasoning
module and a real LLM integration to validate it against. `PromptContribution`
and the `contribute()`/`interpret()` split may return, largely as
described in §5, when that sprint arrives — but as an addition layered
onto this foundation, not a rewrite of it. See `backend/app/analysis/README.md`
for the as-built folder structure, data flow, and module-registration
mechanics.

## What this sprint explicitly does not include

Unchanged from the original design's stance, plus two additions: the exact structured-output schema for the combined reasoning request's envelope (which JSON shape wraps per-module sections) and the Coaching Engine's prompt wording/tone are both real decisions left open for the implementing sprint, not fixed here. The API route(s) that trigger either engine, where `AnalysisReport`/`CoachingReport` are persisted, which LLM model backs `app/llm/`'s implementation, and the authentication gap named in §7 all remain open, exactly as the original design left them.

## Implementation note (Sprint 4.5) — the six reasoning modules, and a disclosed gap against §1's batching requirement

Sprint 4.5 built the first six real Reasoning modules — `StructureModule`,
`ClarityModule`, `LogicalFlowModule`, `TopicDriftModule`,
`ConfidenceModule`, `ConcisenessModule` — plus three supporting pieces
this sprint required: a wider per-module input, a two-phase module
execution order, and a categorized, metadata-bearing prompt library.
Three real architecture changes, and one important disclosed gap,
described below.

**1. `AnalysisModule.analyze()` was widened from `analyze(transcript)` to `analyze(context: AnalysisContext)`.**
Sprint 4.5 requires every module receive "transcript, deterministic
metrics, reasoning context" — three things, not one — so
`app/analysis/models.py` gained a new `AnalysisContext` wrapper
(`transcript`, `metrics: dict[str, ModuleResult]`,
`reasoning_context: dict[str, Any]`) and every existing module's
signature was updated to match: the four Sprint 4.3 Metric modules
(`filler_words.py`, `hesitations.py`, `repetitions.py`,
`speaking_pace.py`) now read `context.transcript` instead of taking a
bare transcript directly. This is a genuine, disclosed breaking change
to the interface Sprint 4.2 shipped and Sprint 4.3 built against — every
call site in the codebase and its tests was updated in the same sprint,
and the four Metric modules' own internal logic is unchanged, only what
they're handed changed shape.

**2. `ModuleRegistry.execute()` is now two-phase, not flat registration order.**
Every METRIC module now runs first (in registration order among
themselves), and its results are collected into a `metrics` dict; every
non-METRIC (i.e. REASONING) module then runs next (in registration order
among themselves), each handed an `AnalysisContext` whose `metrics` dict
is fully populated. This is what lets `ConcisenessModule` use
`speaking_pace`'s already-computed words-per-minute and average sentence
length as supporting context for its own LLM prompt, without calling
`SpeakingPaceModule` itself — it's simply handed the finished result,
preserving §7's per-module isolation. The overall result order changed
as a consequence (all metric results, then all reasoning results,
rather than strict flat registration order) — an intentional,
tested change, not an oversight.

**3. Prompts are now categorized and carry structured metadata.**
Per this sprint's explicit requirement, `app/llm/prompt_loader.py` now
requires every prompt file to open with a JSON frontmatter block (`id`,
`version`, `type`, `expected_output`, `model_hints`) before its body —
JSON rather than YAML to avoid a new third-party dependency, consistent
with this codebase's existing stdlib-preference pattern. Real prompts
now live under `app/analysis/reasoning_pass/prompts/analysis/` (six
files, one per reasoning module), with `prompts/coaching/` and
`prompts/rewrite/` created and reserved-empty for the still-unbuilt
Coaching Engine (§2) and a still-unbuilt rewrite module respectively —
matching §3's original `reasoning_pass/` location, now subdivided by
output category rather than left flat.

**4. Every reasoning module validates against one shared `ReasoningResult` schema, via one shared base class.**
Rather than six bespoke output schemas, all six modules validate their
LLM output against the same `ReasoningResult` (`label`, `explanation`,
`evidence`) already defined in `models.py` — structurally enforcing "no
scores, no coaching language" across all six at once, since that schema
has nowhere to put either. The identical orchestration every module
needs (build a template context, call the shared `LLMReasoner`, map any
`LLMError` to a `failed` `ModuleResult`) is factored into one new
`_BaseReasoningModule` (`app/analysis/modules/reasoning_base.py`); each
concrete module supplies only its `prompt_id` and the logic for what
belongs in its own prompt's template variables.

### The disclosed gap: this sprint did NOT implement §1's batching requirement

**This is the one place Sprint 4.5's actual implementation knowingly
deviates from what this ADR's own revision notes (top of this document)
committed to after Sprint 4.1's approval.** §1 requires that reasoning
modules "should not independently call the LLM by default" — that all
six should share **one combined structured-output request** via a
`ReasoningPass`/`BatchedReasoningModule` mechanism, with independent
calls reserved as an opt-in "deep analysis" escape hatch.

What Sprint 4.5 actually built: each of the six reasoning modules calls
the shared `LLMReasoner` abstraction **independently — six separate
calls, not one combined call.** This satisfies Sprint 4.5's own literal
requirements ("every module receives... reasoning context," "no module
should directly call an LLM provider," "all semantic reasoning must flow
through the shared LLMReasoner abstraction" — all true here, since
`LLMReasoner` is the only thing any module talks to) but does **not**
implement the batching this ADR separately committed to. No
`ReasoningPass`, no `contribute()`/`interpret()` split, no combined
prompt envelope were built this sprint.

This was a deliberate scope decision, not an oversight, made for two
reasons: batching is real, separate infrastructure (a shared-prompt
assembler, a combined-response schema, batch-level failure handling per
§7) that Sprint 4.5's own text scoped to six *modules*, not to that
infrastructure; and building it silently, without being asked, risked
guessing at a shape (`contribute()`/`interpret()`'s exact signatures)
this ADR itself already flagged as an open decision for "the
implementing sprint." Rather than silently build around the gap or
silently build the large undertaking batching represents, it's
disclosed here, plainly, the same way §7's batch-level-failure tradeoff
and the original design's auth gap are both named rather than buried.

**Consequence, until a future sprint closes this gap:** every
transcript that runs all six reasoning modules costs six independent
LLM calls, not one — worse latency and cost than this ADR's approved
design, though each call is still isolated per §7's per-module failure
model (one module's `LLMError` cannot affect another's result, which is
actually *better* isolation than batching's "one call, six modules share
its failure" tradeoff named in §7). Closing this gap — building
`ReasoningPass` and migrating these six modules onto it — is explicitly
out of scope for Sprint 4.5 and is flagged here as follow-up work for a
future sprint, not silently deferred.

## Implementation note (Sprint 4.5.1) — the batching gap is closed

Sprint 4.5.1 built `ReasoningPass` and migrated all six reasoning
modules onto it, closing the gap disclosed immediately above. This is
the batching mechanism §1 originally required, adapted to fit on top of
Sprint 4.2's single unified `AnalysisModule` interface (which Sprint 4.2
and 4.5's implementation notes already chose over this document's
original `AnalysisModule`/`BatchedReasoningModule` split) rather than
introducing a second Protocol.

**`ReasoningPass` (`app/analysis/reasoning_pass/batch.py`)** is the one
component that talks to the LLM on behalf of every reasoning dimension.
`ReasoningPass.run(context)`:
1. Gathers the transcript and every deterministic sub-signal any
   dimension needs — the hedge-word count/examples `ConfidenceModule`
   used to compute itself, and the `speaking_pace` metric hints
   `ConcisenessModule` used to read itself, both now computed once in
   `reasoning_pass/signals.py` rather than once per module.
2. Builds one combined prompt (`prompts/analysis/reasoning_pass_v1.md`
   — replacing the six per-dimension prompt files this ADR's Sprint 4.5
   note described; the six-file layout was retired, not kept
   side-by-side, per this sprint's "no duplicated prompts" requirement).
3. Calls `LLMReasoner.reason()` **exactly once**, validating the whole
   response against one new schema, `BatchedReasoningResult` — a plain
   pydantic model with one field per dimension (`structure`, `clarity`,
   `logical_flow`, `topic_drift`, `confidence`, `conciseness`), each
   typed as the same `ReasoningResult` every dimension validated against
   individually before this sprint. One schema, validated once, is what
   satisfies "no duplicated parsing, no duplicated validation" — there
   is exactly one call to `app/llm`'s parse-then-validate pipeline per
   analysis, not six.

**The six concrete reasoning modules no longer call an LLM at all.**
Each now subclasses a new `_SectionReasoningModule`
(`app/analysis/modules/section_reasoning_base.py`) instead of Sprint
4.5's `_BaseReasoningModule`, and does exactly one thing: read its own
field off the `BatchedReasoningResult` `ModuleRegistry` already produced
and pass it through as that module's `ModuleResult`. `AnalysisModule`'s
interface — `module_name`, `module_type`, `metadata`,
`analyze(context)` — is unchanged; from a caller's or the registry's
perspective, nothing about how a reasoning module is registered, typed,
or executed looks any different than before. Construction changed
(these modules take no constructor arguments now, since none of them
need an `LLMReasoner` injected anymore), which is a visible but narrow
break, confined to test/wiring code, not to the interface itself.

**`ModuleRegistry.execute()` owns calling `ReasoningPass` exactly once
per analysis**, between its existing METRIC phase and REASONING phase
(see `app/analysis/registry.py`), and stashes the result into
`AnalysisContext.reasoning_context` under a shared, well-known key —
the first real use of that field, which Sprint 4.5 deliberately left as
an open, unused extensibility hook for exactly this kind of need. Two
degraded paths, both per-reasoning-module rather than a whole-request
failure: no `ReasoningPass` configured (each reasoning module fails
`NO_PROVIDER_CONFIGURED` without `analyze()` ever running), and the one
combined call itself failing (every reasoning module fails together with
the same translated reason — §7's disclosed "batch-level failure"
tradeoff, now real code, not just a named risk).

**`_BaseReasoningModule` (Sprint 4.5's per-module orchestration) is kept,
not deleted** — it's exactly this document's §1 "deep analysis" escape
hatch: a future dimension whose needs don't fit the shared batched
prompt can still subclass it and make its own independent `LLMReasoner`
call. No concrete module uses it today; it remains real, tested
infrastructure (`tests/test_reasoning_base_escape_hatch.py`), not
aspirational text.

**Benchmarks** (`tests/test_reasoning_pass_benchmarks.py`, measured
against a simulated 50ms-per-call `LLMReasoner`, not a real provider —
no test in this codebase calls a real LLM):

| | LLM calls per analysis | Simulated wall-clock time |
|---|---|---|
| Previous (Sprint 4.5) | 6 | ~0.35s |
| Current (Sprint 4.5.1) | 1 | ~0.06s |
| Reduction | 6.0x fewer calls | ~5.8x faster |

The call-count reduction (6 → 1) is exact and architectural, true
regardless of real-provider latency. The latency figure is illustrative
of the *shape* of the win (avoiding N sequential round-trips), not a
prediction of any specific real provider's actual response time — that
depends on the provider ultimately wired in, which remains unbuilt (§7's
authentication/provider gap, unchanged by this sprint).
