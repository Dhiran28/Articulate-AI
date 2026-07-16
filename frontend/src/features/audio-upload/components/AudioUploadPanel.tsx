"use client";

import { useRef, type ChangeEvent } from "react";
import { UploadCloud } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

import { useAudioUpload } from "../hooks/useAudioUpload";

const ACCEPTED_EXTENSIONS = ".wav,.mp3,.m4a,.webm";

/**
 * Lets a user upload an existing audio file directly, as an alternative
 * to recording one live on this screen. Kept as its own feature folder
 * rather than folded into audio-recording — recording and uploading are
 * different capabilities that happen to both end up as audio bytes for
 * the same backend endpoint, the same reasoning ADR 001 used to keep
 * AudioSource and WaveformSource as separate interfaces even though they
 * often read the same stream.
 *
 * The uploaded file is stored temporarily by the backend and nothing
 * else — no transcription happens yet (see Sprint 3.2 / ADR 002).
 */
export function AudioUploadPanel() {
  const inputRef = useRef<HTMLInputElement>(null);
  const { status, asset, errorMessage, upload, reset } = useAudioUpload();

  const handleFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    // Clear the input's value so selecting the same file again (e.g.
    // after "Upload another file") still fires a change event.
    event.target.value = "";
    if (file) void upload(file);
  };

  return (
    <Card className="w-full max-w-xl">
      <CardHeader>
        <CardTitle className="text-lg">Upload a recording</CardTitle>
        <CardDescription>
          Already have an audio file? Upload it directly — .wav, .mp3, .m4a, or .webm.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col items-center gap-3">
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPTED_EXTENSIONS}
          className="hidden"
          onChange={handleFileChange}
        />

        <Button
          onClick={() => inputRef.current?.click()}
          disabled={status === "uploading"}
          variant="secondary"
          className="gap-2"
        >
          <UploadCloud className="h-4 w-4" aria-hidden="true" />
          {status === "uploading" ? "Uploading…" : "Choose a file"}
        </Button>

        <div role="status" aria-live="polite" className="text-center text-sm">
          {status === "success" && asset && (
            <p className="text-emerald-700">
              Uploaded {asset.original_filename} ({(asset.size_bytes / (1024 * 1024)).toFixed(1)} MB).
              Not transcribed yet.
            </p>
          )}
          {status === "error" && errorMessage && (
            <p role="alert" className="text-destructive">
              {errorMessage}
            </p>
          )}
        </div>

        {(status === "success" || status === "error") && (
          <Button onClick={reset} variant="ghost" size="sm">
            Upload another file
          </Button>
        )}
      </CardContent>
    </Card>
  );
}
