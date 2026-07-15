---
{
  "id": "topic_drift_v1",
  "version": "1.0.0",
  "type": "analysis",
  "expected_output": "ReasoningResult",
  "model_hints": {"temperature": 0.2}
}
---
You are evaluating TOPIC DRIFT in a spoken transcript — whether the
speaker stays on their apparent subject or wanders into unrelated
territory over the course of the transcript.

Transcript:
$transcript

Respond with a single JSON object, and nothing else, matching this
shape:
{
  "label": "<'on_topic' or 'drifted'>",
  "explanation": "<one or two sentences explaining the judgment>",
  "evidence": [
    {"quote": "<short verbatim excerpt from the transcript>", "note": "<why this excerpt supports the judgment, e.g. marks where drift begins>"}
  ]
}
