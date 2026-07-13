# Backend Test Suite

Tests for the Sprint 3 transcription pipeline: audio upload, Whisper
transcription, transcript processing, and cross-cutting failure handling.

## Running the tests

```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # if you don't already have one
pip install -r requirements-dev.txt
pytest -v
```

`requirements-dev.txt` installs `requirements.txt` plus the test-only
tooling (`pytest`, `pytest-asyncio`, `httpx`), so a production install of
the app never pulls in a test runner it'll never use.

No environment variables need to be set to run the suite. No test makes a
real network call to OpenAI — see "Isolation strategy" below.

## Isolation strategy

An autouse fixture in `conftest.py` (`_isolated_environment`) runs before
and after every test:

- Points `UPLOAD_TEMP_DIR` at a fresh `pytest tmp_path`, so each test
  writes to its own throwaway directory instead of the app's real
  `tmp/audio` folder.
- Deletes `OPENAI_API_KEY` from the environment, so a developer's real
  key (needed to run the app locally) never leaks into a test run. Tests
  that need a "configured" provider substitute a fake one via
  `app.dependency_overrides` instead of relying on a real key.
- Clears the `@lru_cache`'d singletons in `app/core/dependencies.py`
  (`get_settings`, `get_blob_store`, `get_record_store`,
  `get_transcription_provider`) before and after each test, so cached
  state from one test (an uploaded asset, a cached setting) can never
  leak into another.
- Clears `app.dependency_overrides` after each test, so an override set
  by one test doesn't affect the next.

Two further conftest fixtures build on this: `client` (a plain FastAPI
`TestClient`) and `uploaded_asset_id` (uploads a small fake `.wav` and
returns its id, for tests that only care about what happens after
upload).

Nothing here talks to a real filesystem outside `tmp_path`, a real
database, or the real OpenAI API. Where a "real" component's behavior
needs verifying (e.g. `OpenAIWhisperProvider`'s response parsing), the
one network-calling method (`client.audio.transcriptions.create`) is
monkeypatched with a fake async function — everything else in that
component runs for real.

## Test files

### `test_upload.py` — audio upload (`POST /api/upload`, `GET /api/upload/{id}`)

- `TestUploadAccepts` — valid uploads succeed: `.wav`, `.mp3`, `.webm`,
  an `.m4a` with a non-canonical content-type (`audio/x-m4a`), and a
  generic `application/octet-stream` content-type trusted via extension.
- `TestUploadValidation` — invalid uploads are rejected: unsupported
  extension, a content-type that contradicts the extension, an empty
  file, and a file over the configured size ceiling (tested against a
  temporarily-lowered 1 MB limit rather than the real 25 MB, so the test
  doesn't need to allocate a 25+ MB payload).
- `TestGetUpload` — fetching a previously uploaded asset's metadata by
  id, and a 404 for an unknown id.

### `test_transcription.py` — Whisper integration (Sprint 3.4)

- `TestOpenAIWhisperProviderResponseParsing` — unit tests directly on
  `OpenAIWhisperProvider`, with the OpenAI SDK's own `create` call
  monkeypatched out:
  - a successful response is mapped correctly into `RawTranscriptionResult`
    (text, language, duration, per-segment start/end/text).
  - an `OpenAIError` (via `APIConnectionError`) is wrapped as a
    `PROVIDER_ERROR`, without leaking the raw SDK exception text into the
    user-facing message.
  - a provider constructed without an API key fails fast with
    `PROVIDER_MISCONFIGURED`, without attempting a network call.
- `TestTranscribeEndpoint` — HTTP-level tests against
  `POST /api/upload/{id}/transcribe`, substituting a `FakeProvider` via
  `app.dependency_overrides[get_transcription_provider]`:
  - a successful transcription is returned wrapped in the processor's
    output shape (raw + processed + metadata).
  - an unknown asset id returns 404 (`asset_not_found`).
  - no override and no API key (the default, thanks to the autouse
    fixture) returns 503 (`provider_misconfigured`) from the real
    provider, genuinely unconfigured.
  - a provider that raises `PROVIDER_ERROR` returns 502 (`provider_error`).

This is also where the Sprint 3.4 dependency-injection bug was caught
during development: an early draft of `get_transcription_service` called
its sub-dependencies as plain function calls instead of chained
`Depends(...)` parameters, which silently defeated
`app.dependency_overrides`. `TestTranscribeEndpoint`'s override-based
tests are what would catch a regression of that bug in the future.

### `test_transcript_processor.py` — transcript processing (Sprint 3.5)

- `TestPreservation` — the component's core reason for existing: the
  processed transcript's text is byte-identical to the raw transcript
  (`test_processed_text_is_byte_identical_to_raw` is the most important
  test in this file), and specific disfluency markers (a false-start
  em-dash cutoff, self-correction cues like "no wait" / "sorry") survive
  processing untouched.
- `TestDisfluencyMetadata` — the metadata counts that ARE computed:
  filler words, repeated adjacent words within a segment (and the
  deliberate limitation that a repeat spanning a segment boundary is
  NOT counted), pauses above the 0.5s threshold (and gaps below it
  correctly not flagged), pass-through of provider fields (provider,
  model, language, duration, segment count), and — importantly — that
  the deliberate non-detection of false starts and self-corrections is
  actively disclosed in `processing_notes` rather than silently absent.
- `TestEdgeCases` — an empty transcript and a single-segment transcript
  don't crash and produce sensible (zeroed/empty) output.

### `test_failure_handling.py` — cross-cutting failure handling (Sprint 3.6)

- `TestErrorReasonCoverage` — a regression guard, not a behavioral test:
  confirms every value in `AudioValidationReason` and every value in
  `TranscriptionErrorReason` has a corresponding entry in that route's
  `_REASON_TO_STATUS` mapping. Catches the mistake of adding a new error
  reason in the future and forgetting to wire it to an HTTP status.
- `TestErrorResponseShape` — confirms every failure mode across the
  whole pipeline (unsupported format, empty file, upload not found,
  transcribe not found) returns the exact same response shape —
  `{"detail": {"error": "<reason>", "message": "<text>"}}` — and that
  the message never leaks raw exception text (no "Traceback", no
  exception class name, no `.py` file path).

## What isn't tested here

- Real network calls to OpenAI (deliberately excluded — see "Isolation
  strategy" above).
- The `InMemoryRecordStore` and `LocalTempBlobStore` implementations
  aren't tested in isolation as separate unit tests; they're exercised
  indirectly through every upload/transcribe test in this suite. If a
  second storage backend is added later (e.g. a database-backed
  `RecordStore`), it should get its own dedicated unit tests written
  against the `RecordStore` Protocol.
- Frontend code — this suite covers only the FastAPI backend.
