import type { ScoreBand } from "../types";

/**
 * One color per score band, used consistently across the badge, the
 * gauge chart, and the per-module bar chart — so "strong" always reads
 * as the same color everywhere on the Results page, rather than each
 * chart picking its own palette independently.
 */
export const SCORE_BAND_COLORS: Record<ScoreBand, string> = {
  excellent: "#16a34a", // emerald-600
  strong: "#2563eb", // blue-600
  developing: "#d97706", // amber-600
  needs_work: "#dc2626", // red-600
};

export const SCORE_BAND_BADGE_CLASSES: Record<ScoreBand, string> = {
  excellent: "bg-emerald-100 text-emerald-800 border-emerald-200",
  strong: "bg-blue-100 text-blue-800 border-blue-200",
  developing: "bg-amber-100 text-amber-800 border-amber-200",
  needs_work: "bg-red-100 text-red-800 border-red-200",
};

/**
 * A module's individual 0-100 score doesn't carry its own `band` field
 * (only the overall score does — see CommunicationScore in types.ts).
 * This mirrors the backend's own anchor-score thresholds
 * (app/scoring/weights.py's SCORE_BAND_THRESHOLDS) so a module score's
 * color matches what that same number would mean as an overall score.
 */
export function bandForScore(score: number): ScoreBand {
  if (score >= 85) return "excellent";
  if (score >= 65) return "strong";
  if (score >= 40) return "developing";
  return "needs_work";
}
