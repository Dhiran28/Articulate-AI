# Reporting (Milestone 5)

`app/reporting/` is the Report Builder — the last stage before
`POST /analyze`'s JSON response. Deliberately the smallest package in
this codebase: one model, one builder class, no business logic.

## Folder structure

```
backend/app/reporting/
├── models.py    # CommunicationReport
└── builder.py     # ReportBuilder
```

## `CommunicationReport`

The single response shape for `POST /analyze`:

```
CommunicationReport
├── transcript_id: str
├── generated_at: datetime
├── executive_summary: str        (CommunicationSummaryGenerator's output)
├── score: CommunicationScore     (app/scoring/)
├── analysis: AnalysisReport      (app/analysis/ — ADR 003)
└── coaching: CoachingReport      (app/coaching/)
```

Every field is exactly the pydantic model its owning engine already
produces and already has its own tests for — this package doesn't
flatten, rename, or re-derive anything from them.

## `ReportBuilder`

`ReportBuilder.build(...)` takes the four already-finished pieces above
and returns one `CommunicationReport`. No validation, no error
handling, no I/O — every decision that could fail already happened
upstream (in `AnalysisEngine`, `ScoringEngine`, `CoachingEngine`, or
`CommunicationSummaryGenerator`), so by the time `ReportBuilder` runs,
assembly is the only thing left to do. The same "engine.py deliberately
thin" discipline `AnalysisEngine` and `ReasoningPass` already hold
themselves to.
