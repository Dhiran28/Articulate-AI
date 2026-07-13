import { describe, expect, it } from "vitest";

import { classifyMicrophoneError } from "./microphoneError";

function domException(name: string): DOMException {
  return new DOMException("test message", name);
}

describe("classifyMicrophoneError", () => {
  it("classifies permission-denial DOMExceptions", () => {
    expect(classifyMicrophoneError(domException("NotAllowedError")).kind).toBe(
      "permission_denied"
    );
    expect(classifyMicrophoneError(domException("PermissionDeniedError")).kind).toBe(
      "permission_denied"
    );
  });

  it("classifies no-device-found DOMExceptions", () => {
    expect(classifyMicrophoneError(domException("NotFoundError")).kind).toBe("not_found");
    expect(classifyMicrophoneError(domException("DevicesNotFoundError")).kind).toBe("not_found");
    expect(classifyMicrophoneError(domException("OverconstrainedError")).kind).toBe("not_found");
  });

  it("classifies device-busy/unreadable DOMExceptions", () => {
    expect(classifyMicrophoneError(domException("NotReadableError")).kind).toBe("not_readable");
    expect(classifyMicrophoneError(domException("TrackStartError")).kind).toBe("not_readable");
  });

  it("classifies SecurityError as an insecure context problem", () => {
    expect(classifyMicrophoneError(domException("SecurityError")).kind).toBe("insecure_context");
  });

  it("classifies AbortError as unknown but still gives a message", () => {
    const result = classifyMicrophoneError(domException("AbortError"));
    expect(result.kind).toBe("unknown");
    expect(result.message.length).toBeGreaterThan(0);
  });

  it("classifies a synthetic MediaStreamTrackEndedError (mic disconnected) as not_readable", () => {
    const error = new Error("The microphone was disconnected.");
    error.name = "MediaStreamTrackEndedError";
    const result = classifyMicrophoneError(error);
    expect(result.kind).toBe("not_readable");
    expect(result.message).toMatch(/disconnected/i);
  });

  it("falls back to unknown for an unrecognized DOMException name", () => {
    expect(classifyMicrophoneError(domException("SomeNewFutureError")).kind).toBe("unknown");
  });

  it("falls back to unknown for non-error values", () => {
    expect(classifyMicrophoneError("just a string").kind).toBe("unknown");
    expect(classifyMicrophoneError(undefined).kind).toBe("unknown");
    expect(classifyMicrophoneError({ some: "object" }).kind).toBe("unknown");
  });

  it("never puts the raw error message directly into the user-facing message", () => {
    const error = domException("NotAllowedError");
    const result = classifyMicrophoneError(error);
    expect(result.message).not.toContain("test message");
  });

  it("keeps the original error available as `cause` for logging", () => {
    const error = domException("NotFoundError");
    const result = classifyMicrophoneError(error);
    expect(result.cause).toBe(error);
  });
});
