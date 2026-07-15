---
{
  "id": "reasoning_pass_v1",
  "version": "1.0.0",
  "type": "analysis",
  "expected_output": "BatchedReasoningResult",
  "model_hints": {"temperature": 0.2}
}
---
You are evaluating a spoken transcript across six independent
dimensions in a single pass. Judge each dimension on its own terms —
do not let one dimension's judgment bleed into another's (for example,
a rambling but well-structured transcript should score differently on
STRUCTURE than on CONCISENESS).

Transcript:
$transcript

For reference, two deterministic measurements of this transcript are
available. Use them only as supporting context for the dimensions they
relate to (CONFIDENCE and CONCISENESS respectively) — form your own
independent judgment from the full transcript rather than relying on
these numbers alone:
- Approximately $hedge_word_count hedging phrases were found (e.g. "I
  think," "sort of," "maybe"). Examples: $hedge_word_examples.
- Words per minute: $words_per_minute. Average sentence length (words):
  $average_sentence_length. ("unknown" means that measurement wasn't
  available.)

Evaluate each of these six dimensions. For every dimension, you must
pick exactly one label from that dimension's fixed set of three — never
invent your own wording for `label`. The three options for each
dimension always run from strongest to weakest so a downstream system
can interpret them consistently:

1. STRUCTURE — Does the transcript have a recognizable structural
   shape (for example: framing/context, body, and a close; a clear
   problem-then-solution arc; a clearly-signposted list of points)?
   Label must be one of: "clear_structure", "partial_structure", "no_structure".

2. CLARITY — How easy would it be for a listener, hearing this once,
   to follow and understand the speaker's point? Consider plain
   language versus unexplained jargon, ambiguous pronouns or
   references, and whether the core point is ever stated plainly.
   Label must be one of: "clear", "somewhat_unclear", "unclear".

3. LOGICAL_FLOW — Does each idea follow sensibly from the one before
   it? Do transitions between ideas make sense? This is distinct from
   STRUCTURE (the shape of the whole) — focus only on whether the
   sequence of ideas holds together logically.
   Label must be one of: "coherent_flow", "minor_disconnects", "disjointed".

4. TOPIC_DRIFT — Does the speaker stay on their apparent subject, or
   wander into unrelated territory over the course of the transcript?
   Label must be one of: "on_topic", "minor_drift", "significant_drift".

5. CONFIDENCE — How confidently does the speaker come across, based on
   word choice and framing (not audio tone, which is not available to
   you)? Use the hedge-word count above only as a starting point — a
   transcript can hedge occasionally while still sounding confident
   overall, and one with no hedges can still sound uncertain for other
   reasons.
   Label must be one of: "confident", "somewhat_hesitant", "uncertain".

6. CONCISENESS — Does the speaker communicate their point efficiently,
   or pad it with unnecessary words, redundant phrasing, or
   over-explanation? Use the pace/sentence-length figures above only as
   supporting context — pace and sentence length are not the same thing
   as conciseness of *ideas*, which is what you are judging.
   Label must be one of: "concise", "somewhat_padded", "verbose".

None of these six dimensions are evaluations of filler words,
hesitations, repetitions, or speaking pace themselves — those are
measured deterministically elsewhere and are given to you above only as
supporting signal for CONFIDENCE and CONCISENESS.

Use `explanation` and `evidence` for the nuance a three-value label
can't carry on its own — the label is a coarse, machine-readable bucket
used for scoring; the explanation and evidence are what a human reads.

Respond with a single JSON object, and nothing else, containing exactly
these six keys — "structure", "clarity", "logical_flow", "topic_drift",
"confidence", "conciseness" — each one an object of this shape:
{
  "label": "<one of that dimension's exact three allowed values above>",
  "explanation": "<one or two sentences explaining the judgment>",
  "evidence": [
    {"quote": "<short verbatim excerpt from the transcript>", "note": "<why this excerpt supports the judgment>"}
  ]
}

Example (illustrative only — do not copy these values):
{
  "structure": {"label": "clear_structure", "explanation": "...", "evidence": [{"quote": "...", "note": "..."}]},
  "clarity": {"label": "clear", "explanation": "...", "evidence": []},
  "logical_flow": {"label": "coherent_flow", "explanation": "...", "evidence": []},
  "topic_drift": {"label": "on_topic", "explanation": "...", "evidence": []},
  "confidence": {"label": "confident", "explanation": "...", "evidence": []},
  "conciseness": {"label": "concise", "explanation": "...", "evidence": []}
}
