import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ErrorMessage } from "./ErrorMessage";

describe("ErrorMessage", () => {
  it("renders the message with an alert role so assistive tech announces it", () => {
    render(<ErrorMessage message="Something went wrong." />);

    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent("Something went wrong.");
  });

  it("merges an optional className with its default styling", () => {
    render(<ErrorMessage message="Oops" className="font-medium" />);

    expect(screen.getByRole("alert")).toHaveClass("font-medium");
    expect(screen.getByRole("alert")).toHaveClass("text-destructive");
  });
});
