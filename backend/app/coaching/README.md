# Coaching (Milestone 5)

`app/coaching/` is ADR 003 §1/§2's deferred second engine, built:
consumes the Communication Intelligence Engine's `AnalysisReport` (never
the transcript itself) and produces prescriptive, evidence-cited
coaching output.

## Folder structure

```
backend/app/coaching/
├── models.py    # CoachingContent (LLM-validated), CoachingReport, CoachingInsight,
│                #   Recommendation, SuggestedExercise
├── errors.py     # CoachingErrorReason, CoachingError
├── engine.py      # CoachingEngine — the one LLM call
└── summary.py     # CommunicationSummaryGenerator — no LLM call
```

The real prompt lives at
`app/analysis/reasoning_pass/prompts/coaching/coaching_v1.md` — the
`prompts/coaching/` location Sprint 4.5 reserved specifically for this
purpose (ADR 003 §3), now filled in rather than left empty.

## `CoachingEngine`

`CoachingEngine.generate(report: AnalysisReport) -> CoachingReport`
makes exactly **one** `LLMReasoner.reason()` call, over a JSON
serialization of every `status == OK` module in the report (never the
transcript — `AnalysisReport` is the only input this class ever reads),
validated against `CoachingContent`. Every strength, weakness, and
recommendation the prompt produces must cite the exact module key it's
grounded in (`based_on_module`) — the same citation discipline ADR 003
§5 named for the Coaching Engine before it existed.

`reasoner: LLMReasoner | None` — mirrors `ModuleRegistry`'s own
`reasoning_pass: ReasoningPass | None`. A server with no LLM provider
configured can still construct a `CoachingEngine`; calling `generate()`
raises a specific `CoachingError(NO_PROVIDER_CONFIGURED)` rather than
never being constructible.

### Failure modes

Unlike the CIE's per-module isolation, `CoachingEngine.generate()` is a
**whole-request** failure: there's exactly one LLM call behind the
entire coaching output, so any failure (no provider, timeout, malformed
response, every CIE module having failed) raises `CoachingError` rather
than returning a partial result. See `errors.py` for the full reason
list — five of its seven values share identical string values with
`LLMErrorReason` (app/llm/errors.py) for the same "direct, lossless
mapping" reason every other LLM-error boundary in this codebase does.

## `CommunicationSummaryGenerator`

Takes the `executive_summary` text `CoachingEngine`'s one call already
produced (as part of `CoachingContent` — see models.py) and applies
deterministic, dashboard-appropriate formatting: whitespace
normalization and a length ceiling with word-boundary truncation.
**Makes no LLM call of its own** — asking the model a second time to
"now summarize the summary" would be a duplicate request over the same
underlying judgment, exactly what Sprint 4.5.1 eliminated for the six
reasoning dimensions.

## How a future consumer of `AnalysisReport` gets added

`CoachingEngine` and `CommunicationSummaryGenerator` are one example of
"something downstream of the CIE" — `ScoringEngine` (app/scoring/) is
another, built the same milestone, reading the same `AnalysisReport`
independently. Neither one calls the other, and neither is a dependency
of `AnalysisEngine` — the CIE has no idea either of them exists, the
same one-way dependency direction ADR 003 §1 designed from the start.
