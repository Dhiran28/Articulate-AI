import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import type { ModuleResult, Recommendation } from "../types";
import { ReasoningCard } from "./ReasoningCard";

function okResult(): ModuleResult {
  return {
    metadata: { module_name: "structure", module_type: "reasoning", generated_at: "2026-01-01T00:00:00Z", description: null },
    status: "ok",
    metric: null,
    reasoning: {
      label: "clear_structure",
      explanation: "The session had a clear beginning, middle, and end.",
      evidence: [{ quote: "First, let's talk about the plan.", note: "Signals the start of the structure." }],
    },
    error: null,
  };
}

const recommendations: Recommendation[] = [
  { message: "Keep using explicit signposting like 'first' and 'next'.", based_on_module: "structure", priority: 1 },
];

describe("ReasoningCard", () => {
  it("shows the module name and label while collapsed, without the explanation or evidence", () => {
    render(<ReasoningCard moduleName="structure" result={okResult()} recommendations={recommendations} />);

    expect(screen.getByText("Structure")).toBeInTheDocument();
    expect(screen.getByText("Clear Structure")).toBeInTheDocument();
    expect(screen.queryByText(/clear beginning, middle, and end/)).not.toBeInTheDocument();
  });

  it("reveals evidence, explanation, and recommendation when 'Explain why' is clicked", async () => {
    const user = userEvent.setup();
    render(<ReasoningCard moduleName="structure" result={okResult()} recommendations={recommendations} />);

    await user.click(screen.getByRole("button", { name: /explain why/i }));

    expect(screen.getByText(/clear beginning, middle, and end/)).toBeInTheDocument();
    expect(screen.getByText(/First, let's talk about the plan\./)).toBeInTheDocument();
    expect(screen.getByText(/Keep using explicit signposting/)).toBeInTheDocument();
  });

  it("collapses again when clicked a second time", async () => {
    const user = userEvent.setup();
    render(<ReasoningCard moduleName="structure" result={okResult()} recommendations={recommendations} />);

    const toggle = screen.getByRole("button", { name: /explain why/i });
    await user.click(toggle);
    await user.click(screen.getByRole("button", { name: /hide why/i }));

    expect(screen.queryByText(/clear beginning, middle, and end/)).not.toBeInTheDocument();
  });

  it("shows a friendly 'no recommendation' message when none apply to this module", async () => {
    const user = userEvent.setup();
    render(<ReasoningCard moduleName="structure" result={okResult()} recommendations={[]} />);

    await user.click(screen.getByRole("button", { name: /explain why/i }));

    expect(screen.getByText(/no specific recommendation/i)).toBeInTheDocument();
  });

  it("shows a friendly error instead of reasoning content when the module failed", () => {
    const failed: ModuleResult = {
      metadata: { module_name: "clarity", module_type: "reasoning", generated_at: "2026-01-01T00:00:00Z", description: null },
      status: "failed",
      metric: null,
      reasoning: null,
      error: { reason: "no_provider_configured", message: "No LLM reasoner is configured on the server." },
    };

    render(<ReasoningCard moduleName="clarity" result={failed} recommendations={[]} />);

    expect(screen.getByText("No LLM reasoner is configured on the server.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /explain why/i })).not.toBeInTheDocument();
  });
});
