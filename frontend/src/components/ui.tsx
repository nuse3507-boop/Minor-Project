import {
  AlertTriangle,
  CheckCircle2,
  FileText,
  Info,
  LoaderCircle,
} from "lucide-react";
import { useEffect, useRef, type ReactNode } from "react";
export function ErrorNotice({ error }: { error: unknown }) {
  return error ? (
    <div role="alert" className="notice error">
      <AlertTriangle size={18} />
      <span>{error instanceof Error ? error.message : String(error)}</span>
    </div>
  ) : null;
}
export function Notice({
  children,
  warning = false,
}: {
  children: ReactNode;
  warning?: boolean;
}) {
  return (
    <div className={`notice ${warning ? "warning" : ""}`}>
      <Info size={18} />
      <div>{children}</div>
    </div>
  );
}
export function Loading({ label = "Loading…" }: { label?: string }) {
  return (
    <div role="status" className="loading">
      <LoaderCircle className="spin" size={22} />
      {label}
    </div>
  );
}
export function Empty({
  title,
  children,
}: {
  title: string;
  children?: ReactNode;
}) {
  return (
    <div className="empty">
      <FileText size={32} />
      <h2>{title}</h2>
      <div className="muted">{children}</div>
    </div>
  );
}
export function Status({
  value,
  valid = true,
}: {
  value: string;
  valid?: boolean;
}) {
  const supported = value === "SUPPORTED" && valid;
  const ready = ["READY", "COMPLETED"].includes(value);
  const text = supported
    ? "Verified against source"
    : !valid
      ? "Source reference invalid"
      : {
          PARTIALLY_SUPPORTED: "Partially supported",
          UNSUPPORTED: "Unsupported interpretation",
          AMBIGUOUS: "Needs review",
          READY: "Source ready",
          COMPLETED: "Completed",
          PARTIAL: "Extraction incomplete",
          PARTIAL_COMPLETION: "Partially completed",
          QUEUED: "Queued",
          PROCESSING: "Processing",
          FAILED: "Failed",
          CANCELLED: "Canceled",
        }[value] || value.replaceAll("_", " ").toLowerCase();
  return (
    <span
      className={`status ${supported || ready ? "supported" : ["UNSUPPORTED", "FAILED"].includes(value) || !valid ? "unsupported" : "neutral"}`}
    >
      {supported || ready ? <CheckCircle2 size={14} /> : <Info size={14} />}{" "}
      {text}
    </span>
  );
}
export function PageHeading({
  eyebrow,
  title,
  children,
  actions,
}: {
  eyebrow?: string;
  title: string;
  children?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <header className="page-heading">
      <div>
        {eyebrow && <p className="eyebrow">{eyebrow}</p>}
        <h1>{title}</h1>
        {children && <p className="muted">{children}</p>}
      </div>
      {actions && <div className="actions">{actions}</div>}
    </header>
  );
}
export function ConfirmDialog({
  titleId,
  onClose,
  children,
}: {
  titleId: string;
  onClose: () => void;
  children: ReactNode;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog = ref.current;
    dialog?.showModal();
    return () => dialog?.close();
  }, []);
  return (
    <dialog
      ref={ref}
      className="panel modal"
      aria-labelledby={titleId}
      onCancel={(e) => {
        e.preventDefault();
        onClose();
      }}
    >
      {children}
    </dialog>
  );
}
