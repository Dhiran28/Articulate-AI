"use client";

import { cn } from "@/lib/utils";

import { useWaveform } from "../hooks/useWaveform";
import type { RecordingStatus } from "../types";

const BAR_COUNT = 32;

interface WaveformVisualizerProps {
  status: RecordingStatus;
  /** The live microphone stream for the current session, or null when there isn't one (idle, requesting permission, stopped, error). */
  stream: MediaStream | null;
}

/**
 * Live microphone waveform, replacing Sprint 2.1's WaveformPlaceholder.
 *
 * Bar heights come from useWaveform, which reads real amplitude data
 * through a WaveformSource — WebAudioWaveformSource (Web Audio's
 * AnalyserNode) for a browser microphone today. See
 * lib/waveformSource.ts for why that's a separate, swappable interface
 * from AudioSource, and what changes (and doesn't) for a future ESP32 or
 * Quest 3 microphone.
 *
 * When `stream` is null, this shows a flat, dim bar row rather than
 * frozen or fabricated data — an honest "nothing is live right now"
 * rather than Sprint 2.1's placeholder animation, which was decorative
 * by necessity before real capture existed.
 */
export function WaveformVisualizer({ status, stream }: WaveformVisualizerProps) {
  const isActive = status === "recording";
  const isLive = stream !== null;
  const levels = useWaveform(stream, isActive, BAR_COUNT);

  return (
    <div
      className="flex h-24 w-full items-center justify-center gap-1 rounded-lg border border-border bg-muted/30 px-4"
      role="img"
      aria-label={isActive ? "Audio waveform, live" : "Audio waveform, not recording"}
    >
      {levels.map((level, i) => (
        <span
          key={i}
          className={cn(
            "w-1 rounded-full bg-primary/70 transition-[height] duration-75",
            !isLive && "opacity-20"
          )}
          style={{ height: `${Math.max(level * 100, 4)}%` }}
        />
      ))}
    </div>
  );
}
