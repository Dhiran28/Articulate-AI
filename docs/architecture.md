# Architecture Notes — Sprint 1

This document explains the structural decisions made while setting up the
project foundation, and what was deliberately left out.

## Why two separate applications, not one

The frontend (Next.js) and backend (FastAPI) are independent projects with
their own dependency trees, build tools, and run commands, rather than a
single unified app or a monorepo managed by a tool like Turborepo or Nx.

Reasoning: at this stage there is no shared code between them (no shared
types, no shared UI, no shared build pipeline), so a monorepo orchestration
layer would add tooling complexity without a corresponding benefit. Next.js
does have a backend-capable API layer of its own, but a standalone Python
service is required regardless, because later milestones (speech
transcription, AI reasoning analysis) need Python's ML/audio ecosystem —
so FastAPI was never optional. Splitting them now, before any inter-service
code exists, avoids ever having to unwind a false dependency later. If the
project later needs shared TypeScript types (e.g. API response shapes)
we'll introduce a lightweight shared package at that point, not before.

## Why FastAPI is structured by layer, not by feature

```
backend/app/
├── main.py       application entrypoint, middleware, router registration
├── api/          route handlers (routers)
├── core/         configuration, settings
└── models/       data models (empty for now)
```

Alternative considered: organize by feature/domain (e.g.
`transcription/`, `analysis/`, `dashboard/`, each with its own routes,
models, and logic).

Decision: layer-based structure for now, because there is exactly one
feature (a health check) — a feature-based structure would just produce a
single near-empty folder and communicate no information. Layer-based
folders (`api`, `core`, `models`) are the FastAPI community's de facto
default and make it obvious where a new route, a new setting, or a new
model goes. When a second real feature is added in a later sprint, we will
revisit this: if features start requiring their own multi-file bundles, we
will convert `api/` into per-feature subpackages
(`api/transcription/`, `api/analysis/`) at that time. Restructuring later is
cheap; over-engineering a folder structure for code that doesn't exist yet
is not.

## Why configuration goes through `pydantic-settings`

`app/core/config.py` defines a single typed `Settings` object read from
environment variables (via a `.env` file locally), instead of calling
`os.environ.get(...)` wherever a value is needed.

Reasoning: typed settings fail fast — a missing or malformed environment
variable raises an error at startup, not partway through a request. It also
gives every setting one canonical definition instead of scattering
`os.environ` calls (and their default values) across the codebase, and
matches how secrets (API keys for the future AI provider, database URLs)
will need to be handled anyway, so we're not migrating a pattern later.

## Why CORS is configured now, even with no real API calls yet

The FastAPI app enables CORS for `http://localhost:3000` (the Next.js dev
server) via `app/core/config.py`'s `cors_origins` setting.

Reasoning: without it, the very first fetch call from the frontend to the
backend in Sprint 2 would fail with a CORS error that has nothing to do
with the feature being built, costing debugging time on an unrelated
concern. Configuring it now, while the answer is simple and obvious (allow
the local dev server), avoids that. Production origins will be added to
this same setting when the app is deployed — no code changes required.

## Why shadcn/ui components are added manually instead of via `npx shadcn add`

Component code is written directly into `frontend/src/components/ui/`
following shadcn/ui's standard patterns (as the CLI would generate),
because the CLI's registry fetch was not reachable from this build
environment. The resulting files are the same code the CLI would produce —
shadcn/ui deliberately ships components as source you own and can edit,
not as an installed package — so this has no long-term consequence. Once
you have this repository on your own machine, `npx shadcn@latest add
<component>` will work normally for future components.

## What was deliberately not built

Per the Sprint 1 scope, none of the following exist yet, even as stubs:

- Audio recording (browser or ESP32)
- Speech-to-text transcription
- Any AI/LLM integration or reasoning analysis
- A database or persistence layer
- The progress dashboard's actual charts/data
- Quest 3 / WebXR visualization
- Authentication

The single `/health` endpoint and placeholder homepage exist only to prove
the two services run and are wired for future communication — they carry
no product logic.

## Known environment caveat

Next.js is pinned to `15.1.11`, the patched release addressing the
December 2025 React Server Components CVEs (CVE-2025-66478, CVE-2025-55183,
CVE-2025-55184/CVE-2025-67779). Next's own bundled internal `postcss`
dependency (used only for Next's build tooling, not the app's own Tailwind
pipeline) remains on an older `postcss` version with a separate, moderate-
severity advisory that Next has not yet updated internally. This is
tracked upstream in the Next.js repository, not something fixable from
application code; it will resolve when Next.js ships a build using a newer
bundled postcss.
