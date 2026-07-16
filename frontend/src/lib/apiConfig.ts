/**
 * Base URL of the FastAPI backend, read from NEXT_PUBLIC_API_BASE_URL so
 * a deployed environment can point at a real API without a code change.
 * Falls back to the local dev server address — the same default the
 * backend README assumes when running `uvicorn app.main:app --reload`.
 *
 * Lives in shared lib/, not a feature folder: this sprint's audio-upload
 * feature is the first thing to call the backend, but it won't be the
 * last, so the base URL itself isn't upload-specific.
 */
export function getApiBaseUrl(): string {
  return process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
}
