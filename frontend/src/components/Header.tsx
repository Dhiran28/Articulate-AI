import Link from "next/link";
import { Mic } from "lucide-react";

/**
 * The site-wide header (Milestone A's checklist "Header" component) —
 * rendered once in the root layout so it's present on every page, not
 * just Home. Kept deliberately slim: a wordmark linking back to "/" and
 * nothing else. Home's own hero (see app/page.tsx) already carries the
 * full pitch; this header exists so a user who lands directly on
 * /analyze or /results (a shared link, a bookmark, a page refresh) still
 * sees consistent app identity and a way back to the start, not a bare
 * card with no branding above it.
 */
export function Header() {
  return (
    <header className="w-full border-b border-border">
      <div className="mx-auto flex max-w-5xl items-center gap-2 px-6 py-4">
        <Link href="/" className="flex items-center gap-2 text-sm font-semibold tracking-tight">
          <Mic className="h-4 w-4 text-primary" aria-hidden="true" />
          Articulate AI
        </Link>
      </div>
    </header>
  );
}
