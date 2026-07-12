"use client";

import { MicOff } from "lucide-react";

import type { MicrophoneError } from "../lib/microphoneError";

interface UnsupportedBrowserNoticeProps {
  support: MicrophoneError;
}

/**
 * Replaces the entire recording UI (controls, waveform, everything) when
 * this browser or connection can't record at all — covers both
 * "unsupported browser" and "insecure connection" (see
 * lib/microphoneError.ts's checkBrowserSupport). Neither is something a
 * Retry button could fix, unlike a denied permission or a busy
 * microphone, so this doesn't offer one — the copy tells the user what
 * to actually do instead (switch browsers, or reload over HTTPS).
 */
export function UnsupportedBrowserNotice({ support }: UnsupportedBrowserNoticeProps) {
  return (
    <div
      role="alert"
      className="flex w-full flex-col items-center gap-3 rounded-lg border border-border bg-muted/30 px-6 py-10 text-center"
    >
      <MicOff className="h-8 w-8 text-muted-foreground" aria-hidden="true" />
      <p className="text-sm font-medium text-foreground">Recording isn&apos;t available</p>
      <p className="max-w-sm text-sm text-muted-foreground">{support.message}</p>
    </div>
  );
}
