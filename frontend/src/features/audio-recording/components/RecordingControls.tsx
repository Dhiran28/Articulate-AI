"use client";

import { Circle, Pause, Play, RotateCcw, Square } from "lucide-react";

import { Button } from "@/components/ui/button";

import type { RecordingStatus } from "../types";

interface RecordingControlsProps {
  status: RecordingStatus;
  onRecord: () => void;
  onPause: () => void;
  onResume: () => void;
  onStop: () => void;
  onReset: () => void;
}

/**
 * All five transport controls in one component, rather than five
 * separate files each wrapping a single <Button>. Which buttons are
 * enabled at a given status is one small table (below) shared by all
 * five — keeping that in one place is easier to verify at a glance than
 * tracing it across five files, and there's no reuse case yet that would
 * justify splitting them apart.
 */
export function RecordingControls({
  status,
  onRecord,
  onPause,
  onResume,
  onStop,
  onReset,
}: RecordingControlsProps) {
  const canRecord = status === "idle" || status === "stopped";
  const canPause = status === "recording";
  const canResume = status === "paused";
  const canStop = status === "recording" || status === "paused";
  const canReset = status !== "idle";

  return (
    <div
      className="flex flex-wrap items-center justify-center gap-3"
      role="group"
      aria-label="Recording controls"
    >
      <Button onClick={onRecord} disabled={!canRecord} size="lg" className="gap-2">
        <Circle className="h-4 w-4 fill-current" />
        Record
      </Button>

      <Button
        onClick={onPause}
        disabled={!canPause}
        variant="secondary"
        size="lg"
        className="gap-2"
      >
        <Pause className="h-4 w-4" />
        Pause
      </Button>

      <Button
        onClick={onResume}
        disabled={!canResume}
        variant="secondary"
        size="lg"
        className="gap-2"
      >
        <Play className="h-4 w-4" />
        Resume
      </Button>

      <Button
        onClick={onStop}
        disabled={!canStop}
        variant="destructive"
        size="lg"
        className="gap-2"
      >
        <Square className="h-4 w-4 fill-current" />
        Stop
      </Button>

      <Button
        onClick={onReset}
        disabled={!canReset}
        variant="outline"
        size="lg"
        className="gap-2"
      >
        <RotateCcw className="h-4 w-4" />
        Reset
      </Button>
    </div>
  );
}
