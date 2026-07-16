import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { PendingCaptureProvider, usePendingCapture } from "../context/PendingCaptureContext";
import { CaptureChooser } from "./CaptureChooser";

const pushMock = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock }),
}));

// A tiny probe component so tests can assert on PendingCaptureContext's
// state from outside CaptureChooser, without reaching into internals.
function PendingFileProbe() {
  const { hasPendingFile } = usePendingCapture();
  return <span data-testid="has-pending-file">{String(hasPendingFile)}</span>;
}

function renderChooser() {
  return render(
    <PendingCaptureProvider>
      <CaptureChooser />
      <PendingFileProbe />
    </PendingCaptureProvider>
  );
}

describe("CaptureChooser", () => {
  beforeEach(() => {
    pushMock.mockClear();
  });

  it("navigates to /analyze?start=record when 'Record now' is clicked, without stashing a file", async () => {
    const user = userEvent.setup();
    renderChooser();

    await user.click(screen.getByRole("button", { name: /record now/i }));

    expect(pushMock).toHaveBeenCalledWith("/analyze?start=record");
    expect(screen.getByTestId("has-pending-file")).toHaveTextContent("false");
  });

  it("stashes a valid uploaded file and navigates to /analyze", async () => {
    const user = userEvent.setup();
    renderChooser();

    const file = new File(["audio bytes"], "speech.wav", { type: "audio/wav" });
    const input = screen.getByLabelText(/upload an audio file/i);

    await user.upload(input, file);

    expect(pushMock).toHaveBeenCalledWith("/analyze");
    expect(screen.getByTestId("has-pending-file")).toHaveTextContent("true");
  });

  it("shows a validation error and does not navigate when the file type is unsupported", () => {
    // Dropped via the drag-and-drop zone rather than the file input:
    // the input's `accept` attribute would make @testing-library/user-event
    // (correctly mirroring real browser file-picker behavior) filter this
    // file out before it ever reaches CaptureChooser. Drag-and-drop has no
    // such filtering, which is exactly why acceptFile()'s own validation
    // matters — it's the only thing guarding this path.
    renderChooser();

    const file = new File(["not audio"], "notes.txt", { type: "text/plain" });
    const dropZone = screen.getByTestId("drop-zone");

    fireEvent.drop(dropZone, { dataTransfer: { files: [file] } });

    expect(screen.getByRole("alert")).toHaveTextContent(/only \.wav, \.mp3, \.m4a, and \.webm/i);
    expect(pushMock).not.toHaveBeenCalledWith("/analyze");
    expect(screen.getByTestId("has-pending-file")).toHaveTextContent("false");
  });
});
