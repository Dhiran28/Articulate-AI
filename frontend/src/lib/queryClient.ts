import { QueryClient } from "@tanstack/react-query";

/**
 * One QueryClient config shared by the whole app. `retry: false` on
 * queries/mutations is deliberate here, not React Query's default
 * (3 retries with backoff): the one real network call this app makes,
 * POST /api/analyze, can take a while (transcription plus up to two LLM
 * calls — see ADR 004 §2) and isn't cheap or idempotent-feeling from a
 * user's point of view to silently retry in the background. If it
 * fails, useAnalyzeMutation surfaces the classified error and lets the
 * user explicitly choose to try again — the same "explicit retry, not
 * silent" preference the backend's own RetryPolicy documents for
 * schema/timeout failures it never retries either.
 */
export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, refetchOnWindowFocus: false },
      mutations: { retry: false },
    },
  });
}
