import { Suspense } from "react";

import { AnalyzeScreen } from "@/features/analyze/components/AnalyzeScreen";

/**
 * `useSearchParams()` (used inside AnalyzeScreen to read `?start=record`)
 * requires a Suspense boundary around anything that calls it in the
 * App Router — without one, Next.js's build fails static generation for
 * this route. There's no meaningful fallback UI to show during that
 * (practically instant) suspense window, so `null` is intentional here,
 * not a placeholder left unfinished.
 */
export default function AnalyzePage() {
  return (
    <Suspense fallback={null}>
      <AnalyzeScreen />
    </Suspense>
  );
}
