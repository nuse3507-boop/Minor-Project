import { useId, type ReactNode } from "react";
export function Tabs({
  label,
  value,
  onChange,
  items,
  disabled = false,
  className = "",
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  items: { value: string; label: ReactNode }[];
  disabled?: boolean;
  className?: string;
}) {
  const id = useId();
  return (
    <div
      className={`tabs ${className}`}
      role="tablist"
      aria-label={label}
      onKeyDown={(event) => {
        const index = items.findIndex((item) => item.value === value);
        let next = index;
        if (event.key === "ArrowRight") next = (index + 1) % items.length;
        else if (event.key === "ArrowLeft")
          next = (index + items.length - 1) % items.length;
        else if (event.key === "Home") next = 0;
        else if (event.key === "End") next = items.length - 1;
        else return;
        event.preventDefault();
        if (disabled) return;
        onChange(items[next].value);
        const buttons =
          event.currentTarget.querySelectorAll<HTMLButtonElement>(
            '[role="tab"]',
          );
        buttons[next]?.focus();
      }}
    >
      {items.map((item) => (
        <button
          key={item.value}
          id={`${id}-${item.value}`}
          type="button"
          role="tab"
          tabIndex={item.value === value ? 0 : -1}
          aria-selected={item.value === value}
          disabled={disabled}
          onClick={() => onChange(item.value)}
        >
          {item.label}
        </button>
      ))}
    </div>
  );
}
