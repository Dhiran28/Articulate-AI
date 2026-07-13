"use client";

import { RotateCcw, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";

import { formatDuration } from "../lib/formatDuration";
import type { RecordingArtifact } from "../types";

interface PlaybackPanelProps {
  artifact: RecordingArtifact;
  playbackUrl: string;
  onRecordAgain: () => void;
  onDelete: () => void;
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  const kb = bytes / 1024;
  return kb < 1024 ? `${kb.toFixed(1)} KB` : `${(kb / 1024).toFixed(1)} MB`;
}

/**
 * Shown once a recording is finished (status === "stopped"), replacing
 * the primary transport controls: playback, restart, and delete for the
 * take that was just captured.
 *
 * Playback uses the browser's native <audio controls> rather than a
 * hand-rolled play/pause button and a custom hook to track its state.
 * The native element already handles play/pause/seek/volume reliably
 * and accessibly (keyboard control included) — wrapping that in custom
 * state would mean re-solving an already-solved problem for no benefit
 * at this stage. If a future sprint needs a fully custom player (e.g.
 * one integrated with a real waveform), that's the point to introduce
 * a dedicated hook — not before there's an actual design that needs it.
 *
 * One limitation worth naming: MediaRecorder-produced audio blobs often
 * don't carry a proper duration header (they're captured as a live
 * stream, not written as a pre-sized file), so the native player's own
 * scrubber/duration readout can show as 0:00 or be inaccurate in some
 * browsers. The duration shown above the player is NOT read from the
 * audio element — it's the value this app tracked itself from real
 * timestamps while recording (see useAudioRecorder), so it's correct
 * regardless of what the player displays.
 *
 * Delete is a permanent, unrecoverable action (there's no undo and no
 * backend copy to restore from), so it's gated behind a native confirm()
 * dialog rather than firing immediately on click. A native dialog was
 * chosen over a custom one for this: it's keyboard- and screen-reader
 * accessible by default, and the extra weight of a custom confirmation
 * component isn't justified for a single destructive action on one screen.
 */
export function PlaybackPanel({
  artifact,
  playbackUrl,
  onRecordAgain,
  onDelete,
}: PlaybackPanelProps) {
  const handleDelete = () => {
    if (window.confirm("Delete this recording? This can't be undone.")) {
      onDelete();
    }
  };

  return (
    <div className="flex w-full flex-col items-center gap-4 rounded-lg border border-border p-4">
      <p className="text-sm text-muted-foreground">
        Duration:{" "}
        <span className="font-medium text-foreground">{formatDuration(artifact.durationMs)}</span>
        <span className="mx-1.5">·</span>
        {formatBytes(artifact.blob.size)}
      </p>

      <audio controls src={playbackUrl} className="w-full" />

      <div className="flex flex-wrap items-center justify-center gap-3">
        <Button onClick={onRecordAgain} variant="secondary" size="lg" className="gap-2">
          <RotateCcw className="h-4 w-4" aria-hidden="true" />
          Record Again
        </Button>

        <Button onClick={handleDelete} variant="destructive" size="lg" className="gap-2">
          <Trash2 className="h-4 w-4" aria-hidden="true" />
          Delete
        </Button>
      </div>
    </div>
  );
}
