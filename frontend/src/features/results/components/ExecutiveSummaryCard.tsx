import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export function ExecutiveSummaryCard({ summary, sessionLabel }: { summary: string; sessionLabel: string | null }) {
  return (
    <Card className="w-full">
      <CardHeader>
        <CardTitle>{sessionLabel ?? "Executive Summary"}</CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-base leading-relaxed text-foreground">{summary}</p>
      </CardContent>
    </Card>
  );
}
