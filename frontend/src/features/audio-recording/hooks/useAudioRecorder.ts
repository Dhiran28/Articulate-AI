"use client";

import { useCallback, useEffect, useReducer, useRef, useState } from "react";

import { BrowserMediaRecorderSource, type AudioSource } from "../lib/audioSource";
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
 * Sprint 2.4's waveform to tap independently — see useWaveform), and
 * `errorMessage`, none of which exist without real capture involved.
 */
export function useAudioRecorder() {
  const [status, dispatch] = useReducer(recordingMachineReducer, "idle");
  const [elapsedMs, setElapsedMs] = useState(0);
  const [artifact, setArtifact] = useState<RecordingArtifact | null>(null);
  const [playbackUrl, setPlaybackUrl] = useState<string | null>(null);
  const [mediaStream, setMediaStream] = useState<MediaStream | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const sourceRef = useRef<AudioSource | null>(null);
  const sinkRef = useRef(new LocalObjectUrlSink());
  const objectUrlRef = useRef<string | null>(null);

  const startedAtRef = useRef<number | null>(null);
  const accumulatedMsRef = useRef(0);

  const handleSourceError = useCallback((error: Error) => {
    setErrorMessage(error.message);
    dispatch({ type: "ERROR" });
    sourceRef.current?.dispose();
    sourceRef.current = null;
    setMediaStream(null);
  }, []);

  // Timer: same timestamp-based approach as Sprint 2.1, now driven by
  // real recording state instead of a mock.
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

  // Freeze the clock on pause by folding the running segment into the
  // accumulated total. (The "stopped" case is finalized synchronously
  // inside stop() below, since that path needs an accurate value
  // immediately for the artifact — it can't wait for this effect.)
  useEffect(() => {
    if (status === "paused" && startedAtRef.current !== null) {
      accumulatedMsRef.current += Date.now() - startedAtRef.current;
      startedAtRef.current = null;
      setElapsedMs(accumulatedMsRef.current);
    }
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
      dispatch({ type: "PERMISSION_GRANTED" });
    } catch (err) {
      // Clean up anything partially acquired so the mic indicator
      // doesn't stay on after a failed start.
      sourceRef.current?.dispose();
      sourceRef.current = null;
      stream?.getTracks().forEach((track) => track.stop());
      setMediaStream(null);
      setErrorMessage(
        err instanceof Error ? err.message : "Microphone access was denied or unavailable."
      );
      dispatch({ type: "PERMISSION_DENIED" });
    }
  }, [status, handleSourceError]);

  const pause = useCallback(() => {
    sourceRef.current?.pause();
    dispatch({ type: "PAUSE" });
  }, []);

  const resume = useCallback(() => {
    sourceRef.current?.resume();
    dispatch({ type: "RESUME" });
  }, []);

  const stop = useCallback(async () => {
    const source = sourceRef.current;
    if (!source) return;

    // Finalize elapsed time here rather than relying on the pause/stop
    // effect above — the artifact needs an accurate duration
    // synchronously, before that effect has a chance to run.
    let finalElapsedMs = accumulatedMsRef.current;
    if (startedAtRef.current !== null) {
      finalElapsedMs += Date.now() - startedAtRef.current;
    }
    accumulatedMsRef.current = finalElapsedMs;
    startedAtRef.current = null;
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
  }, []);

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
    errorMessage,
    record,
    pause,
    resume,
    stop,
    reset,
  };
}
