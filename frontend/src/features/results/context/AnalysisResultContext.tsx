"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import type { CommunicationReport } from "../types";

const STORAGE_KEY = "articulate-ai:last-analysis-report";

/**
 * A stored report plus the optional, purely client-side label the user
 * gave the session on the Analyze page (see SessionLabelField) — never
 * sent to the backend, which has no field for it. Kept alongside the
 * report rather than as a separate Context so the two can never drift
 * out of sync (a label persisting past the report it was written for,
 * or vice versa).
 */
interface StoredAnalysisResult {
  report: CommunicationReport;
  sessionLabel: string | null;
}

/**
 * Holds the most recently completed `CommunicationReport` — the client
 * state /results reads from. Backed by `sessionStorage` (not just React
 * state) for one reason: the backend has no persistence of its own
 * (ADR 004 §5 discloses this), so if /results doesn't keep its own
 * copy somewhere that survives a reload, refreshing the results page
 * loses the report permanently with no way to fetch it again. This is
 * the one piece of client-only state this frontend persists, and only
 * for the current tab/session, not across devices or after closing
 * the tab.
 *
 * Split deliberately from React Query (see src/app/providers.tsx):
 * React Query owns the *server* state of the POST /analyze request
 * itself (loading/error/success of that one call, in useAnalyzeMutation);
 * this Context owns the *client* state of "what's the last completed
 * report," which outlives the mutation that produced it and needs to
 * be readable from a completely different route/page.
 */
interface AnalysisResultContextValue {
  report: CommunicationReport | null;
  sessionLabel: string | null;
  setReport: (report: CommunicationReport, sessionLabel?: string | null) => void;
  clearReport: () => void;
}

const AnalysisResultContext = createContext<AnalysisResultContextValue | null>(null);

function readFromStorage(): StoredAnalysisResult | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.sessionStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as StoredAnalysisResult) : null;
  } catch {
    // A corrupted or unexpectedly-shaped stored value shouldn't crash
    // the app — treat it the same as "nothing stored."
    return null;
  }
}

export function AnalysisResultProvider({ children }: { children: ReactNode }) {
  // Starts `null` on both server and client render (sessionStorage
  // doesn't exist during SSR) to avoid a hydration mismatch, then reads
  // the real stored value once, after mount — the same pattern
  // useAudioRecorder's browserSupport check already establishes in
  // this codebase for client-only state.
  const [stored, setStored] = useState<StoredAnalysisResult | null>(null);

  useEffect(() => {
    setStored(readFromStorage());
  }, []);

  const setReport = useCallback((next: CommunicationReport, sessionLabel: string | null = null) => {
    const value: StoredAnalysisResult = { report: next, sessionLabel };
    setStored(value);
    try {
      window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(value));
    } catch {
      // Storage can fail (quota, private browsing) — the report still
      // works for this render via React state; it just won't survive
      // a reload. Not worth surfacing as a user-facing error.
    }
  }, []);

  const clearReport = useCallback(() => {
    setStored(null);
    try {
      window.sessionStorage.removeItem(STORAGE_KEY);
    } catch {
      // Same reasoning as above.
    }
  }, []);

  const value = useMemo(
    () => ({
      report: stored?.report ?? null,
      sessionLabel: stored?.sessionLabel ?? null,
      setReport,
      clearReport,
    }),
    [stored, setReport, clearReport]
  );

  return <AnalysisResultContext.Provider value={value}>{children}</AnalysisResultContext.Provider>;
}

export function useAnalysisResult(): AnalysisResultContextValue {
  const context = useContext(AnalysisResultContext);
  if (!context) {
    throw new Error("useAnalysisResult must be used within an AnalysisResultProvider");
  }
  return context;
}
