<!--
  Test fixture for PromptLoader/PromptRegistry (Sprint 4.4).
  NOT a real reasoning-module prompt — see structure_v1.md for why.
-->
Evaluate the clarity of the following transcript, spoken by $speaker.

Transcript:
$transcript

Respond with a single JSON object matching this shape:
{"label": "<clear|unclear>", "explanation": "<one sentence>"}
