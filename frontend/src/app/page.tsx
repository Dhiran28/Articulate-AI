import { Button } from "@/components/ui/button";

/**
 * Sprint 1 placeholder landing page.
 * No business logic — just confirms the frontend, Tailwind, and
 * shadcn/ui component wiring all work end-to-end.
 */
export default function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-4 p-24">
      <h1 className="text-2xl font-semibold">Articulate AI</h1>
      <p className="text-muted-foreground">
        Project foundation — Sprint 1
      </p>
      <Button>Placeholder Button</Button>
    </main>
  );
}
