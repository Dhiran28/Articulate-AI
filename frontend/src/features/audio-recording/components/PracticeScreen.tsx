"use client";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

import { useAudioRecorder } from "../hooks/useAudioRecorder";
import { PlaybackPanel } from "./PlaybackPanel";
import { RecordingControls } from "./RecordingControls";
import { RecordingStatusBadge } from "./RecordingStatusBadge";
import { RecordingTimer } from "./RecordingTimer";
import { UnsupportedBrowserNotice } from "./UnsupportedBrowserNotice";
import { WaveformVisualizer } from "./WaveformVisualizer";

/**
 * Composes the Practice screen and owns the one hook that drives it.
 *
 * As of Sprint 2.2 this uses the real `useAudioRecorder` hook (browser
 * microphone capture via MediaRecorder) instead of Sprint 2.1's
 * `useRecordingUIState` mock. The component tree and prop-drilling
 * approach underneath are unchanged — being able to swap the hook
 * without touching this file or any of its children was the entire
 * point of designing it behind one interface in ADR 001.
 *
 * As of Sprint 2.3, the screen shows one of two mutually exclusive
 * views: the transport controls (record/pause/resume/stop) while a
 * recording is idle or in progress, or the playback panel
 * (play/record again/delete) once a recording exists. Showing both at
 * once would give two different ways to "start over" (Record vs. Record
 * Again) at the same time, which is confusing rather than flexible.
 *
 * As of Sprint 2.4, the waveform is real: WaveformVisualizer reads the
 * hook's `mediaStream` directly rather than just `status`, since it
 * needs the live stream to visualize, not just to know what state
 * recording is in.
 *
 * As of Sprint 2.6, `browserSupport` gates everything else: if it's set
 * (unsupported browser, or an insecure connection), the whole recording
 * UI — status badge, waveform, timer, controls — is replaced by
 * UnsupportedBrowserNotice. None of those controls would work anyway,
 * and showing them disabled with an error underneath would look broken
 * rather than explain what's actually going on.
 */
export function PracticeScreen() {
  const {
    status,
    elapsedMs,
    artifact,
    playbackUrl,
    mediaStream,
    browserSupport,
    errorMessage,
    record,
    pause,
    resume,
    stop,
    reset,
  } = useAudioRecorder();

  const hasFinishedRecording = status === "stopped" && artifact !== null && playbackUrl !== null;

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
          {browserSupport ? (
            <UnsupportedBrowserNotice support={browserSupport} />
          ) : (
            <>
              <RecordingStatusBadge status={status} />

              {errorMessage && (
                <p role="alert" className="text-center text-sm text-destructive">
                  {errorMessage}
                </p>
              )}

              {hasFinishedRecording ? (
                <PlaybackPanel
                  artifact={artifact}
                  playbackUrl={playbackUrl}
                  onRecordAgain={record}
                  onDelete={reset}
                />
              ) : (
                <>
                  <WaveformVisualizer status={status} stream={mediaStream} />
                  <RecordingTimer elapsedMs={elapsedMs} />
                  <RecordingControls
                    status={status}
                    onRecord={record}
                    onPause={pause}
                    onResume={resume}
                    onStop={stop}
                    onReset={reset}
                  />
                </>
              )}
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
