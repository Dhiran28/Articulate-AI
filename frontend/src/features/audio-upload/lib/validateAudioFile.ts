const ALLOWED_EXTENSIONS = ["wav", "mp3", "m4a", "webm"] as const;

// Mirrors the backend's default MAX_UPLOAD_SIZE_MB (see
// backend/app/core/config.py). Duplicated deliberately for instant
// client-side feedback without a round trip — but this is a UX nicety
// only, not enforcement. The server re-validates every upload regardless
// of what runs here, and if the two ever drift (someone changes the
// backend's configured limit without updating this constant), the
// server's answer is still the one that actually matters.
const MAX_SIZE_BYTES = 25 * 1024 * 1024;

export interface AudioFileValidationError {
  reason: "unsupported_format" | "file_too_large" | "empty_file";
  message: string;
}

/**
 * Client-side pre-check for the upload picker. Not a substitute for the
 * backend's own validation (see uploadClient.ts) — trivially bypassable,
 * and only checks what's cheap to know before a network call: extension
 * and file size.
 */
export function validateAudioFileClientSide(file: File): AudioFileValidationError | null {
  const extension = file.name.split(".").pop()?.toLowerCase();

  if (!extension || !(ALLOWED_EXTENSIONS as readonly string[]).includes(extension)) {
    return {
      reason: "unsupported_format",
      message: "Only .wav, .mp3, .m4a, and .webm files are supported.",
    };
  }

  if (file.size === 0) {
    return { reason: "empty_file", message: "That file is empty." };
  }

  if (file.size > MAX_SIZE_BYTES) {
    return {
      reason: "file_too_large",
      message: `Files must be ${MAX_SIZE_BYTES / (1024 * 1024)} MB or smaller.`,
    };
  }

  return null;
}
