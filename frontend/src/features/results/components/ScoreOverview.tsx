"use client";

import { RadialBar, RadialBarChart, ResponsiveContainer } from "recharts";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

import type { CommunicationScore } from "../types";
import { SCORE_BAND_COLORS } from "../lib/scoreBandStyles";
import { ScoreBandBadge } from "./ScoreBandBadge";

/**
 * The Overall Communication Score as a radial gauge (Recharts
 * RadialBarChart), plus its band. The gauge is one bar out of 100 —
 * deliberately not a generic multi-series chart — so `data` is a
 * single-element array; RadialBarChart still requires an array, not a
 * bare number.
 *
 * The score's own transparent, weighted-average methodology (structural
 * thinking dimensions weighted highest, fluency mechanics lowest) is
 * documented in the backend, not re-explained here — see
 * docs/decisions/004-user-ready-backend-v1.md §4 and
 * app/scoring/weights.py. This component only visualizes the number and
 * band the backend already computed; it makes no scoring decisions of
 * its own.
 */
export function ScoreOverview({ score }: { score: CommunicationScore }) {
  const color = SCORE_BAND_COLORS[score.band];
  const data = [{ name: "score", value: score.overall_score, fill: color }];

  return (
    <Card className="w-full">
      <CardHeader>
        <CardTitle>Overall Communication Score</CardTitle>
        <CardDescription>A single, transparent score across all ten evaluation dimensions.</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col items-center gap-4">
        <div className="relative h-48 w-48">
          <ResponsiveContainer width="100%" height="100%">
            <RadialBarChart
              data={data}
              innerRadius="75%"
              outerRadius="100%"
              startAngle={90}
              endAngle={-270}
              barSize={16}
            >
              <RadialBar dataKey="value" cornerRadius={8} background={{ fill: "hsl(var(--secondary))" }} max={100} />
            </RadialBarChart>
          </ResponsiveContainer>
          <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
            <span className="text-4xl font-bold" style={{ color }}>
              {score.overall_score.toFixed(1)}
            </span>
            <span className="text-xs text-muted-foreground">out of 100</span>
          </div>
        </div>

        <ScoreBandBadge band={score.band} />
      </CardContent>
    </Card>
  );
}
