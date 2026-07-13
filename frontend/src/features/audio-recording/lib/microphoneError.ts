/**
 * Classifies everything that can go wrong getting microphone access into
 * a small set of causes, each with friendly, professional, user-facing
 * copy — instead of surfacing whatever raw string the browser happens to
 * throw. Browsers report failures as DOMExceptions with a `name` that
 * identifies the cause (see MDN's getUserMedia exceptions); matching on
 * `name` rather than `message` is what makes this reliable across
 * browsers and locales, since the raw message text varies by browser and
 * is sometimes in the browser's own UI language rather than the app's.
 */
export type MicrophoneErrorKind =
  | "unsupported"
  | "insecure_context"
  | "permission_denied"
  | "not_found"
  | "not_readable"
  | "unknown";

export interface MicrophoneError {
  kind: MicrophoneErrorKind;
  /** Friendly, professional copy — safe to render directly to the user. */
  message: string;
  /** The original error, kept for console logging only, never shown to the user. */
  cause?: unknown;
}

/**
 * Checks whether this browser exposes what recording depends on, without
 * requesting any permission or touching hardware. Returns null if
 * everything looks supported.
 *
 * Only ever call this from the client (e.g. inside a useEffect) — it
 * reads `window`/`navigator`, which don't exist during Next.js's
 * server-rendered pass. The `typeof window` guard below is a defensive
 * fallback for that case, not the primary safeguard.
 */
export function checkBrowserSupport(): MicrophoneError | null {
  if (typeof window === "undefined") return null;

  if (!window.isSecureContext) {
    return {
      kind: "insecure_context",
      message:
        "Recording requires a secure connection. This page was loaded over an insecure connection, so the microphone can't be accessed — try reloading it over HTTPS.",
    };
  }

  const hasGetUserMedia =
    typeof navigator !== "undefined" &&
    !!navigator.mediaDevices &&
    typeof navigator.mediaDevices.getUserMedia === "function";

  if (!hasGetUserMedia || typeof MediaRecorder === "undefined") {
    return {
      kind: "unsupported",
      message:
        "This browser doesn't support audio recording. Try a recent version of Chrome, Firefox, Edge, or Safari.",
    };
  }

  return null;
}

/**
 * Maps a failed getUserMedia (or MediaRecorder) call to a friendly,
 * professional message. Falls back to a generic message for anything
 * that isn't a recognized error, rather than ever showing raw technical
 * error text to the user.
 *
 * `name` is read from any Error-shaped value, not just DOMException:
 * BrowserMediaRecorderSource also reports a mid-recording microphone
 * disconnect (a MediaStreamTrack "ended" event, which carries no
 * DOMException of its own) as a plain Error with a synthetic
 * `name: "MediaStreamTrackEndedError"`, specifically so that failure
 * mode gets classified here too instead of needing its own hardcoded
 * message elsewhere. Every user-facing string for "something went wrong
 * with the microphone" lives in this one file.
 */
export function classifyMicrophoneError(error: unknown): MicrophoneError {
  const name =
    error instanceof DOMException
      ? error.name
      : error instanceof Error
        ? error.name
        : undefined;

  switch (name) {
    case "NotAllowedError":
    case "PermissionDeniedError":
      return {
        kind: "permission_denied",
        message:
          "Microphone access was denied. Practice needs microphone permission to record — check your browser's site settings to allow microphone access, then try again.",
        cause: error,
      };

    case "NotFoundError":
    case "DevicesNotFoundError":
    case "OverconstrainedError":
      return {
        kind: "not_found",
        message: "No microphone was found. Connect a microphone and try again.",
        cause: error,
      };

    case "NotReadableError":
    case "TrackStartError":
      return {
        kind: "not_readable",
        message:
          "Your microphone couldn't be started. It may be in use by another application — close anything else using the microphone and try again.",
        cause: error,
      };

    case "MediaStreamTrackEndedError":
      return {
        kind: "not_readable",
        message:
          "The microphone was disconnected. Reconnect it and start recording again.",
        cause: error,
      };

    case "SecurityError":
      return {
        kind: "insecure_context",
        message:
          "Recording requires a secure connection. Reload this page over HTTPS and try again.",
        cause: error,
      };

    case "AbortError":
      return {
        kind: "unknown",
        message: "Starting the recording was interrupted. Please try again.",
        cause: error,
      };

    default:
      return {
        kind: "unknown",
        message: "Something went wrong accessing the microphone. Please try again.",
        cause: error,
      };
  }
}
