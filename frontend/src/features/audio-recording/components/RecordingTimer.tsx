"use client";

interface RecordingTimerProps {
  elapsedMs: number;
}

function formatElapsed(ms: number): string {
  const totalSeconds = Math.floor(ms / 1000);
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;

  const pad = (n: number) => n.toString().padStart(2, "0");

  return hours > 0
    ? `${pad(hours)}:${pad(minutes)}:${pad(seconds)}`
    : `${pad(minutes)}:${pad(seconds)}`;
}

/**
 * Displays elapsed recording time as mm:ss (or hh:mm:ss past one hour).
 * `tabular-nums` keeps digit widths fixed so the timer doesn't visibly
 * jitter side to side as digits change every second.
 */
export function RecordingTimer({ elapsedMs }: RecordingTimerProps) {
  const formatted = formatElapsed(elapsedMs);

  return (
    <div
      className="font-mono text-4xl font-semibold tabular-nums text-foreground"
      aria-label={`Recording time: ${formatted}`}
    >
      {formatted}
    </div>
  );
}
