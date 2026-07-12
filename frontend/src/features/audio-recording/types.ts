/**
 * Recording states for the Practice screen, matching the state machine
 * described in docs/decisions/001-audio-recording-module-architecture.md.
 * The transitions between them live in state/recordingMachine.ts.
 *
 * Note on where other module types live: this file holds the shared
 * domain shapes (this and RecordingArtifact, below) that are referenced
 * across many files. Types that are tightly coupled to one specific
 * piece of logic — AudioSource in lib/audioSource.ts, RecordingSink in
 * lib/recordingSink.ts, WaveformSource in lib/waveformSource.ts,
 * MicrophoneError in lib/microphoneError.ts — are defined alongside that
 * logic instead, so the interface and its only (or primary)
 * implementation stay in the same place.
 */
export type RecordingStatus =
  | "idle"
  | "requesting_permission"
  | "recording"
  | "paused"
  | "stopped"
  | "error";

/**
 * A finished recording, produced by an AudioSource and handed to a
 * RecordingSink. `source` is deliberately a discriminable field (not
 * just "browser" forever) so the backend's future data model doesn't
 * need a breaking change when ESP32/Quest 3 capture is added later.
 */
export interface RecordingArtifact {
  blob: Blob;
  mimeType: string;
  durationMs: number;
  createdAt: number;
  source: "browser";
}
