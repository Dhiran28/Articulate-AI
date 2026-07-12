"use client";

interface RecordingTimerProps {
  elapsedMs: number;
}

function formatElapsed(ms: number): string {
  // Defensive clamp: negative values (a system clock adjusted backwards
  // mid-recording is the realistic cause) and non-finite values (NaN,
  // Infinity — shouldn't happen given how useAudioRecorder computes
  // elapsedMs, but this is the component users actually see, so it
  // shouldn't be able to render "NaN:NaN" or a negative time under any
  // input) both fall back to zero rather than propagating into the
  // display.
  const safeMs = Number.isFinite(ms) && ms > 0 ? ms : 0;

  const totalSeconds = Math.floor(safeMs / 1000);
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;

  const pad = (n: number) => n.toString().padStart(2, "0");

  // Base format is mm:ss (e.g. "00:00"). Past one hour this expands to
  // hh:mm:ss instead of letting minutes run past 59 (e.g. "90:00"),
  // which would read as almost-two-hours-as-minutes rather than
  // anything meaningful at a glance.
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
