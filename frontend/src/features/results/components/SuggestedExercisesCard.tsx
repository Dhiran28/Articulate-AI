import { Dumbbell } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

import { moduleDisplayName, type SuggestedExercise } from "../types";

export function SuggestedExercisesCard({ exercises }: { exercises: SuggestedExercise[] }) {
  return (
    <Card className="w-full">
      <CardHeader>
        <CardTitle>Suggested exercises</CardTitle>
      </CardHeader>
      <CardContent>
        {exercises.length === 0 ? (
          <p className="text-sm text-muted-foreground">No exercises were suggested for this session.</p>
        ) : (
          <ul className="flex flex-col gap-4">
            {exercises.map((exercise, index) => (
              <li key={index} className="flex gap-3">
                <Dumbbell className="mt-0.5 h-4 w-4 shrink-0 text-primary" aria-hidden="true" />
                <div>
                  <p className="font-medium text-foreground">{exercise.title}</p>
                  <p className="text-sm text-muted-foreground">{exercise.description}</p>
                  {exercise.based_on_module && (
                    <p className="mt-0.5 text-xs text-muted-foreground">
                      Based on {moduleDisplayName(exercise.based_on_module)}
                    </p>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
