# Articulate AI

An AI-powered communication coach focused on structural thinking — how clearly
an argument is organized — rather than English grammar or wording.

This repository is being built iteratively, in small milestones. Each sprint
adds one working slice of the system; nothing is built ahead of the current
milestone.

## Planned system

- Browser audio recording — **implemented** (record, pause, resume, stop,
  playback, live waveform, timer, permission handling)
- Speech transcription — **implemented** (backend only; OpenAI Whisper)
- AI reasoning analysis — **implemented** (backend only; six reasoning
  dimensions plus four deterministic metrics, one shared LLM call — see
  [ADR 003](docs/decisions/003-communication-intelligence-engine-architecture.md))
- Coaching, scoring, and a unified report API — **implemented** (backend
  only; `POST /api/analyze` — see
  [ADR 004](docs/decisions/004-user-ready-backend-v1.md))
- Frontend integration with the backend — not implemented (the frontend
  still doesn't call the backend for anything; see
  [Project status](#project-status))
- Progress dashboard — not implemented
- ESP32 integration — not implemented
- Quest 3 visualization — not implemented

See [Audio Recording (Practice)](#audio-recording-practice) below for the
frontend, [Backend](#backend) for the API, and [Project status](#project-status)
for what's next.

## Tech stack

| Layer      | Technology                                  |
| ---------- | -------------------------------------------- |
| Frontend   | Next.js 15 (App Router), TypeScript, Tailwind CSS, shadcn/ui |
| Backend    | FastAPI, Python, Uvicorn                     |
| Transcription | OpenAI Whisper                           |
| LLM reasoning/coaching | OpenAI, Anthropic, Google Gemini, or Ollama — configurable, see [docs/configuration.md](docs/configuration.md) |

## Repository layout

```
articulate-ai/
├── frontend/        Next.js app (TypeScript, Tailwind, shadcn/ui)
├── backend/         FastAPI service
└── docs/
    ├── architecture.md      design decisions and system overview
    ├── api.md                backend API reference
    ├── configuration.md      backend environment variables
    ├── deployment.md         running the backend outside local dev
    └── decisions/            individual architecture decision records (ADRs)
```

See [docs/architecture.md](docs/architecture.md) for the reasoning behind
this structure.

## Backend

The FastAPI backend implements the full pipeline described in the
[Planned system](#planned-system) list above: audio upload, Whisper
transcription, a ten-dimension Communication Intelligence Engine (four
deterministic metrics plus six LLM-reasoned dimensions via one shared
call), an Overall Communication Score, a Coaching Engine, and one public
endpoint — `POST /api/analyze` — that runs all of it end to end and
returns a single JSON report.

- [docs/api.md](docs/api.md) — every endpoint, request/response
  examples, and error shapes.
- [docs/configuration.md](docs/configuration.md) — every environment
  variable, including LLM provider selection (OpenAI, Anthropic,
  Gemini, or Ollama).
- [docs/deployment.md](docs/deployment.md) — running the backend outside
  of local development: health checks, logging, secrets, and known
  limitations (no auth, no persistence, single-process state).
- [ADR 002](docs/decisions/002-transcription-pipeline-architecture.md),
  [ADR 003](docs/decisions/003-communication-intelligence-engine-architecture.md),
  [ADR 004](docs/decisions/004-user-ready-backend-v1.md) — the
  architectural reasoning behind each layer.

The frontend does not call any of this yet — see
[Project status](#project-status).

## Audio Recording (Practice)

The `/practice` page is where the recording feature lives. This section
covers how it works, what it runs on, and what it doesn't do yet. For the
full architectural reasoning, see
[ADR 001](docs/decisions/001-audio-recording-module-architecture.md).

### How recording works

The user flow: open `/practice`, click **Record** (the browser will ask for
microphone permission the first time), **Pause**/**Resume** any number of
times, then **Stop**. Once stopped, you can **Play** the recording back,
**Record Again**, or **Delete** it.

Under the hood, the [MediaRecorder
API](https://developer.mozilla.org/en-US/docs/Web/API/MediaRecorder) captures
microphone audio into a Blob entirely inside the browser — nothing is
uploaded or sent to the backend. The live waveform is a separate, independent
tap into the same microphone stream via the Web Audio API's `AnalyserNode`;
it visualizes the input in real time but isn't derived from the recorded
audio itself. The timer is computed from real timestamps rather than a
naive counter, so it stays accurate across pauses.

### Supported browsers

Recording requires a [secure
context](https://developer.mozilla.org/en-US/docs/Web/Security/Secure_Contexts)
(HTTPS, or `localhost` during development) plus browser support for
`MediaRecorder` and `getUserMedia`:

| Browser | Minimum version |
| ------- | ---------------- |
| Chrome  | 49+ |
| Edge    | 79+ |
| Firefox | 29+ |
| Safari  | 14.1+ (macOS), 14.5+ (iOS) |

(See [caniuse.com/mediarecorder](https://caniuse.com/mediarecorder) for the
current picture — browser support evolves.)

Audio format is negotiated automatically: the app tries
`audio/webm;codecs=opus`, then `audio/webm`, `audio/mp4`, and
`audio/ogg;codecs=opus`, falling back to the browser's own default. This is
what makes Safari work despite lacking native WebM support — it transparently
falls through to `audio/mp4`. Mobile browsers haven't been explicitly tested
yet; they're expected to work given standards support, but this is
unverified.

### Permissions

- The browser's native microphone permission prompt appears on the first
  click of **Record**.
- A secure context is required — recording will not work over plain HTTP
  (other than `localhost`).
- If permission is denied, the app shows a friendly, specific message and
  leaves Record enabled so you can retry after allowing access in the
  browser's site settings.
- If no microphone is found, or it's already in use by another
  application, a distinct message explains that too (see
  `lib/microphoneError.ts`).
- Permission is granted per browser origin and remembered by the browser
  across visits until revoked.
- The browser's own mic-in-use indicator (tab icon, OS menu bar, etc.) is
  the authoritative signal that recording is active — the app's status
  badge mirrors it but isn't the source of truth.

### Known limitations

- Recordings live only in the browser tab's memory for the current
  session — there is no local persistence or backend upload yet, so
  reloading or closing the tab discards them.
- No maximum recording length is enforced.
- MediaRecorder-produced Blobs often lack a proper duration header, so the
  native `<audio>` player's own scrubber can misreport duration in some
  browsers. The duration shown above the player is unaffected — it's
  tracked from real timestamps, not read from the audio file.
- The live waveform is a bar-style frequency visualization (from the Web
  Audio `AnalyserNode`), not a literal oscilloscope trace.
- The recording timer and the playback duration display use two slightly
  different formatting conventions (`00:05` vs. `0:05`) — a known
  inconsistency flagged during the Sprint 2.7 code review and intentionally
  left unfixed since it would change on-screen output during a review pass
  scoped to not change functionality. Worth unifying later.
- Not yet tested on mobile browsers.
- No transcription, AI analysis, or cloud storage — see below.

### Future Whisper integration

`lib/recordingSink.ts` defines a `RecordingSink` interface with a single
implementation today (`LocalObjectUrlSink`, which just creates an object
URL). Adding transcription means introducing an `UploadSink` that instead
POSTs the recording to the backend, which would queue it for Whisper
transcription and attach the result once ready — without changing anything
that calls `RecordingSink`.

### Future ESP32 integration

`lib/audioSource.ts` defines the `AudioSource` interface the browser
recorder implements today (`BrowserMediaRecorderSource`). An ESP32
microphone would most likely stream audio over WiFi directly to the
backend rather than through the browser, so it may not go through this
same interface at all — but `RecordingArtifact.source` is already typed as
a discriminable field (currently only `"browser"`) so a future `"esp32"`
source can be added without breaking existing consumers.

### Future Quest integration

The Quest 3's browser is Chromium-based, so it likely supports
`getUserMedia` and the Web Audio API the same way desktop Chrome does — in
the best case, `BrowserMediaRecorderSource` and `WebAudioWaveformSource`
would work on Quest largely unmodified. This is an assumption, not a
tested fact; it hasn't been validated on real Quest hardware yet.

## Running locally

Two services run independently: the Next.js frontend (port 3000) and the
FastAPI backend (port 8000). Start both in separate terminals.

### Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

The API is now running at http://localhost:8000. Interactive docs (Swagger
UI) are available at http://localhost:8000/docs. Confirm it's healthy:

```bash
curl http://localhost:8000/health
# {"status": "ok"}
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

The app is now running at http://localhost:3000.

### Notes

- The frontend and backend are independent processes with no shared build
  step. There is currently no proxy between them — the frontend does not
  yet call the backend for anything.
- `backend/.env.example` documents every environment variable the API
  reads — see [docs/configuration.md](docs/configuration.md) for the full
  guide, including how to select and configure an LLM provider. Copy it
  to `.env` before running.
- Try the full pipeline directly against the backend once it's running:
  `curl -F "file=@some-recording.wav" http://localhost:8000/api/analyze`
  — see [docs/api.md](docs/api.md) for the response shape. Without an
  `LLM_PROVIDER` configured, the four deterministic metrics still work;
  reasoning and coaching require one (see
  [docs/configuration.md](docs/configuration.md)).

## Project status

**Sprint 1 — complete.** Project foundation: frontend and backend scaffolds,
no business logic, no recording, no AI integration.

**Sprint 2 (2.1–2.7) — complete.** Browser audio recording is fully built:
record/pause/resume/stop, playback with restart/delete, a live microphone
waveform, an accurate elapsed-time timer, and friendly handling of denied
permissions, unsupported browsers, and unavailable microphones. See
[Audio Recording (Practice)](#audio-recording-practice) above for details
and known limitations.

**Sprint 3 (3.1–3.6) — complete, backend only.** Audio upload
(`POST /api/upload`), OpenAI Whisper transcription
(`POST /api/upload/{id}/transcribe`), and a Transcript Processor that
preserves the verbatim transcript while extracting disfluency metadata.
See [ADR 002](docs/decisions/002-transcription-pipeline-architecture.md).

**Sprint 4 (4.1–4.5.1) — complete, backend only.** The Communication
Intelligence Engine: four deterministic metric modules (filler words,
hesitations, repetitions, speaking pace) and six LLM-reasoned dimensions
(structure, clarity, logical flow, topic drift, confidence, conciseness),
all six covered by one shared LLM call rather than six independent ones.
See [ADR 003](docs/decisions/003-communication-intelligence-engine-architecture.md).

**Milestone 5 — complete, backend only.** A Coaching Engine, a
transparent weighted Overall Communication Score, and one public
endpoint (`POST /api/analyze`) that runs the complete pipeline — audio
in, one unified JSON report out. See
[ADR 004](docs/decisions/004-user-ready-backend-v1.md).

**Milestone 5.1 — complete, backend only.** Production-readiness for the
backend: real LLM provider adapters (OpenAI, Anthropic, Gemini, Ollama),
environment-based configuration for all of it, a provider health
endpoint, structured logging, and prompt versioning surfaced in the
final report. See [ADR 004 §7](docs/decisions/004-user-ready-backend-v1.md#7-implementation-note-milestone-51--production-backend-finalization),
[docs/configuration.md](docs/configuration.md), and
[docs/deployment.md](docs/deployment.md).

Not yet started: frontend integration with the backend, a progress
dashboard, backend persistence, authentication, ESP32 integration, and
Quest 3 integration. See [docs/architecture.md](docs/architecture.md) and
[ADR 001](docs/decisions/001-audio-recording-module-architecture.md) for
what's intentionally deferred and why.
