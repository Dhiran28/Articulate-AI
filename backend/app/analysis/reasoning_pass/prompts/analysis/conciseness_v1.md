---
{
  "id": "conciseness_v1",
  "version": "1.0.0",
  "type": "analysis",
  "expected_output": "ReasoningResult",
  "model_hints": {"temperature": 0.2}
}
---
You are evaluating the CONCISENESS of a spoken transcript — whether the
speaker communicates their point efficiently, or pads it with
unnecessary words, redundant phrasing, or over-explanation.

For reference, deterministic measurements of this transcript's delivery
were: words per minute = $words_per_minute, average sentence length
(words) = $average_sentence_length. ("unknown" means that measurement
wasn't available.) Use these only as supporting context — pace and
sentence length are not the same thing as conciseness of *ideas*, which
is what you are judging.

Transcript:
$transcript

Respond with a single JSON object, and nothing else, matching this
shape:
{
  "label": "<a short label, e.g. 'concise', 'somewhat_padded', 'verbose'>",
  "explanation": "<one or two sentences explaining the judgment>",
  "evidence": [
    {"quote": "<short verbatim excerpt from the transcript>", "note": "<why this excerpt supports the judgment>"}
  ]
}
