"use client";

import { useCallback, useState } from "react";
import { useMutation } from "@tanstack/react-query";

import type { CommunicationReport } from "@/features/results/types";

import { analyzeAudio } from "../lib/analyzeClient";

/**
 * Wraps analyzeAudio() in a React Query mutation — the "server state"
 * half of the Analyze feature (see src/app/providers.tsx's docstring for
 * the split with client-state Contexts). React Query gives this hook
 * `isPending`/`isError`/`error`/`data` for free, and a `mutate`/`reset`
 * API the UI can drive directly.
 *
 * Upload progress is tracked outside the mutation's own state, in a
 * plain `useState` here: React Query's `useMutation` has no built-in
 * concept of "percent complete" for an in-flight mutation (it's designed
 * around request/response, not progress events), so this hook adds the
 * one piece React Query doesn't cover, alongside the piece it does.
 */
export function useAnalyzeMutation() {
  const [uploadProgress, setUploadProgress] = useState(0);

  const mutation = useMutation<CommunicationReport, Error, File>({
    mutationFn: (file: File) => {
      setUploadProgress(0);
      return analyzeAudio(file, { onUploadProgress: setUploadProgress });
    },
  });

  const analyze = useCallback(
    (file: File) => {
      mutation.mutate(file);
    },
    [mutation]
  );

  const reset = useCallback(() => {
    setUploadProgress(0);
    mutation.reset();
  }, [mutation]);

  return {
    analyze,
    reset,
    uploadProgress,
    isUploading: mutation.isPending && uploadProgress < 100,
    isProcessing: mutation.isPending && uploadProgress >= 100,
    isError: mutation.isError,
    error: mutation.error,
    isSuccess: mutation.isSuccess,
    report: mutation.data,
  };
}
