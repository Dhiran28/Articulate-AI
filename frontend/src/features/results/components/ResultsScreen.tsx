"use client";

import Link from "next/link";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

import { useAnalysisResult } from "../context/AnalysisResultContext";
import { METRIC_MODULE_ORDER, REASONING_MODULE_ORDER } from "../types";
import { CoachingInsightsCard } from "./CoachingInsightsCard";
import { ExecutiveSummaryCard } from "./ExecutiveSummaryCard";
import { MetricCard } from "./MetricCard";
import { ModuleScoreBreakdown } from "./ModuleScoreBreakdown";
import { NextPracticeFocusCard } from "./NextPracticeFocusCard";
import { ReasoningCard } from "./ReasoningCard";
import { ScoreOverview } from "./ScoreOverview";
import { SuggestedExercisesCard } from "./SuggestedExercisesCard";
import { TranscriptViewer } from "./TranscriptViewer";

function EmptyResultsState() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-6 p-6">
      <Card className="w-full max-w-md text-center">
        <CardHeader>
          <CardTitle>No results yet</CardTitle>
          <CardDescription>
            Record or upload a session on the Analyze page to see your communication report here.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Button asChild size="lg">
            <Link href="/analyze">Go to Analyze</Link>
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}

/**
 * The Results page, in full: executive summary, overall score, the
 * per-module breakdown behind it, the transcript, one card per metric
 * and reasoning dimension, and the Coaching Engine's output. Every
 * number and piece of text here comes directly from the
 * `CommunicationReport` `useAnalyzeMutation` produced — this component
 * lays it out, but computes nothing itself (the same "no business logic
 * in the presentation layer" split the backend's own ReportBuilder
 * holds itself to).
 */
export function ResultsScreen() {
  const { report, sessionLabel } = useAnalysisResult();

  if (!report) {
    return <EmptyResultsState />;
  }

  const recommendationsByModule = new Map<string, typeof report.coaching.recommendations>();
  for (const recommendation of report.coaching.recommendations) {
    const existing = recommendationsByModule.get(recommendation.based_on_module) ?? [];
    existing.push(recommendation);
    recommendationsByModule.set(recommendation.based_on_module, existing);
  }

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-6 p-6">
      <ExecutiveSummaryCard summary={report.executive_summary} sessionLabel={sessionLabel} />

      <div className="grid gap-6 md:grid-cols-2">
        <ScoreOverview score={report.score} />
        <ModuleScoreBreakdown moduleScores={report.score.module_scores} unscoredModules={report.score.unscored_modules} />
      </div>

      <TranscriptViewer transcript={report.transcript} />

      <section>
        <h2 className="mb-3 text-lg font-semibold text-foreground">Metrics</h2>
        <div className="grid gap-4 sm:grid-cols-2">
          {METRIC_MODULE_ORDER.filter((name) => report.analysis.modules[name]).map((name) => (
            <MetricCard key={name} moduleName={name} result={report.analysis.modules[name]} />
          ))}
        </div>
      </section>

      <section>
        <h2 className="mb-3 text-lg font-semibold text-foreground">Reasoning</h2>
        <div className="grid gap-4 sm:grid-cols-2">
          {REASONING_MODULE_ORDER.filter((name) => report.analysis.modules[name]).map((name) => (
            <ReasoningCard
              key={name}
              moduleName={name}
              result={report.analysis.modules[name]}
              recommendations={recommendationsByModule.get(name) ?? []}
            />
          ))}
        </div>
      </section>

      <CoachingInsightsCard strengths={report.coaching.strengths} weaknesses={report.coaching.weaknesses} />

      {report.coaching.unavailable.length > 0 && (
        <p className="text-sm text-muted-foreground">{report.coaching.unavailable.join(" ")}</p>
      )}

      <SuggestedExercisesCard exercises={report.coaching.suggested_exercises} />

      <NextPracticeFocusCard focus={report.coaching.next_practice_focus} />
    </div>
  );
}
