"use client";

import { useEffect, useState } from "react";
import { FileAudio, Sparkles, XCircle } from "lucide-react";

import { Button } from "@/components/ui/button";

interface FilePreviewPanelProps {
  file: File;
  onAnalyze: () => void;
  onChooseDifferentFile: () => void;
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  const kb = bytes / 1024;
  return kb < 1024 ? `${kb.toFixed(1)} KB` : `${(kb / 1024).toFixed(1)} MB`;
}

/**
 * The upload/drag-and-drop equivalent of RecordingReviewPanel: lets the
 * user hear the file they picked before submitting it ("Audio playback
 * before upload" applies here too, not just to live recordings).
 *
 * Creates its own object URL from the File — separate from
 * audio-recording's RecordingSink (LocalObjectUrlSink), which only ever
 * wraps a freshly-recorded Blob, not an arbitrary File a user picked.
 * Revoked on unmount/file-change via the effect below, the same
 * lifecycle discipline useAudioRecorder's own cleanup effect follows
 * for its own object URLs.
 */
export function FilePreviewPanel({ file, onAnalyze, onChooseDifferentFile }: FilePreviewPanelProps) {
  const [objectUrl, setObjectUrl] = useState<string | null>(null);

  useEffect(() => {
    const url = URL.createObjectURL(file);
    setObjectUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  return (
    <div className="flex w-full flex-col items-center gap-4 rounded-lg border border-border p-4">
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <FileAudio className="h-4 w-4" aria-hidden="true" />
        <span className="font-medium text-foreground">{file.name}</span>
        <span>·</span>
        <span>{formatBytes(file.size)}</span>
      </div>

      {objectUrl && <audio controls src={objectUrl} className="w-full" data-testid="playback-audio" />}

      <div className="flex flex-wrap items-center justify-center gap-3">
        <Button onClick={onAnalyze} size="lg" className="gap-2">
          <Sparkles className="h-4 w-4" aria-hidden="true" />
          Analyze this file
        </Button>
        <Button onClick={onChooseDifferentFile} variant="ghost" size="lg" className="gap-2">
          <XCircle className="h-4 w-4" aria-hidden="true" />
          Choose a different file
        </Button>
      </div>
    </div>
  );
}
