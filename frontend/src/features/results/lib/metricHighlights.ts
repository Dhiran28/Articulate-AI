/**
 * Each metric module's `details` bag is an intentionally open
 * `dict[str, Any]` on the backend (see MetricResult in
 * backend/app/analysis/models.py) — there's no shared schema across the
 * four metric modules to render generically. Rather than dumping every
 * key of that bag onto the card, this picks the two or three details
 * actually worth a user's attention per module, by name. An unknown
 * module (or a detail this list doesn't know about) simply shows none
 * — never a crash, never raw JSON.
 */
export interface MetricHighlight {
  label: string;
  value: string;
}

function round(value: unknown, digits = 1): string | null {
  if (typeof value !== "number" || !Number.isFinite(value)) return null;
  return value.toFixed(digits);
}

export function getMetricHighlights(moduleName: string, details: Record<string, unknown>): MetricHighlight[] {
  switch (moduleName) {
    case "filler_words": {
      const highlights: MetricHighlight[] = [];
      const frequency = round(details.frequency_per_100_words, 2);
      if (frequency) highlights.push({ label: "Per 100 words", value: frequency });
      const topFillers = details.top_fillers;
      if (Array.isArray(topFillers) && topFillers.length > 0) {
        const summary = topFillers
          .slice(0, 3)
          .map((entry) => (entry && typeof entry === "object" ? `"${(entry as { word?: string }).word}"` : null))
          .filter(Boolean)
          .join(", ");
        if (summary) highlights.push({ label: "Most common", value: summary });
      }
      return highlights;
    }
    case "hesitations": {
      const highlights: MetricHighlight[] = [];
      const totalPause = round(details.total_pause_seconds, 1);
      if (totalPause) highlights.push({ label: "Total pause time", value: `${totalPause}s` });
      const longPauses = details.long_pauses;
      if (Array.isArray(longPauses)) highlights.push({ label: "Long pauses", value: String(longPauses.length) });
      return highlights;
    }
    case "repetitions": {
      const highlights: MetricHighlight[] = [];
      const repeatedPhrases = details.repeated_phrases;
      if (Array.isArray(repeatedPhrases) && repeatedPhrases.length > 0) {
        const top = repeatedPhrases[0] as { phrase?: string; count?: number };
        if (top?.phrase) highlights.push({ label: "Most repeated", value: `"${top.phrase}" (${top.count}x)` });
      }
      return highlights;
    }
    case "speaking_pace": {
      const highlights: MetricHighlight[] = [];
      const sentenceLength = round(details.average_sentence_length, 1);
      if (sentenceLength) highlights.push({ label: "Avg. sentence length", value: `${sentenceLength} words` });
      const longestPause = round(details.longest_pause_seconds, 1);
      if (longestPause) highlights.push({ label: "Longest pause", value: `${longestPause}s` });
      return highlights;
    }
    default:
      return [];
  }
}

const UNIT_LABELS: Record<string, (value: number) => string> = {
  count: (value) => `${value}`,
  words_per_minute: (value) => `${value} wpm`,
};

export function formatMetricValue(value: number | null, unit: string | null): string {
  if (value === null) return "—";
  if (unit && UNIT_LABELS[unit]) return UNIT_LABELS[unit](value);
  return unit ? `${value} ${unit}` : `${value}`;
}
