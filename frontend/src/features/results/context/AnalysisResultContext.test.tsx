import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import type { CommunicationReport } from "../types";
import { AnalysisResultProvider, useAnalysisResult } from "./AnalysisResultContext";

const STORAGE_KEY = "articulate-ai:last-analysis-report";

function fakeReport(overrides: Partial<CommunicationReport> = {}): CommunicationReport {
  return {
    transcript_id: "t-1",
    generated_at: "2026-01-01T00:00:00Z",
    executive_summary: "Solid session.",
    transcript: "we should ship it",
    score: { overall_score: 80, band: "strong", module_scores: [], unscored_modules: [] },
    analysis: { transcript_id: "t-1", generated_at: "2026-01-01T00:00:00Z", modules: {} },
    coaching: {
      transcript_id: "t-1",
      generated_at: "2026-01-01T00:00:00Z",
      strengths: [],
      weaknesses: [],
      recommendations: [],
      suggested_exercises: [],
      next_practice_focus: "Practice pacing.",
      executive_summary: "Solid session.",
      unavailable: [],
    },
    prompt_versions: { reasoning_pass: "1.0.0", coaching: "1.0.0" },
    ...overrides,
  };
}

afterEach(() => {
  window.sessionStorage.clear();
});

describe("AnalysisResultContext", () => {
  it("starts with no report", async () => {
    const { result } = renderHook(() => useAnalysisResult(), { wrapper: AnalysisResultProvider });
    await waitFor(() => expect(result.current.report).toBeNull());
  });

  it("setReport stores the report and an optional session label", async () => {
    const { result } = renderHook(() => useAnalysisResult(), { wrapper: AnalysisResultProvider });

    act(() => result.current.setReport(fakeReport(), "Standup practice"));

    expect(result.current.report?.transcript_id).toBe("t-1");
    expect(result.current.sessionLabel).toBe("Standup practice");
  });

  it("defaults sessionLabel to null when not provided", () => {
    const { result } = renderHook(() => useAnalysisResult(), { wrapper: AnalysisResultProvider });

    act(() => result.current.setReport(fakeReport()));

    expect(result.current.sessionLabel).toBeNull();
  });

  it("persists the report to sessionStorage so a fresh mount can read it back", async () => {
    const { result, unmount } = renderHook(() => useAnalysisResult(), { wrapper: AnalysisResultProvider });
    act(() => result.current.setReport(fakeReport(), "My session"));
    unmount();

    expect(window.sessionStorage.getItem(STORAGE_KEY)).toContain("t-1");

    const { result: result2 } = renderHook(() => useAnalysisResult(), { wrapper: AnalysisResultProvider });
    await waitFor(() => expect(result2.current.report?.transcript_id).toBe("t-1"));
    expect(result2.current.sessionLabel).toBe("My session");
  });

  it("clearReport removes the stored report", async () => {
    const { result } = renderHook(() => useAnalysisResult(), { wrapper: AnalysisResultProvider });
    act(() => result.current.setReport(fakeReport()));

    act(() => result.current.clearReport());

    expect(result.current.report).toBeNull();
    expect(window.sessionStorage.getItem(STORAGE_KEY)).toBeNull();
  });

  it("treats corrupted sessionStorage content as no report, rather than throwing", async () => {
    window.sessionStorage.setItem(STORAGE_KEY, "{not valid json");

    const { result } = renderHook(() => useAnalysisResult(), { wrapper: AnalysisResultProvider });

    await waitFor(() => expect(result.current.report).toBeNull());
  });
});
