import { describe, expect, it } from "vitest";

import { formatDuration } from "./formatDuration";

describe("formatDuration", () => {
  it("formats zero as 00:00", () => {
    expect(formatDuration(0)).toBe("00:00");
  });

  it("formats sub-minute durations as mm:ss", () => {
    expect(formatDuration(5_000)).toBe("00:05");
    expect(formatDuration(59_000)).toBe("00:59");
  });

  it("rolls over into minutes", () => {
    expect(formatDuration(60_000)).toBe("01:00");
    expect(formatDuration(125_000)).toBe("02:05");
  });

  it("expands to hh:mm:ss past one hour instead of overflowing minutes", () => {
    expect(formatDuration(3_600_000)).toBe("01:00:00");
    expect(formatDuration(3_661_000)).toBe("01:01:01");
    expect(formatDuration(5_400_000)).toBe("01:30:00");
  });

  it("floors partial seconds rather than rounding", () => {
    expect(formatDuration(5_999)).toBe("00:05");
  });

  it("clamps negative values to zero", () => {
    expect(formatDuration(-500)).toBe("00:00");
  });

  it("clamps non-finite values to zero", () => {
    expect(formatDuration(NaN)).toBe("00:00");
    expect(formatDuration(Infinity)).toBe("00:00");
  });
});
