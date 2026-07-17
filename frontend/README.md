# Articulate AI — Frontend

Next.js 15 (App Router) frontend for Articulate AI. Records audio in the
browser (or accepts an uploaded/dragged-in file) and submits it to the
FastAPI backend's `POST /api/analyze` for structural-communication
analysis and coaching. See `../docs/api.md` for the full API contract and
`../docs/architecture.md` for the system as a whole.

## Setup

```bash
npm install
cp .env.example .env.local
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). The backend
(`../backend`) must be running separately — see the backend's own README
— since this app makes no attempt to mock or fake `/api/analyze`
responses.

## Environment variables

| Variable | Default (if unset) | Meaning |
|---|---|---|
| `NEXT_PUBLIC_API_BASE_URL` | `http://localhost:8000` | Base URL of the FastAPI backend this app calls (see `src/lib/apiConfig.ts`). Set this to your deployed backend's URL in any non-local environment. |

`.env.example` documents the same variable with its default value — copy it
to `.env.local` (Next.js's convention for local overrides, git-ignored) to
customize.

## Pages

- `/` — product introduction, record/upload/drag-and-drop entry point
  (`Header` + `CaptureChooser`).
- `/analyze` — live recording (start/pause/resume/stop, waveform, timer),
  upload/recording review before submission, real upload-progress and
  processing states, and error handling with retry. Routes to `/results`
  once analysis succeeds.
- `/results` — executive summary, overall score, transcript, metric/reasoning/coaching
  cards, suggested exercises.
- `/practice` — an earlier, standalone audio-recording demo from an
  initial sprint. Left in place and still fully functional, but
  intentionally not linked from the main navigation — superseded by the
  `/analyze` flow.

## Recording

Built on the browser's native `MediaRecorder` API (`src/features/audio-recording/`),
not a third-party recording library. Start, pause, resume, and stop are
all real `MediaRecorder` calls, not simulated; the recorded format is
whatever the browser's `MediaRecorder` natively supports (checked via a
capability probe with a fallback chain — see `lib/audioSource.ts`), which
in practice is a WebM/Opus container in every current major browser (no
browser natively produces WAV directly). The recorded blob is later
converted to a `File` with the right extension before upload — see
`features/analyze/lib/toAudioFile.ts`.

Keyboard shortcuts (while a recording is idle/in progress): `R` to
start/retry, `P` to pause or resume, `S` to stop. Ignored while typing in
a text field — see `useRecordingShortcuts`'s own docstring.

## Testing

```bash
npm run test        # vitest run (one-shot)
npm run test:watch  # vitest, watch mode
npx tsc --noEmit     # typecheck
npx eslint src --ext .ts,.tsx
npm run build        # production build + static prerender check
```

## Known MVP limitation

`src/features/results/types.ts` hand-mirrors the backend's Pydantic
response schema rather than being generated from it (no codegen step
exists yet). Field names and nesting are kept identical to the backend
source specifically so the two can be diffed by eye — see that file's own
docstring, and `docs/decisions/004-user-ready-backend-v1.md` for the
broader context this tradeoff was made in.
