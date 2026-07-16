"use client";

import { createContext, useCallback, useContext, useMemo, useRef, useState, type ReactNode } from "react";

/**
 * Carries a file the user picked or dropped on the Home page across the
 * client-side navigation to /analyze, without going through the URL or
 * sessionStorage — a `File`/`Blob` can't be serialized into either.
 *
 * This works because Next.js App Router navigation between routes under
 * the same layout is a client-side transition, not a full page load:
 * `Providers` (see src/app/providers.tsx) is mounted once, above the
 * router outlet, in the root layout, so this Context's state survives
 * `router.push("/analyze")` intact. It does NOT survive a hard refresh
 * or a direct URL visit to /analyze — that's a disclosed, acceptable
 * limitation for this MVP: /analyze's own capture chooser (the same
 * CaptureChooser component Home uses) is always there as a fallback
 * when no pending file exists, so landing on /analyze with nothing
 * pending is never a dead end, just a fresh start.
 *
 * The "record" path doesn't need this at all — Home's Record button
 * navigates straight to `/analyze?start=record`, and /analyze's own
 * `useAudioRecorder` instance starts itself from that query param
 * (see AnalyzeScreen). Only a concrete File (from upload or drag&drop)
 * needs to be carried across the navigation like this.
 */
interface PendingCaptureContextValue {
  /** True once a file has been set and not yet consumed by /analyze. */
  hasPendingFile: boolean;
  setPendingFile: (file: File) => void;
  /** Reads and clears the pending file in one call, so a later remount of /analyze doesn't see a stale one. */
  consumePendingFile: () => File | null;
}

const PendingCaptureContext = createContext<PendingCaptureContextValue | null>(null);

export function PendingCaptureProvider({ children }: { children: ReactNode }) {
  // A ref, not state: the file itself never needs to trigger a
  // re-render of anything holding the context — only `hasPendingFile`
  // (a boolean) does, for the rare case something wants to react to
  // "a file just became pending." Consumers that need the file itself
  // call consumePendingFile() once, imperatively, on mount.
  const fileRef = useRef<File | null>(null);
  const [hasPendingFile, setHasPendingFile] = useState(false);

  const setPendingFile = useCallback((file: File) => {
    fileRef.current = file;
    setHasPendingFile(true);
  }, []);

  const consumePendingFile = useCallback((): File | null => {
    const file = fileRef.current;
    fileRef.current = null;
    setHasPendingFile(false);
    return file;
  }, []);

  const value = useMemo(
    () => ({ hasPendingFile, setPendingFile, consumePendingFile }),
    [hasPendingFile, setPendingFile, consumePendingFile]
  );

  return <PendingCaptureContext.Provider value={value}>{children}</PendingCaptureContext.Provider>;
}

export function usePendingCapture(): PendingCaptureContextValue {
  const context = useContext(PendingCaptureContext);
  if (!context) {
    throw new Error("usePendingCapture must be used within a PendingCaptureProvider");
  }
  return context;
}
