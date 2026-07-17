"use client";

import { ErrorMessage } from "@/components/ErrorMessage";
import { RecordingControls } from "@/features/audio-recording/components/RecordingControls";
import { RecordingStatusBadge } from "@/features/audio-recording/components/RecordingStatusBadge";
import { RecordingTimer } from "@/features/audio-recording/components/RecordingTimer";
import { UnsupportedBrowserNotice } from "@/features/audio-recording/components/UnsupportedBrowserNotice";
import { WaveformVisualizer } from "@/features/audio-recording/components/WaveformVisualizer";
import type { UseAudioRecorderResult } from "@/features/audio-recording/hooks/useAudioRecorder";
import { useRecordingShortcuts } from "@/features/audio-recording/hooks/useRecordingShortcuts";

/**
 * The "Recording" feature group (status, live waveform, timer,
 * pause/resume/stop) — identical in spirit to /practice's
 * PracticeScreen, reusing the exact same components from
 * features/audio-recording/ rather than re-implementing them. The one
 * difference from PracticeScreen: once stopped, /analyze shows
 * RecordingReviewPanel (with an "Analyze" primary action) instead of
 * PlaybackPanel — that swap happens one level up, in AnalyzeScreen,
 * which is why this component only covers the in-progress states.
 */
export function LiveRecordingSection({ recorder }: { recorder: UseAudioRecorderResult }) {
  const { status, elapsedMs, mediaStream, browserSupport, errorMessage, pause, resume, stop, reset } = recorder;

  // Milestone A's keyboard-shortcut requirement: R record, P pause/resume,
  // S stop — see the hook's own docstring for why this never hijacks
  // normal typing. Registered unconditionally (not just while browser
  // support is confirmed) since the hook itself is a no-op until a key is
  // actually pressed, and status already gates every action correctly.
  useRecordingShortcuts({ status, onRecord: recorder.record, onPause: pause, onResume: resume, onStop: stop });

  if (browserSupport) {
    return <UnsupportedBrowserNotice support={browserSupport} />;
  }

  return (
    <div className="flex w-full flex-col items-center gap-6">
      <RecordingStatusBadge status={status} />

      {errorMessage && <ErrorMessage message={errorMessage} />}

      <WaveformVisualizer status={status} stream={mediaStream} />
      <RecordingTimer elapsedMs={elapsedMs} />
      <RecordingControls
        status={status}
        onRecord={recorder.record}
        onPause={pause}
        onResume={resume}
        onStop={stop}
        onReset={reset}
      />
      <p className="text-xs text-muted-foreground">Shortcuts: R record · P pause/resume · S stop</p>
    </div>
  );
}
