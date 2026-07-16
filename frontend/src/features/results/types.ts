/**
 * TypeScript mirror of the backend's `CommunicationReport` response
 * shape (`POST /api/analyze` — see backend/app/reporting/models.py and
 * docs/api.md). Deliberately kept as one file of plain interfaces, not
 * generated from the backend's OpenAPI schema: this project has no
 * codegen step yet, and hand-mirroring a frozen, versioned backend
 * contract (ADR 004) is a reasonable, honestly-scoped tradeoff for an
 * MVP — see the frontend README for that disclosed limitation.
 *
 * Every field name and nesting here matches the backend pydantic model
 * it mirrors exactly (snake_case preserved, not camelCased) so a reader
 * can cross-reference this file against the backend source directly
 * without a translation step.
 */

export type ModuleType = "metric" | "reasoning";
export type ModuleStatus = "ok" | "failed";

export interface ResultMetadata {
  module_name: string;
  module_type: ModuleType;
  generated_at: string;
  description: string | null;
}

export interface MetricResult {
  value: number | null;
  unit: string | null;
  details: Record<string, unknown>;
}

export interface EvidenceItem {
  quote?: string;
  note?: string;
  [key: string]: unknown;
}

export interface ReasoningResult {
  label: string | null;
  explanation: string | null;
  evidence: EvidenceItem[];
}

export interface ModuleErrorDetail {
  reason: string;
  message: string;
}

export interface ModuleResult {
  metadata: ResultMetadata;
  status: ModuleStatus;
  metric: MetricResult | null;
  reasoning: ReasoningResult | null;
  error: ModuleErrorDetail | null;
}

export interface AnalysisReport {
  transcript_id: string;
  generated_at: string;
  modules: Record<string, ModuleResult>;
}

export type ScoreBand = "excellent" | "strong" | "developing" | "needs_work";

export interface ModuleScore {
  module_name: string;
  score: number;
  nominal_weight: number;
  effective_weight: number;
  driver: string;
}

export interface CommunicationScore {
  overall_score: number;
  band: ScoreBand;
  module_scores: ModuleScore[];
  unscored_modules: string[];
}

export interface CoachingInsight {
  message: string;
  based_on_module: string;
}

export interface Recommendation {
  message: string;
  based_on_module: string;
  priority: number;
}

export interface SuggestedExercise {
  title: string;
  description: string;
  based_on_module: string | null;
}

export interface CoachingReport {
  transcript_id: string;
  generated_at: string;
  strengths: CoachingInsight[];
  weaknesses: CoachingInsight[];
  recommendations: Recommendation[];
  suggested_exercises: SuggestedExercise[];
  next_practice_focus: string;
  executive_summary: string;
  unavailable: string[];
}

export interface PromptVersions {
  reasoning_pass: string | null;
  coaching: string | null;
}

/**
 * The single response shape for `POST /api/analyze`. `transcript` is a
 * Milestone 6 addition to the backend (see ADR 004 §8) — the one field
 * added specifically so this page's Transcript Viewer has real content
 * to show.
 */
export interface CommunicationReport {
  transcript_id: string;
  generated_at: string;
  executive_summary: string;
  transcript: string;
  score: CommunicationScore;
  analysis: AnalysisReport;
  coaching: CoachingReport;
  prompt_versions: PromptVersions;
}

/** The six reasoning dimensions, in the fixed order the backend prompt defines them. */
export const REASONING_MODULE_ORDER = [
  "structure",
  "clarity",
  "logical_flow",
  "topic_drift",
  "confidence",
  "conciseness",
] as const;

/** The four deterministic metric dimensions, in the order the scoring engine's fluency tier lists them. */
export const METRIC_MODULE_ORDER = [
  "filler_words",
  "hesitations",
  "repetitions",
  "speaking_pace",
] as const;

const MODULE_DISPLAY_NAMES: Record<string, string> = {
  structure: "Structure",
  clarity: "Clarity",
  logical_flow: "Logical Flow",
  topic_drift: "Topic Drift",
  confidence: "Confidence",
  conciseness: "Conciseness",
  filler_words: "Filler Words",
  hesitations: "Hesitations",
  repetitions: "Repetitions",
  speaking_pace: "Speaking Pace",
};

export function moduleDisplayName(moduleName: string): string {
  return MODULE_DISPLAY_NAMES[moduleName] ?? moduleName;
}

const SCORE_BAND_LABELS: Record<ScoreBand, string> = {
  excellent: "Excellent",
  strong: "Strong",
  developing: "Developing",
  needs_work: "Needs Work",
};

export function scoreBandLabel(band: ScoreBand): string {
  return SCORE_BAND_LABELS[band];
}
