import { describe, expect, it } from "vitest";
import { citationValid, splitPassage, verified } from "./evidence";
import type { Finding, Citation } from "./types";
const citation: Citation = {
  source_id: "s1",
  section_id: "sec1",
  quote: "consent",
  start: 4,
  end: 11,
  match_status: "EXACT",
};
describe("source evidence display boundary", () => {
  it("uses Unicode code-point offsets after non-BMP characters", () => {
    expect(splitPassage("A𝒙B consent", 4, 11)).toEqual(["A𝒙B ", "consent", ""]);
  });
  it("rejects out-of-range and reversed highlights", () => {
    expect(splitPassage("Text", 0, 8)).toBeNull();
    expect(splitPassage("Text", 3, 2)).toBeNull();
  });
  it("never treats OCR or invalid coordinates as source valid", () => {
    expect(citationValid({ ...citation, match_status: "OCR_ESTIMATED" })).toBe(
      false,
    );
    expect(citationValid({ ...citation, start: -1 })).toBe(false);
  });
  it("does not equate exact quote matching with semantic support", () => {
    const f = { support_status: "AMBIGUOUS", citations: [citation] } as Finding;
    expect(verified(f)).toBe(false);
  });
  it("requires at least one valid citation for a supported label", () => {
    expect(
      verified({
        support_status: "SUPPORTED",
        citations: [],
      } as unknown as Finding),
    ).toBe(false);
    expect(
      verified({
        support_status: "SUPPORTED",
        citations: [citation],
      } as Finding),
    ).toBe(true);
  });
});
