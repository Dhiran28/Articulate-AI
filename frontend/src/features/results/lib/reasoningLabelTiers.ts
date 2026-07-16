/**
 * Each reasoning dimension's exact three-value label vocabulary, in the
 * same strongest-to-weakest order the backend prompt defines them (see
 * backend/app/analysis/reasoning_pass/prompts/analysis/reasoning_pass_v1.md
 * and app/scoring/dimension_scores.py's `REASONING_LABEL_BANDS`, which
 * this mirrors for display purposes only — the actual 100/60/20 scoring
 * already happened on the backend before this ever reaches the
 * frontend).
 */
const LABEL_ORDER: Record<string, string[]> = {
  structure: ["clear_structure", "partial_structure", "no_structure"],
  clarity: ["clear", "somewhat_unclear", "unclear"],
  logical_flow: ["coherent_flow", "minor_disconnects", "disjointed"],
  topic_drift: ["on_topic", "minor_drift", "significant_drift"],
  confidence: ["confident", "somewhat_hesitant", "uncertain"],
  conciseness: ["concise", "somewhat_padded", "verbose"],
};

const TIER_COLORS = ["#16a34a", "#d97706", "#dc2626"] as const; // emerald, amber, red
const UNKNOWN_TIER_COLOR = "#6b7280"; // gray-500, for a label the model produced outside the documented vocabulary

export function colorForReasoningLabel(moduleName: string, label: string | null): string {
  if (!label) return UNKNOWN_TIER_COLOR;
  const order = LABEL_ORDER[moduleName];
  const tier = order?.indexOf(label) ?? -1;
  return tier >= 0 ? TIER_COLORS[tier] : UNKNOWN_TIER_COLOR;
}

/** Turns a label like "somewhat_hesitant" into "Somewhat Hesitant" for display. */
export function formatReasoningLabel(label: string | null): string {
  if (!label) return "Not available";
  return label
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}
