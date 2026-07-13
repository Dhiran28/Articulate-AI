import { describe, expect, it } from "vitest";

import type { RecordingStatus } from "../types";
import { recordingMachineReducer } from "./recordingMachine";

const ALL_STATUSES: RecordingStatus[] = [
  "idle",
  "requesting_permission",
  "recording",
  "paused",
  "stopped",
  "error",
];

describe("recordingMachineReducer", () => {
  it("moves from idle/stopped/error to requesting_permission on REQUEST_PERMISSION", () => {
    for (const status of ["idle", "stopped", "error"] as const) {
      expect(recordingMachineReducer(status, { type: "REQUEST_PERMISSION" })).toBe(
        "requesting_permission"
      );
    }
  });

  it("ignores REQUEST_PERMISSION from recording/paused/requesting_permission", () => {
    for (const status of ["recording", "paused", "requesting_permission"] as const) {
      expect(recordingMachineReducer(status, { type: "REQUEST_PERMISSION" })).toBe(status);
    }
  });

  it("moves from requesting_permission to recording on PERMISSION_GRANTED", () => {
    expect(recordingMachineReducer("requesting_permission", { type: "PERMISSION_GRANTED" })).toBe(
      "recording"
    );
  });

  it("ignores PERMISSION_GRANTED from any other status", () => {
    for (const status of ALL_STATUSES.filter((s) => s !== "requesting_permission")) {
      expect(recordingMachineReducer(status, { type: "PERMISSION_GRANTED" })).toBe(status);
    }
  });

  it("moves from requesting_permission to error on PERMISSION_DENIED", () => {
    expect(recordingMachineReducer("requesting_permission", { type: "PERMISSION_DENIED" })).toBe(
      "error"
    );
  });

  it("moves from recording to paused on PAUSE, ignores it elsewhere", () => {
    expect(recordingMachineReducer("recording", { type: "PAUSE" })).toBe("paused");
    for (const status of ALL_STATUSES.filter((s) => s !== "recording")) {
      expect(recordingMachineReducer(status, { type: "PAUSE" })).toBe(status);
    }
  });

  it("moves from paused to recording on RESUME, ignores it elsewhere", () => {
    expect(recordingMachineReducer("paused", { type: "RESUME" })).toBe("recording");
    for (const status of ALL_STATUSES.filter((s) => s !== "paused")) {
      expect(recordingMachineReducer(status, { type: "RESUME" })).toBe(status);
    }
  });

  it("moves from recording or paused to stopped on STOP, ignores it elsewhere", () => {
    expect(recordingMachineReducer("recording", { type: "STOP" })).toBe("stopped");
    expect(recordingMachineReducer("paused", { type: "STOP" })).toBe("stopped");
    for (const status of ALL_STATUSES.filter((s) => s !== "recording" && s !== "paused")) {
      expect(recordingMachineReducer(status, { type: "STOP" })).toBe(status);
    }
  });

  it("moves to idle from any status on RESET", () => {
    for (const status of ALL_STATUSES) {
      expect(recordingMachineReducer(status, { type: "RESET" })).toBe("idle");
    }
  });

  it("moves to error from any status on ERROR", () => {
    for (const status of ALL_STATUSES) {
      expect(recordingMachineReducer(status, { type: "ERROR" })).toBe("error");
    }
  });
});
