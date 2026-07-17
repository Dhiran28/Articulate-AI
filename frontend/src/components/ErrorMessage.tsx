import { cn } from "@/lib/utils";

interface ErrorMessageProps {
  message: string;
  className?: string;
}

/**
 * The one shared "something went wrong, here's why" inline text
 * convention used across the app — role="alert" so assistive tech
 * announces it the moment it appears, without the user needing to
 * navigate to find it.
 *
 * Milestone A's checklist calls for a reusable error message component.
 * This consolidates what were three independently-written copies of the
 * same `<p role="alert">` markup (CaptureChooser, LiveRecordingSection,
 * and — before this component existed — a near-identical line inside
 * SubmissionProgress's own richer error panel).
 *
 * Deliberately just the message line, not a full panel: SubmissionProgress's
 * error state (icon, retry/cancel actions, card styling) is a distinct,
 * more elaborate "error state panel" with its own role="alert" on the
 * outer container — wrapping this component inside it would double up
 * the alert role and announce the failure twice. Use this component
 * directly wherever a page just needs to show why something failed,
 * without extra chrome.
 */
export function ErrorMessage({ message, className }: ErrorMessageProps) {
  return (
    <p role="alert" className={cn("text-center text-sm text-destructive", className)}>
      {message}
    </p>
  );
}
