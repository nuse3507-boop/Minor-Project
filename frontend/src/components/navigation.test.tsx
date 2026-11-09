import { fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { describe, it, expect, vi } from "vitest";
import { Tabs } from "./Tabs";
import { Pagination } from "./Pagination";
import { pageOffset } from "../lib/query";

describe("accessible navigation and server paging", () => {
  it("moves tab focus and selection with keyboard arrows", () => {
    function Example() {
      const [value, setValue] = useState("first");
      return (
        <Tabs
          label="Example"
          value={value}
          onChange={setValue}
          items={[
            { value: "first", label: "First" },
            { value: "second", label: "Second" },
          ]}
        />
      );
    }
    render(<Example />);
    const first = screen.getByRole("tab", { name: "First" });
    first.focus();
    fireEvent.keyDown(first, { key: "ArrowRight" });
    expect(screen.getByRole("tab", { name: "Second" })).toHaveFocus();
    expect(screen.getByRole("tab", { name: "Second" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
  });
  it("keeps pagination bounded by actual server totals", () => {
    const change = vi.fn();
    render(
      <Pagination
        offset={0}
        total={45}
        count={30}
        pageSize={30}
        onChange={change}
      />,
    );
    expect(screen.getByRole("button", { name: "Previous" })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(change).toHaveBeenCalledWith(30);
  });
  it("rejects malformed bookmark offsets", () => {
    expect(pageOffset("-1", 30)).toBe(0);
    expect(pageOffset("NaN", 30)).toBe(0);
    expect(pageOffset("31", 30)).toBe(30);
  });
});
