import { BarChart3, MessageSquareText, Sparkles } from "lucide-react";

import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { CaptureChooser } from "@/features/capture/components/CaptureChooser";

const FEATURES = [
  {
    icon: MessageSquareText,
    title: "Structural thinking, not grammar",
    description: "Feedback on how clearly your argument is organized — not word choice or spelling.",
  },
  {
    icon: Sparkles,
    title: "Evidence-based coaching",
    description: "Every strength, weakness, and recommendation is grounded in a specific, quoted moment.",
  },
  {
    icon: BarChart3,
    title: "One transparent score",
    description: "A single 0-100 score with a full, documented breakdown of exactly how it was computed.",
  },
];

/**
 * The landing page: a short pitch plus the same CaptureChooser that
 * drives the whole app — recording, uploading, or dragging a file in
 * all start here (see CaptureChooser's own docstring for why it's
 * shared with /analyze rather than being Home-specific markup).
 */
export default function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center gap-12 px-6 py-16">
      <div className="flex flex-col items-center gap-4 text-center">
        <h1 className="text-4xl font-bold tracking-tight">Articulate AI</h1>
        <p className="max-w-xl text-lg text-muted-foreground">
          An AI-powered communication coach focused on structural thinking — how clearly an
          argument is organized — rather than grammar or wording.
        </p>
      </div>

      <CaptureChooser />

      <div className="grid w-full max-w-4xl gap-4 sm:grid-cols-3">
        {FEATURES.map((feature) => (
          <Card key={feature.title}>
            <CardHeader>
              <feature.icon className="h-6 w-6 text-primary" aria-hidden="true" />
              <CardTitle className="text-base">{feature.title}</CardTitle>
              <CardDescription>{feature.description}</CardDescription>
            </CardHeader>
          </Card>
        ))}
      </div>
    </main>
  );
}
