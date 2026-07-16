import { describe, expect, it } from "vitest";

import { formatMetricValue, getMetricHighlights } from "./metricHighlights";

describe("formatMetricValue", () => {
  it("formats a words-per-minute value with its unit label", () => {
    expect(formatMetricValue(142, "words_per_minute")).toBe("142 wpm");
  });

  it("formats a plain count without a unit suffix", () => {
    expect(formatMetricValue(3, "count")).toBe("3");
  });

  it("returns an em dash placeholder for a null value", () => {
    expect(formatMetricValue(null, "count")).toBe("—");
  });

  it("falls back to '<value> <unit>' for an unrecognized unit", () => {
    expect(formatMetricValue(5, "widgets")).toBe("5 widgets");
  });
});

describe("getMetricHighlights", () => {
  it("surfaces filler_words' frequency and most common fillers", () => {
    const highlights = getMetricHighlights("filler_words", {
      frequency_per_100_words: 3.03,
      top_fillers: [{ word: "um", count: 2 }],
    });
    expect(highlights).toContainEqual({ label: "Per 100 words", value: "3.03" });
    expect(highlights.some((h) => h.value.includes("um"))).toBe(true);
  });

  it("surfaces hesitations' total pause time and long pause count", () => {
    const highlights = getMetricHighlights("hesitations", {
      total_pause_seconds: 4.2,
      long_pauses: [{ start: 1 }, { start: 5 }],
    });
    expect(highlights).toContainEqual({ label: "Total pause time", value: "4.2s" });
    expect(highlights).toContainEqual({ label: "Long pauses", value: "2" });
  });

  it("returns an empty list for a module it doesn't know, rather than throwing", () => {
    expect(getMetricHighlights("some_future_module", { anything: true })).toEqual([]);
  });

  it("omits a highlight whose underlying detail is missing", () => {
    const highlights = getMetricHighlights("filler_words", {});
    expect(highlights).toEqual([]);
  });
});
