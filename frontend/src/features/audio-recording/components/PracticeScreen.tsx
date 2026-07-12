"use client";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

import { useRecordingUIState } from "../hooks/useRecordingUIState";
import { RecordingControls } from "./RecordingControls";
import { RecordingStatusBadge } from "./RecordingStatusBadge";
import { RecordingTimer } from "./RecordingTimer";
import { WaveformPlaceholder } from "./WaveformPlaceholder";

/**
 * Composes the Practice screen from its pieces and owns the one hook
 * that drives all of them.
 *
 * State is passed down as plain props rather than through a
 * RecordingProvider context, even though ADR 001 sketches a context for
 * the eventual real implementation. For a single flat screen with a
 * handful of direct children, prop drilling one level is simpler than a
 * context and just as easy to follow. Context earns its cost once state
 * needs to reach components nested deeper than this, or needs to be read
 * from outside this screen — worth revisiting when Sprint 2.2 wires up
 * real microphone capture, which has more state and lifecycle to manage.
 */
export function PracticeScreen() {
  const { status, elapsedMs, record, pause, resume, stop, reset } = useRecordingUIState();

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
        </CardContent>
      </Card>
    </div>
  );
}
