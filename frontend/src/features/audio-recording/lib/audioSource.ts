/**
 * What a "thing that produces recorded audio" looks like, independent of
 * the device or browser API doing the capturing.
 *
 * Per ADR 001, this is the seam that keeps the session/UI layers from
 * ever depending on MediaRecorder directly. A future ESP32Source or
 * Quest3Source would implement this same shape without anything above
 * this file needing to change. Note that duration/timing is deliberately
 * NOT part of what a source returns — that's session-level bookkeeping
 * (it has to account for paused time, which a capture source doesn't
 * know about), owned by useAudioRecorder instead.
 */
export interface AudioSource {
  start(): Promise<void>;
  pause(): void;
  resume(): void;
  stop(): Promise<{ blob: Blob; mimeType: string }>;
  /** Releases any underlying hardware (stops MediaStream tracks). */
  dispose(): void;
}

/**
 * MediaRecorder mimeTypes in priority order. Browsers differ in what
 * they can record — notably Safari has no native WebM support — so this
 * picks the first type the current browser actually supports, falling
 * back to the browser's own default (undefined) if none of the
 * preferred types are available.
 */
const MIME_TYPE_CANDIDATES = [
  "audio/webm;codecs=opus",
  "audio/webm",
  "audio/mp4",
  "audio/ogg;codecs=opus",
];

export function pickSupportedMimeType(): string | undefined {
  if (typeof MediaRecorder === "undefined") return undefined;
  return MIME_TYPE_CANDIDATES.find((type) => MediaRecorder.isTypeSupported(type));
}

/**
 * The only AudioSource implementation this sprint: wraps the browser's
 * native MediaRecorder over a MediaStream obtained from getUserMedia.
 *
 * `onError` is called if the recorder itself reports an error, or if a
 * hardware track ends unexpectedly (mic unplugged, permission revoked
 * mid-session) — see ADR 001 section 7. The caller (useAudioRecorder)
 * uses this to move the session into an error state instead of leaving
 * it silently stuck in "recording".
 *
 * `onError` is handed the raw underlying error rather than a
 * pre-formatted message, so lib/microphoneError.ts remains the single
 * place that decides what the user actually sees — this class shouldn't
 * also be in the business of writing user-facing copy. The recorder's
 * own "error" event carries a real DOMException, classified directly by
 * name. A track "ended" event carries no DOMException at all (the
 * browser gives no reason), so it's reported as a plain Error with a
 * synthetic `name: "MediaStreamTrackEndedError"` that
 * classifyMicrophoneError recognizes as its own case.
 */
export class BrowserMediaRecorderSource implements AudioSource {
  private stream: MediaStream;
  private recorder: MediaRecorder;
  private chunks: BlobPart[] = [];

  constructor(stream: MediaStream, onError?: (error: unknown) => void) {
    this.stream = stream;

    const mimeType = pickSupportedMimeType();
    this.recorder = mimeType
      ? new MediaRecorder(stream, { mimeType })
      : new MediaRecorder(stream);

    this.recorder.addEventListener("dataavailable", (event) => {
      if (event.data.size > 0) this.chunks.push(event.data);
    });

    this.recorder.addEventListener("error", (event) => {
      const domError = (event as Event & { error?: DOMException }).error;
      onError?.(domError ?? new Error("Recording device error."));
    });

    stream.getTracks().forEach((track) => {
      track.addEventListener("ended", () => {
        const error = new Error("The microphone was disconnected.");
        error.name = "MediaStreamTrackEndedError";
        onError?.(error);
      });
    });
  }

  async start(): Promise<void> {
    this.chunks = [];
    this.recorder.start();
  }

  pause(): void {
    if (this.recorder.state === "recording") this.recorder.pause();
  }

  resume(): void {
    if (this.recorder.state === "paused") this.recorder.resume();
  }

  stop(): Promise<{ blob: Blob; mimeType: string }> {
    return new Promise((resolve, reject) => {
      if (this.recorder.state === "inactive") {
        reject(new Error("Recorder is not active."));
        return;
      }

      this.recorder.addEventListener(
        "stop",
        () => {
          const mimeType = this.recorder.mimeType || "audio/webm";
          const blob = new Blob(this.chunks, { type: mimeType });
          resolve({ blob, mimeType });
        },
        { once: true }
      );

      this.recorder.stop();
    });
  }

  dispose(): void {
    this.stream.getTracks().forEach((track) => track.stop());
  }
}
