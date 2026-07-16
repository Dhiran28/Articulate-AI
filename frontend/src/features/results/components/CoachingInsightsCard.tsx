import { ThumbsDown, ThumbsUp } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

import { moduleDisplayName, type CoachingInsight } from "../types";

function InsightList({ insights }: { insights: CoachingInsight[] }) {
  if (insights.length === 0) {
    return <p className="text-sm text-muted-foreground">Nothing to report here for this session.</p>;
  }
  return (
    <ul className="flex flex-col gap-3">
      {insights.map((insight, index) => (
        <li key={index} className="text-sm">
          <p className="text-foreground">{insight.message}</p>
          <p className="text-xs text-muted-foreground">Based on {moduleDisplayName(insight.based_on_module)}</p>
        </li>
      ))}
    </ul>
  );
}

/**
 * Strengths and weaknesses, each grounded in a specific module
 * (`based_on_module`) — the same citation discipline ADR 003 §5 named
 * for the Coaching Engine before it existed: it can only point at
 * observations the Communication Intelligence Engine already surfaced,
 * never invent a new one.
 */
export function CoachingInsightsCard({
  strengths,
  weaknesses,
}: {
  strengths: CoachingInsight[];
  weaknesses: CoachingInsight[];
}) {
  return (
    <Card className="w-full">
      <CardHeader>
        <CardTitle>Coaching</CardTitle>
      </CardHeader>
      <CardContent className="grid gap-6 sm:grid-cols-2">
        <div>
          <h3 className="mb-2 flex items-center gap-1.5 text-sm font-semibold text-emerald-700">
            <ThumbsUp className="h-4 w-4" aria-hidden="true" />
            Strengths
          </h3>
          <InsightList insights={strengths} />
        </div>
        <div>
          <h3 className="mb-2 flex items-center gap-1.5 text-sm font-semibold text-amber-700">
            <ThumbsDown className="h-4 w-4" aria-hidden="true" />
            Areas to work on
          </h3>
          <InsightList insights={weaknesses} />
        </div>
      </CardContent>
    </Card>
  );
}
