/**
 * A live source of audio amplitude data for visualization, independent
 * of where the audio physically comes from.
 *
 * This is a separate interface from AudioSource (lib/audioSource.ts),
 * not an extension of it — recording and visualizing are different
 * capabilities that happen to often read the same microphone. Keeping
 * them separate means a WaveformSource never needs to know how (or
 * whether) the audio is being recorded, and AudioSource never needs to
 * know how (or whether) it's being visualized.
 *
 * Today's only implementation (WebAudioWaveformSource, below) wraps a
 * browser MediaStream via the Web Audio API — used for the desktop
 * microphone now, and expected to work unmodified for a Quest 3
 * microphone too, since Quest's browser exposes getUserMedia and Web
 * Audio the same way desktop Chromium does (see ADR 001 section 8).
 *
 * An ESP32 microphone is a different story: its audio never becomes a
 * browser MediaStream at all — it arrives as raw PCM samples over
 * WebSocket or serial, relayed through the backend. A future
 * `Esp32WaveformSource` would compute levels directly from those PCM
 * chunks instead of an AnalyserNode. Because WaveformVisualizer and
 * useWaveform only depend on this interface — start / getLevels /
 * dispose — swapping in that implementation later means writing one new
 * class, not touching the UI or the browser-mic path at all.
 */
export interface WaveformSource {
  /** Begin producing data (e.g. resume a suspended AudioContext). */
  start(): void;
  /** A snapshot of current amplitude levels, one per bar, each in [0, 1]. */
  getLevels(barCount: number): number[];
  /** Stop producing data and release any resources it holds. */
  dispose(): void;
}

/**
 * WaveformSource backed by the Web Audio API's AnalyserNode, reading
 * directly from a live MediaStream.
 *
 * Deliberately not connected to `audioContext.destination` — this node
 * only reads the signal for visualization; connecting it to the
 * speakers would play the user's own voice back to them in real time
 * (audible feedback/echo), which nothing here should do.
 */
export class WebAudioWaveformSource implements WaveformSource {
  private audioContext: AudioContext;
  private analyser: AnalyserNode;
  private sourceNode: MediaStreamAudioSourceNode;
  private frequencyData: Uint8Array<ArrayBuffer>;

  constructor(stream: MediaStream) {
    this.audioContext = new AudioContext();

    this.analyser = this.audioContext.createAnalyser();
    this.analyser.fftSize = 256;
    this.analyser.smoothingTimeConstant = 0.75;

    this.sourceNode = this.audioContext.createMediaStreamSource(stream);
    this.sourceNode.connect(this.analyser);

    // Constructed from an explicit ArrayBuffer (rather than
    // `new Uint8Array(length)` directly) so TypeScript infers
    // Uint8Array<ArrayBuffer> — the specific type
    // AnalyserNode.getByteFrequencyData expects — rather than the more
    // general Uint8Array<ArrayBufferLike>.
    this.frequencyData = new Uint8Array(new ArrayBuffer(this.analyser.frequencyBinCount));
  }

  start(): void {
    if (this.audioContext.state === "suspended") {
      void this.audioContext.resume();
    }
  }

  getLevels(barCount: number): number[] {
    this.analyser.getByteFrequencyData(this.frequencyData);

    // Downsample the analyser's frequency bins to exactly `barCount`
    // bars by averaging each bucket, so the number of bars on screen is
    // independent of the FFT size used internally.
    const bucketSize = Math.max(1, Math.floor(this.frequencyData.length / barCount));
    const levels: number[] = [];

    for (let i = 0; i < barCount; i++) {
      let sum = 0;
      for (let j = 0; j < bucketSize; j++) {
        sum += this.frequencyData[i * bucketSize + j] ?? 0;
      }
      levels.push(sum / bucketSize / 255);
    }

    return levels;
  }

  dispose(): void {
    this.sourceNode.disconnect();
    this.analyser.disconnect();
    void this.audioContext.close();
  }
}
