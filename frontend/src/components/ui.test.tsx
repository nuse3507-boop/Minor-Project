import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ErrorNotice, Status } from "./ui";
describe("trust labels", () => {
  it("labels support only after source coordinates are valid", () => {
    render(<Status value="SUPPORTED" valid={false} />);
    expect(screen.getByText("Source reference invalid")).toBeVisible();
    expect(screen.queryByText("Verified against source")).toBeNull();
  });
  it("visibly distinguishes partial support from verification", () => {
    render(<Status value="PARTIALLY_SUPPORTED" />);
    expect(screen.getByText("Partially supported")).toBeVisible();
    expect(screen.queryByText("Verified against source")).toBeNull();
  });
  it("announces failure rather than displaying an empty successful state", () => {
    render(<ErrorNotice error={new Error("Extraction requires OCR")} />);
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Extraction requires OCR",
    );
  });
});
