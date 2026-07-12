"use client";

import { useCallback, useEffect, useReducer, useRef, useState } from "react";

import type { RecordingStatus } from "../types";

type StatusAction =
  | { type: "RECORD" }
  | { type: "PAUSE" }
  | { type: "RESUME" }
  | { type: "STOP" }
  | { type: "RESET" };

/**
 * Pure status transitions. Invalid transitions (e.g. pausing while idle)
 * are ignored rather than throwing — the UI disables the relevant button
 * for those cases, so this is a second line of defense, not the primary
 * guard.
 */
function statusReducer(status: RecordingStatus, action: StatusAction): RecordingStatus {
  switch (action.type) {
    case "RECORD":
      return status === "idle" || status === "stopped" ? "recording" : status;
    case "PAUSE":
      return status === "recording" ? "paused" : status;
    case "RESUME":
      return status === "paused" ? "recording" : status;
    case "STOP":
      return status === "recording" || status === "paused" ? "stopped" : status;
    case "RESET":
      return "idle";
    default:
      return status;
  }
}

const TICK_INTERVAL_MS = 250;

/**
 * Drives the Practice screen's controls, status badge, and timer without
 * touching any real audio APIs.
 *
 * This stands in for the `useAudioRecorder` hook designed in ADR 001
 * until Sprint 2.2 wires up actual microphone capture. It will be
 * replaced outright at that point, not extended in place — the real hook
 * has a fundamentally different job (owning a MediaStream and an
 * AudioSource) rather than faking a clock.
 *
 * Elapsed time is computed from timestamps rather than incremented by a
 * fixed amount per tick, so it stays accurate even if the browser delays
 * the interval (backgrounded tab, busy main thread, etc.) — the same
 * approach the real hook will use, per ADR 001 section 4.
 */
export function useRecordingUIState() {
  const [status, dispatch] = useReducer(statusReducer, "idle");
  const [elapsedMs, setElapsedMs] = useState(0);

  const startedAtRef = useRef<number | null>(null);
  const accumulatedMsRef = useRef(0);

  // While recording, tick the displayed elapsed time off the wall clock.
  useEffect(() => {
    if (status !== "recording") return;

    if (startedAtRef.current === null) {
      startedAtRef.current = Date.now();
    }

    const interval = setInterval(() => {
      setElapsedMs(accumulatedMsRef.current + (Date.now() - startedAtRef.current!));
    }, TICK_INTERVAL_MS);

    return () => clearInterval(interval);
  }, [status]);

  // Freeze the clock on pause or stop by folding the running segment into
  // the accumulated total.
  useEffect(() => {
    if ((status === "paused" || status === "stopped") && startedAtRef.current !== null) {
      accumulatedMsRef.current += Date.now() - startedAtRef.current;
      startedAtRef.current = null;
      setElapsedMs(accumulatedMsRef.current);
    }
  }, [status]);

  const record = useCallback(() => {
    if (status === "recording" || status === "paused") return;
    accumulatedMsRef.current = 0;
    startedAtRef.current = null;
    setElapsedMs(0);
    dispatch({ type: "RECORD" });
  }, [status]);

  const pause = useCallback(() => dispatch({ type: "PAUSE" }), []);
  const resume = useCallback(() => dispatch({ type: "RESUME" }), []);
  const stop = useCallback(() => dispatch({ type: "STOP" }), []);

  const reset = useCallback(() => {
    accumulatedMsRef.current = 0;
    startedAtRef.current = null;
    setElapsedMs(0);
    dispatch({ type: "RESET" });
  }, []);

  return { status, elapsedMs, record, pause, resume, stop, reset };
}
