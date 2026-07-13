"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { foldElapsed } from "../lib/recordingClockMath";

const TICK_INTERVAL_MS = 250;

export interface RecordingClock {
  /** Milliseconds elapsed so far, excluding any paused time. */
  elapsedMs: number;
  /** Marks "now" as the start of a new running segment (call from record()/resume()). */
  startSegment: () => void;
  /**
   * Folds the current running segment into the accumulated total,
   * updates `elapsedMs` to match, and returns the new total. Call this
   * synchronously at the exact moment a segment ends — pause(), stop(),
   * or an error that interrupts recording — never from an effect keyed
   * on status.
   *
   * An earlier version of this timer (pre-extraction, still visible in
   * git history) finalized accumulated time from an effect watching
   * `status === "paused"`. That worked for the common case, but effects
   * run asynchronously after a commit: pausing and immediately stopping
   * — or resuming and immediately stopping — could call stop() before
   * that effect ran, silently dropping the last segment's time. Folding
   * synchronously, at the call site of each action, removes that whole
   * class of bug instead of narrowing the window. See
   * useRecordingClock.test.ts for a regression test of this exact case.
   */
  finalizeSegment: () => number;
  /** Zeroes the clock for a fresh recording. */
  reset: () => void;
}

/**
 * Tracks elapsed recording time across pause/resume/stop, ticking a
 * display value every TICK_INTERVAL_MS while `isRunning`.
 *
 * Split out of useAudioRecorder so this timing-sensitive bookkeeping —
 * the exact area that produced a real race-condition bug in Sprint 2.5 —
 * is one small, independently testable unit, rather than interleaved
 * with permission handling and MediaRecorder orchestration.
 *
 * The tick itself recomputes elapsed as (accumulated + time since this
 * segment started) rather than incrementing a counter per tick. That
 * matters if the browser throttles or delays setInterval — which it
 * routinely does for background/inactive tabs — because the next tick
 * that does fire still lands on the correct value instead of having
 * drifted.
 */
export function useRecordingClock(isRunning: boolean): RecordingClock {
  const [elapsedMs, setElapsedMs] = useState(0);
  const startedAtRef = useRef<number | null>(null);
  const accumulatedMsRef = useRef(0);

  const finalizeSegment = useCallback((): number => {
    const total = foldElapsed(accumulatedMsRef.current, startedAtRef.current, Date.now());
    accumulatedMsRef.current = total;
    startedAtRef.current = null;
    setElapsedMs(total);
    return total;
  }, []);

  const startSegment = useCallback((): void => {
    startedAtRef.current = Date.now();
  }, []);

  const reset = useCallback((): void => {
    accumulatedMsRef.current = 0;
    startedAtRef.current = null;
    setElapsedMs(0);
  }, []);

  useEffect(() => {
    if (!isRunning) return;

    const interval = setInterval(() => {
      if (startedAtRef.current === null) return; // shouldn't happen; defensive only
      const elapsed = foldElapsed(accumulatedMsRef.current, startedAtRef.current, Date.now());
      setElapsedMs(Math.max(0, elapsed));
    }, TICK_INTERVAL_MS);

    return () => clearInterval(interval);
  }, [isRunning]);

  return { elapsedMs, startSegment, finalizeSegment, reset };
}
