import { useEffect, useRef } from "react";

import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { PendingCaptureProvider, usePendingCapture } from "@/features/capture/context/PendingCaptureContext";
import { AnalysisResultProvider, useAnalysisResult } from "@/features/results/context/AnalysisResultContext";
import type { CommunicationReport } from "@/features/results/types";

import { AnalyzeError } from "../lib/analyzeClient";
import { AnalyzeScreen } from "./AnalyzeScreen";

/**
 * Integration test for the milestone's core end-to-end flow: choosing a
 * file, submitting it, and either landing on the results context (success)
 * or seeing a retryable error (failure) — exercising AnalyzeScreen together
 * with the real PendingCaptureContext, AnalysisResultContext, and
 * useAnalyzeMutation/React Query, rather than each in isolation.
 *
 * Only analyzeAudio (the network boundary) and next/navigation are mocked.
 * Live recording is intentionally not exercised here — jsdom has no real
 * MediaRecorder/getUserMedia, and that path is already covered by
 * useAudioRecorder's own unit tests.
 */

const pushMock = vi.fn();
const replaceMock = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock, replace: replaceMock }),
  useSearchParams: () => new URLSearchParams(""),
}));

const analyzeAudioMock = vi.fn();

vi.mock("../lib/analyzeClient", async () => {
  const actual = await vi.importActual<typeof import("../lib/analyzeClient")>("../lib/analyzeClient");
  return {
    ...actual,
    analyzeAudio: (...args: unknown[]) => analyzeAudioMock(...args),
  };
});

function fakeReport(): CommunicationReport {
  return {
    transcript_id: "t-1",
    generated_at: "2026-01-01T00:00:00Z",
    executive_summary: "Solid session overall.",
    transcript: "we should ship it",
    score: { overall_score: 82, band: "strong", module_scores: [], unscored_modules: [] },
    analysis: { transcript_id: "t-1", generated_at: "2026-01-01T00:00:00Z", modules: {} },
    coaching: {
      transcript_id: "t-1",
      generated_at: "2026-01-01T00:00:00Z",
      strengths: [],
      weaknesses: [],
      recommendations: [],
      suggested_exercises: [],
      next_practice_focus: "Practice pacing.",
      executive_summary: "Solid session overall.",
      unavailable: [],
    },
    prompt_versions: { reasoning_pass: "1.0.0", coaching: "1.0.0" },
  };
}

// Stashes a file as "pending" (as CaptureChooser would after an upload)
// before AnalyzeScreen ever mounts, then renders AnalyzeScreen under the
// same provider tree so its consuming effect picks the file up on mount.
function ResultProbe() {
  const { report, sessionLabel } = useAnalysisResult();
  return (
    <div data-testid="result-probe">
      {report ? `report:${report.transcript_id}:label:${sessionLabel ?? "none"}` : "no-report"}
    </div>
  );
}

function Harness({ file }: { file: File }) {
  const { setPendingFile } = usePendingCapture();
  const stashedRef = useRef(false);

  // Stashed in an effect (not during render — React forbids updating a
  // different component's state while this one is rendering). This runs
  // before AnalyzeScreen's own consuming effect settles, since React
  // flushes child effects before parent effects and both are plain
  // mount-time effects here — AnalyzeScreen's effect is reactive on
  // `hasPendingFile`, so it still picks up the file once this fires.
  useEffect(() => {
    if (!stashedRef.current) {
      stashedRef.current = true;
      setPendingFile(file);
    }
  }, [file, setPendingFile]);

  return (
    <>
      <AnalyzeScreen />
      <ResultProbe />
    </>
  );
}

function renderFlow(file: File) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <PendingCaptureProvider>
        <AnalysisResultProvider>
          <Harness file={file} />
        </AnalysisResultProvider>
      </PendingCaptureProvider>
    </QueryClientProvider>
  );
}

beforeEach(() => {
  pushMock.mockClear();
  replaceMock.mockClear();
  analyzeAudioMock.mockReset();
  window.sessionStorage.clear();
  // jsdom doesn't implement object URLs; FilePreviewPanel creates one to
  // preview the picked file before submission. Assigned directly on the
  // real URL constructor (rather than via vi.stubGlobal with a spread
  // copy) so every other static member of URL keeps working normally.
  URL.createObjectURL = vi.fn(() => "blob:mock");
  URL.revokeObjectURL = vi.fn();
});

describe("Analyze flow: capture -> submit -> results", () => {
  it("uploads a file, shows progress, and lands the report in AnalysisResultContext on success", async () => {
    const user = userEvent.setup();
    let resolveAnalyze!: (report: CommunicationReport) => void;
    analyzeAudioMock.mockImplementation(
      () =>
        new Promise<CommunicationReport>((resolve) => {
          resolveAnalyze = resolve;
        })
    );

    const file = new File(["audio bytes"], "speech.wav", { type: "audio/wav" });
    renderFlow(file);

    // The file preview should appear immediately (picked up from
    // PendingCaptureContext), with no submission in flight yet.
    expect(await screen.findByText("speech.wav")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /analyze this file/i }));

    // Submission is now in flight — analyzeAudio was called with the file.
    expect(analyzeAudioMock).toHaveBeenCalledWith(file, expect.anything());
    expect(await screen.findByText(/uploading|analyzing/i)).toBeInTheDocument();

    act(() => resolveAnalyze(fakeReport()));

    await waitFor(() => expect(replaceMock).toHaveBeenCalledWith("/results"));
    expect(await screen.findByTestId("result-probe")).toHaveTextContent("report:t-1:label:none");
    expect(window.sessionStorage.getItem("articulate-ai:last-analysis-report")).toContain("t-1");
  });

  it("shows a retryable error when analysis fails, and succeeds on retry", async () => {
    const user = userEvent.setup();
    analyzeAudioMock
      .mockRejectedValueOnce(new AnalyzeError("server_error", "The analysis service is unavailable."))
      .mockResolvedValueOnce(fakeReport());

    const file = new File(["audio bytes"], "speech.wav", { type: "audio/wav" });
    renderFlow(file);

    await screen.findByText("speech.wav");
    await user.click(screen.getByRole("button", { name: /analyze this file/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent("The analysis service is unavailable.");

    await user.click(screen.getByRole("button", { name: /try again/i }));

    await waitFor(() => expect(replaceMock).toHaveBeenCalledWith("/results"));
    expect(analyzeAudioMock).toHaveBeenCalledTimes(2);
  });
});
