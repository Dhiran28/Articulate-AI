/**
 * Formats a millisecond duration as mm:ss, expanding to hh:mm:ss past one
 * hour.
 *
 * Previously RecordingTimer and PlaybackPanel each had their own copy of
 * this (formatElapsed / formatDuration), with different padding and
 * hour-rollover behavior — the same five seconds rendered as "00:05" in
 * one place and "0:05" in the other. That was flagged during the
 * Sprint 2.7 review as unintentional drift, not a deliberate distinction.
 * This is the single shared version both now use.
 *
 * Defensively clamps non-finite or negative input to zero rather than
 * rendering "NaN:NaN" or a negative time — negative values are the
 * realistic case (a system clock adjusted backwards mid-recording).
 */
export function formatDuration(ms: number): string {
  const safeMs = Number.isFinite(ms) && ms > 0 ? ms : 0;

  const totalSeconds = Math.floor(safeMs / 1000);
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;

  const pad = (n: number) => n.toString().padStart(2, "0");

  return hours > 0
    ? `${pad(hours)}:${pad(minutes)}:${pad(seconds)}`
    : `${pad(minutes)}:${pad(seconds)}`;
}
