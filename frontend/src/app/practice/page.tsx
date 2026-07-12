import type { Metadata } from "next";

import { PracticeScreen } from "@/features/audio-recording/components/PracticeScreen";

export const metadata: Metadata = {
  title: "Practice — Articulate AI",
  description: "Record yourself speaking and review the structure of your answer.",
};

export default function PracticePage() {
  return <PracticeScreen />;
}
