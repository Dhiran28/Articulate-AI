import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useRecordingClock } from "./useRecordingClock";

describe("useRecordingClock", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("starts at zero and stays zero until a segment starts", () => {
    const { result } = renderHook(() => useRecordingClock(false));
    expect(result.current.elapsedMs).toBe(0);
  });

  it("ticks elapsedMs upward while a segment is running and isRunning is true", () => {
    const { result } = renderHook(() => useRecordingClock(true));

    act(() => {
      result.current.startSegment();
    });
    act(() => {
      vi.advanceTimersByTime(1000);
    });

    expect(result.current.elapsedMs).toBeGreaterThanOrEqual(1000);
  });

  it("does not tick while isRunning is false, even with a segment running", () => {
    const { result } = renderHook(() => useRecordingClock(false));

    act(() => {
      result.current.startSegment();
      vi.advanceTimersByTime(1000);
    });

    // No interval is scheduled while isRunning is false, so the displayed
    // value only ever updates when finalizeSegment is called explicitly.
    expect(result.current.elapsedMs).toBe(0);
  });

  it("finalizeSegment reflects elapsed time immediately, without waiting for the next tick", () => {
    // Regression test for the Sprint 2.5 timer bug: finalizing (what
    // pause()/stop() do) must reflect the true elapsed time the instant
    // it's called, even if the 250ms tick interval hasn't fired yet —
    // otherwise a fast pause-then-stop could lose the last segment.
    const { result } = renderHook(() => useRecordingClock(true));

    act(() => {
      result.current.startSegment();
    });
    act(() => {
      vi.advanceTimersByTime(50); // well under the 250ms tick interval
    });

    let finalized = 0;
    act(() => {
      finalized = result.current.finalizeSegment();
    });

    expect(finalized).toBeGreaterThanOrEqual(50);
    expect(result.current.elapsedMs).toBe(finalized);
  });

  it("finalizeSegment is idempotent when called again with no new segment started", () => {
    const { result } = renderHook(() => useRecordingClock(true));

    act(() => {
      result.current.startSegment();
    });
    act(() => {
      vi.advanceTimersByTime(200);
    });

    let first = 0;
    act(() => {
      first = result.current.finalizeSegment();
    });

    let second = -1;
    act(() => {
      second = result.current.finalizeSegment();
    });

    expect(second).toBe(first);
  });

  it("accumulates across multiple start/finalize segments (pause and resume)", () => {
    const { result } = renderHook(() => useRecordingClock(true));

    act(() => {
      result.current.startSegment();
    });
    act(() => {
      vi.advanceTimersByTime(300);
    });
    let afterFirstSegment = 0;
    act(() => {
      afterFirstSegment = result.current.finalizeSegment();
    });
    expect(afterFirstSegment).toBeGreaterThanOrEqual(300);

    // Simulate a pause: time passes with no segment running, shouldn't count.
    act(() => {
      vi.advanceTimersByTime(5000);
    });

    act(() => {
      result.current.startSegment();
    });
    act(() => {
      vi.advanceTimersByTime(100);
    });
    let afterSecondSegment = 0;
    act(() => {
      afterSecondSegment = result.current.finalizeSegment();
    });

    expect(afterSecondSegment).toBeGreaterThanOrEqual(afterFirstSegment + 100);
    expect(afterSecondSegment).toBeLessThan(afterFirstSegment + 5000);
  });

  it("reset zeroes the clock", () => {
    const { result } = renderHook(() => useRecordingClock(true));

    act(() => {
      result.current.startSegment();
      vi.advanceTimersByTime(500);
    });
    act(() => {
      result.current.finalizeSegment();
    });
    expect(result.current.elapsedMs).toBeGreaterThan(0);

    act(() => {
      result.current.reset();
    });
    expect(result.current.elapsedMs).toBe(0);
  });
});
