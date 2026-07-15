---
{
  "id": "confidence_v1",
  "version": "1.0.0",
  "type": "analysis",
  "expected_output": "ReasoningResult",
  "model_hints": {"temperature": 0.2}
}
---
You are evaluating how CONFIDENT the speaker sounds in this transcript
— their command of the material and certainty in what they're saying,
based on word choice and framing (not on audio tone, which is not
available to you).

As a deterministic starting signal, this transcript contains
approximately $hedge_word_count hedging phrases (e.g. "I think," "sort
of," "maybe"). Examples found: $hedge_word_examples. Use this only as a
starting point — a transcript can hedge occasionally while still
sounding confident overall, and one with no hedges can still sound
uncertain for other reasons. Form your own independent judgment from the
full transcript.

Transcript:
$transcript

Respond with a single JSON object, and nothing else, matching this
shape:
{
  "label": "<a short label, e.g. 'confident', 'somewhat_hesitant', 'uncertain'>",
  "explanation": "<one or two sentences explaining the judgment>",
  "evidence": [
    {"quote": "<short verbatim excerpt from the transcript>", "note": "<why this excerpt supports the judgment>"}
  ]
}
