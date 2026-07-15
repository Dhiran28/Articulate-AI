---
{
  "id": "clarity_v1",
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
Evaluate the clarity of the following transcript, spoken by $speaker.

Transcript:
$transcript

Respond with a single JSON object matching this shape:
{"label": "<clear|unclear>", "explanation": "<one sentence>"}
