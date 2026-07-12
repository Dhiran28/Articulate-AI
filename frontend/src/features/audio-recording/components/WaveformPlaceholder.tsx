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
 * avoids that — but only if the formula itself is guaranteed to produce
 * identical output on both sides. An earlier version of this function
 * used Math.sin(), which is a transcendental function: the ECMAScript
 * spec doesn't require every engine to compute it bit-for-bit
 * identically, so the Node.js engine doing the server render and the
 * browser engine doing the client render could (rarely) round the last
 * few bits differently and still trip the hydration check. This version
 * uses only integer multiply/XOR/shift, all of which the spec *does*
 * guarantee are exact everywhere (a standard Murmur3-style hash).
 */
function seededRandom(seed: number): number {
  let x = (seed + 1) * 2654435761;
  x = (x ^ (x >>> 16)) >>> 0;
  x = Math.imul(x, 2246822519);
  x = (x ^ (x >>> 13)) >>> 0;
  x = Math.imul(x, 3266489917);
  x = (x ^ (x >>> 16)) >>> 0;
  return x / 4294967296;
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
