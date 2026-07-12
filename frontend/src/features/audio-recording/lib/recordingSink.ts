import type { RecordingArtifact } from "../types";

/**
 * Where a finished recording goes once capture is done.
 *
 * Per ADR 001, this is the seam for cloud storage / backend upload in a
 * later sprint. Recording capture and persisting/uploading a finished
 * recording are separate concerns, so the only implementation here
 * works entirely client-side: it turns the artifact's Blob into an
 * object URL for playback and nothing more — no network call. Swapping
 * in an UploadSink later means adding a new class that implements this
 * same interface, not changing anything that calls it.
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
