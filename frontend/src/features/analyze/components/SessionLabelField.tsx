"use client";

import type { FieldError, UseFormRegister } from "react-hook-form";

import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";

export interface SessionDetailsFormValues {
  sessionLabel: string;
}

interface SessionLabelFieldProps {
  register: UseFormRegister<SessionDetailsFormValues>;
  error?: FieldError;
}

export const SESSION_LABEL_MAX_LENGTH = 60;

/**
 * One optional field, validated with React Hook Form, before a
 * recording or uploaded file is submitted for analysis: a short label
 * ("Standup update," "Interview practice #3") shown on the Results page
 * so a user reviewing several sessions can tell them apart. Purely
 * client-side — the backend's `/analyze` endpoint has no field for it
 * (see AnalysisResultContext, which stores it alongside the report
 * rather than sending it anywhere).
 *
 * `register`/`error` are passed down from AnalyzeScreen's single
 * `useForm()` call rather than this component owning its own form —
 * both RecordingReviewPanel's and FilePreviewPanel's "Analyze" actions
 * need to trigger the same validated submission, so one form instance
 * lives at the screen level (see AnalyzeScreen's `onConfirmAnalyze`).
 */
export function SessionLabelField({ register, error }: SessionLabelFieldProps) {
  return (
    <div className="flex w-full flex-col gap-1.5 text-left">
      <Label htmlFor="session-label">Session label (optional)</Label>
      <Input
        id="session-label"
        placeholder="e.g. Standup update, Interview practice"
        maxLength={SESSION_LABEL_MAX_LENGTH}
        {...register("sessionLabel", {
          maxLength: {
            value: SESSION_LABEL_MAX_LENGTH,
            message: `Keep it under ${SESSION_LABEL_MAX_LENGTH} characters.`,
          },
        })}
        aria-invalid={Boolean(error)}
        aria-describedby={error ? "session-label-error" : undefined}
      />
      {error && (
        <p id="session-label-error" role="alert" className="text-xs text-destructive">
          {error.message}
        </p>
      )}
    </div>
  );
}
