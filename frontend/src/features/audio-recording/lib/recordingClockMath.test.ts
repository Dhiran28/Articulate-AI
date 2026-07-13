import { describe, expect, it } from "vitest";

import { foldElapsed } from "./recordingClockMath";

describe("foldElapsed", () => {
  it("returns the accumulated total unchanged when no segment is running", () => {
    expect(foldElapsed(5_000, null, 10_000)).toBe(5_000);
  });

  it("adds the running segment's duration to the accumulated total", () => {
    // Segment started at t=1_000, "now" is t=4_000 -> 3s running segment.
    expect(foldElapsed(5_000, 1_000, 4_000)).toBe(8_000);
  });

  it("treats a zero accumulated total as a fresh first segment", () => {
    expect(foldElapsed(0, 0, 2_500)).toBe(2_500);
  });

  it("returns exactly the accumulated total when now equals segmentStartedAt", () => {
    expect(foldElapsed(1_200, 5_000, 5_000)).toBe(1_200);
  });
});
