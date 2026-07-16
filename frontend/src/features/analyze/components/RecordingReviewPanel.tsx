"use client";

import { RotateCcw, Trash2, Sparkles } from "lucide-react";

import { Button } from "@/components/ui/button";
import { formatDuration } from "@/features/audio-recording/lib/formatDuration";
import type { RecordingArtifact } from "@/features/audio-recording/types";
import { formatBytes } from "@/lib/formatBytes";

interface RecordingReviewPanelProps {
  artifact: RecordingArtifact;
  playbackUrl: string;
  onAnalyze: () => void;
  onRecordAgain: () => void;
  onDiscard: () => void;
}

/**
 * The Analyze page's equivalent of audio-recording's PlaybackPanel —
 * "Audio playback before upload" from the Recording feature list — but
 * with the primary action here being "Analyze," not "Record Again."
 * Kept as its own component instead of extending PlaybackPanel directly:
 * PlaybackPanel is /practice's component, with its own primary action
 * (Record Again) appropriate to a page that has nothing to submit
 * anywhere. Duplicating the small amount of markup (duration/size line
 * + native <audio controls>) was simpler and less risky than adding an
 * optional "primary action" prop to a component another page already
 * depends on.
 */
export function RecordingReviewPanel({
  artifact,
  playbackUrl,
  onAnalyze,
  onRecordAgain,
  onDiscard,
}: RecordingReviewPanelProps) {
  const handleDiscard = () => {
    if (window.confirm("Discard this recording? This can't be undone.")) {
      onDiscard();
    }
  };

  return (
    <div className="flex w-full flex-col items-center gap-4 rounded-lg border border-border p-4">
      <p className="text-sm text-muted-foreground">
        Duration: <span className="font-medium text-foreground">{formatDuration(artifact.durationMs)}</span>
        <span className="mx-1.5">·</span>
        {formatBytes(artifact.blob.size)}
      </p>

      <audio controls src={playbackUrl} className="w-full" data-testid="playback-audio" />

      <div className="flex flex-wrap items-center justify-center gap-3">
        <Button onClick={onAnalyze} size="lg" className="gap-2">
          <Sparkles className="h-4 w-4" aria-hidden="true" />
          Analyze this recording
        </Button>
        <Button onClick={onRecordAgain} variant="secondary" size="lg" className="gap-2">
          <RotateCcw className="h-4 w-4" aria-hidden="true" />
          Record Again
        </Button>
        <Button onClick={handleDiscard} variant="ghost" size="lg" className="gap-2 text-destructive">
          <Trash2 className="h-4 w-4" aria-hidden="true" />
          Discard
        </Button>
      </div>
    </div>
  );
}
