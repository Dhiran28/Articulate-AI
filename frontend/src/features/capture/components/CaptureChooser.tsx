"use client";

import { useRef, useState, type ChangeEvent } from "react";
import { useRouter } from "next/navigation";
import { Mic, UploadCloud } from "lucide-react";

import { ErrorMessage } from "@/components/ErrorMessage";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { validateAudioFileClientSide } from "@/features/audio-upload/lib/validateAudioFile";

import { usePendingCapture } from "../context/PendingCaptureContext";
import { useFileDropZone } from "../lib/dragAndDrop";

const ACCEPTED_EXTENSIONS = ".wav,.mp3,.m4a,.webm";

/**
 * The one place a user starts a new analysis: record live, upload an
 * existing file, or drag one in. Shared by the Home page (as the
 * primary call to action) and the Analyze page (as the fallback shown
 * whenever there's no recording in progress and no pending file — see
 * AnalyzeScreen). Sharing this component rather than duplicating it on
 * both pages is what keeps their capture behavior — validation,
 * copy, accepted formats — from drifting apart.
 *
 * Recording and file capture are handled completely differently here,
 * deliberately:
 *
 * - Record just navigates to `/analyze?start=record` — no audio state
 *   is created on this page at all. /analyze's own useAudioRecorder
 *   instance is what actually requests the microphone, once mounted
 *   there (see AnalyzeScreen). This avoids ever needing to hand a live
 *   MediaStream or MediaRecorder across a route change, which isn't
 *   possible to do safely anyway.
 * - Upload/drag-and-drop already have a concrete `File` in hand before
 *   any navigation happens, so that File is stashed in
 *   PendingCaptureContext (a plain in-memory reference, survives
 *   client-side navigation) and /analyze reads it back on mount.
 */
export function CaptureChooser() {
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);
  const { setPendingFile } = usePendingCapture();
  const [validationError, setValidationError] = useState<string | null>(null);

  const acceptFile = (file: File) => {
    const error = validateAudioFileClientSide(file);
    if (error) {
      setValidationError(error.message);
      return;
    }
    setValidationError(null);
    setPendingFile(file);
    router.push("/analyze");
  };

  const handleFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    // Reset so choosing the same file again still fires a change event.
    event.target.value = "";
    if (file) acceptFile(file);
  };

  const dropZone = useFileDropZone(acceptFile);

  const startRecording = () => {
    router.push("/analyze?start=record");
  };

  return (
    <Card className="w-full max-w-xl">
      <CardHeader className="items-center text-center">
        <CardTitle className="text-xl">Start a session</CardTitle>
        <CardDescription>Record yourself speaking, or upload a recording you already have.</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col items-center gap-4">
        <Button onClick={startRecording} size="lg" className="w-full gap-2 sm:w-auto">
          <Mic className="h-4 w-4" aria-hidden="true" />
          Record now
        </Button>

        <div className="flex w-full items-center gap-3 text-xs uppercase text-muted-foreground">
          <div className="h-px flex-1 bg-border" />
          or
          <div className="h-px flex-1 bg-border" />
        </div>

        <div
          onDragEnter={dropZone.onDragEnter}
          onDragLeave={dropZone.onDragLeave}
          onDragOver={dropZone.onDragOver}
          onDrop={dropZone.onDrop}
          className={cn(
            "flex w-full flex-col items-center gap-3 rounded-lg border-2 border-dashed p-6 text-center transition-colors",
            dropZone.isDraggingOver ? "border-primary bg-accent" : "border-input"
          )}
          data-testid="drop-zone"
        >
          <UploadCloud className="h-8 w-8 text-muted-foreground" aria-hidden="true" />
          <p className="text-sm text-muted-foreground">
            Drag and drop an audio file here, or
          </p>
          <input
            ref={inputRef}
            type="file"
            accept={ACCEPTED_EXTENSIONS}
            className="hidden"
            onChange={handleFileChange}
            aria-label="Upload an audio file"
          />
          <Button onClick={() => inputRef.current?.click()} variant="secondary" size="sm">
            Browse files
          </Button>
          <p className="text-xs text-muted-foreground">.wav, .mp3, .m4a, or .webm — up to 25 MB</p>
        </div>

        {validationError && <ErrorMessage message={validationError} />}
      </CardContent>
    </Card>
  );
}
