"use client";

import { useState } from "react";
import { AlertCircle, ChevronDown, ChevronUp, Quote } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

import { moduleDisplayName, type ModuleResult, type Recommendation } from "../types";
import { colorForReasoningLabel, formatReasoningLabel } from "../lib/reasoningLabelTiers";

interface ReasoningCardProps {
  moduleName: string;
  result: ModuleResult;
  /** Coaching recommendations already filtered to this module (based_on_module === moduleName) — see ResultsScreen. */
  recommendations: Recommendation[];
}

/**
 * One card per reasoning dimension (structure, clarity, logical flow,
 * topic drift, confidence, conciseness). Collapsed, it shows just the
 * label — the "Explain Why" requirement: expanding reveals the three
 * things that justify it:
 *
 * - Evidence: verbatim quotes from the transcript the model cited
 *   (`ReasoningResult.evidence`, each a `{quote, note}` pair — see
 *   the prompt's own JSON schema).
 * - Explanation: the model's one-or-two-sentence reasoning
 *   (`ReasoningResult.explanation`).
 * - Recommendation: unlike evidence/explanation, this doesn't come from
 *   the reasoning module itself — `ReasoningResult` has no recommendation
 *   field, by ADR 003's design (the Coaching Engine, not the CIE, owns
 *   prescriptive language). This card cross-references
 *   `CoachingReport.recommendations` for entries whose `based_on_module`
 *   matches this dimension, so "why" (evidence/explanation) and "what to
 *   do about it" (recommendation) sit in one place even though they come
 *   from two different backend engines.
 */
export function ReasoningCard({ moduleName, result, recommendations }: ReasoningCardProps) {
  const [isExpanded, setIsExpanded] = useState(false);
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
            {result.error?.message ?? "This dimension couldn't be assessed for this session."}
          </p>
        </CardContent>
      </Card>
    );
  }

  const reasoning = result.reasoning;
  const label = reasoning?.label ?? null;
  const color = colorForReasoningLabel(moduleName, label);

  return (
    <Card className="w-full">
      <CardHeader className="flex-row items-center justify-between space-y-0">
        <CardTitle className="text-base">{displayName}</CardTitle>
        <Badge
          variant="outline"
          className="border-current font-semibold"
          style={{ color, borderColor: color, backgroundColor: `${color}1a` }}
        >
          {formatReasoningLabel(label)}
        </Badge>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <Button
          variant="ghost"
          size="sm"
          className="w-fit gap-1.5 self-start text-muted-foreground"
          onClick={() => setIsExpanded((value) => !value)}
          aria-expanded={isExpanded}
          aria-controls={`reasoning-detail-${moduleName}`}
        >
          {isExpanded ? (
            <>
              <ChevronUp className="h-4 w-4" aria-hidden="true" />
              Hide why
            </>
          ) : (
            <>
              <ChevronDown className="h-4 w-4" aria-hidden="true" />
              Explain why
            </>
          )}
        </Button>

        {isExpanded && (
          <div id={`reasoning-detail-${moduleName}`} className="flex flex-col gap-4 border-t border-border pt-3">
            <section>
              <h4 className="mb-1 text-xs font-semibold uppercase text-muted-foreground">Explanation</h4>
              <p className="text-sm text-foreground">{reasoning?.explanation ?? "No explanation was provided."}</p>
            </section>

            <section>
              <h4 className="mb-1 text-xs font-semibold uppercase text-muted-foreground">Evidence</h4>
              {reasoning && reasoning.evidence.length > 0 ? (
                <ul className="flex flex-col gap-2">
                  {reasoning.evidence.map((item, index) => (
                    <li key={index} className="flex gap-2 rounded-md bg-muted p-2 text-sm">
                      <Quote className="mt-0.5 h-3.5 w-3.5 shrink-0 text-muted-foreground" aria-hidden="true" />
                      <div>
                        {item.quote && <p className="italic text-foreground">&ldquo;{item.quote}&rdquo;</p>}
                        {item.note && <p className="mt-0.5 text-xs text-muted-foreground">{item.note}</p>}
                      </div>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-muted-foreground">No specific evidence was cited for this dimension.</p>
              )}
            </section>

            <section>
              <h4 className="mb-1 text-xs font-semibold uppercase text-muted-foreground">Recommendation</h4>
              {recommendations.length > 0 ? (
                <ul className="flex flex-col gap-1.5">
                  {recommendations.map((recommendation, index) => (
                    <li key={index} className="text-sm text-foreground">
                      {recommendation.message}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-muted-foreground">
                  No specific recommendation was made for this dimension.
                </p>
              )}
            </section>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
