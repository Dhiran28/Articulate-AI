---
{
  "id": "structure_v1",
  "version": "1.0.0",
  "type": "analysis",
  "expected_output": "ReasoningResult",
  "model_hints": {"temperature": 0.2}
}
---
You are evaluating the STRUCTURE of a spoken transcript — not its
grammar, not its content quality, only whether the speaker organized
their thoughts in a recognizable shape (for example: framing/context,
body, and a close; or a clear problem-then-solution arc; or a
clearly-signposted list of points).

Transcript:
$transcript

Judge only structural organization. Do not comment on filler words,
pacing, or confidence — those are evaluated elsewhere.

Respond with a single JSON object, and nothing else, matching this
shape:
{
  "label": "<a short structure label, e.g. 'clear_three_part_structure', 'no_recognizable_structure', 'structured_but_unbalanced'>",
  "explanation": "<one or two sentences explaining the judgment>",
  "evidence": [
    {"quote": "<short verbatim excerpt from the transcript>", "note": "<why this excerpt supports the judgment>"}
  ]
}
