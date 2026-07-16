# ADR 002: Transcription Pipeline Architecture

**Status:** Proposed — awaiting approval before implementation (Sprint 3)
**Scope:** The backend pipeline that turns a finished audio artifact into a canonical, provider-agnostic transcript — covering browser recordings and directly uploaded audio files now, with Whisper API and self-hosted ("local") Whisper as the two transcription providers this design targets first. Deepgram, AssemblyAI, ESP32 microphone input, Quest 3 microphone input, and the AI reasoning analysis that eventually consumes these transcripts are all designed for as seams, not implemented. No code is written in this sprint.

---

## 0. Where this picks up

Sprint 2 ends at:

```
Browser Recording → Audio Blob
```

— a `RecordingArtifact` that exists only in the browser tab's memory (per ADR 001, `LocalObjectUrlSink` never uploads anything). This ADR designs everything that happens once that blob (or an uploaded file, or, later, ESP32/Quest audio) actually leaves the client and reaches the backend:

```
Browser Recording ─┐
Uploaded File ──────┼──▶ Audio Service ──▶ Transcription Service ──▶ Transcript Processor ──▶ Storage Layer ──▶ (future) AI Analysis Layer
ESP32 Audio* ───────┤
Quest Audio* ───────┘                                  ▲
                                          pluggable providers:
                                    Whisper API · Local Whisper
                                    Deepgram* · AssemblyAI*

* future, not built this sprint
```

The important design commitment: **every future audio source converges on the same entry point.** ESP32 and Quest audio will almost certainly arrive over a different transport (streaming over Wi-Fi/serial rather than an HTTP blob upload — see ADR 001 §8), but they still end up producing the same thing a browser upload does — bytes handed to the Audio Service — so nothing downstream of that boundary needs to know or care where the audio came from.

## 1. Architecture

Five services, each with one job. Like ADR 001's layers, lower/downstream services know nothing about what's upstream of them; every service talks to its neighbors only through an interface.

| Service | Responsibility | Depends on |
|---|---|---|
| **Audio Service** | Accept audio from any ingestion path, validate it, persist the raw bytes, create a canonical `AudioAsset` record, enqueue a transcription job. | Storage Layer, Job Queue |
| **Transcription Service** | Given an `AudioAsset`, pick a transcription provider and call it. Returns that provider's raw, unnormalized result. | Storage Layer (to fetch audio), a `TranscriptionProvider` per vendor |
| **Transcript Processor** | Normalize a provider's raw result into one canonical `Transcript` model, regardless of which provider produced it. | Storage Layer (to persist the result) |
| **Storage Layer** | Persist and retrieve raw audio bytes, `AudioAsset` records, raw provider responses, and canonical `Transcript` records. The only service allowed to touch a filesystem/blob store/database directly. | (nothing — it's the floor) |
| **AI Analysis Layer** | Consume a finished `Transcript` and run the actual reasoning-structure analysis. **Not built this sprint** — only its input contract is fixed here, so Sprint 4+ has a stable shape to build against. | Storage Layer |

Four interfaces are the seams that make the "future" column of the requirements (Deepgram, AssemblyAI, ESP32, Quest) additive rather than a rewrite:

- **`AudioIngestor`** — "a thing that accepts audio and hands the Audio Service validated bytes." Today: `HttpUploadIngestor` (browser blob or a picked file, both arrive as an HTTP body — from the Audio Service's point of view they're indistinguishable). Future: `Esp32StreamIngestor`, `QuestStreamIngestor`.
- **`TranscriptionProvider`** — "a thing that turns audio bytes into a raw transcription result." Today (design target): `OpenAIWhisperProvider`, `LocalWhisperProvider`. Future: `DeepgramProvider`, `AssemblyAIProvider`.
- **`TranscriptNormalizer`** — "a thing that turns one provider's raw result into a canonical `Transcript`." One per provider, owned by the Transcript Processor, so the very different shapes each vendor returns (Whisper's flat segment list vs. Deepgram's word-level, speaker-diarized JSON) never leak past this one boundary.
- **`AudioBlobStore` / `RecordStore`** — "where raw audio bytes live" and "where structured records live," kept as two separate interfaces because they have different scaling paths (blob storage vs. a database) and will very likely be swapped independently of each other.

None of these interfaces have a committed implementation yet beyond what's named above as "today's design target" — this sprint fixes the shapes and boundaries, not the concrete vendor SDKs or database engine. That's a real, open decision left for the sprint that implements the Storage Layer (see §6).

## 2. Folder structure

`docs/architecture.md` already flagged this moment in Sprint 1: *"When a second real feature is added in a later sprint... we will convert `api/` into per-feature subpackages... at that time."* This is that time — the backend gets its first real feature-based folders, while `core/` stays as shared, cross-cutting configuration.

```
backend/app/
├── main.py
├── core/
│   ├── config.py
│   └── job_queue.py              # JobQueue interface — the seam for Celery/SQS/etc. later (see §6)
├── api/
│   ├── health.py
│   ├── upload.py                 # POST /api/upload, GET /api/upload/{id}
│   └── transcripts.py            # GET /api/transcripts/{id}
├── audio/                        # Audio Service
│   ├── models.py                 # AudioAsset, AudioStatus
│   ├── service.py                # validate → store → enqueue orchestration
│   └── ingestors/
│       ├── base.py                # AudioIngestor interface
│       └── http_upload.py         # today's only implementation
├── transcription/                # Transcription Service
│   ├── models.py                 # RawTranscriptionResult (deliberately provider-shaped)
│   ├── provider_selector.py       # config-driven provider choice + fallback policy
│   ├── worker.py                  # pulls jobs off the queue, calls the selected provider
│   └── providers/
│       ├── base.py                # TranscriptionProvider interface
│       ├── openai_whisper.py
│       ├── local_whisper.py
│       ├── deepgram.py            # future
│       └── assemblyai.py          # future
├── transcript_processing/        # Transcript Processor
│   ├── models.py                 # Transcript, TranscriptSegment (canonical, provider-agnostic)
│   ├── processor.py
│   └── normalizers/
│       ├── base.py                 # TranscriptNormalizer interface
│       ├── whisper_normalizer.py
│       ├── deepgram_normalizer.py    # future
│       └── assemblyai_normalizer.py  # future
├── storage/                      # Storage Layer
│   ├── blob_store.py              # AudioBlobStore interface (local disk today; S3 later)
│   └── record_store.py            # RecordStore interface (engine intentionally undecided — see §6)
└── analysis/                     # AI Analysis Layer — contract only, no logic
    ├── base.py                    # AnalysisEngine interface: Transcript -> AnalysisResult
    └── models.py                  # AnalysisResult shape (draft; will firm up when this is actually built)
```

Two things worth calling out about this layout:

- **`transcription/` and `transcript_processing/` are separate folders, not one.** This mirrors the ADR 001 decision to keep `AudioSource` and `WaveformSource` as separate interfaces even though they often read the same stream: calling a provider and normalizing its response are different responsibilities that happen to run back-to-back. Keeping them apart means a provider integration bug and a normalization bug are never the same bug, and a new provider (Deepgram) touches `providers/` + `normalizers/` without anyone needing to re-read `worker.py` or `processor.py`.
- **`analysis/` exists as an empty contract, not a stub with fake logic.** Same principle Sprint 1 applied to `models/` and Sprint 2 applied to `RecordingSink`: define the shape now, build the substance in the sprint that actually needs it.

## 3. Data flow

1. Client submits audio to `POST /api/upload` — a browser-recorded blob (Sprint 2's `RecordingArtifact`) or a directly picked file. From here on the Audio Service treats both identically; it only knows "audio bytes arrived over HTTP." ESP32/Quest will submit through a different `AudioIngestor` later, converging on the same next step.
2. **Audio Service** validates the upload (mimetype is one it recognizes, size/duration under a to-be-decided ceiling — see §4), then:
   - persists the raw bytes via `AudioBlobStore`,
   - creates an `AudioAsset` record via `RecordStore` (`status: pending_transcription`, `source: "browser" | "upload" | "esp32" | "quest3"`),
   - enqueues a transcription job referencing the asset's id,
   - returns the `AudioAsset` to the client immediately (202-style "accepted, not finished" response) — the client does not wait on a transcription that could take anywhere from seconds (Whisper API) to much longer (local Whisper on modest hardware).
3. **Transcription Service**'s worker picks up the job, fetches the audio bytes via `AudioBlobStore`, asks `provider_selector` which `TranscriptionProvider` to use (config-driven default, e.g. local Whisper first for cost/privacy, with an optional fallback provider — see §4), and calls it.
4. The provider returns a `RawTranscriptionResult` — intentionally left in that provider's own shape at this stage. The Transcription Service does not normalize; that boundary is deliberate (§1).
5. **Transcript Processor** takes the `RawTranscriptionResult`, picks the matching `TranscriptNormalizer` for whichever provider produced it, and produces one canonical `Transcript` (full text, ordered segments with start/end timestamps, optional speaker label, optional confidence, detected language, and a pointer back to which provider/model produced it).
6. **Storage Layer** persists the `Transcript` (and, separately, the raw provider response — kept for debugging/reprocessing, see §4) and the `AudioAsset`'s status moves to `transcription_completed`.
7. Client polls `GET /api/upload/{id}` (or, later, gets pushed a notification) to see the status transition, then fetches `GET /api/transcripts/{id}` once complete.
8. **(Future, not built)** AI Analysis Layer reads the completed `Transcript` via the Storage Layer and runs the structural-reasoning analysis that's the actual product feature — as its own job, triggered once a `Transcript` exists, not as a step bolted onto this pipeline.

## 4. Error handling

Every `AudioAsset` carries an explicit status (`pending_transcription → transcribing → transcription_completed | transcription_failed`), the same principle ADR 001's recording state machine established: failure is a visible, representable state in the data model, not a silent gap or a log line no one reads.

**Audio Service**
- Unsupported mimetype or a file that fails basic validation → rejected at the HTTP boundary (4xx); no `AudioAsset` is ever created for it, so it can't show up as a mysterious stuck job later.
- Oversized or over-long audio → rejected the same way. The actual size/duration ceiling is an open policy question, not a design question — deliberately left for the implementing sprint, same as ADR 001 left "maximum recording duration" open.
- Partial/interrupted upload → validated as a complete, decodable file before an `AudioAsset` is created, not after.

**Transcription Service**
- Provider timeout → a configurable per-provider timeout; the job is retried with bounded, backed-off attempts, not indefinitely.
- Provider rate-limit/quota errors (e.g. Whisper API 429s) → backoff-and-retry up to a cap, then — if a fallback provider is configured — retry once against that provider before giving up.
- Local Whisper process crash or resource exhaustion (a real risk on modest self-hosted hardware) → caught and classified distinctly from a remote-provider failure, since the right response differs: a crashed local process needs a cooldown before retrying, not an immediate retry that just crashes again.
- Any exhausted-retries case → `AudioAsset.status = transcription_failed` with a stored, specific reason (timeout / rate_limited / provider_error / crashed), not a bare "failed."

**Transcript Processor**
- A provider response that doesn't match the shape its normalizer expects (a vendor API change, or a bug) is caught by validating the raw response defensively rather than assuming its shape — a malformed response produces a distinct `processing_error` status rather than either crashing the worker or silently producing a garbage `Transcript`.
- The raw provider response is preserved in Storage regardless of whether normalization succeeds, specifically so a normalizer bug can be fixed and replayed against already-paid-for provider output, instead of needing to re-call (and re-pay for) the provider.

**Storage Layer**
- Write failures (disk full, blob store unavailable) are surfaced as exceptions the calling service must explicitly handle — never swallowed. What "handle" means concretely (retry vs. fail the asset) is decided per-caller, not centrally, since an Audio Service ingestion failure and a Transcript Processor write failure warrant different responses.
- Local-disk storage is assumed strongly consistent (read-after-write); this stops being a safe assumption once cloud object storage is introduced, and is flagged here so it isn't quietly assumed to still hold later.

**Cross-cutting**
- No retry loop in this system is unbounded — every retry policy has a maximum attempt count.
- Both "the audio itself" and "the raw provider response" are retained on failure (subject to the size/retention policy decided later), so a failed job is always debuggable after the fact rather than only reproducible by asking the user to re-record.

## 5. Sequence diagram

*(Rendered above as an interactive diagram.)* In text form, the full lifecycle for one successful transcription plus the failure branch:

1. Client → **Audio Service**: `POST /api/upload` (browser blob or uploaded file).
2. Audio Service → **Storage Layer**: save raw audio bytes (`AudioBlobStore`).
3. Audio Service → **Storage Layer**: create `AudioAsset` (`RecordStore`, `status: pending_transcription`).
4. Audio Service → **Job Queue**: enqueue `TranscribeJob(assetId)`.
5. Audio Service --> Client: `202 { assetId, status: pending_transcription }`.
6. Job Queue → **Transcription Service**: deliver `TranscribeJob(assetId)`.
7. Transcription Service → Storage Layer: fetch audio bytes for `assetId`.
8. Transcription Service → **provider_selector**: resolve provider (e.g. Local Whisper, configured default).
9. Transcription Service → **Provider** (Local Whisper / Whisper API / Deepgram\* / AssemblyAI\*): `transcribe(audioBytes)`.
10. **Success path:** Provider --> Transcription Service: `RawTranscriptionResult`.
    Transcription Service → **Transcript Processor**: `normalize(RawTranscriptionResult, providerName)`.
    Transcript Processor → Storage Layer: save `Transcript`; save raw result (audit trail).
    Transcript Processor → Storage Layer: update `AudioAsset.status = transcription_completed`.
11. **Failure path:** Provider --> Transcription Service: error (timeout / rate limit / crash).
    Transcription Service: retry with backoff up to the configured limit; try the fallback provider if one is configured.
    On exhausted retries → Storage Layer: update `AudioAsset.status = transcription_failed`, with reason.
12. Client → **Audio Service** (or a Storage read API): `GET /api/upload/{id}` (poll for status).
13. Once completed, Client → Storage read API: `GET /api/transcripts/{id}`.
14. **(Future, dashed)** AI Analysis Layer → Storage Layer: read `Transcript` → run analysis, independently of the pipeline above.

\* future providers, not implemented this sprint.

## 6. Future scalability

- **New providers are additive.** Deepgram and AssemblyAI each need one new `TranscriptionProvider` implementation, one new `TranscriptNormalizer`, and a config entry — nothing in the Audio Service, Storage Layer, or AI Analysis Layer changes.
- **ESP32 and Quest audio are additive on the ingestion side.** A new `AudioIngestor` per device handles whatever transport that device actually uses (likely streaming over Wi-Fi/serial for ESP32, rather than one HTTP blob — see ADR 001 §8 for the same conclusion about capture). Once bytes are handed to the Audio Service, the rest of the pipeline is unaware anything changed.
- **The job queue is the seam for horizontal scaling.** Local Whisper in particular is CPU/GPU-heavy; `core/job_queue.py`'s `JobQueue` interface is what lets a later sprint swap an in-process/simple queue for Celery + Redis/SQS (or a managed equivalent) and run multiple transcription workers, without the Audio Service or Transcript Processor changing at all. Which concrete queue implementation to start with is explicitly left open here, same as the database engine (§1) — a decision for the implementing sprint, not this design.
- **The Storage Layer's two interfaces (`AudioBlobStore`, `RecordStore`) are what let local-disk-and-nothing storage migrate to S3 + a real database later** without the other four services noticing — they only ever call the interface.
- **Real-time/streaming transcription is a meaningfully different data flow, not just a new provider**, and is explicitly out of scope until requested: this design assumes "audio fully captured, then transcribed" (batch). A live-captioning feature would need the Transcription Service to support a streaming variant (e.g. Deepgram's real-time WebSocket API), which is a different worker shape, not a drop-in provider swap.
- **The AI Analysis Layer growing into multiple passes** (e.g. structure analysis and delivery/tone analysis as separate stages) is naturally accommodated, since it depends only on the stable `Transcript` contract fixed in §1 — not on which provider or normalizer produced it.
- **No user/account concept exists yet** (no auth, per Sprint 1's explicit scope). `AudioAsset` and `Transcript` don't carry an owner field today; adding one later is an additive field, not a redesign, once auth exists.

---

## What this sprint explicitly does not include

No code, and no implementation-level decisions: which database engine backs `RecordStore`, which job queue library backs `JobQueue`, which local Whisper runtime (whisper.cpp vs. faster-whisper vs. something else), audio size/duration limits, and retry/backoff tuning are all real decisions still open, deliberately deferred to whichever sprint actually builds each piece — consistent with how ADR 001 left the recording duration cap and Sprint 2.8's README left the object-storage question open. Deepgram, AssemblyAI, ESP32 ingestion, Quest ingestion, and the entire AI Analysis Layer remain interface-only seams until their own sprints.
