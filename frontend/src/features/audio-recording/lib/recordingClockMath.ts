/**
 * Pure timing math for useRecordingClock, kept free of React/DOM so it
 * can be unit tested directly without mocking timers or rendering a
 * hook.
 *
 * Folds a currently-running segment (if one is open) into a previously
 * accumulated total. This is the exact computation that mattered for the
 * Sprint 2.5 timer bug: finalizing must happen synchronously at the
 * moment a segment actually ends (pause/stop/error), using the real
 * elapsed wall-clock time for that segment — never inferred from a tick
 * interval, which can be delayed or throttled by the browser.
 */
export function foldElapsed(
  accumulatedMs: number,
  segmentStartedAt: number | null,
  now: number
): number {
  return segmentStartedAt !== null ? accumulatedMs + (now - segmentStartedAt) : accumulatedMs;
}
