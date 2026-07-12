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

const STATUS_CLASSES: Record<RecordingStatus, string> = {
  idle: "bg-muted text-muted-foreground",
  requesting_permission: "bg-blue-500 text-white",
  recording: "bg-red-600 text-white",
  paused: "bg-amber-500 text-white",
  stopped: "bg-emerald-600 text-white",
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
