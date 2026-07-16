# Reporting (Milestone 5, `transcript` field added Milestone 6)

`app/reporting/` is the Report Builder — the last stage before
`POST /analyze`'s JSON response. Deliberately the smallest package in
this codebase: one model, one builder class, no business logic.

## Folder structure

```
backend/app/reporting/
├── models.py    # CommunicationReport, PromptVersions
└── builder.py     # ReportBuilder
```

## `CommunicationReport`

The single response shape for `POST /analyze`:

```
CommunicationReport
├── transcript_id: str
├── generated_at: datetime
├── executive_summary: str        (CommunicationSummaryGenerator's output)
├── transcript: str                (Milestone 6 — see note below)
├── score: CommunicationScore     (app/scoring/)
├── analysis: AnalysisReport      (app/analysis/ — ADR 003)
├── coaching: CoachingReport      (app/coaching/)
└── prompt_versions: PromptVersions (Milestone 5.1)
```

Every field except `transcript` is exactly the pydantic model its
owning engine already produces and already has its own tests for — this
package doesn't flatten, rename, or re-derive anything from them.

**`transcript` (Milestone 6):** the one explicitly user-approved
exception to that milestone's otherwise-frozen backend. The frontend's
Transcript Viewer needed the verbatim processed transcript text, and
`/analyze`'s response had no field for it anywhere — every other field
here describes *judgments about* the transcript (metrics, reasoning
labels, coaching), never the transcript itself. `app/api/analyze.py`
passes `processed_transcript.processed_transcript.text` — text it
already had in hand for `AnalysisEngine.run()` — straight through to
`ReportBuilder.build()`'s new, required `transcript` parameter. No
existing field, engine interface, or endpoint contract changed; this is
strictly additive.

## `ReportBuilder`

`ReportBuilder.build(...)` takes the already-finished pieces above and
returns one `CommunicationReport`. No validation, no error handling, no
I/O — every decision that could fail already happened upstream (in
`AnalysisEngine`, `ScoringEngine`, `CoachingEngine`, or
`CommunicationSummaryGenerator`), so by the time `ReportBuilder` runs,
assembly is the only thing left to do. The same "engine.py deliberately
thin" discipline `AnalysisEngine` and `ReasoningPass` already hold
themselves to.
