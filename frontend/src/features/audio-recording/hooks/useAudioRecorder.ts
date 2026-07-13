"use client";

import { useCallback, useEffect, useReducer, useRef, useState } from "react";

import { BrowserMediaRecorderSource, type AudioSource } from "../lib/audioSource";
import { checkBrowserSupport, classifyMicrophoneError, type MicrophoneError } from "../lib/microphoneError";
import { LocalObjectUrlSink } from "../lib/recordingSink";
import { recordingMachineReducer } from "../state/recordingMachine";
import type { RecordingArtifact, RecordingStatus } from "../types";
import { useRecordingClock } from "./useRecordingClock";

/**
 * The full public contract of useAudioRecorder — everything the Practice
 * screen (or any future consumer) can read or call.
 */
export interface UseAudioRecorderResult {
  status: RecordingStatus;
  /** Milliseconds recorded so far, excluding any paused time. */
  elapsedMs: number;
  /** The finished recording once stop() resolves, until the next record() or reset(). */
  artifact: RecordingArtifact | null;
  /** A ready-to-play object URL for `artifact`, or null when there isn't one. */
  playbackUrl: string | null;
  /** The live microphone stream while a session is open (recording or paused), for a waveform or similar to tap independently. */
  mediaStream: MediaStream | null;
  /** Set once, after mount, if this browser or connection can't record at all — see lib/microphoneError.ts. */
  browserSupport: MicrophoneError | null;
  /** A friendly, user-facing description of the most recent failure, or null. */
  errorMessage: string | null;
  record: () => Promise<void>;
  pause: () => void;
  resume: () => void;
  stop: () => Promise<void>;
  reset: () => void;
}

/**
 * Owns real browser audio capture for the Practice screen.
 *
 * record() requests microphone access, wraps the resulting MediaStream
 * in an AudioSource (BrowserMediaRecorderSource — see lib/audioSource.ts)
 * to drive an actual MediaRecorder, and tracks status through
 * pause/resume/stop. Elapsed time is delegated entirely to
 * useRecordingClock (see that file) rather than tracked inline here —
 * it's timing-sensitive bookkeeping that's easier to get right, and to
 * test, in isolation. stop() hands the finished recording to a
 * RecordingSink (lib/recordingSink.ts) and exposes it as both `artifact`
 * (the Blob and its metadata) and `playbackUrl` (a ready-to-play object
 * URL).
 *
 * `mediaStream` is exposed separately from the recording pipeline itself
 * so a live waveform (useWaveform) can read the same microphone in
 * parallel, without needing to know anything about MediaRecorder.
 * `browserSupport` is checked once after mount for browsers or
 * connections that can't record at all — see the effect below for why
 * that check can't happen inline during render. `errorMessage` covers
 * everything else that can go wrong starting or finishing a recording,
 * classified into friendly, specific copy by lib/microphoneError.ts
 * rather than shown as a raw browser error.
 */
export function useAudioRecorder(): UseAudioRecorderResult {
  const [status, dispatch] = useReducer(recordingMachineReducer, "idle");
  const [artifact, setArtifact] = useState<RecordingArtifact | null>(null);
  const [playbackUrl, setPlaybackUrl] = useState<string | null>(null);
  const [mediaStream, setMediaStream] = useState<MediaStream | null>(null);
  const [browserSupport, setBrowserSupport] = useState<MicrophoneError | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const { elapsedMs, startSegment, finalizeSegment, reset: resetClock } = useRecordingClock(
    status === "recording"
  );

  const sourceRef = useRef<AudioSource | null>(null);
  const sinkRef = useRef(new LocalObjectUrlSink());
  const objectUrlRef = useRef<string | null>(null);

  // Guards against two overlapping record() calls (e.g. a rapid or
  // programmatic double-invocation) racing each other to acquire a
  // microphone stream. This is a ref, not the `status` state, precisely
  // because it must be checked and set synchronously within a single
  // call — a state-based guard can't close the window between "read
  // status" and "the resulting re-render actually disabling the Record
  // button," since record() is async and status doesn't change until
  // after the first `await`.
  const isStartingRef = useRef(false);

  // Set once on mount, false on unmount. record() and stop() check this
  // after their one async gap (getUserMedia / source.stop()) before
  // touching any resource that would otherwise be left with nothing to
  // release it — see the comments at each call site. The same effect
  // also releases the microphone and any object URL on unmount, so
  // navigating away mid-recording doesn't leave the browser's mic
  // indicator on.
  const isMountedRef = useRef(true);
  useEffect(() => {
    isMountedRef.current = true;
    const sink = sinkRef.current;
    return () => {
      isMountedRef.current = false;
      sourceRef.current?.dispose();
      if (objectUrlRef.current) sink.release(objectUrlRef.current);
    };
  }, []);

  /**
   * Disposes the current AudioSource (releasing the microphone) and
   * clears `mediaStream`. Shared by handleSourceError, record()'s
   * failure path, stop()'s finally, and reset() — all four previously
   * repeated this same three-line sequence inline.
   */
  const releaseSource = useCallback((): void => {
    sourceRef.current?.dispose();
    sourceRef.current = null;
    setMediaStream(null);
  }, []);

  /**
   * Releases the current playback object URL (if any) and clears
   * `playbackUrl`. Shared by record() (starting a new take discards the
   * previous one's URL) and reset().
   */
  const clearPlayback = useCallback((): void => {
    if (objectUrlRef.current) {
      sinkRef.current.release(objectUrlRef.current);
      objectUrlRef.current = null;
      setPlaybackUrl(null);
    }
  }, []);

  const handleSourceError = useCallback(
    (error: unknown) => {
      // Freeze the timer at the exact moment of failure, rather than
      // leaving it to whatever the last periodic tick happened to show
      // (which could be up to one tick interval stale).
      finalizeSegment();
      // Classified the same way record()'s failures are, so every
      // microphone-related message the user sees comes from one place
      // (lib/microphoneError.ts) — see BrowserMediaRecorderSource for
      // what values this can receive.
      const classified = classifyMicrophoneError(error);
      console.error("Recording source error:", error);
      setErrorMessage(classified.message);
      dispatch({ type: "ERROR" });
      releaseSource();
    },
    [finalizeSegment, releaseSource]
  );

  // Detect browser/connection support once, on mount, client-side only.
  //
  // This deliberately isn't computed inline during render (e.g. via a
  // useState lazy initializer). checkBrowserSupport() reads
  // window/navigator, which don't exist during Next.js's server-rendered
  // pass; if the *client's* first render produced a different result
  // than the (window-less) server render, React would treat it as a
  // hydration mismatch — the same class of bug that shows up in any
  // client-only computation done during render instead of after mount.
  // Starting from `null` (assume supported) on both the server and the
  // client's initial render, then correcting it here after mount, avoids
  // that: there's a brief window where an actually-unsupported browser
  // still shows the normal recording UI, but it resolves within the same
  // tick, before a user could act on it.
  useEffect(() => {
    setBrowserSupport(checkBrowserSupport());
  }, []);

  const record = useCallback(async () => {
    if (status === "recording" || status === "paused" || status === "requesting_permission") {
      return;
    }
    if (isStartingRef.current) return;

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

    isStartingRef.current = true;
    setErrorMessage(null);
    setArtifact(null);
    clearPlayback();
    resetClock();

    dispatch({ type: "REQUEST_PERMISSION" });

    let stream: MediaStream | null = null;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });

      if (!isMountedRef.current) {
        // Unmounted while the permission prompt was pending. Release the
        // microphone immediately — there's no cleanup effect left to run
        // that would ever do it, since the one that existed already ran
        // when this component unmounted.
        stream.getTracks().forEach((track) => track.stop());
        return;
      }

      const source = new BrowserMediaRecorderSource(stream, handleSourceError);
      sourceRef.current = source;
      await source.start();
      setMediaStream(stream);
      // Set synchronously, at the exact moment recording actually
      // starts, rather than lazily from the tick effect — see
      // useRecordingClock's finalizeSegment doc comment for why that
      // timing matters.
      startSegment();
      dispatch({ type: "PERMISSION_GRANTED" });
    } catch (err) {
      // Clean up anything partially acquired so the mic indicator
      // doesn't stay on after a failed start. Stopping the raw stream
      // directly (in addition to releaseSource()) covers the case where
      // getUserMedia succeeded but constructing the AudioSource itself
      // threw before sourceRef was ever assigned.
      releaseSource();
      stream?.getTracks().forEach((track) => track.stop());

      // Classified by error name (permission denied / no device / device
      // in use / etc.) rather than shown as the browser's raw error text
      // — see lib/microphoneError.ts for why. The original error still
      // goes to the console for debugging.
      const classified = classifyMicrophoneError(err);
      console.error("Failed to start recording:", err);
      setErrorMessage(classified.message);
      // PERMISSION_DENIED is this state machine's name for "the attempt
      // to start recording failed" broadly — not literally only
      // permission denial. See state/recordingMachine.ts.
      dispatch({ type: "PERMISSION_DENIED" });
    } finally {
      isStartingRef.current = false;
    }
  }, [status, handleSourceError, clearPlayback, resetClock, startSegment, releaseSource]);

  const pause = useCallback(() => {
    sourceRef.current?.pause();
    finalizeSegment();
    dispatch({ type: "PAUSE" });
  }, [finalizeSegment]);

  const resume = useCallback(() => {
    sourceRef.current?.resume();
    // Set synchronously — same reasoning as record(): this is the exact
    // moment the current segment starts, so it can't wait for an effect.
    startSegment();
    dispatch({ type: "RESUME" });
  }, [startSegment]);

  const stop = useCallback(async () => {
    const source = sourceRef.current;
    if (!source) return;

    // The artifact needs an accurate duration synchronously, so finalize
    // here rather than deferring to an effect.
    const finalElapsedMs = finalizeSegment();

    try {
      const { blob, mimeType } = await source.stop();

      // If the component unmounted while this await was pending, don't
      // create a playback object URL for it — the unmount cleanup effect
      // that would normally revoke it already ran, so one created now
      // would never be released for the rest of the page's lifetime.
      if (!isMountedRef.current) return;

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
      // Logged for debugging, but never shown to the user as raw text —
      // same principle as classifyMicrophoneError, just without needing
      // a full classification scheme for this one failure mode (the
      // recorder unexpectedly not being active when stop() runs).
      console.error("Failed to finish recording:", err);
      setErrorMessage("Something went wrong finishing the recording. Please try again.");
      dispatch({ type: "ERROR" });
    } finally {
      releaseSource();
    }
  }, [finalizeSegment, releaseSource]);

  const reset = useCallback(() => {
    releaseSource();
    clearPlayback();
    resetClock();
    setArtifact(null);
    setErrorMessage(null);
    dispatch({ type: "RESET" });
  }, [releaseSource, clearPlayback, resetClock]);

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
