"""
Concrete `LLMProvider` implementations (Milestone 5.1).

Nothing in `app/llm/` above this package changed to make these possible —
`provider.py`'s Protocol was deliberately built in Sprint 4.4 so any of
these could be added later without touching `LLMReasoner`,
`ReasoningPass`, `CoachingEngine`, or any prompt. Each adapter here does
exactly what `provider.py`'s docstring asks of it: turn a prompt string
into a text response, exposing `provider_name`/`model_name`/`version`,
and raising plain exceptions on failure for `LLMReasoner` to classify.

See `factory.py` for how one of these four gets selected from
`app/core/config.py`'s `Settings.llm_provider`.
"""
