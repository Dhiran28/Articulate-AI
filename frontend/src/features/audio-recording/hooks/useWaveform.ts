"use client";

import { useEffect, useRef, useState } from "react";

import { WebAudioWaveformSource } from "../lib/waveformSource";
import type { WaveformSource } from "../lib/waveformSource";

/**
 * Drives a live waveform from a MediaStream, deliberately isolated from
 * useAudioRecorder's own state.
 *
 * Per ADR 001 section 4, waveform samples can update up to 60 times a
 * second. Routing that through the same state as the status badge,
 * timer, and controls would re-render all of them on every frame for no
 * reason. Calling this hook from a leaf component (WaveformVisualizer)
 * instead means only the waveform itself repaints that often.
 *
 * `isActive` freezes the displayed levels — stops sampling, keeps the
 * last frame on screen — without tearing down the underlying
 * WaveformSource. This is what makes "recording paused" look frozen:
 * the microphone stream is still open (MediaRecorder.pause() doesn't
 * stop the hardware), but nothing should visually read as "live"
 * anymore.
 *
 * `barCount` is a parameter, not a hardcoded constant, so a different
 * consumer (e.g. a compact meter elsewhere in the app) can ask for a
 * different number of bars without this hook changing.
 */
export function useWaveform(
  stream: MediaStream | null,
  isActive: boolean,
  barCount: number = 32
): number[] {
  const [levels, setLevels] = useState<number[]>(() => new Array(barCount).fill(0));
  const isActiveRef = useRef(isActive);

  useEffect(() => {
    isActiveRef.current = isActive;
  }, [isActive]);

  useEffect(() => {
    if (!stream) {
      setLevels(new Array(barCount).fill(0));
      return;
    }

    const source: WaveformSource = new WebAudioWaveformSource(stream);
    source.start();

    let frame: number;
    const tick = () => {
      if (isActiveRef.current) {
        setLevels(source.getLevels(barCount));
      }
      frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);

    return () => {
      cancelAnimationFrame(frame);
      source.dispose();
    };
  }, [stream, barCount]);

  return levels;
}
