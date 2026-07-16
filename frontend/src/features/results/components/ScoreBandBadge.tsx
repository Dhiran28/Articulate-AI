import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

import { scoreBandLabel, type ScoreBand } from "../types";
import { SCORE_BAND_BADGE_CLASSES } from "../lib/scoreBandStyles";

export function ScoreBandBadge({ band }: { band: ScoreBand }) {
  return (
    <Badge variant="outline" className={cn("text-sm font-semibold", SCORE_BAND_BADGE_CLASSES[band])}>
      {scoreBandLabel(band)}
    </Badge>
  );
}
