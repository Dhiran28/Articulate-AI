"""
CommunicationSummaryGenerator (Milestone 5) — the "Communication Summary
Generator" component the sprint asks for, kept genuinely separate from
`CoachingEngine` even though it makes no LLM call of its own.

Why no second LLM call: `CoachingEngine`'s one coaching request already
produces `executive_summary` as part of `CoachingContent` (see
models.py) — asking the LLM a second, separate time for "now summarize
it for a dashboard" would be a duplicate request over the same
underlying judgment, exactly the kind of redundant call Sprint 4.5.1
was built to eliminate. This class's real job is the deterministic,
dashboard-specific formatting layer on top of that text: enforcing a
length ceiling appropriate for a dashboard card, and normalizing
whitespace — concerns that have nothing to do with LLM reasoning and
everything to do with where the text is displayed, which is exactly the
kind of thing that should be deterministic, testable Python, not one
more thing asked of the model.
"""

from app.coaching.models import CoachingReport

DASHBOARD_SUMMARY_MAX_LENGTH = 400
"""
A deliberately round ceiling for a dashboard summary card — long enough
for a few sentences of real content, short enough not to require
scrolling in a compact UI element. Not tied to any specific frontend
component's actual pixel budget (the frontend doesn't exist yet at this
milestone); a future frontend sprint may need to revisit this number
once a real layout exists to measure against.
"""


class CommunicationSummaryGenerator:
    def generate(self, coaching_report: CoachingReport) -> str:
        summary = " ".join(coaching_report.executive_summary.split())  # normalize whitespace/newlines

        if len(summary) > DASHBOARD_SUMMARY_MAX_LENGTH:
            # Truncate on a word boundary rather than mid-word, then mark
            # the truncation explicitly with an ellipsis rather than
            # silently cutting the sentence off.
            truncated = summary[:DASHBOARD_SUMMARY_MAX_LENGTH].rsplit(" ", 1)[0]
            summary = truncated.rstrip(".,;: ") + "…"

        return summary
