import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Header } from "./Header";

describe("Header", () => {
  it("shows the app name and links back to the home page", () => {
    render(<Header />);

    const link = screen.getByRole("link", { name: /articulate ai/i });
    expect(link).toHaveAttribute("href", "/");
  });
});
