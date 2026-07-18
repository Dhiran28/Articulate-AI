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
  // Strip MediaRecorder's codec parameter (e.g. 'audio/webm;codecs="opus"'
  // -> "audio/webm") before using it anywhere — not just for the
  // extension lookup below, but for the File's own `type`, which becomes
  // the multipart Content-Type header the backend actually validates
  // against (app/audio/validation.py's _ALLOWED_CONTENT_TYPES does an
  // exact-match check with no codec suffix). Bug fix: this used to pass
  // the raw, codec-suffixed mimeType straight through as the File's
  // `type`, which the backend's exact-match check always rejected as
  // "unsupported_format" — even though the extension was correct — since
  // a live recording's mimeType (from MediaRecorder) always carries a
  // codec parameter, unlike a plain file picked from disk. This is why
  // uploading a file worked but analyzing a live recording didn't.
  const baseMimeType = artifact.mimeType.split(";")[0];
  const extension = MIME_TO_EXTENSION[baseMimeType] ?? "webm";
  const filename = `recording-${new Date(artifact.createdAt).toISOString().replace(/[:.]/g, "-")}.${extension}`;
  return new File([artifact.blob], filename, { type: baseMimeType });
}
