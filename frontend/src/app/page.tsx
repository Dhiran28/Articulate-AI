import Link from "next/link";

import { Button } from "@/components/ui/button";

/**
 * Landing page. Minimal by design — its only job right now is to get a
 * visitor to the Practice screen, where the actual recording feature
 * lives.
 */
export default function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-4 p-24">
      <h1 className="text-2xl font-semibold">Articulate AI</h1>
      <p className="text-muted-foreground">
        An AI-powered communication coach for structural thinking.
      </p>
      <Button asChild size="lg">
        <Link href="/practice">Go to Practice</Link>
      </Button>
    </main>
  );
}
