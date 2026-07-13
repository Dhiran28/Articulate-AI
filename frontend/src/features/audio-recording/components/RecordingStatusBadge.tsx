"use client";

import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

import type { RecordingStatus } from "../types";

const STATUS_LABEL: Record<RecordingStatus, string> = {
  idle: "Idle",
  requesting_permission: "Requesting Mic Access",
  recording: "Recording",
  paused: "Paused",
  stopped: "Stopped",
  error: "Error",
};

// Colors verified against WCAG AA (4.5:1 for normal-size text) with white
// foreground text, since this badge renders at text-xs (12px):
//   blue-600    ~5.17:1   (blue-500 measured ~3.68:1 — failed)
//   amber-700   ~5.02:1   (amber-500 measured ~2.15:1 — failed badly)
//   emerald-700 ~5.48:1   (emerald-600 measured ~3.77:1 — failed)
//   red-600     ~4.83:1   (already passing, unchanged)
//   red-800     darker than red-600, passes with margin (unchanged)
const STATUS_CLASSES: Record<RecordingStatus, string> = {
  idle: "bg-muted text-muted-foreground",
  requesting_permission: "bg-blue-600 text-white",
  recording: "bg-red-600 text-white",
  paused: "bg-amber-700 text-white",
  stopped: "bg-emerald-700 text-white",
  error: "bg-red-800 text-white",
};

interface RecordingStatusBadgeProps {
  status: RecordingStatus;
}

/**
 * Visual and screen-reader-accessible indicator of the current recording
 * state. `aria-live="polite"` means assistive tech announces state
 * changes (e.g. "Recording" -> "Paused") without the user needing to
 * refocus anything — this control is operated by ear as much as by
 * sight.
 */
export function RecordingStatusBadge({ status }: RecordingStatusBadgeProps) {
  return (
    <div aria-live="polite">
      <Badge
        className={cn(
          "gap-1.5 border-transparent px-3 py-1 text-xs font-medium",
          STATUS_CLASSES[status]
        )}
      >
        {status === "recording" && (
          <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-white" />
        )}
        {STATUS_LABEL[status]}
      </Badge>
    </div>
  );
}
