<!--
  Test fixture for PromptLoader/PromptRegistry (Sprint 4.4).
  NOT a real reasoning-module prompt — Sprint 4.4 explicitly builds no
  reasoning modules. Once the Structural Thinking module is actually
  built (a future sprint), its real prompt will live under
  app/analysis/reasoning_pass/prompts/, per ADR 003 §3.
-->
Evaluate the structure of the following transcript.

Transcript:
$transcript

Respond with a single JSON object matching this shape:
{"label": "<short structure label>", "explanation": "<one sentence>"}
