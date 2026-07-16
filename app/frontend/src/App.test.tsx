import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import App from "./App";

vi.mock("./api/health", () => ({
  getBackendHealth: vi.fn().mockResolvedValue({ status: "healthy" }),
}));

describe("App", () => {
  it("renders the application heading", () => {
    render(<App />);

    expect(
      screen.getByRole("heading", { name: "AI Email Agent" }),
    ).toBeInTheDocument();
  });

  it("shows a successful backend connection", async () => {
    render(<App />);

    expect(
      await screen.findByText("Backend connected successfully."),
    ).toBeInTheDocument();
  });
});
