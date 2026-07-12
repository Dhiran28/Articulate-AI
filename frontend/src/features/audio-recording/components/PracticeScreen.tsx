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
 * Composes the Practice screen from a single hook, useAudioRecorder,
 * with state passed down as plain props (see that hook for why: no
 * Context, no global store — this is one screen with a shallow tree).
 * Nothing here talks to the microphone or MediaRecorder directly; that
 * detail lives entirely behind the hook, per ADR 001's layering.
 *
 * Content within the card is gated by three conditions, checked in
 * order of how fundamental they are:
 *
 * 1. `browserSupport` — if the browser or connection can't record at
 *    all, everything else (status badge, waveform, timer, controls) is
 *    replaced by UnsupportedBrowserNotice. None of those controls would
 *    work anyway, and showing them disabled with an error underneath
 *    would look broken rather than explain what's going on.
 * 2. `hasFinishedRecording` — once a take exists, the transport controls
 *    (record/pause/resume/stop) are replaced by PlaybackPanel
 *    (play/record again/delete). The two are never shown together:
 *    Record and Record Again would otherwise be two different ways to
 *    do the same thing at the same time.
 * 3. Otherwise, the normal recording controls and live waveform are
 *    shown, driven directly by the hook's `status`, `elapsedMs`, and
 *    `mediaStream`.
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
