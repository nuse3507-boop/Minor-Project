import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import { CoverageNotice, coverageSummary } from "./CoverageNotice";
it("describes text extraction without inventing page counts", () => {
  expect(
    coverageSummary(
      { pages_total: 0, pages_extracted: 0, sections_total: 3 },
      true,
    ),
  ).toBe("3 extracted sections");
});
it("makes incomplete extraction and skipped analysis visible", () => {
  expect(
    coverageSummary({
      pages_total: 4,
      pages_extracted: 2,
      sections_total: 6,
      sections_processed: 3,
      chunks_total: 4,
      chunks_processed: 2,
    }),
  ).toContain("2 of 4 pages extracted");
  render(
    <CoverageNotice
      coverage={{ warnings: ["Two scanned pages require OCR."] }}
    />,
  );
  expect(screen.getByText("Two scanned pages require OCR.")).toBeVisible();
});
