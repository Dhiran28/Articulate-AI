"use client";

import { useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useForm } from "react-hook-form";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { CaptureChooser } from "@/features/capture/components/CaptureChooser";
import { usePendingCapture } from "@/features/capture/context/PendingCaptureContext";
import { useAudioRecorder } from "@/features/audio-recording/hooks/useAudioRecorder";
import { useAnalysisResult } from "@/features/results/context/AnalysisResultContext";

import { useAnalyzeMutation } from "../hooks/useAnalyzeMutation";
import { recordingArtifactToFile } from "../lib/toAudioFile";
import { FilePreviewPanel } from "./FilePreviewPanel";
import { LiveRecordingSection } from "./LiveRecordingSection";
import { RecordingReviewPanel } from "./RecordingReviewPanel";
import { SessionLabelField, type SessionDetailsFormValues } from "./SessionLabelField";
import { SubmissionProgress } from "./SubmissionProgress";

/**
 * Orchestrates the whole Analyze page: capturing audio (by recording, or
 * by already having a file via CaptureChooser/PendingCaptureContext),
 * reviewing it before upload, submitting it to POST /analyze, and
 * routing to /results once a report exists.
 *
 * Which section renders is derived from three independent pieces of
 * state — the recorder's own status/artifact (useAudioRecorder already
 * owns this), `selectedFile` (a file from upload/drag-and-drop, or a
 * just-stopped recording converted to a File right before submission),
 * and the mutation's status (useAnalyzeMutation) — rather than a
 * separate hand-maintained "screen mode" enum that could drift out of
 * sync with any of them. See the render logic at the bottom for the
 * exact precedence between them.
 */
export function AnalyzeScreen() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const shouldAutoStartRecording = searchParams.get("start") === "record";

  const { hasPendingFile, consumePendingFile } = usePendingCapture();
  const { setReport } = useAnalysisResult();
  const recorder = useAudioRecorder();
  const mutation = useAnalyzeMutation();

  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [submittedFile, setSubmittedFile] = useState<File | null>(null);
  const [submittedLabel, setSubmittedLabel] = useState<string | null>(null);

  const { register, handleSubmit, formState } = useForm<SessionDetailsFormValues>({
    defaultValues: { sessionLabel: "" },
  });

  // Pull in a file stashed by CaptureChooser (upload or drag & drop), if
  // there is one. Reactive on `hasPendingFile` rather than mount-only,
  // so this also covers landing on /analyze with nothing pending (the
  // chooser shown as a fallback) and picking a file from there.
  useEffect(() => {
    if (hasPendingFile && !selectedFile) {
      const file = consumePendingFile();
      if (file) setSelectedFile(file);
    }
  }, [hasPendingFile, selectedFile, consumePendingFile]);

  useEffect(() => {
    if (shouldAutoStartRecording && !selectedFile && recorder.status === "idle") {
      void recorder.record();
    }
    // recorder.record is a stable useCallback (see useAudioRecorder) —
    // safe to omit from deps here without risking a stale closure.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [shouldAutoStartRecording, selectedFile, recorder.status]);

  useEffect(() => {
    if (mutation.isSuccess && mutation.report) {
      setReport(mutation.report, submittedLabel);
      // replace, not push: once analysis has completed, the back button
      // shouldn't return to a submission-in-progress screen for a
      // request that has already resolved.
      router.replace("/results");
    }
  }, [mutation.isSuccess, mutation.report, submittedLabel, setReport, router]);

  const onConfirmAnalyze = handleSubmit(({ sessionLabel }) => {
    const file =
      recorder.status === "stopped" && recorder.artifact
        ? recordingArtifactToFile(recorder.artifact)
        : selectedFile;
    if (!file) return;

    setSubmittedFile(file);
    setSubmittedLabel(sessionLabel.trim() || null);
    mutation.analyze(file);
  });

  const handleChooseDifferentFile = () => setSelectedFile(null);

  const handleRetry = () => {
    if (submittedFile) mutation.analyze(submittedFile);
  };

  const handleStartOver = () => {
    mutation.reset();
    setSelectedFile(null);
    setSubmittedFile(null);
    recorder.reset();
  };

  const hasStoppedRecording =
    recorder.status === "stopped" && recorder.artifact !== null && recorder.playbackUrl !== null;
  const hasSelectedUpload = selectedFile !== null && !hasStoppedRecording;
  const isRecordingLive =
    recorder.status === "requesting_permission" || recorder.status === "recording" || recorder.status === "paused";
  const isSubmitting = mutation.isUploading || mutation.isProcessing || mutation.isError;
  const shouldShowLiveRecording = isRecordingLive || (shouldAutoStartRecording && !selectedFile);

  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-6 p-6">
      <Card className="w-full max-w-xl">
        <CardHeader className="items-center text-center">
          <CardTitle className="text-2xl">Analyze a session</CardTitle>
          <CardDescription>
            Review your recording, then send it for structural analysis and coaching.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col items-center gap-6">
          {isSubmitting ? (
            <SubmissionProgress
              isUploading={mutation.isUploading}
              isProcessing={mutation.isProcessing}
              uploadProgress={mutation.uploadProgress}
              isError={mutation.isError}
              errorMessage={mutation.error?.message ?? null}
              onRetry={handleRetry}
              onCancel={handleStartOver}
            />
          ) : hasStoppedRecording && recorder.artifact && recorder.playbackUrl ? (
            <>
              <SessionLabelField register={register} error={formState.errors.sessionLabel} />
              <RecordingReviewPanel
                artifact={recorder.artifact}
                playbackUrl={recorder.playbackUrl}
                onAnalyze={onConfirmAnalyze}
                onRecordAgain={recorder.record}
                onDiscard={recorder.reset}
              />
            </>
          ) : hasSelectedUpload && selectedFile ? (
            <>
              <SessionLabelField register={register} error={formState.errors.sessionLabel} />
              <FilePreviewPanel
                file={selectedFile}
                onAnalyze={onConfirmAnalyze}
                onChooseDifferentFile={handleChooseDifferentFile}
              />
            </>
          ) : shouldShowLiveRecording ? (
            <LiveRecordingSection recorder={recorder} />
          ) : (
            <CaptureChooser />
          )}
        </CardContent>
      </Card>
    </div>
  );
}
