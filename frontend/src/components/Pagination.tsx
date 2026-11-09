import { ChevronLeft, ChevronRight } from "lucide-react";
export function Pagination({
  offset,
  total,
  pageSize,
  count,
  onChange,
}: {
  offset: number;
  total: number | null;
  pageSize: number;
  count: number;
  onChange: (offset: number) => void;
}) {
  return (
    <nav className="pagination" aria-label="Results pagination">
      <span className="muted small-copy">
        {count ? offset + 1 : 0}–{offset + count}
        {total !== null ? ` of ${total}` : ""}
      </span>
      <div className="actions">
        <button
          className="button secondary small"
          disabled={offset === 0}
          onClick={() => onChange(Math.max(0, offset - pageSize))}
        >
          <ChevronLeft size={16} />
          Previous
        </button>
        <button
          className="button secondary small"
          disabled={total !== null ? offset + count >= total : count < pageSize}
          onClick={() => onChange(offset + pageSize)}
        >
          Next
          <ChevronRight size={16} />
        </button>
      </div>
    </nav>
  );
}
