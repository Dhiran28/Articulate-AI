import type { RecordingArtifact } from "@/features/audio-recording/types";

const MIME_TO_EXTENSION: Record<string, string> = {
  "audio/webm": "webm",
  "audio/ogg": "ogg",
  "audio/mp4": "m4a",
  "audio/wav": "wav",
  "audio/mpeg": "mp3",
};

/**
 * Turns a finished recording (a Blob plus metadata — see
 * features/audio-recording/types.ts) into a `File`, the shape
 * analyzeClient.ts (and the backend's `POST /analyze`) actually expects.
 * A browser MediaRecorder produces a Blob, not a File, and never a
 * filename — this is the one small translation step between "a
 * finished recording" and "something uploadable," kept in the Analyze
 * feature rather than audio-recording, since audio-recording has no
 * reason to know anything about uploading.
 */
export function recordingArtifactToFile(artifact: RecordingArtifact): File {
  const extension = MIME_TO_EXTENSION[artifact.mimeType.split(";")[0]] ?? "webm";
  const filename = `recording-${new Date(artifact.createdAt).toISOString().replace(/[:.]/g, "-")}.${extension}`;
  return new File([artifact.blob], filename, { type: artifact.mimeType });
}
