---
{
  "id": "structure_v1",
  "version": "1.0.0",
  "type": "analysis",
  "expected_output": "ReasoningResult",
  "model_hints": {"temperature": 0.2}
}
---
<!--
  Test fixture for PromptLoader/PromptRegistry (Sprint 4.4/4.5).
  NOT a real reasoning-module prompt — Sprint 4.4 explicitly builds no
  reasoning modules. Real prompts live under
  app/analysis/reasoning_pass/prompts/analysis/, per ADR 003 §3.
-->
Evaluate the structure of the following transcript.

Transcript:
$transcript

Respond with a single JSON object matching this shape:
{"label": "<short structure label>", "explanation": "<one sentence>"}
