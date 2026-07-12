import type { RecordingArtifact } from "../types";

/**
 * Where a finished recording goes once capture is done.
 *
 * Per ADR 001, this is the seam for cloud storage / backend upload in a
 * later sprint. Sprint 2.2 is scoped to capture only — no upload — so
 * the only implementation here works entirely in the browser: it turns
 * the artifact's Blob into an object URL (for a future playback view to
 * use) and nothing more. Swapping in an UploadSink later means adding a
 * new class that implements this same interface, not changing anything
 * that calls it.
 */
export interface RecordingSink {
  /** Persists (locally, in this implementation) and returns a URL usable by an <audio> element. */
  save(artifact: RecordingArtifact): string;
  /** Releases a URL previously returned by save(), to avoid leaking memory. */
  release(url: string): void;
}

export class LocalObjectUrlSink implements RecordingSink {
  save(artifact: RecordingArtifact): string {
    return URL.createObjectURL(artifact.blob);
  }

  release(url: string): void {
    URL.revokeObjectURL(url);
  }
}
