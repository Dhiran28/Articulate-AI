<!--
  Test fixture for PromptLoader/PromptRegistry (Sprint 4.4).
  NOT a real reasoning-module prompt — see structure_v1.md for why.
-->
Evaluate whether the following transcript stays on topic.

Transcript:
$transcript

Respond with a single JSON object matching this shape:
{"label": "<on_topic|drifted>", "explanation": "<one sentence>"}
