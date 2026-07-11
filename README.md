# Articulate AI

An AI-powered communication coach focused on structural thinking — how clearly
an argument is organized — rather than English grammar or wording.

This repository is being built iteratively, in small milestones. Each sprint
adds one working slice of the system; nothing is built ahead of the current
milestone.

## Planned system

- Browser audio recording
- Speech transcription
- AI reasoning analysis
- Progress dashboard
- ESP32 integration
- Quest 3 visualization

Only the project foundation (Sprint 1) exists so far. None of the above
features are implemented yet.

## Tech stack

| Layer      | Technology                                  |
| ---------- | -------------------------------------------- |
| Frontend   | Next.js 15 (App Router), TypeScript, Tailwind CSS, shadcn/ui |
| Backend    | FastAPI, Python, Uvicorn                     |

## Repository layout

```
articulate-ai/
├── frontend/        Next.js app (TypeScript, Tailwind, shadcn/ui)
├── backend/         FastAPI service
└── docs/
    ├── architecture.md   design decisions and system overview
    └── decisions/        individual architecture decision records (ADRs)
```

See [docs/architecture.md](docs/architecture.md) for the reasoning behind
this structure.

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
- `backend/.env.example` documents the environment variables the API reads
  (currently just `ENVIRONMENT` and `CORS_ORIGINS`). Copy it to `.env` before
  running.

## Project status

**Sprint 1 — complete.** Project foundation: frontend and backend scaffolds,
no business logic, no recording, no AI integration.

Sprint 2 onward will add functionality incrementally. See
[docs/architecture.md](docs/architecture.md) for what's intentionally
deferred and why.
