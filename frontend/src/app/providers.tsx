"use client";

import { useState, type ReactNode } from "react";
import { QueryClientProvider } from "@tanstack/react-query";

import { PendingCaptureProvider } from "@/features/capture/context/PendingCaptureContext";
import { AnalysisResultProvider } from "@/features/results/context/AnalysisResultContext";
import { createQueryClient } from "@/lib/queryClient";

/**
 * Every cross-page provider the app needs, composed once here and
 * mounted in the root layout — above `{children}`, so its state
 * survives client-side navigation between `/`, `/analyze`, and
 * `/results` (see PendingCaptureContext's own docstring for why that
 * matters for carrying a File across a route change).
 *
 * `useState(createQueryClient)` (a lazy initializer, not
 * `createQueryClient()` called inline) is the standard React Query +
 * Next.js App Router pattern: it guarantees exactly one QueryClient
 * instance per component instance rather than a new one on every
 * render, while still being created fresh per request on the server
 * (avoiding cross-request cache leakage in a server environment) and
 * once per browser tab on the client.
 */
export function Providers({ children }: { children: ReactNode }) {
  const [queryClient] = useState(createQueryClient);

  return (
    <QueryClientProvider client={queryClient}>
      <PendingCaptureProvider>
        <AnalysisResultProvider>{children}</AnalysisResultProvider>
      </PendingCaptureProvider>
    </QueryClientProvider>
  );
}
