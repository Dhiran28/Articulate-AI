import { getApiBaseUrl } from "@/lib/apiConfig";

export interface UploadedAudioAsset {
  id: string;
  original_filename: string;
  format: "wav" | "mp3" | "m4a" | "webm";
  content_type: string;
  size_bytes: number;
  status: "stored";
  uploaded_at: string;
}

interface BackendErrorDetail {
  error: string;
  message: string;
}

/**
 * Thrown by uploadAudioFile with the backend's own classified reason
 * (unsupported_format / file_too_large / empty_file / not_found) and
 * friendly message, or "network_error" if the request never reached the
 * server — mirrors how lib/microphoneError.ts classifies recording
 * failures by kind rather than surfacing raw technical text.
 */
export class AudioUploadError extends Error {
  readonly reason: string;

  constructor(reason: string, message: string) {
    super(message);
    this.name = "AudioUploadError";
    this.reason = reason;
  }
}

/**
 * POSTs a single audio file to the backend's upload endpoint
 * (POST /api/upload — see ADR 002 and backend/app/api/upload.py). The
 * backend validates format and size and stores the file temporarily; it
 * does not transcribe it.
 */
export async function uploadAudioFile(file: File): Promise<UploadedAudioAsset> {
  const formData = new FormData();
  formData.append("file", file);

  let response: Response;
  try {
    response = await fetch(`${getApiBaseUrl()}/api/upload`, {
      method: "POST",
      body: formData,
    });
  } catch {
    throw new AudioUploadError(
      "network_error",
      "Couldn't reach the server. Check your connection and try again."
    );
  }

  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as { detail?: BackendErrorDetail } | null;
    const detail = body?.detail;
    throw new AudioUploadError(
      detail?.error ?? "unknown_error",
      detail?.message ?? "Something went wrong uploading the file. Please try again."
    );
  }

  return (await response.json()) as UploadedAudioAsset;
}
