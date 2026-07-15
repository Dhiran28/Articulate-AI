---
{
  "id": "clarity_v1",
  "version": "1.0.0",
  "type": "analysis",
  "expected_output": "ReasoningResult",
  "model_hints": {"temperature": 0.2}
}
---
You are evaluating the CLARITY of a spoken transcript — how easy it
would be for a listener, hearing this once, to follow and understand
the speaker's point. Do not evaluate structure, pacing, or confidence;
those are evaluated elsewhere.

Transcript:
$transcript

Consider: plain language versus unexplained jargon, ambiguous
pronouns or references, and whether the core point is ever stated
plainly.

Respond with a single JSON object, and nothing else, matching this
shape:
{
  "label": "<a short clarity label, e.g. 'clear', 'somewhat_unclear', 'hard_to_follow'>",
  "explanation": "<one or two sentences explaining the judgment>",
  "evidence": [
    {"quote": "<short verbatim excerpt from the transcript>", "note": "<why this excerpt supports the judgment>"}
  ]
}
