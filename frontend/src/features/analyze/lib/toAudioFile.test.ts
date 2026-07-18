import { describe, expect, it } from "vitest";

import type { RecordingArtifact } from "@/features/audio-recording/types";

import { recordingArtifactToFile } from "./toAudioFile";

function artifact(overrides: Partial<RecordingArtifact> = {}): RecordingArtifact {
  return {
    blob: new Blob(["fake audio bytes"], { type: "audio/webm" }),
    mimeType: "audio/webm",
    durationMs: 5000,
    createdAt: Date.parse("2026-01-01T00:00:00.000Z"),
    source: "browser",
    ...overrides,
  };
}

describe("recordingArtifactToFile", () => {
  it("produces a File carrying the artifact's bytes and mime type", () => {
    const file = recordingArtifactToFile(artifact());
    expect(file).toBeInstanceOf(File);
    expect(file.type).toBe("audio/webm");
    expect(file.size).toBeGreaterThan(0);
  });

  it("picks the extension matching the mime type", () => {
    expect(recordingArtifactToFile(artifact({ mimeType: "audio/webm" })).name).toMatch(/\.webm$/);
    expect(recordingArtifactToFile(artifact({ mimeType: "audio/mp4" })).name).toMatch(/\.m4a$/);
    expect(recordingArtifactToFile(artifact({ mimeType: "audio/ogg" })).name).toMatch(/\.ogg$/);
  });

  it("strips MediaRecorder codec parameters before looking up the extension", () => {
    expect(recordingArtifactToFile(artifact({ mimeType: 'audio/webm;codecs="opus"' })).name).toMatch(/\.webm$/);
  });

  it("strips MediaRecorder codec parameters from the File's type, not just the extension", () => {
    // Regression test: recordingArtifactToFile used to pass the raw,
    // codec-suffixed mimeType straight through as the File's `type`,
    // which becomes the multipart Content-Type header on upload. The
    // backend's content-type check (app/audio/validation.py) does an
    // exact match against plain types like "audio/webm" with no codec
    // parameter, so a live recording's real mimeType (which always
    // carries one, e.g. 'audio/webm;codecs="opus"') was always rejected
    // as unsupported_format — even though the extension was correct.
    const file = recordingArtifactToFile(artifact({ mimeType: 'audio/webm;codecs="opus"' }));
    expect(file.type).toBe("audio/webm");
  });

  it("falls back to .webm for an unrecognized mime type", () => {
    expect(recordingArtifactToFile(artifact({ mimeType: "audio/x-mystery" })).name).toMatch(/\.webm$/);
  });
});
