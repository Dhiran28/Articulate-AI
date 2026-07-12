"use client";

import { cn } from "@/lib/utils";

import type { RecordingStatus } from "../types";

const BAR_COUNT = 32;

/**
 * Deterministic pseudo-random value in [0, 1), seeded by index.
 *
 * A real Math.random() here would produce different bar heights during
 * Next.js's server-rendered HTML pass than during the client's first
 * render, which React flags as a hydration mismatch. Seeding by index
 * keeps the output identical on both passes.
 */
function seededRandom(seed: number): number {
  const x = Math.sin(seed * 12.9898) * 43758.5453;
  return x - Math.floor(x);
}

const BAR_HEIGHTS = Array.from({ length: BAR_COUNT }, (_, i) => 0.25 + seededRandom(i) * 0.75);

interface WaveformPlaceholderProps {
  status: RecordingStatus;
}

/**
 * Stand-in for the real waveform, which (per ADR 001) will eventually be
 * driven by an AnalyserNode reading the live MediaStream. Sprint 2.2
 * wires up real audio capture but deliberately does not touch this
 * component — reading live audio data to draw a waveform is a form of
 * audio analysis, which is out of scope for this sprint. This still
 * renders a fixed bar pattern that animates only while
 * `status === "recording"`, and freezes on pause or stop.
 */
export function WaveformPlaceholder({ status }: WaveformPlaceholderProps) {
  const isRecording = status === "recording";
  const isIdle = status === "idle" || status === "requesting_permission" || status === "error";
  const isAnimated = status === "recording" || status === "paused" || status === "stopped";

  return (
    <div
      className="flex h-24 w-full items-center justify-center gap-1 rounded-lg border border-border bg-muted/30 px-4"
      role="img"
      aria-label={isRecording ? "Audio waveform, live" : "Audio waveform placeholder, not recording"}
    >
      {BAR_HEIGHTS.map((height, i) => (
        <span
          key={i}
          className={cn(
            "w-1 rounded-full bg-primary/70",
            isIdle && "opacity-20",
            isAnimated && "animate-waveform-pulse"
          )}
          style={{
            height: `${height * 100}%`,
            animationDelay: `${(i % 8) * 0.08}s`,
            animationPlayState: isRecording ? "running" : "paused",
          }}
        />
      ))}
    </div>
  );
}
