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
 * Every transition here corresponds to something that can actually
 * happen with real microphone access: requesting permission can be
 * pending (`requesting_permission`) or fail (`error`) before recording
 * ever starts, not just succeed immediately.
 *
 * Invalid transitions are ignored rather than thrown: the UI disables
 * the relevant control for each case (see RecordingControls), so this
 * reducer is a second line of defense, not the primary guard.
 *
 * PERMISSION_DENIED covers any failure to start recording — permission
 * refused, no microphone found, the device already in use, and so on —
 * not literally only the user clicking "Block". lib/microphoneError.ts
 * is what tells those cases apart for the message shown to the user;
 * this state machine only needs to know "starting failed," since
 * idle/stopped/error all recover the same way (Record is enabled again
 * to retry).
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
