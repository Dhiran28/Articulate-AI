"use client";

import { AlertTriangle, Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";

interface SubmissionProgressProps {
  isUploading: boolean;
  isProcessing: boolean;
  uploadProgress: number;
  isError: boolean;
  errorMessage: string | null;
  onRetry: () => void;
  onCancel: () => void;
}

/**
 * The "Analysis" feature group's three required states — upload
 * progress, processing, and error handling — in one component, since
 * they're mutually exclusive moments of the same submission rather than
 * separate screens.
 *
 * Upload progress is a real, measured percentage (see analyzeClient.ts's
 * XHR-based `onUploadProgress`) — not a fake/simulated bar. Once the
 * upload reaches 100%, there is no further signal from the server until
 * the whole pipeline finishes (transcription, then up to two LLM
 * calls — ADR 004 §2), so "processing" is deliberately indeterminate
 * (a spinner, not a second progress bar that would have to lie about
 * how much is left).
 */
export function SubmissionProgress({
  isUploading,
  isProcessing,
  uploadProgress,
  isError,
  errorMessage,
  onRetry,
  onCancel,
}: SubmissionProgressProps) {
  if (isError) {
    return (
      <div
        role="alert"
        className="flex w-full flex-col items-center gap-4 rounded-lg border border-destructive/30 bg-destructive/5 p-6 text-center"
      >
        <AlertTriangle className="h-8 w-8 text-destructive" aria-hidden="true" />
        <p className="text-sm font-medium text-destructive">
          {errorMessage ?? "Something went wrong analyzing this recording."}
        </p>
        <div className="flex gap-3">
          <Button onClick={onRetry}>Try again</Button>
          <Button onClick={onCancel} variant="ghost">
            Start over
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex w-full flex-col items-center gap-4 rounded-lg border border-border p-6 text-center">
      <Loader2 className="h-8 w-8 animate-spin text-primary" aria-hidden="true" />

      {isUploading && (
        <div className="flex w-full flex-col gap-2">
          <p className="text-sm text-muted-foreground">Uploading… {uploadProgress}%</p>
          <div
            role="progressbar"
            aria-valuenow={uploadProgress}
            aria-valuemin={0}
            aria-valuemax={100}
            className="h-2 w-full overflow-hidden rounded-full bg-secondary"
          >
            <div
              className="h-full rounded-full bg-primary transition-all"
              style={{ width: `${uploadProgress}%` }}
            />
          </div>
        </div>
      )}

      {isProcessing && (
        <p className="text-sm text-muted-foreground">
          Analyzing your communication — transcribing, then reasoning about structure,
          clarity, and delivery. This can take a little while.
        </p>
      )}
    </div>
  );
}
