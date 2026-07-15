---
{
  "id": "topic_drift_v1",
  "version": "1.0.0",
  "type": "analysis",
  "expected_output": "ReasoningResult",
  "model_hints": {"temperature": 0.2}
}
---
<!--
  Test fixture for PromptLoader/PromptRegistry (Sprint 4.4/4.5).
  NOT a real reasoning-module prompt — see structure_v1.md for why.
-->
Evaluate whether the following transcript stays on topic.

Transcript:
$transcript

Respond with a single JSON object matching this shape:
{"label": "<on_topic|drifted>", "explanation": "<one sentence>"}
