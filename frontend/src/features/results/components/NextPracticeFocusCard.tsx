import { Target } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export function NextPracticeFocusCard({ focus }: { focus: string }) {
  return (
    <Card className="w-full border-primary/30 bg-primary/5">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Target className="h-4 w-4 text-primary" aria-hidden="true" />
          Next practice focus
        </CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-sm text-foreground">{focus}</p>
      </CardContent>
    </Card>
  );
}
