import { describe, expect, it } from "vitest";

import { colorForReasoningLabel, formatReasoningLabel } from "./reasoningLabelTiers";

describe("formatReasoningLabel", () => {
  it("title-cases a snake_case label", () => {
    expect(formatReasoningLabel("somewhat_hesitant")).toBe("Somewhat Hesitant");
    expect(formatReasoningLabel("clear_structure")).toBe("Clear Structure");
  });

  it("returns a friendly fallback for a null label", () => {
    expect(formatReasoningLabel(null)).toBe("Not available");
  });
});

describe("colorForReasoningLabel", () => {
  it("returns the strongest tier's color for the first label in a dimension's vocabulary", () => {
    const color = colorForReasoningLabel("structure", "clear_structure");
    expect(color).toBe(colorForReasoningLabel("clarity", "clear"));
  });

  it("returns the weakest tier's color for the last label in a dimension's vocabulary", () => {
    const color = colorForReasoningLabel("confidence", "uncertain");
    expect(color).toBe(colorForReasoningLabel("conciseness", "verbose"));
  });

  it("falls back to a distinct gray for a label outside the documented vocabulary", () => {
    const known = colorForReasoningLabel("structure", "clear_structure");
    const unknown = colorForReasoningLabel("structure", "some_unexpected_label");
    expect(unknown).not.toBe(known);
  });

  it("falls back to gray for a null label", () => {
    expect(colorForReasoningLabel("structure", null)).toBe(colorForReasoningLabel("clarity", null));
  });
});
