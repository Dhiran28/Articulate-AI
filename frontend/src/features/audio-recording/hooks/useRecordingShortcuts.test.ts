import { renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { useRecordingShortcuts } from "./useRecordingShortcuts";

function pressKey(key: string, target: EventTarget = document, extra: Partial<KeyboardEventInit> = {}) {
  const event = new KeyboardEvent("keydown", { key, bubbles: true, cancelable: true, ...extra });
  target.dispatchEvent(event);
}

describe("useRecordingShortcuts", () => {
  it("calls onRecord when 'r' is pressed while idle", () => {
    const onRecord = vi.fn();
    renderHook(() =>
      useRecordingShortcuts({ status: "idle", onRecord, onPause: vi.fn(), onResume: vi.fn(), onStop: vi.fn() })
    );

    pressKey("r");

    expect(onRecord).toHaveBeenCalledTimes(1);
  });

  it("does not call onRecord for 'r' while already recording", () => {
    const onRecord = vi.fn();
    renderHook(() =>
      useRecordingShortcuts({ status: "recording", onRecord, onPause: vi.fn(), onResume: vi.fn(), onStop: vi.fn() })
    );

    pressKey("r");

    expect(onRecord).not.toHaveBeenCalled();
  });

  it("calls onPause for 'p' while recording", () => {
    const onPause = vi.fn();
    renderHook(() =>
      useRecordingShortcuts({ status: "recording", onRecord: vi.fn(), onPause, onResume: vi.fn(), onStop: vi.fn() })
    );

    pressKey("p");

    expect(onPause).toHaveBeenCalledTimes(1);
  });

  it("calls onResume for 'p' while paused", () => {
    const onResume = vi.fn();
    renderHook(() =>
      useRecordingShortcuts({ status: "paused", onRecord: vi.fn(), onPause: vi.fn(), onResume, onStop: vi.fn() })
    );

    pressKey("p");

    expect(onResume).toHaveBeenCalledTimes(1);
  });

  it("calls onStop for 's' while recording or paused", () => {
    const onStop = vi.fn();
    renderHook(() =>
      useRecordingShortcuts({ status: "recording", onRecord: vi.fn(), onPause: vi.fn(), onResume: vi.fn(), onStop })
    );

    pressKey("s");

    expect(onStop).toHaveBeenCalledTimes(1);
  });

  it("ignores shortcuts while a modifier key is held", () => {
    const onRecord = vi.fn();
    renderHook(() =>
      useRecordingShortcuts({ status: "idle", onRecord, onPause: vi.fn(), onResume: vi.fn(), onStop: vi.fn() })
    );

    pressKey("r", document, { metaKey: true });

    expect(onRecord).not.toHaveBeenCalled();
  });

  it("ignores shortcuts while focus is inside a text input", () => {
    const input = document.createElement("input");
    document.body.appendChild(input);
    input.focus();

    const onRecord = vi.fn();
    renderHook(() =>
      useRecordingShortcuts({ status: "idle", onRecord, onPause: vi.fn(), onResume: vi.fn(), onStop: vi.fn() })
    );

    pressKey("r", input);

    expect(onRecord).not.toHaveBeenCalled();
    document.body.removeChild(input);
  });

  it("removes its listener on unmount", () => {
    const onRecord = vi.fn();
    const { unmount } = renderHook(() =>
      useRecordingShortcuts({ status: "idle", onRecord, onPause: vi.fn(), onResume: vi.fn(), onStop: vi.fn() })
    );

    unmount();
    pressKey("r");

    expect(onRecord).not.toHaveBeenCalled();
  });
});
