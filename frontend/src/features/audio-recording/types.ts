/**
 * Recording states for the Practice screen.
 *
 * Sprint 2.1 only used idle/recording/paused/stopped, since there was no
 * real microphone access that could be pending or fail. Now that Sprint
 * 2.2 wires up getUserMedia and MediaRecorder, `requesting_permission`
 * and `error` are real, reachable states — matching the full machine
 * described in docs/decisions/001-audio-recording-module-architecture.md.
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
