/**
 * Formats a byte count as a short, human-readable size string
 * ("512 B", "3.2 KB", "1.4 MB").
 *
 * RC1 consolidation: this exact 4-line implementation used to be
 * copy-pasted independently in three places — PlaybackPanel.tsx,
 * RecordingReviewPanel.tsx, and FilePreviewPanel.tsx — the same kind of
 * unintentional-drift risk formatDuration.ts's own docstring describes
 * for time formatting (flagged in Sprint 2.7's review, fixed then for
 * duration but never done for byte sizes). One shared copy here, in
 * src/lib rather than a feature folder, since it's genuinely
 * feature-agnostic and used across both audio-recording and analyze.
 */
export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  const kb = bytes / 1024;
  return kb < 1024 ? `${kb.toFixed(1)} KB` : `${(kb / 1024).toFixed(1)} MB`;
}
