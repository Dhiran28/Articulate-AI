import { AlertCircle } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

import { moduleDisplayName, type ModuleResult } from "../types";
import { formatMetricValue, getMetricHighlights } from "../lib/metricHighlights";

/**
 * One card per deterministic Metric module (filler words, hesitations,
 * repetitions, speaking pace). These are the four modules
 * app/scoring/weights.py calls the "fluency mechanics" tier — measured,
 * not judged by an LLM, so there's no expandable evidence/explanation
 * here the way there is for ReasoningCard; the number and its details
 * *are* the explanation.
 */
export function MetricCard({ moduleName, result }: { moduleName: string; result: ModuleResult }) {
  const displayName = moduleDisplayName(moduleName);

  if (result.status === "failed") {
    return (
      <Card className="w-full">
        <CardHeader>
          <CardTitle className="text-base">{displayName}</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="flex items-center gap-2 text-sm text-muted-foreground">
            <AlertCircle className="h-4 w-4 shrink-0" aria-hidden="true" />
            {result.error?.message ?? "This metric couldn't be measured for this session."}
          </p>
        </CardContent>
      </Card>
    );
  }

  const metric = result.metric;
  const highlights = metric ? getMetricHighlights(moduleName, metric.details) : [];

  return (
    <Card className="w-full">
      <CardHeader>
        <CardTitle className="text-base">{displayName}</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <p className="text-3xl font-semibold text-foreground">
          {metric ? formatMetricValue(metric.value, metric.unit) : "—"}
        </p>
        {highlights.length > 0 && (
          <dl className="flex flex-col gap-1 text-sm text-muted-foreground">
            {highlights.map((highlight) => (
              <div key={highlight.label} className="flex justify-between gap-2">
                <dt>{highlight.label}</dt>
                <dd className="text-right font-medium text-foreground">{highlight.value}</dd>
              </div>
            ))}
          </dl>
        )}
      </CardContent>
    </Card>
  );
}
