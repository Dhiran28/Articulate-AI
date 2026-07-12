"use client";

import { useCallback, useEffect, useReducer, useRef, useState } from "react";

import { BrowserMediaRecorderSource, type AudioSource } from "../lib/audioSource";
import { checkBrowserSupport, classifyMicrophoneError, type MicrophoneError } from "../lib/microphoneError";
import { LocalObjectUrlSink } from "../lib/recordingSink";
import { recordingMachineReducer } from "../state/recordingMachine";
import type { RecordingArtifact } from "../types";

const TICK_INTERVAL_MS = 250;

/**
 * Owns real browser audio capture for the Practice screen: requests
 * microphone access, drives a MediaRecorder through an AudioSource, and
 * hands the finished recording to a RecordingSink.
 *
 * This replaces Sprint 2.1's useRecordingUIState outright — that hook's
 * header comment said as much. The two expose a near-identical surface
 * ({ status, elapsedMs, record, pause, resume, stop, reset }); this one
 * additionally exposes `artifact` (the finished Blob + metadata),
 * `playbackUrl` (an object URL for that same artifact, for playback),
 * `mediaStream` (the live microphone stream while a session is open, for
 * Sprint 2.4's waveform to tap independently — see useWaveform),
 * `browserSupport` (Sprint 2.6: set once, client-side only, if this
 * browser or connection can't record at all), and `errorMessage`, none
 * of which exist without real capture involved.
 */
export function useAudioRecorder() {
  const [status, dispatch] = useReducer(recordingMachineReducer, "idle");
  const [elapsedMs, setElapsedMs] = useState(0);
  const [artifact, setArtifact] = useState<RecordingArtifact | null>(null);
  const [playbackUrl, setPlaybackUrl] = useState<string | null>(null);
  const [mediaStream, setMediaStream] = useState<MediaStream | null>(null);
  const [browserSupport, setBrowserSupport] = useState<MicrophoneError | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const sourceRef = useRef<AudioSource | null>(null);
  const sinkRef = useRef(new LocalObjectUrlSink());
  const objectUrlRef = useRef<string | null>(null);

  const startedAtRef = useRef<number | null>(null);
  const accumulatedMsRef = useRef(0);

  /**
   * Folds the currently-running segment (if any) into accumulatedMsRef
   * and returns the new total. Called synchronously from pause(), stop(),
   * and handleSourceError() — never from a useEffect keyed on `status`.
   *
   * An earlier version of this hook finalized the accumulated time from
   * an effect that watched `status === "paused"`. That worked for the
   * common case, but effects run asynchronously after a commit: a user
   * (or a fast script) pausing and then immediately stopping — or
   * resuming and then immediately stopping — could call stop() before
   * that effect had run, silently dropping the last segment's time from
   * the recorded duration. Computing the fold-in synchronously, at the
   * moment each action actually happens, removes that whole class of
   * timing bug rather than narrowing the window.
   */
  const finalizeElapsed = useCallback((): number => {
    if (startedAtRef.current !== null) {
      accumulatedMsRef.current += Date.now() - startedAtRef.current;
      startedAtRef.current = null;
    }
    return accumulatedMsRef.current;
  }, []);

  const handleSourceError = useCallback(
    (error: Error) => {
      // Freeze the timer at the exact moment of failure, rather than
      // leaving it to whatever the last periodic tick happened to show
      // (which could be up to TICK_INTERVAL_MS stale).
      setElapsedMs(finalizeElapsed());
      setErrorMessage(error.message);
      dispatch({ type: "ERROR" });
      sourceRef.current?.dispose();
      sourceRef.current = null;
      setMediaStream(null);
    },
    [finalizeElapsed]
  );

  // Detect browser/connection support once, on mount, client-side only.
  //
  // This deliberately isn't computed inline during render (e.g. via a
  // useState lazy initializer). checkBrowserSupport() reads
  // window/navigator, which don't exist during Next.js's server-rendered
  // pass; if the *client's* first render produced a different result
  // than the (window-less) server render, React would treat it as a
  // hydration mismatch — the same class of bug fixed in Sprint 2.2 for
  // the waveform's bar heights. Starting from `null` (assume supported)
  // on both the server and the client's initial render, then correcting
  // it here after mount, avoids that: there's a brief window where an
  // actually-unsupported browser still shows the normal recording UI,
  // but it resolves within the same tick, before a user could act on it.
  useEffect(() => {
    setBrowserSupport(checkBrowserSupport());
  }, []);

  // Timer display: ticks every TICK_INTERVAL_MS while recording, but
  // always computes elapsed as (accumulated + time since this segment
  // started) rather than incrementing a counter per tick. That matters
  // if the browser throttles or delays setInterval — which it routinely
  // does for background/inactive tabs — because the next tick that does
  // fire still lands on the correct value instead of having drifted.
  //
  // startedAtRef is set synchronously by record() and resume() (not
  // lazily here) — see finalizeElapsed's comment for why relying on
  // effect timing was the wrong place for that.
  useEffect(() => {
    if (status !== "recording") return;

    const interval = setInterval(() => {
      if (startedAtRef.current === null) return; // shouldn't happen; defensive only
      const elapsed = accumulatedMsRef.current + (Date.now() - startedAtRef.current);
      setElapsedMs(Math.max(0, elapsed));
    }, TICK_INTERVAL_MS);

    return () => clearInterval(interval);
  }, [status]);

  // Release the microphone and any object URL on unmount, so navigating
  // away mid-recording doesn't leave the browser's mic indicator on.
  useEffect(() => {
    const sink = sinkRef.current;
    return () => {
      sourceRef.current?.dispose();
      if (objectUrlRef.current) sink.release(objectUrlRef.current);
    };
  }, []);

  const record = useCallback(async () => {
    if (status === "recording" || status === "paused" || status === "requesting_permission") {
      return;
    }

    // Defensive re-check, even though the UI shouldn't offer a Record
    // button at all once browserSupport is set (see PracticeScreen) —
    // this guards the rare case of record() being reached before that
    // effect has run, or being called some other way.
    const unsupported = checkBrowserSupport();
    if (unsupported) {
      setBrowserSupport(unsupported);
      setErrorMessage(unsupported.message);
      return;
    }

    setErrorMessage(null);
    setArtifact(null);
    if (objectUrlRef.current) {
      sinkRef.current.release(objectUrlRef.current);
      objectUrlRef.current = null;
      setPlaybackUrl(null);
    }
    accumulatedMsRef.current = 0;
    startedAtRef.current = null;
    setElapsedMs(0);

    dispatch({ type: "REQUEST_PERMISSION" });

    let stream: MediaStream | null = null;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const source = new BrowserMediaRecorderSource(stream, handleSourceError);
      sourceRef.current = source;
      await source.start();
      setMediaStream(stream);
      // Set synchronously, at the exact moment recording actually
      // starts, rather than lazily from the tick effect — see
      // finalizeElapsed's comment for why that timing matters.
      startedAtRef.current = Date.now();
      dispatch({ type: "PERMISSION_GRANTED" });
    } catch (err) {
      // Clean up anything partially acquired so the mic indicator
      // doesn't stay on after a failed start.
      sourceRef.current?.dispose();
      sourceRef.current = null;
      stream?.getTracks().forEach((track) => track.stop());
      setMediaStream(null);

      // Classified by DOMException name (permission denied / no device /
      // device in use / etc.) rather than shown as the browser's raw
      // error text — see lib/microphoneError.ts for why. The original
      // error still goes to the console for debugging.
      const classified = classifyMicrophoneError(err);
      console.error("Failed to start recording:", err);
      setErrorMessage(classified.message);
      // PERMISSION_DENIED is this state machine's name for "the attempt
      // to start recording failed" broadly — not literally only
      // permission denial. See state/recordingMachine.ts.
      dispatch({ type: "PERMISSION_DENIED" });
    }
  }, [status, handleSourceError]);

  const pause = useCallback(() => {
    sourceRef.current?.pause();
    const finalMs = finalizeElapsed();
    setElapsedMs(finalMs);
    dispatch({ type: "PAUSE" });
  }, [finalizeElapsed]);

  const resume = useCallback(() => {
    sourceRef.current?.resume();
    // Set synchronously — same reasoning as record(): this is the exact
    // moment the current segment starts, so it can't wait for an effect.
    startedAtRef.current = Date.now();
    dispatch({ type: "RESUME" });
  }, []);

  const stop = useCallback(async () => {
    const source = sourceRef.current;
    if (!source) return;

    // The artifact needs an accurate duration synchronously, so finalize
    // here rather than deferring to an effect.
    const finalElapsedMs = finalizeElapsed();
    setElapsedMs(finalElapsedMs);

    try {
      const { blob, mimeType } = await source.stop();
      const finalArtifact: RecordingArtifact = {
        blob,
        mimeType,
        durationMs: finalElapsedMs,
        createdAt: Date.now(),
        source: "browser",
      };
      setArtifact(finalArtifact);
      objectUrlRef.current = sinkRef.current.save(finalArtifact);
      setPlaybackUrl(objectUrlRef.current);
      dispatch({ type: "STOP" });
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : "Failed to finish the recording.");
      dispatch({ type: "ERROR" });
    } finally {
      source.dispose();
      sourceRef.current = null;
      setMediaStream(null);
    }
  }, [finalizeElapsed]);

  const reset = useCallback(() => {
    sourceRef.current?.dispose();
    sourceRef.current = null;
    setMediaStream(null);
    if (objectUrlRef.current) {
      sinkRef.current.release(objectUrlRef.current);
      objectUrlRef.current = null;
      setPlaybackUrl(null);
    }
    accumulatedMsRef.current = 0;
    startedAtRef.current = null;
    setElapsedMs(0);
    setArtifact(null);
    setErrorMessage(null);
    dispatch({ type: "RESET" });
  }, []);

  return {
    status,
    elapsedMs,
    artifact,
    playbackUrl,
    mediaStream,
    browserSupport,
    errorMessage,
    record,
    pause,
    resume,
    stop,
    reset,
  };
}
