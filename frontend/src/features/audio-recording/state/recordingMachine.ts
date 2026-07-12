import type { RecordingStatus } from "../types";

export type RecordingMachineAction =
  | { type: "REQUEST_PERMISSION" }
  | { type: "PERMISSION_GRANTED" }
  | { type: "PERMISSION_DENIED" }
  | { type: "PAUSE" }
  | { type: "RESUME" }
  | { type: "STOP" }
  | { type: "RESET" }
  | { type: "ERROR" };

/**
 * The full recording state machine described in ADR 001.
 *
 * Sprint 2.1 used a smaller subset (idle/recording/paused/stopped)
 * because there was no real microphone access that could fail.
 * `requesting_permission` and `error` are real, reachable states now
 * that getUserMedia and MediaRecorder are involved — not speculative
 * ones added ahead of need.
 *
 * As in Sprint 2.1, invalid transitions are ignored rather than thrown:
 * the UI disables the relevant control for each case, so this is a
 * second line of defense.
 */
export function recordingMachineReducer(
  status: RecordingStatus,
  action: RecordingMachineAction
): RecordingStatus {
  switch (action.type) {
    case "REQUEST_PERMISSION":
      return status === "idle" || status === "stopped" || status === "error"
        ? "requesting_permission"
        : status;
    case "PERMISSION_GRANTED":
      return status === "requesting_permission" ? "recording" : status;
    case "PERMISSION_DENIED":
      return status === "requesting_permission" ? "error" : status;
    case "PAUSE":
      return status === "recording" ? "paused" : status;
    case "RESUME":
      return status === "paused" ? "recording" : status;
    case "STOP":
      return status === "recording" || status === "paused" ? "stopped" : status;
    case "RESET":
      return "idle";
    case "ERROR":
      return "error";
    default:
      return status;
  }
}
