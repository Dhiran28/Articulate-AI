"use client";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

import { useAudioRecorder } from "../hooks/useAudioRecorder";
import { RecordingControls } from "./RecordingControls";
import { RecordingStatusBadge } from "./RecordingStatusBadge";
import { RecordingTimer } from "./RecordingTimer";
import { WaveformPlaceholder } from "./WaveformPlaceholder";

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  const kb = bytes / 1024;
  return kb < 1024 ? `${kb.toFixed(1)} KB` : `${(kb / 1024).toFixed(1)} MB`;
}

/**
 * Composes the Practice screen and owns the one hook that drives it.
 *
 * As of Sprint 2.2 this uses the real `useAudioRecorder` hook (browser
 * microphone capture via MediaRecorder) instead of Sprint 2.1's
 * `useRecordingUIState` mock. The component tree and prop-drilling
 * approach underneath are unchanged — being able to swap the hook
 * without touching this file or any of its children was the entire
 * point of designing it behind one interface in ADR 001.
 */
export function PracticeScreen() {
  const { status, elapsedMs, artifact, errorMessage, record, pause, resume, stop, reset } =
    useAudioRecorder();

  return (
    <div className="flex min-h-screen items-center justify-center p-6">
      <Card className="w-full max-w-xl">
        <CardHeader className="items-center text-center">
          <CardTitle className="text-2xl">Practice</CardTitle>
          <CardDescription>
            Record yourself speaking, then review the structure of what you said.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col items-center gap-6">
          <RecordingStatusBadge status={status} />

          {errorMessage && (
            <p role="alert" className="text-center text-sm text-destructive">
              {errorMessage}
            </p>
          )}

          <WaveformPlaceholder status={status} />
          <RecordingTimer elapsedMs={elapsedMs} />

          <RecordingControls
            status={status}
            onRecord={record}
            onPause={pause}
            onResume={resume}
            onStop={stop}
            onReset={reset}
          />

          {artifact && (
            <p className="text-xs text-muted-foreground">
              Recording captured — {formatBytes(artifact.blob.size)}, {artifact.mimeType}
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
