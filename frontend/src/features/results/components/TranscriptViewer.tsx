"use client";

import { useState } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

/**
 * The verbatim transcript this analysis was based on — the one field
 * (`CommunicationReport.transcript`) added specifically to make this
 * component possible; see ADR 004 §8 for why the otherwise-frozen
 * backend gained this one exception.
 *
 * Shown unmodified, filler words and all — this backend's Transcript
 * Processor deliberately preserves rather than cleans the transcript
 * (see ADR 002), so what's shown here is exactly what the Filler Words,
 * Hesitations, and Repetitions metric modules also measured against.
 */
export function TranscriptViewer({ transcript }: { transcript: string }) {
  const [isExpanded, setIsExpanded] = useState(false);

  return (
    <Card className="w-full">
      <CardHeader>
        <CardTitle>Transcript</CardTitle>
        <CardDescription>The verbatim transcript this analysis is based on.</CardDescription>
      </CardHeader>
      <CardContent>
        <div className={isExpanded ? "" : "max-h-40 overflow-hidden"}>
          <p className="whitespace-pre-wrap text-sm leading-relaxed text-foreground">{transcript}</p>
        </div>
        <Button
          variant="ghost"
          size="sm"
          className="mt-2 gap-1.5 text-muted-foreground"
          onClick={() => setIsExpanded((value) => !value)}
          aria-expanded={isExpanded}
        >
          {isExpanded ? (
            <>
              <ChevronUp className="h-4 w-4" aria-hidden="true" />
              Show less
            </>
          ) : (
            <>
              <ChevronDown className="h-4 w-4" aria-hidden="true" />
              Show full transcript
            </>
          )}
        </Button>
      </CardContent>
    </Card>
  );
}
