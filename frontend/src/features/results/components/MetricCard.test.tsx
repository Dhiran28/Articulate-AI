import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { ModuleResult } from "../types";
import { MetricCard } from "./MetricCard";

function okResult(overrides: Partial<ModuleResult> = {}): ModuleResult {
  return {
    metadata: { module_name: "filler_words", module_type: "metric", generated_at: "2026-01-01T00:00:00Z", description: null },
    status: "ok",
    metric: { value: 3, unit: "count", details: { frequency_per_100_words: 2.5 } },
    reasoning: null,
    error: null,
    ...overrides,
  };
}

describe("MetricCard", () => {
  it("shows the module's display name and formatted value", () => {
    render(<MetricCard moduleName="filler_words" result={okResult()} />);

    expect(screen.getByText("Filler Words")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
  });

  it("shows a highlight derived from the metric's details", () => {
    render(<MetricCard moduleName="filler_words" result={okResult()} />);

    expect(screen.getByText("Per 100 words")).toBeInTheDocument();
    expect(screen.getByText("2.50")).toBeInTheDocument();
  });

  it("shows a friendly error instead of a value when the module failed", () => {
    const failed: ModuleResult = {
      metadata: {
        module_name: "hesitations",
        module_type: "metric",
        generated_at: "2026-01-01T00:00:00Z",
        description: null,
      },
      status: "failed",
      metric: null,
      reasoning: null,
      error: { reason: "module_error", message: "This metric crashed." },
    };

    render(<MetricCard moduleName="hesitations" result={failed} />);

    expect(screen.getByText("This metric crashed.")).toBeInTheDocument();
    expect(screen.queryByText("3")).not.toBeInTheDocument();
  });
});
