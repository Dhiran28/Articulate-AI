# ADR 001: Audio Recording Module Architecture

**Status:** Proposed — awaiting approval before implementation (Sprint 2)
**Scope:** Browser-based recording (MediaRecorder API) with start/pause/resume/stop, playback, timer, and waveform. Designed to remain compatible with future Whisper transcription, ESP32 microphone input, Quest 3 microphone input, cloud storage, and AI analysis — none of which are implemented in this sprint.

---

## 1. High-level architecture

The module is split into five layers, each with a single responsibility. Lower layers know nothing about layers above them; higher layers depend downward only through the abstractions defined at the boundary.

| Layer | Responsibility | Built this sprint? |
|---|---|---|
| **UI Layer** (React components) | Render controls, timer, waveform, playback panel. No audio logic. | Yes |
| **Session State Layer** (Context + hook) | Own the recording state machine, expose start/pause/resume/stop/state to the UI. | Yes |
| **Audio Capture Abstraction** (`AudioSource` interface) | Define what "a thing that produces recorded audio" looks like, independent of the device capturing it. | Interface: yes. Only implementation: browser MediaRecorder. |
| **Browser / Native APIs** | `getUserMedia`, `MediaRecorder`, `AnalyserNode` (Web Audio) — the actual capture and analysis primitives. | Yes (used, not modified) |
| **Artifact & Sink** (`Recording` model + `RecordingSink` interface) | Package the finished recording into a standard shape and hand it off for storage/processing. | Interface: yes. Only implementation: an in-memory/local stub — no upload. |

The two interfaces — `AudioSource` and `RecordingSink` — are the seams that keep this sprint's scope (browser-only, no persistence) from having to be rewritten when later sprints add ESP32/Quest 3 capture, cloud storage, transcription, and analysis. Everything above those seams (UI, state machine) is written against the interface, never against `MediaRecorder` or a specific storage backend directly.

## 2. Component hierarchy

```
<AudioRecorderFeature>                      (route-level composition)
 └── <RecordingProvider>                    (Context: owns the state machine)
       ├── <RecordingStatusBadge />         (idle / recording / paused / stopped / error)
       ├── <RecordingControls>
       │     ├── <RecordButton />
       │     ├── <PauseResumeButton />
       │     └── <StopButton />
       ├── <RecordingTimer />               (derived from timestamps, not a naive counter)
       ├── <WaveformVisualizer />           (live, reads the MediaStream directly)
       └── <PlaybackPanel>                  (mounted only after a recording exists)
             ├── <PlaybackWaveform />       (static, decoded from the finished blob)
             ├── <PlaybackControls />       (play / pause / seek)
             └── <PlaybackTimeline />
```

Supporting hooks (not components, but part of the same tree conceptually):

- `useAudioRecorder()` — the state machine: start/pause/resume/stop, current state, elapsed time, error.
- `useMicrophonePermission()` — requests `getUserMedia`, tracks granted/denied/prompt state.
- `useAudioVisualizer(stream)` — wraps an `AnalyserNode` tap on the live stream for the recording-time waveform.
- `useAudioPlayback(blob)` — wraps a native `<audio>` element for playback, decodes the blob separately (via `AudioContext.decodeAudioData`) only when the static playback waveform needs to be drawn.

## 3. Folder structure

Sprint 1 structured the FastAPI backend by layer (`api/core/models`) because it had one feature. The frontend now gets its first real feature, so it's organized by feature instead — everything about recording lives together, which matters once a second feature (e.g. the dashboard) exists and shouldn't share folders with this one.

```
frontend/src/
├── app/
│   └── record/
│       └── page.tsx                  route that mounts <AudioRecorderFeature>
├── features/
│   └── audio-recording/
│       ├── components/
│       │   ├── RecordingControls.tsx
│       │   ├── RecordButton.tsx
│       │   ├── PauseResumeButton.tsx
│       │   ├── StopButton.tsx
│       │   ├── RecordingTimer.tsx
│       │   ├── WaveformVisualizer.tsx
│       │   ├── PlaybackPanel.tsx
│       │   ├── PlaybackControls.tsx
│       │   └── RecordingStatusBadge.tsx
│       ├── hooks/
│       │   ├── useAudioRecorder.ts
│       │   ├── useMicrophonePermission.ts
│       │   ├── useAudioVisualizer.ts
│       │   └── useAudioPlayback.ts
│       ├── lib/
│       │   ├── audioSource.ts        AudioSource interface + BrowserMediaRecorderSource
│       │   ├── recordingSink.ts      RecordingSink interface + local stub implementation
│       │   └── waveform.ts           waveform sampling / drawing utilities
│       ├── state/
│       │   └── recordingMachine.ts   states, transitions, reducer
│       ├── context/
│       │   └── RecordingProvider.tsx
│       └── types.ts                  Recording, RecordingStatus, AudioSourceType, etc.
└── components/ui/                    existing shared shadcn/ui primitives
```

## 4. State management

**Decision: a finite state machine (React Context + `useReducer`), scoped to the feature — not a global store (Redux/Zustand), not ad hoc booleans.**

Why not booleans (`isRecording`, `isPaused`, `isStopped`): independent booleans can represent impossible combinations (e.g. `isRecording=true` and `isPaused=true` at once), and MediaRecorder itself has strict valid-transition rules (you cannot pause an already-paused recorder, cannot resume an idle one). A state machine makes invalid states unrepresentable and invalid transitions a no-op or explicit error, rather than a bug that only shows up when a user clicks buttons in an unexpected order.

States: `idle → requesting_permission → recording ⇄ paused → stopped`, with an `error` state reachable from any of them (permission denied, device disconnected, unsupported browser).

Why not a global store: recording session state belongs to one screen. Nothing else in the app needs to read or write it yet. Introducing Redux/Zustand now would add a dependency and indirection with no current beneficiary — a violation of the "prioritize maintainability over speed" principle in the sense that unused flexibility is itself a maintenance cost. If a later feature needs to know "is a recording in progress" from elsewhere in the app (e.g. a nav-bar indicator), the fix is to lift the existing `RecordingProvider` higher in the tree — not to introduce a new state management library.

Two things are deliberately kept **outside** the state machine:

- **Waveform samples** — updated up to 60 times/second from the `AnalyserNode`. Routing this through the reducer would re-render every consumer of the recording state on every frame. It stays local to `useAudioVisualizer`, typically in a ref, and only the canvas/SVG it drives re-paints.
- **Elapsed time** — not stored as an incrementing number updated by `setInterval` (which drifts and complicates pause/resume math). Instead the machine stores `startedAt` and `accumulatedPausedMs`; the timer component computes `elapsed = now - startedAt - accumulatedPausedMs` on each tick. This is simpler to reason about and immune to timer drift.

## 5. Data flow

1. User clicks **Record** → `useMicrophonePermission` requests `getUserMedia` (browser prompts on first use) → a `MediaStream` is obtained.
2. The same `MediaStream` is handed to two consumers in parallel: the `AudioSource` (which wraps a native `MediaRecorder` and will capture the audio) and `useAudioVisualizer` (which taps it via `AnalyserNode` for the live waveform). Visualization never depends on decoding recorded output — it reads the live stream directly, so it works identically regardless of what the recorder is doing internally.
3. State machine transitions to `recording`; timer begins tracking `startedAt`.
4. `MediaRecorder` emits `dataavailable` at intervals; chunks accumulate inside the `AudioSource` implementation (not in React state — no re-render per chunk).
5. **Pause** → `MediaRecorder.pause()` → state → `paused`; timer freezes; waveform sampling halts.
6. **Resume** → `MediaRecorder.resume()` → state → `recording`; timer resumes (adds the paused interval to `accumulatedPausedMs`); waveform sampling resumes.
7. **Stop** → `MediaRecorder.stop()` → final `dataavailable` fires → chunks are combined into one `Blob` → the `AudioSource` resolves a `Recording` artifact (`{ blob, durationMs, mimeType, createdAt, source: "browser" }`) → state → `stopped` → all `MediaStream` tracks are stopped (releases the OS mic indicator).
8. The artifact is handed to a `RecordingSink`. This sprint's only implementation, `LocalObjectUrlSink`, creates an in-memory object URL purely for playback — nothing is uploaded or persisted. Swapping in an upload-to-backend sink later is additive, not a rewrite.
9. **Playback**: `useAudioPlayback` wraps a native `<audio>` element pointed at the object URL (chosen over driving raw Web Audio buffers manually, since native playback handles scrubbing, buffering, and browser-level controls for free). The static playback waveform is produced separately by decoding the blob via `AudioContext.decodeAudioData`, once, when the panel mounts.

**Future extension (not built now):** `RecordingSink` gains an implementation that `POST`s the blob to the FastAPI backend, which stores it in cloud storage and queues a Whisper transcription job; the transcript then feeds the (also future) AI analysis pipeline. ESP32 and Quest 3 capture will very likely produce audio artifacts through an entirely separate path (e.g. ESP32 streaming directly to the backend over Wi-Fi, bypassing the browser module altogether) that converges on the same backend storage/transcription pipeline — which is exactly why this module's responsibility stops at "produce a standard artifact," not "know how every future device gets its audio to the server."

## 6. Sequence diagram

Rendered above as an interactive diagram (`audio_recording_sequence`). In text form, the full lifecycle:

1. User clicks Record → UI calls `start()` on the hook.
2. Hook requests `getUserMedia()` → receives a `MediaStream`.
3. Hook creates the `MediaRecorderSource` and starts it → underlying `MediaRecorder.start()`.
   State → `recording`; timer starts.
4. Browser emits `dataavailable` repeatedly; chunks accumulate in the Source.
5. User clicks Pause → `pause()` cascades UI → Hook → Source → `MediaRecorder.pause()`.
   State → `paused`.
6. User clicks Resume → `resume()` cascades the same path → `MediaRecorder.resume()`.
   State → `recording`.
7. User clicks Stop → `stop()` cascades the same path → `MediaRecorder.stop()` → final chunk + `onstop`.
8. Source assembles the `Recording` artifact and returns it to the Hook.
   State → `stopped`; mic released.
9. Hook renders `PlaybackPanel`.
10. User clicks Play → UI calls `audio.play()` on the native audio element.

## 7. Potential edge cases

- **Permission denied or revoked mid-session** — must surface a distinct `error`/`permission_denied` state, not a silent failure.
- **No microphone available, or device disconnected during recording** (e.g. USB mic unplugged) — `MediaRecorder` fires an error event; the state machine must catch it and transition to `error` rather than hanging in `recording`.
- **Browser/mimeType support gaps** — Safari's supported `MediaRecorder` mimeTypes differ from Chrome's (no native WebM; typically `audio/mp4`). The `AudioSource` must negotiate from a prioritized list of supported types rather than hardcoding one.
- **iOS Safari specifics** — `getUserMedia` must be triggered by a direct user gesture; `MediaRecorder` support is comparatively recent. Needs explicit testing, not just "should work everywhere."
- **Tab closed or navigated away while recording** — must stop all `MediaStream` tracks on unmount/`beforeunload` so the OS mic indicator doesn't stay on after the user leaves.
- **Rapid/duplicate button clicks** — start/pause/resume/stop must be guarded against being fired while a transition is already in flight (disable the relevant button during the async gap, or make the reducer reject invalid transitions outright).
- **Very long recordings** — chunks accumulate in memory; there's currently no upper bound. A sane maximum duration (or a future move to periodic chunked upload) needs to be decided before this ships to real users, but is out of scope to solve this sprint.
- **Zero-length recording** (record then immediately stop) — must not crash the playback view on an empty/near-empty blob.
- **Multiple concurrent instances** — component remounting (e.g. fast navigation) while a stream is still open must not leak an active `MediaStream`; cleanup must be deterministic.
- **Insecure context** — `getUserMedia` requires HTTPS (or `localhost`); will simply fail on plain HTTP in any other environment.
- **Waveform rendering cost** — redrawing at 60fps is cheap on desktop but a real concern on lower-power hardware, Quest 3 standalone in particular; the visualizer should be throttleable.
- **No persistence on crash** — if the browser tab crashes mid-recording, the audio is lost; there is no local durability in this sprint. Worth flagging now as a known, accepted limitation rather than discovering it later.

## 8. Future scalability

- **`AudioSource` is the seam for ESP32 and Quest 3.** Neither will likely reuse the browser component tree directly, but because the interface is defined now as "produces a standard `Recording` artifact," adding those integrations means writing a new capture path that targets the same artifact shape — not redesigning the session, UI, or artifact model.
- **`RecordingSink` is the seam for cloud storage.** Swapping `LocalObjectUrlSink` for an upload-to-backend sink is a new implementation of an existing interface, not a change to any component or the state machine.
- **The `Recording` artifact's metadata** (`source: "browser" | "esp32" | "quest3"`, `mimeType`, `durationMs`) is designed now specifically so the backend's future data model doesn't need a breaking migration when new capture sources are added.
- **Whisper transcription and AI analysis are downstream, independent stages.** Once a recording reaches the backend, transcription and analysis operate on the stored artifact/transcript, not on live audio — this module's job ends at "produce and hand off a finished recording," keeping it single-responsibility and insulated from changes in the analysis pipeline.
- **The waveform utilities are directly reusable** for the future Progress Dashboard (e.g. showing a static waveform preview of past recordings) without modification.
- **Quest 3 caveat:** if Quest 3's browser (Meta Browser / WebXR context) supports `getUserMedia` the same way desktop Chromium does, `BrowserMediaRecorderSource` might work there unmodified. This is not assumed or relied upon — WebXR permission and audio APIs are known to diverge from standard browser behavior — but it's a plausible best case worth validating early in whichever sprint takes on Quest 3 support.

---

## What this sprint explicitly does not include

No code has been written yet — this is the design only. When implementation begins, it covers browser recording, playback, timer, and waveform exclusively. It does not include: any backend upload, Whisper integration, ESP32/Quest 3 capture, cloud storage, or AI analysis. Those remain interface-only seams (`AudioSource`, `RecordingSink`) until their own sprints.
