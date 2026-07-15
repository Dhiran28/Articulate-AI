---
{
  "id": "logical_flow_v1",
  "version": "1.0.0",
  "type": "analysis",
  "expected_output": "ReasoningResult",
  "model_hints": {"temperature": 0.2}
}
---
You are evaluating the LOGICAL FLOW of a spoken transcript — whether
each idea follows sensibly from the one before it, and whether
transitions between ideas make sense. This is distinct from overall
structure (the shape of the whole) and distinct from clarity (whether
individual statements are easy to understand) — focus only on whether
the sequence of ideas holds together logically.

Transcript:
$transcript

Respond with a single JSON object, and nothing else, matching this
shape:
{
  "label": "<a short label, e.g. 'coherent_flow', 'minor_disconnects', 'disjointed'>",
  "explanation": "<one or two sentences explaining the judgment>",
  "evidence": [
    {"quote": "<short verbatim excerpt from the transcript>", "note": "<why this excerpt supports the judgment>"}
  ]
}
