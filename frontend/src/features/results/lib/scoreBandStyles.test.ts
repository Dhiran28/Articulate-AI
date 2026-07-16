import { describe, expect, it } from "vitest";

import { bandForScore } from "./scoreBandStyles";

describe("bandForScore", () => {
  it("mirrors the backend's SCORE_BAND_THRESHOLDS boundaries", () => {
    expect(bandForScore(100)).toBe("excellent");
    expect(bandForScore(85)).toBe("excellent");
    expect(bandForScore(84.9)).toBe("strong");
    expect(bandForScore(65)).toBe("strong");
    expect(bandForScore(64.9)).toBe("developing");
    expect(bandForScore(40)).toBe("developing");
    expect(bandForScore(39.9)).toBe("needs_work");
    expect(bandForScore(0)).toBe("needs_work");
  });
});
