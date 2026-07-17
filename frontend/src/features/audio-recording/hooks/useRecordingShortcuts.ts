"use client";

import { useEffect } from "react";

import type { RecordingStatus } from "../types";

interface UseRecordingShortcutsArgs {
  status: RecordingStatus;
  onRecord: () => void;
  onPause: () => void;
  onResume: () => void;
  onStop: () => void;
}

/**
 * Milestone A's accessibility checklist item: keyboard shortcuts for the
 * same three actions RecordingControls exposes as buttons — R to
 * start/retry a recording, P to pause/resume, S to stop — so a
 * keyboard-only or screen-reader user isn't limited to tabbing through
 * five buttons for every action during an active recording.
 *
 * Two guards keep this from ever hijacking normal keyboard use:
 *  - Ignored while any modifier key is held, so it never shadows a
 *    browser or OS shortcut that happens to share a letter (Cmd+R, etc).
 *  - Ignored while focus is inside a text input, textarea, or any
 *    contenteditable element (e.g. the session label field on the
 *    Analyze page), so typing a word containing "r", "p", or "s" is
 *    never interpreted as a transport command.
 *
 * A document-level listener (not element-scoped) is deliberate: the
 * recording controls are meant to be operable without first clicking
 * into a specific element, the same way a hardware transport button
 * would be — but see the two guards above for why this is still safe.
 */
export function useRecordingShortcuts({
  status,
  onRecord,
  onPause,
  onResume,
  onStop,
}: UseRecordingShortcutsArgs): void {
  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (event.ctrlKey || event.metaKey || event.altKey) return;

      const target = event.target as HTMLElement | null;
      const tagName = target?.tagName;
      if (tagName === "INPUT" || tagName === "TEXTAREA" || target?.isContentEditable) return;

      switch (event.key.toLowerCase()) {
        case "r":
          if (status === "idle" || status === "stopped" || status === "error") {
            event.preventDefault();
            onRecord();
          }
          break;
        case "p":
          if (status === "recording") {
            event.preventDefault();
            onPause();
          } else if (status === "paused") {
            event.preventDefault();
            onResume();
          }
          break;
        case "s":
          if (status === "recording" || status === "paused") {
            event.preventDefault();
            onStop();
          }
          break;
      }
    }

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [status, onRecord, onPause, onResume, onStop]);
}
