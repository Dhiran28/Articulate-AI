"use client";

import { formatDuration } from "../lib/formatDuration";

interface RecordingTimerProps {
  elapsedMs: number;
}

/**
 * Displays elapsed recording time as mm:ss (or hh:mm:ss past one hour),
 * via the shared formatDuration (also used by PlaybackPanel). `tabular-nums`
 * keeps digit widths fixed so the timer doesn't visibly jitter side to
 * side as digits change every second.
 */
export function RecordingTimer({ elapsedMs }: RecordingTimerProps) {
  const formatted = formatDuration(elapsedMs);

  return (
    <div
      className="font-mono text-4xl font-semibold tabular-nums text-foreground"
      aria-label={`Recording time: ${formatted}`}
    >
      {formatted}
    </div>
  );
}
