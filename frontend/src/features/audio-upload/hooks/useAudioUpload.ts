"use client";

import { useCallback, useState } from "react";

import { AudioUploadError, uploadAudioFile, type UploadedAudioAsset } from "../lib/uploadClient";
import { validateAudioFileClientSide } from "../lib/validateAudioFile";

export type AudioUploadStatus = "idle" | "uploading" | "success" | "error";

export interface UseAudioUploadResult {
  status: AudioUploadStatus;
  asset: UploadedAudioAsset | null;
  errorMessage: string | null;
  upload: (file: File) => Promise<void>;
  reset: () => void;
}

/**
 * Drives the "upload an existing audio file" flow: client-side pre-check
 * for instant feedback, then POST /api/upload, tracked through a small
 * status enum (idle/uploading/success/error) — the same shape
 * useAudioRecorder uses for its own status, for consistency across the
 * two features.
 */
export function useAudioUpload(): UseAudioUploadResult {
  const [status, setStatus] = useState<AudioUploadStatus>("idle");
  const [asset, setAsset] = useState<UploadedAudioAsset | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const upload = useCallback(async (file: File) => {
    const clientError = validateAudioFileClientSide(file);
    if (clientError) {
      setAsset(null);
      setErrorMessage(clientError.message);
      setStatus("error");
      return;
    }

    setStatus("uploading");
    setErrorMessage(null);

    try {
      const uploaded = await uploadAudioFile(file);
      setAsset(uploaded);
      setStatus("success");
    } catch (err) {
      console.error("Audio upload failed:", err);
      setAsset(null);
      setErrorMessage(
        err instanceof AudioUploadError
          ? err.message
          : "Something went wrong uploading the file. Please try again."
      );
      setStatus("error");
    }
  }, []);

  const reset = useCallback(() => {
    setStatus("idle");
    setAsset(null);
    setErrorMessage(null);
  }, []);

  return { status, asset, errorMessage, upload, reset };
}
