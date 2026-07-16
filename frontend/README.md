# Articulate AI — Frontend

Next.js 15 (App Router) frontend for Articulate AI. Consumes the FastAPI
backend's `POST /api/analyze` endpoint — see `../docs/api.md` for the full
API contract and `../docs/architecture.md` for the system as a whole.

## Setup

```bash
npm install
cp .env.example .env.local
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

## Environment variables

| Variable | Default (if unset) | Meaning |
|---|---|---|
| `NEXT_PUBLIC_API_BASE_URL` | `http://localhost:8000` | Base URL of the FastAPI backend this app calls (see `src/lib/apiConfig.ts`). Set this to your deployed backend's URL in any non-local environment. |

`.env.example` documents the same variable with its default value — copy it
to `.env.local` (Next.js's convention for local overrides, git-ignored) to
customize.

## Pages

- `/` — product introduction, record/upload/drag-and-drop entry point.
- `/analyze` — recording review, upload review, submission progress, and
  error handling; routes to `/results` once analysis succeeds.
- `/results` — executive summary, overall score, transcript, metric/reasoning/coaching
  cards, suggested exercises.
- `/practice` — an earlier, standalone audio-recording demo from an
  initial sprint. Left in place and still fully functional, but
  intentionally not linked from the main navigation — superseded by the
  `/analyze` flow.

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
