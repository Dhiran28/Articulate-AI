import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { analyzeAudio, AnalyzeError } from "./analyzeClient";

/**
 * A minimal fake XMLHttpRequest — analyzeClient.ts is deliberately built
 * on XHR (not fetch) specifically to get real upload progress, so
 * testing it means faking the same API surface it actually uses:
 * open/send, upload.onprogress, onload/onerror/ontimeout, status, and
 * responseText. Nothing here makes a real network call.
 */
class FakeXMLHttpRequest {
  static instances: FakeXMLHttpRequest[] = [];

  status = 0;
  responseText = "";
  timeout = 0;
  upload: { onprogress: ((event: { lengthComputable: boolean; loaded: number; total: number }) => void) | null } = {
    onprogress: null,
  };
  onload: (() => void) | null = null;
  onerror: (() => void) | null = null;
  ontimeout: (() => void) | null = null;
  onabort: (() => void) | null = null;
  openedUrl: string | null = null;
  sentBody: FormData | null = null;

  constructor() {
    FakeXMLHttpRequest.instances.push(this);
  }

  open(_method: string, url: string) {
    this.openedUrl = url;
  }

  send(body: FormData) {
    this.sentBody = body;
  }

  // Test helpers — not part of the real XHR API.
  simulateProgress(loaded: number, total: number) {
    this.upload.onprogress?.({ lengthComputable: true, loaded, total });
  }

  simulateResponse(status: number, body: unknown) {
    this.status = status;
    this.responseText = typeof body === "string" ? body : JSON.stringify(body);
    this.onload?.();
  }

  simulateNetworkError() {
    this.onerror?.();
  }
}

beforeEach(() => {
  FakeXMLHttpRequest.instances = [];
  vi.stubGlobal("XMLHttpRequest", FakeXMLHttpRequest);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

function currentXhr(): FakeXMLHttpRequest {
  const xhr = FakeXMLHttpRequest.instances.at(-1);
  if (!xhr) throw new Error("No FakeXMLHttpRequest was constructed");
  return xhr;
}

describe("analyzeAudio", () => {
  it("resolves with the parsed CommunicationReport on a 2xx response", async () => {
    const file = new File(["audio bytes"], "speech.wav", { type: "audio/wav" });
    const promise = analyzeAudio(file);

    currentXhr().simulateResponse(201, { transcript_id: "abc-123", executive_summary: "Good session." });

    await expect(promise).resolves.toMatchObject({ transcript_id: "abc-123" });
  });

  it("posts to /api/analyze with the file in a multipart form", async () => {
    const file = new File(["audio bytes"], "speech.wav", { type: "audio/wav" });
    const promise = analyzeAudio(file);

    const xhr = currentXhr();
    expect(xhr.openedUrl).toMatch(/\/api\/analyze$/);
    expect(xhr.sentBody?.get("file")).toBe(file);

    xhr.simulateResponse(201, {});
    await promise;
  });

  it("reports real upload progress via onUploadProgress", async () => {
    const file = new File(["audio bytes"], "speech.wav", { type: "audio/wav" });
    const onUploadProgress = vi.fn();
    const promise = analyzeAudio(file, { onUploadProgress });

    const xhr = currentXhr();
    xhr.simulateProgress(50, 100);
    expect(onUploadProgress).toHaveBeenCalledWith(50);

    xhr.simulateResponse(201, {});
    await promise;
  });

  it("rejects with the backend's classified reason and message on an error response", async () => {
    const file = new File(["audio bytes"], "speech.wav", { type: "audio/wav" });
    const promise = analyzeAudio(file);

    currentXhr().simulateResponse(422, {
      detail: { error: "transcript_empty", message: "There isn't enough transcript content to analyze." },
    });

    await expect(promise).rejects.toMatchObject({
      reason: "transcript_empty",
      message: "There isn't enough transcript content to analyze.",
    });
    await expect(promise).rejects.toBeInstanceOf(AnalyzeError);
  });

  it("falls back to a generic reason/message when the error body isn't valid JSON", async () => {
    const file = new File(["audio bytes"], "speech.wav", { type: "audio/wav" });
    const promise = analyzeAudio(file);

    currentXhr().simulateResponse(500, "not json at all");

    await expect(promise).rejects.toMatchObject({ reason: "unknown_error" });
  });

  it("rejects with a network_error reason when the request never reaches the server", async () => {
    const file = new File(["audio bytes"], "speech.wav", { type: "audio/wav" });
    const promise = analyzeAudio(file);

    currentXhr().simulateNetworkError();

    await expect(promise).rejects.toMatchObject({ reason: "network_error" });
  });
});
