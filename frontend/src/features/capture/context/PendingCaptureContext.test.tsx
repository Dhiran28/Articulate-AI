import { act, renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { PendingCaptureProvider, usePendingCapture } from "./PendingCaptureContext";

describe("PendingCaptureContext", () => {
  it("starts with no pending file", () => {
    const { result } = renderHook(() => usePendingCapture(), { wrapper: PendingCaptureProvider });
    expect(result.current.hasPendingFile).toBe(false);
  });

  it("setPendingFile flips hasPendingFile to true", () => {
    const { result } = renderHook(() => usePendingCapture(), { wrapper: PendingCaptureProvider });
    const file = new File(["bytes"], "speech.wav", { type: "audio/wav" });

    act(() => result.current.setPendingFile(file));

    expect(result.current.hasPendingFile).toBe(true);
  });

  it("consumePendingFile returns the file and clears it", () => {
    const { result } = renderHook(() => usePendingCapture(), { wrapper: PendingCaptureProvider });
    const file = new File(["bytes"], "speech.wav", { type: "audio/wav" });

    act(() => result.current.setPendingFile(file));
    let consumed: File | null = null;
    act(() => {
      consumed = result.current.consumePendingFile();
    });

    expect(consumed).toBe(file);
    expect(result.current.hasPendingFile).toBe(false);
  });

  it("consumePendingFile returns null when nothing is pending", () => {
    const { result } = renderHook(() => usePendingCapture(), { wrapper: PendingCaptureProvider });

    let consumed: File | null = new File([], "placeholder");
    act(() => {
      consumed = result.current.consumePendingFile();
    });

    expect(consumed).toBeNull();
  });

  it("throws a clear error when used outside its provider", () => {
    expect(() => renderHook(() => usePendingCapture())).toThrow(/usePendingCapture must be used within/);
  });
});
