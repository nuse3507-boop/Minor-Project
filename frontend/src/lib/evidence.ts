import type { Citation, Finding } from "./types";
export function citationValid(c?: Citation) {
  return (
    !!c &&
    ["EXACT", "NORMALIZED"].includes(c.match_status) &&
    Number.isInteger(c.start) &&
    c.start >= 0 &&
    c.end > c.start
  );
}
export function verified(f: Finding) {
  return (
    f.support_status === "SUPPORTED" &&
    f.citations.length > 0 &&
    f.citations.every(citationValid)
  );
}
/** API coordinates are Unicode code points, not JavaScript UTF-16 code units. */
export function splitPassage(text: string, start: number, end: number) {
  const points = Array.from(text);
  if (start < 0 || end > points.length || end <= start) return null;
  return [
    points.slice(0, start).join(""),
    points.slice(start, end).join(""),
    points.slice(end).join(""),
  ] as const;
}
