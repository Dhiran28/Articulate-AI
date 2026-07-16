"use client";

import { Bar, BarChart, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

import { moduleDisplayName, type ModuleScore } from "../types";
import { bandForScore, SCORE_BAND_COLORS } from "../lib/scoreBandStyles";

interface ModuleScoreBreakdownProps {
  moduleScores: ModuleScore[];
  unscoredModules: string[];
}

interface TooltipPayloadEntry {
  payload: ModuleScore & { displayName: string };
}

function ScoreTooltip({ active, payload }: { active?: boolean; payload?: TooltipPayloadEntry[] }) {
  if (!active || !payload?.length) return null;
  const entry = payload[0].payload;
  return (
    <div className="rounded-md border border-border bg-popover p-3 text-sm shadow-md">
      <p className="font-medium text-popover-foreground">{entry.displayName}</p>
      <p className="text-muted-foreground">
        Score {entry.score.toFixed(1)} · weight {entry.effective_weight.toFixed(1)}%
      </p>
      <p className="mt-1 max-w-xs text-xs text-muted-foreground">{entry.driver}</p>
    </div>
  );
}

/**
 * The full, transparent per-module breakdown behind the Overall
 * Communication Score — every module's score, its effective weight
 * (post-redistribution if any module failed to run), and a
 * human-readable `driver` explaining what produced it, all already
 * computed by the backend (app/scoring/engine.py). This chart adds no
 * new numbers; it's a visualization of `CommunicationScore.module_scores`
 * exactly as returned.
 */
export function ModuleScoreBreakdown({ moduleScores, unscoredModules }: ModuleScoreBreakdownProps) {
  const data = moduleScores
    .map((module) => ({ ...module, displayName: moduleDisplayName(module.module_name) }))
    .sort((a, b) => b.effective_weight - a.effective_weight);

  return (
    <Card className="w-full">
      <CardHeader>
        <CardTitle>Per-module breakdown</CardTitle>
        <CardDescription>
          Every dimension&apos;s score and how much it contributed to the overall score.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div style={{ width: "100%", height: Math.max(data.length * 40, 200) }}>
          <ResponsiveContainer>
            <BarChart data={data} layout="vertical" margin={{ left: 24, right: 24 }}>
              <XAxis type="number" domain={[0, 100]} hide />
              <YAxis
                type="category"
                dataKey="displayName"
                width={110}
                tick={{ fontSize: 12 }}
                axisLine={false}
                tickLine={false}
              />
              <Tooltip content={<ScoreTooltip />} cursor={{ fill: "hsl(var(--accent))" }} />
              <Bar dataKey="score" radius={[0, 4, 4, 0]} barSize={18}>
                {data.map((module) => (
                  <Cell key={module.module_name} fill={SCORE_BAND_COLORS[bandForScore(module.score)]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        {unscoredModules.length > 0 && (
          <p className="mt-4 text-xs text-muted-foreground">
            Not scored this session (weight redistributed among the rest):{" "}
            {unscoredModules.map(moduleDisplayName).join(", ")}.
          </p>
        )}
      </CardContent>
    </Card>
  );
}
